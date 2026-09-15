#!/usr/bin/env python3
"""Inference Quota Radar — Phase1 Hermes skill frontend.

Shadow mode: advise headroom only; never gate routing; never write secrets.
Reads keys from environment only (Hermes/BWS inject). Honest STUB when no API.
No fabricated quota numbers — pct_remaining is None unless computed from real data.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Optional

SCHEMA = "radar.phase1"
UA = "hermes-quota-radar/0.3"
TIMEOUT = 20

# Thresholds (headroom watching — not spend maximization)
EXCLUDE_PCT = 10.0
WARN_PCT = 25.0
STALE_HOURS = 2.0

# error_class taxonomy (honest, machine-readable)
# KEY_UNSET | AUTH_FAILED | FORBIDDEN | RATE_LIMITED | TIMEOUT | NETWORK |
# HTTP_ERROR | PARSE | CLI_MISSING | CLI_FAILED | NO_PUBLIC_API | UNHANDLED


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env(*names: str) -> Optional[str]:
    for n in names:
        v = os.environ.get(n)
        if v and str(v).strip():
            return str(v).strip()
    return None


def _classify_http(exc: BaseException) -> tuple[str, str]:
    """Return (error_class, note) for urllib/network failures."""
    if isinstance(exc, socket.timeout) or isinstance(exc, TimeoutError):
        return "TIMEOUT", f"timeout: {exc}"
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        body = ""
        try:
            body = (exc.read() or b"")[:120].decode("utf-8", errors="replace")
        except Exception:
            pass
        if code in (401,):
            return "AUTH_FAILED", f"HTTP {code}: {body}".strip()
        if code in (403,):
            return "FORBIDDEN", f"HTTP {code}: {body}".strip()
        if code == 429:
            return "RATE_LIMITED", f"HTTP {code}: {body}".strip()
        return "HTTP_ERROR", f"HTTP {code}: {body}".strip()
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            return "TIMEOUT", f"timeout: {reason}"
        return "NETWORK", f"network: {reason}"
    if isinstance(exc, (ConnectionError, OSError)):
        return "NETWORK", f"network: {exc}"
    if isinstance(exc, (json.JSONDecodeError, ValueError, KeyError, TypeError)):
        return "PARSE", f"parse: {exc}"
    return "UNHANDLED", str(exc)


def _get_json(
    url: str,
    key: Optional[str] = None,
    headers: Optional[dict] = None,
    timeout: float = TIMEOUT,
) -> Any:
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    if key:
        hdrs["Authorization"] = f"Bearer {key}"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _row(
    provider: str,
    status: str,
    mechanism: str,
    confidence: str,
    *,
    pct: Optional[float] = None,
    raw: Any = None,
    note: Optional[str] = None,
    error_class: Optional[str] = None,
    **extra: Any,
) -> dict:
    out: dict[str, Any] = {
        "provider": provider,
        "status": status,  # OK | PARTIAL | STUB | ERROR
        "mechanism": mechanism,
        "confidence": confidence,  # VERIFIED | INFERRED | UNKNOWN
        "pct_remaining": pct,  # never fabricate
        "raw": raw,
        "note": note,
        "error_class": error_class,
    }
    out.update(extra)
    return out


def _stub(provider: str, reason: str, mechanism: str, confidence: str, **extra: Any) -> dict:
    return _row(
        provider, "STUB", mechanism, confidence,
        note=reason, error_class="NO_PUBLIC_API", **extra,
    )


def _ok(
    provider: str,
    mechanism: str,
    confidence: str,
    pct: Optional[float],
    raw: Any,
    **extra: Any,
) -> dict:
    status = "OK" if pct is not None else "PARTIAL"
    return _row(provider, status, mechanism, confidence, pct=pct, raw=raw, **extra)


def _err(
    provider: str,
    mechanism: str,
    confidence: str,
    err: str,
    error_class: str = "UNHANDLED",
    **extra: Any,
) -> dict:
    return _row(
        provider, "ERROR", mechanism, confidence,
        note=err, error_class=error_class, **extra,
    )


def _from_exc(
    provider: str,
    mechanism: str,
    confidence: str,
    exc: BaseException,
) -> dict:
    ec, note = _classify_http(exc)
    return _err(provider, mechanism, confidence, note, error_class=ec)


def _caut_bin() -> Optional[str]:
    """Prefer PATH caut, then known box work-tree release path if present."""
    which = shutil.which("caut")
    if which:
        return which
    candidates = [
        "/workspace/inference-quota-radar-work/caut-hermes/target/release/caut",
        os.path.expanduser("~/bin/caut"),
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


# ---- providers (live / partial) --------------------------------------------

def fetch_openrouter() -> dict:
    key = _env("OPENROUTER_API_KEY")
    if not key:
        return _err("openrouter", "apiToken", "VERIFIED", "OPENROUTER_API_KEY unset", "KEY_UNSET")
    try:
        data = _get_json("https://openrouter.ai/api/v1/key", key)
        payload = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(payload, dict):
            return _err("openrouter", "apiToken", "VERIFIED", "unexpected payload shape", "PARSE")
        limit = payload.get("limit")
        rem = payload.get("limit_remaining")
        pct = None
        if isinstance(limit, (int, float)) and limit and isinstance(rem, (int, float)):
            pct = round(100.0 * float(rem) / float(limit), 2)
        elif isinstance(rem, (int, float)) and limit is None:
            # unlimited key — treat as high headroom (documented API semantics)
            pct = 100.0
        return _ok(
            "openrouter", "apiToken", "VERIFIED", pct, payload,
            limit=limit, limit_remaining=rem, limit_reset=payload.get("limit_reset"),
        )
    except Exception as e:
        return _from_exc("openrouter", "apiToken", "VERIFIED", e)


def fetch_deepseek() -> dict:
    key = _env("DEEPSEEK_API_KEY")
    if not key:
        return _err("deepseek", "apiToken", "VERIFIED", "DEEPSEEK_API_KEY unset", "KEY_UNSET")
    try:
        data = _get_json("https://api.deepseek.com/user/balance", key)
        infos = data.get("balance_infos") if isinstance(data, dict) else None
        total = None
        if infos and isinstance(infos, list):
            try:
                total = float(infos[0].get("total_balance"))
            except (TypeError, ValueError, IndexError, AttributeError):
                total = None
        budget = _env("DEEPSEEK_BUDGET_USD")
        pct = None
        note = "prepaid balance; set DEEPSEEK_BUDGET_USD for pct_remaining"
        if total is not None and budget:
            try:
                b = float(budget)
                if b > 0:
                    pct = round(100.0 * min(total, b) / b, 2)
                    note = None
            except ValueError:
                pass
        return _ok(
            "deepseek", "apiToken", "VERIFIED", pct, data,
            balance_usd=total, is_available=(data.get("is_available") if isinstance(data, dict) else None),
            note=note,
        )
    except Exception as e:
        return _from_exc("deepseek", "apiToken", "VERIFIED", e)


def fetch_minimax() -> dict:
    if shutil.which("mmx"):
        try:
            p = subprocess.run(
                ["mmx", "quota", "show", "--output", "json", "--non-interactive"],
                capture_output=True, text=True, timeout=30,
            )
            if p.returncode == 0 and p.stdout.strip():
                try:
                    data = json.loads(p.stdout)
                except json.JSONDecodeError as e:
                    return _err("minimax", "cli", "VERIFIED", f"mmx JSON parse: {e}", "PARSE")
                remains = data.get("model_remains") or []
                pct = None
                for m in remains:
                    if isinstance(m, dict) and m.get("model_name") == "general":
                        pct = m.get("current_interval_remaining_percent")
                        break
                if pct is None and remains and isinstance(remains[0], dict):
                    pct = remains[0].get("current_interval_remaining_percent")
                if pct is not None and not isinstance(pct, (int, float)):
                    pct = None
                return _ok("minimax", "cli", "VERIFIED", pct, data, via="mmx quota show")
            return _err(
                "minimax", "cli", "VERIFIED",
                f"mmx rc={p.returncode}: {(p.stderr or '')[:200]}",
                "CLI_FAILED",
            )
        except subprocess.TimeoutExpired:
            return _err("minimax", "cli", "VERIFIED", "mmx quota show timed out", "TIMEOUT")
        except Exception as e:
            return _err("minimax", "cli", "VERIFIED", str(e), "CLI_FAILED")
    if _env("MINIMAX_API_KEY", "MINIMAX_API_KEY1ST"):
        return _stub(
            "minimax",
            "mmx CLI missing; no public usage REST — meter Hermes logs later (key present)",
            "metered",
            "VERIFIED",
        )
    return _err(
        "minimax", "cli", "VERIFIED",
        "mmx not on PATH and MINIMAX_API_KEY unset",
        "CLI_MISSING",
    )


def fetch_xai() -> dict:
    key = _env("XAI_API_KEY", "GROK_API_KEY")
    if not key:
        return _err("xai", "metered", "VERIFIED", "XAI_API_KEY unset", "KEY_UNSET")
    # Optional liveness probe — still no public credits REST
    try:
        data = _get_json("https://api.x.ai/v1/models", key)
        models = data.get("data") if isinstance(data, dict) else None
        n = len(models) if isinstance(models, list) else None
        return _row(
            "xai", "PARTIAL", "metered", "VERIFIED",
            pct=None,
            raw={"models_visible": n},
            note="key live; no public credits-remaining REST — meter Hermes session spend vs budget",
            coverage="partial",
        )
    except Exception as e:
        # Key may still be valid for chat; classify but keep honest no-credits note on auth fail
        ec, note = _classify_http(e)
        if ec in ("AUTH_FAILED", "FORBIDDEN"):
            return _err("xai", "apiToken", "VERIFIED", note, ec)
        return _stub(
            "xai",
            f"models probe failed ({note}); no public credits endpoint — meter later",
            "metered",
            "VERIFIED",
        )


def fetch_openai() -> dict:
    key = _env("OPENAI_API_KEY")
    if not key:
        return _err("openai", "apiToken", "VERIFIED", "OPENAI_API_KEY unset", "KEY_UNSET")
    try:
        data = _get_json("https://api.openai.com/v1/models", key)
        models = data.get("data") if isinstance(data, dict) else None
        return _row(
            "openai", "PARTIAL", "apiToken", "INFERRED",
            pct=None,
            raw={"models_sample": [m.get("id") for m in (models or [])[:5] if isinstance(m, dict)]},
            note="key live; usage/completions quota needs Usage API + budget baseline (later)",
            coverage="partial",
        )
    except Exception as e:
        return _from_exc("openai", "apiToken", "VERIFIED", e)


def fetch_anthropic() -> dict:
    """Anthropic API-key path (liveness). Subscription headroom → claude_oauth/caut."""
    key = _env("ANTHROPIC_API_KEY")
    if not key:
        return _err(
            "anthropic", "apiToken", "INFERRED",
            "ANTHROPIC_API_KEY unset (subscription usage → claude_oauth/caut)",
            "KEY_UNSET",
        )
    try:
        data = _get_json(
            "https://api.anthropic.com/v1/models",
            key=None,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "User-Agent": UA,
                "Accept": "application/json",
            },
        )
        return _row(
            "anthropic", "PARTIAL", "apiToken", "INFERRED",
            pct=None,
            raw={"raw_keys": list(data)[:8] if isinstance(data, dict) else type(data).__name__},
            note="API key live/models; no simple remaining-quota REST — prefer claude_oauth via caut",
            coverage="partial",
        )
    except Exception as e:
        return _from_exc("anthropic", "apiToken", "INFERRED", e)


def fetch_nvidia() -> dict:
    key = _env("NVIDIA_API_KEY", "NIM_API_KEY_1", "NIM_API_KEY_2", "NIM_API_KEY_3", "NGC_API_KEY")
    base = _env("NIM_BASE_URL", "NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
    if not key:
        return _err(
            "nvidia", "apiToken", "INFERRED",
            "NVIDIA_API_KEY / NIM_API_KEY_* unset",
            "KEY_UNSET",
        )
    try:
        url = base.rstrip("/") + "/models"
        data = _get_json(url, key)
        models = data.get("data") if isinstance(data, dict) else None
        n = len(models) if isinstance(models, list) else None
        return _row(
            "nvidia", "PARTIAL", "apiToken", "INFERRED",
            pct=None,
            raw={"probe": "models", "models_visible": n, "ok": True},
            note="key/base live; no verified credits API — meter later",
            base_url=base,
            coverage="partial",
        )
    except Exception as e:
        ec, note = _classify_http(e)
        return _stub(
            "nvidia",
            f"probe failed ({note}); no verified credits API — STUB/meter",
            "metered",
            "INFERRED",
            probe_error_class=ec,
        )


def fetch_gemini() -> dict:
    key = _env("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_API_KEY", "GOOGLE_AI_STUDIO_API_KEY")
    if not key:
        return _err("gemini", "apiToken", "INFERRED", "GOOGLE_API_KEY unset", "KEY_UNSET")
    try:
        # AI Studio list models (key as query param — documented)
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={urllib.parse.quote(key, safe='')}"
        # Avoid putting key in Authorization; use bare request
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode())
        models = data.get("models") if isinstance(data, dict) else None
        n = len(models) if isinstance(models, list) else None
        return _row(
            "gemini", "PARTIAL", "apiToken", "INFERRED",
            pct=None,
            raw={"models_visible": n},
            note="AI Studio liveness; quotas are console/project based — no simple credits REST",
            coverage="partial",
        )
    except Exception as e:
        ec, note = _classify_http(e)
        return _stub(
            "gemini",
            f"probe failed ({note}); AI Studio quotas console-based — meter/stub",
            "metered",
            "INFERRED",
            probe_error_class=ec,
        )


def fetch_cerebras() -> dict:
    key = _env("CEREBRAS_API_KEY")
    if not key:
        return _stub(
            "cerebras",
            "CEREBRAS_API_KEY not in env — STUB (no verified public balance REST)",
            "stub",
            "UNKNOWN",
        )
    try:
        data = _get_json("https://api.cerebras.ai/v1/models", key)
        models = data.get("data") if isinstance(data, dict) else None
        n = len(models) if isinstance(models, list) else None
        return _row(
            "cerebras", "PARTIAL", "apiToken", "INFERRED",
            pct=None,
            raw={"models_visible": n},
            note="key live; no verified public balance REST — meter",
            coverage="partial",
        )
    except Exception as e:
        ec, note = _classify_http(e)
        return _stub(
            "cerebras",
            f"probe failed ({note}); no verified balance REST — meter",
            "metered",
            "INFERRED",
            probe_error_class=ec,
        )


def fetch_huggingface() -> dict:
    key = _env("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACEHUB_API_TOKEN", "HUGGINGFACE_API_KEY")
    if not key:
        return _err("huggingface", "apiToken", "INFERRED", "HF_TOKEN unset", "KEY_UNSET")
    try:
        data = _get_json("https://huggingface.co/api/whoami-v2", key)
        return _row(
            "huggingface", "PARTIAL", "apiToken", "INFERRED",
            pct=None,
            raw={
                "name": data.get("name") if isinstance(data, dict) else None,
                "type": data.get("type") if isinstance(data, dict) else None,
            },
            note="token identity OK; Inference credit APIs vary by product — meter/stub",
            coverage="partial",
        )
    except Exception as e:
        return _from_exc("huggingface", "apiToken", "INFERRED", e)


# ---- stubs / caut-preferred ------------------------------------------------

def fetch_nous() -> dict:
    if _env("NOUS_API_KEY"):
        return _stub(
            "nous",
            "NOUS_API_KEY present but OpenAPI has no balance — portal XHR or meter",
            "metered",
            "VERIFIED",
        )
    return _stub(
        "nous",
        "no public balance API; portal UI only — meter Hermes logs or reverse USAGE XHR later",
        "stub",
        "VERIFIED",
    )


def fetch_cursor() -> dict:
    return _stub(
        "cursor",
        "subscription quota behind Cursor auth portal — no documented REST",
        "stub",
        "UNKNOWN",
    )


def fetch_codex() -> dict:
    caut = _caut_bin()
    if caut:
        try:
            p = subprocess.run(
                [caut, "usage", "--json", "--provider", "codex"],
                capture_output=True, text=True, timeout=60,
            )
            if p.returncode == 0 and p.stdout.strip():
                try:
                    data = json.loads(p.stdout)
                except json.JSONDecodeError as e:
                    return _err("codex", "webDashboard", "VERIFIED", f"caut JSON: {e}", "PARSE")
                return _ok("codex", "webDashboard", "VERIFIED", None, data, via=caut)
            return _err(
                "codex", "webDashboard", "VERIFIED",
                f"caut rc={p.returncode}: {(p.stderr or '')[:200]}",
                "CLI_FAILED",
            )
        except subprocess.TimeoutExpired:
            return _err("codex", "webDashboard", "VERIFIED", "caut timed out", "TIMEOUT")
        except Exception as e:
            return _err("codex", "webDashboard", "VERIFIED", str(e), "CLI_FAILED")
    return _stub(
        "codex",
        "caut not built — Codex usage via caut web-dashboard/CLI-RPC later (see docs/CAUT.md)",
        "webDashboard",
        "VERIFIED",
    )


def fetch_claude_oauth() -> dict:
    caut = _caut_bin()
    if caut:
        try:
            p = subprocess.run(
                [caut, "usage", "--json", "--provider", "claude"],
                capture_output=True, text=True, timeout=60,
            )
            if p.returncode == 0 and p.stdout.strip():
                try:
                    data = json.loads(p.stdout)
                except json.JSONDecodeError as e:
                    return _err("claude_oauth", "oauth", "VERIFIED", f"caut JSON: {e}", "PARSE")
                return _ok("claude_oauth", "oauth", "VERIFIED", None, data, via=caut)
            return _err(
                "claude_oauth", "oauth", "VERIFIED",
                f"caut rc={p.returncode}: {(p.stderr or '')[:200]}",
                "CLI_FAILED",
            )
        except subprocess.TimeoutExpired:
            return _err("claude_oauth", "oauth", "VERIFIED", "caut timed out", "TIMEOUT")
        except Exception as e:
            return _err("claude_oauth", "oauth", "VERIFIED", str(e), "CLI_FAILED")
    if shutil.which("claude"):
        return _stub(
            "claude_oauth",
            "claude CLI present but caut binary missing — wire caut OAuth after build (docs/CAUT.md)",
            "cli",
            "VERIFIED",
        )
    return _stub(
        "claude_oauth",
        "caut not built — Claude Code / subscription usage via caut OAuth later (docs/CAUT.md)",
        "oauth",
        "VERIFIED",
    )


def fetch_devin() -> dict:
    return _stub(
        "devin",
        "Cognition/Devin — no public quota API discovered",
        "stub",
        "UNKNOWN",
    )


def fetch_droid() -> dict:
    return _stub(
        "droid",
        "Factory Droid — no public quota API discovered",
        "stub",
        "UNKNOWN",
    )


def fetch_cognition() -> dict:
    return _stub(
        "cognition",
        "Same family as Devin — no public quota API; stub until documented",
        "stub",
        "UNKNOWN",
    )


def fetch_ai_gateway() -> dict:
    if _env("AI_GATEWAY_API_KEY"):
        return _stub(
            "ai-gateway",
            "AI_GATEWAY_API_KEY present; aggregator usage API UNKNOWN — meter",
            "metered",
            "UNKNOWN",
        )
    return _stub("ai-gateway", "no AI_GATEWAY_API_KEY — STUB", "stub", "UNKNOWN")


def fetch_local_probe(name: str, base_url: str) -> dict:
    try:
        url = base_url.rstrip("/") + "/models"
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            _ = r.read(256)
        return _ok(
            name, "localProbe", "VERIFIED", 100.0,
            {"base_url": base_url, "reachable": True},
            note="availability-gated infinite quota floor",
        )
    except Exception as e:
        return _from_exc(name, "localProbe", "VERIFIED", e)


PROVIDERS: list[tuple[str, Callable[[], dict]]] = [
    ("openrouter", fetch_openrouter),
    ("deepseek", fetch_deepseek),
    ("minimax", fetch_minimax),
    ("xai", fetch_xai),
    ("openai", fetch_openai),
    ("anthropic", fetch_anthropic),
    ("nvidia", fetch_nvidia),
    ("gemini", fetch_gemini),
    ("cerebras", fetch_cerebras),
    ("huggingface", fetch_huggingface),
    ("nous", fetch_nous),
    ("cursor", fetch_cursor),
    ("codex", fetch_codex),
    ("claude_oauth", fetch_claude_oauth),
    ("devin", fetch_devin),
    ("droid", fetch_droid),
    ("cognition", fetch_cognition),
    ("ai-gateway", fetch_ai_gateway),
]


def collect(only: Optional[list[str]] = None) -> dict:
    rows = []
    for name, fn in PROVIDERS:
        if only and name not in only:
            continue
        try:
            rows.append(fn())
        except Exception as e:
            rows.append(_err(name, "?", "UNKNOWN", f"unhandled: {e}", "UNHANDLED"))
    probes = _env("LOCAL_PROBE_URLS")
    if probes and not only:
        for i, u in enumerate(p.strip() for p in probes.split(",") if p.strip()):
            rows.append(fetch_local_probe(f"local-{i}", u))
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": _now(),
        "shadow": True,
        "mission": "quota-headroom-watching",
        "errorTaxonomy": [
            "KEY_UNSET", "AUTH_FAILED", "FORBIDDEN", "RATE_LIMITED", "TIMEOUT",
            "NETWORK", "HTTP_ERROR", "PARSE", "CLI_MISSING", "CLI_FAILED",
            "NO_PUBLIC_API", "UNHANDLED",
        ],
        "providers": rows,
    }


def status_for(row: dict, sprint_hours: Optional[float]) -> str:
    st = row.get("status")
    if st == "STUB":
        return "STUB"
    if st == "ERROR":
        ec = row.get("error_class") or ""
        return f"ERROR[{ec}]: {(row.get('note') or '')[:50]}"
    if st == "PARTIAL":
        return "PARTIAL (prefer meter / caut)"
    pct = row.get("pct_remaining")
    if pct is None:
        return "UNKNOWN (prefer local / meter)"
    if pct < EXCLUDE_PCT:
        return "EXCLUDE"
    if pct < WARN_PCT:
        return "WARN OPERATOR"
    return "OK"


def render_md(env: dict, sprint_hours: Optional[float] = None) -> None:
    print(f"# inference-quota-radar {SCHEMA} (shadow) @ {env['generatedAt']}")
    print("| Provider | Status | Mech | Conf | Remaining % | ErrClass | Note |")
    print("|---|---|---|---|---|---|---|")
    for r in env["providers"]:
        print(
            f"| {r['provider']} | {status_for(r, sprint_hours)} | {r.get('mechanism')} | "
            f"{r.get('confidence')} | "
            f"{r.get('pct_remaining') if r.get('pct_remaining') is not None else '?'} | "
            f"{r.get('error_class') or '-'} | {(r.get('note') or '')[:70]} |"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Inference Quota Radar (shadow mode)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--for-sprint", type=float, dest="sprint", default=None)
    ap.add_argument("--only", nargs="+", help="subset of provider ids")
    args = ap.parse_args()
    env = collect(args.only)
    if args.json:
        print(json.dumps(env, indent=2, default=str))
    else:
        render_md(env, args.sprint)
    # Exit 0 if any OK/PARTIAL/STUB (stubs are honest success); 1 if all ERROR
    statuses = {r.get("status") for r in env["providers"]}
    if statuses and statuses <= {"ERROR"}:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
