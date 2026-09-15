#!/usr/bin/env python3
"""Inference Quota Radar — Phase1 Hermes skill frontend.

Shadow mode: advise headroom only; never gate routing; never write secrets.
Reads keys from environment only (Hermes/BWS inject). Honest STUB when no API.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Optional

SCHEMA = "radar.phase1"
UA = "hermes-quota-radar/0.2"
TIMEOUT = 20

# Thresholds (headroom watching — not spend maximization)
EXCLUDE_PCT = 10.0
WARN_PCT = 25.0
STALE_HOURS = 2.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env(*names: str) -> Optional[str]:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def _get_json(url: str, key: Optional[str] = None, headers: Optional[dict] = None) -> Any:
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    if key:
        hdrs["Authorization"] = f"Bearer {key}"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def _stub(provider: str, reason: str, mechanism: str, confidence: str) -> dict:
    return {
        "provider": provider,
        "status": "STUB",
        "mechanism": mechanism,
        "confidence": confidence,
        "pct_remaining": None,
        "raw": None,
        "note": reason,
    }


def _ok(provider: str, mechanism: str, confidence: str, pct: Optional[float], raw: Any, **extra) -> dict:
    row = {
        "provider": provider,
        "status": "OK",
        "mechanism": mechanism,
        "confidence": confidence,
        "pct_remaining": pct,
        "raw": raw,
        "note": None,
    }
    row.update(extra)
    return row


def _err(provider: str, mechanism: str, confidence: str, err: str) -> dict:
    return {
        "provider": provider,
        "status": "ERROR",
        "mechanism": mechanism,
        "confidence": confidence,
        "pct_remaining": None,
        "raw": None,
        "note": err,
    }


# ---- providers -------------------------------------------------------------

def fetch_openrouter() -> dict:
    key = _env("OPENROUTER_API_KEY")
    if not key:
        return _err("openrouter", "apiToken", "VERIFIED", "OPENROUTER_API_KEY unset")
    try:
        data = _get_json("https://openrouter.ai/api/v1/key", key)
        # documented: data.limit / limit_remaining / limit_reset (shape may nest under "data")
        payload = data.get("data", data) if isinstance(data, dict) else data
        limit = payload.get("limit")
        rem = payload.get("limit_remaining")
        pct = None
        if isinstance(limit, (int, float)) and limit and isinstance(rem, (int, float)):
            pct = round(100.0 * rem / limit, 2)
        elif isinstance(rem, (int, float)) and limit is None:
            # unlimited key — treat as high headroom
            pct = 100.0
        return _ok(
            "openrouter", "apiToken", "VERIFIED", pct, payload,
            limit=limit, limit_remaining=rem, limit_reset=payload.get("limit_reset"),
        )
    except Exception as e:
        return _err("openrouter", "apiToken", "VERIFIED", str(e))


def fetch_deepseek() -> dict:
    key = _env("DEEPSEEK_API_KEY")
    if not key:
        return _err("deepseek", "apiToken", "VERIFIED", "DEEPSEEK_API_KEY unset")
    try:
        data = _get_json("https://api.deepseek.com/user/balance", key)
        # balance_infos[].total_balance — prepaid; % needs budget baseline
        infos = data.get("balance_infos") or []
        total = None
        if infos and isinstance(infos, list):
            try:
                total = float(infos[0].get("total_balance"))
            except (TypeError, ValueError, IndexError):
                total = None
        budget = _env("DEEPSEEK_BUDGET_USD")
        pct = None
        if total is not None and budget:
            try:
                b = float(budget)
                if b > 0:
                    pct = round(100.0 * min(total, b) / b, 2)
            except ValueError:
                pass
        return _ok(
            "deepseek", "apiToken", "VERIFIED", pct, data,
            balance_usd=total, is_available=data.get("is_available"),
            note="prepaid balance; set DEEPSEEK_BUDGET_USD for pct_remaining",
        )
    except Exception as e:
        return _err("deepseek", "apiToken", "VERIFIED", str(e))


def fetch_minimax() -> dict:
    # Prefer mmx CLI quota show (verified on box)
    if shutil.which("mmx"):
        try:
            p = subprocess.run(
                ["mmx", "quota", "show", "--output", "json", "--non-interactive"],
                capture_output=True, text=True, timeout=30,
            )
            if p.returncode == 0 and p.stdout.strip():
                data = json.loads(p.stdout)
                remains = data.get("model_remains") or []
                # Prefer "general" interval remaining %
                pct = None
                for m in remains:
                    if m.get("model_name") == "general":
                        pct = m.get("current_interval_remaining_percent")
                        break
                if pct is None and remains:
                    pct = remains[0].get("current_interval_remaining_percent")
                return _ok("minimax", "cli", "VERIFIED", pct, data, via="mmx quota show")
            return _err("minimax", "cli", "VERIFIED", f"mmx rc={p.returncode}: {(p.stderr or '')[:200]}")
        except Exception as e:
            return _err("minimax", "cli", "VERIFIED", str(e))
    # No public usage REST — meter/stub
    if _env("MINIMAX_API_KEY", "MINIMAX_API_KEY1ST"):
        return _stub(
            "minimax",
            "mmx CLI missing; no public usage API — use metered Hermes logs later",
            "metered",
            "VERIFIED",
        )
    return _err("minimax", "cli", "VERIFIED", "mmx not on PATH and MINIMAX_API_KEY unset")


def fetch_xai() -> dict:
    key = _env("XAI_API_KEY")
    if not key:
        return _err("xai", "metered", "VERIFIED", "XAI_API_KEY unset")
    # No public credits REST [VERIFIED] — honest stub with metered path note
    return _stub(
        "xai",
        "no public credits endpoint; spend-tier RPS/TPM only — meter Hermes session spend vs monthly budget",
        "metered",
        "VERIFIED",
    )


def fetch_openai() -> dict:
    key = _env("OPENAI_API_KEY")
    if not key:
        return _err("openai", "apiToken", "VERIFIED", "OPENAI_API_KEY unset")
    # Usage API exists but needs org admin + date range; Phase1: probe auth only
    try:
        # lightweight authenticated probe — models list proves key alive
        data = _get_json("https://api.openai.com/v1/models", key)
        models = data.get("data") if isinstance(data, dict) else None
        return _ok(
            "openai", "apiToken", "INFERRED", None,
            {"models_sample": [m.get("id") for m in (models or [])[:5]]},
            note="key live; usage/completions quota needs Usage API + budget baseline (later)",
        )
    except Exception as e:
        return _err("openai", "apiToken", "VERIFIED", str(e))


def fetch_anthropic_claude() -> dict:
    # Prefer caut if built; else CLI `claude` usage if present; else stub
    if shutil.which("caut"):
        try:
            p = subprocess.run(
                ["caut", "usage", "--json", "--provider", "claude"],
                capture_output=True, text=True, timeout=60,
            )
            if p.returncode == 0 and p.stdout.strip():
                data = json.loads(p.stdout)
                return _ok("claude", "cli", "VERIFIED", None, data, via="caut usage")
            return _err("claude", "cli", "VERIFIED", f"caut rc={p.returncode}: {(p.stderr or '')[:200]}")
        except Exception as e:
            return _err("claude", "cli", "VERIFIED", str(e))
    if shutil.which("claude"):
        return _stub(
            "claude",
            "claude CLI present but caut binary missing — wire caut OAuth fetch after build",
            "cli",
            "VERIFIED",
        )
    if _env("ANTHROPIC_API_KEY"):
        return _stub(
            "claude",
            "ANTHROPIC_API_KEY present but no public usage REST for API keys; caut OAuth path preferred",
            "apiToken",
            "INFERRED",
        )
    return _stub("claude", "caut not built; no ANTHROPIC_API_KEY; use Claude Code OAuth via caut later", "oauth", "VERIFIED")


def fetch_codex() -> dict:
    if shutil.which("caut"):
        try:
            p = subprocess.run(
                ["caut", "usage", "--json", "--provider", "codex"],
                capture_output=True, text=True, timeout=60,
            )
            if p.returncode == 0 and p.stdout.strip():
                return _ok("codex", "webDashboard", "VERIFIED", None, json.loads(p.stdout), via="caut")
            return _err("codex", "webDashboard", "VERIFIED", f"caut rc={p.returncode}")
        except Exception as e:
            return _err("codex", "webDashboard", "VERIFIED", str(e))
    return _stub("codex", "caut not built — Codex usage via caut web-dashboard/CLI-RPC later", "webDashboard", "VERIFIED")


def fetch_nvidia() -> dict:
    key = _env("NVIDIA_API_KEY", "NIM_API_KEY_1", "NIM_API_KEY_2", "NIM_API_KEY_3")
    base = _env("NIM_BASE_URL", "NVIDIA_BASE_URL") or "https://integrate.api.nvidia.com/v1"
    if not key:
        return _err("nvidia", "stub", "INFERRED", "NVIDIA_API_KEY / NIM_API_KEY_* unset")
    # No verified public balance endpoint — probe models if possible
    try:
        url = base.rstrip("/") + "/models"
        data = _get_json(url, key)
        return _ok(
            "nvidia", "apiToken", "INFERRED", None, {"probe": "models", "ok": True},
            note="key/base live; no verified credits API — meter later",
            base_url=base,
        )
    except Exception as e:
        return _stub("nvidia", f"probe failed ({e}); no verified credits API — STUB/meter", "metered", "INFERRED")


def fetch_gemini() -> dict:
    key = _env("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_AI_API_KEY")
    if not key:
        return _err("gemini", "stub", "INFERRED", "GOOGLE_API_KEY unset")
    # AI Studio free-tier quotas are project-console based; no simple credits REST
    return _stub(
        "gemini",
        "GOOGLE_API_KEY present; AI Studio quotas are console/project based — no simple credits REST — meter/stub",
        "metered",
        "INFERRED",
    )


def fetch_nous() -> dict:
    if _env("NOUS_API_KEY"):
        return _stub("nous", "NOUS_API_KEY present but OpenAPI has no balance — portal XHR or meter", "metered", "VERIFIED")
    return _stub("nous", "no public balance API; portal UI only — meter Hermes logs or reverse USAGE XHR later", "stub", "VERIFIED")


def fetch_cerebras() -> dict:
    if _env("CEREBRAS_API_KEY"):
        return _stub("cerebras", "key present; no verified public balance REST — meter", "metered", "INFERRED")
    return _stub("cerebras", "CEREBRAS_API_KEY not in env/BWS inventory — STUB", "stub", "UNKNOWN")


def fetch_huggingface() -> dict:
    if _env("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACEHUB_API_TOKEN"):
        return _stub("huggingface", "HF_TOKEN present; Inference credit APIs vary by product — meter/stub", "metered", "INFERRED")
    return _err("huggingface", "stub", "INFERRED", "HF_TOKEN unset")


def fetch_ai_gateway() -> dict:
    if _env("AI_GATEWAY_API_KEY"):
        return _stub("ai-gateway", "AI_GATEWAY_API_KEY present; aggregator usage API UNKNOWN — meter", "metered", "UNKNOWN")
    return _stub("ai-gateway", "no AI_GATEWAY_API_KEY — STUB", "stub", "UNKNOWN")


def fetch_cursor() -> dict:
    return _stub("cursor", "subscription quota behind Cursor auth portal — no documented REST", "stub", "UNKNOWN")


def fetch_devin() -> dict:
    return _stub("devin", "Cognition/Devin — no public quota API discovered", "stub", "UNKNOWN")


def fetch_droid() -> dict:
    return _stub("droid", "Factory Droid — no public quota API discovered", "stub", "UNKNOWN")


def fetch_local_probe(name: str, base_url: str) -> dict:
    try:
        url = base_url.rstrip("/") + "/models"
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            _ = r.read(256)
        return _ok(name, "localProbe", "VERIFIED", 100.0, {"base_url": base_url, "reachable": True},
                   note="availability-gated infinite quota floor")
    except Exception as e:
        return _err(name, "localProbe", "VERIFIED", f"unreachable {base_url}: {e}")


PROVIDERS: list[tuple[str, Callable[[], dict]]] = [
    ("openrouter", fetch_openrouter),
    ("deepseek", fetch_deepseek),
    ("minimax", fetch_minimax),
    ("xai", fetch_xai),
    ("openai", fetch_openai),
    ("claude", fetch_anthropic_claude),
    ("codex", fetch_codex),
    ("nvidia", fetch_nvidia),
    ("gemini", fetch_gemini),
    ("nous", fetch_nous),
    ("cerebras", fetch_cerebras),
    ("huggingface", fetch_huggingface),
    ("ai-gateway", fetch_ai_gateway),
    ("cursor", fetch_cursor),
    ("devin", fetch_devin),
    ("droid", fetch_droid),
]


def collect(only: Optional[list[str]] = None) -> dict:
    rows = []
    for name, fn in PROVIDERS:
        if only and name not in only:
            continue
        try:
            rows.append(fn())
        except Exception as e:
            rows.append(_err(name, "?", "UNKNOWN", f"unhandled: {e}"))
    # optional local probes from env LOCAL_PROBE_URLS=url1,url2
    probes = _env("LOCAL_PROBE_URLS")
    if probes and not only:
        for i, u in enumerate(p.strip() for p in probes.split(",") if p.strip()):
            rows.append(fetch_local_probe(f"local-{i}", u))
    return {
        "schemaVersion": SCHEMA,
        "generatedAt": _now(),
        "shadow": True,
        "mission": "quota-headroom-watching",
        "providers": rows,
    }


def status_for(row: dict, sprint_hours: Optional[float]) -> str:
    if row.get("status") == "STUB":
        return "STUB"
    if row.get("status") == "ERROR":
        return f"ERROR: {(row.get('note') or '')[:60]}"
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
    print("| Provider | Status | Mech | Conf | Remaining % | Note |")
    print("|---|---|---|---|---|---|")
    for r in env["providers"]:
        print(
            f"| {r['provider']} | {status_for(r, sprint_hours)} | {r.get('mechanism')} | "
            f"{r.get('confidence')} | {r.get('pct_remaining') if r.get('pct_remaining') is not None else '?'} | "
            f"{(r.get('note') or '')[:80]} |"
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
    # Exit 0 if any OK or STUB rows exist (stubs are honest success); 1 if all ERROR
    statuses = {r.get("status") for r in env["providers"]}
    if statuses <= {"ERROR"}:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
