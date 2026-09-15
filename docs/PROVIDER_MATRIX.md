# Provider Matrix — IQR Phase1

Legend: **V** = VERIFIED (in spec/box), **I** = INFERRED (reasonable but unproven), **U** = UNKNOWN (needs probe/reverse).
Mechanism tags: `api` = token REST, `cli` = local binary, `oauth` = OAuth/keyring, `web` = browser/HTML, `lp` = LocalProbe (OpenAI-compat), `meter` = token-spend estimation, `stub` = honest placeholder, `dash` = web dashboard scrape.

| Provider | Mechanism | Conf | Phase | Notes |
|---|---|---|---|---|
| Claude (Anthropic) | `oauth` / `cli` / `keyring` | V | Phase1 (reuse caut) | Endpoints: caut `cli|web|oauth|apiToken|localProbe|webDashboard` already implemented. Env key name TBD per caut convention. Headroom via existing OAuth. |
| OpenAI / Codex | `web` + `cli` | V | Phase1 (reuse caut) | caut `webDashboard` for chatg.com usage + Codex CLI-RPC. OpenAI usage endpoints documented but not 1:1 for ChatGPT subscription. Headroom from dashboard. |
| xAI / Grok | `api` (meter) + `dash` (stub) | V | Phase1 meter / Phase1+ dash | No public credits REST. RPS/TPM tier headers documented. Use `XAI_API_KEY`; meter spend via `/v1/chat/completions` token counts. Dash scrape deferred. |
| OpenRouter | `api` | V | Phase1 | `GET openrouter.ai/api/v1/key` + `/credits`. Env via BWS (likely `OPENROUTER_API_KEY`). Bitwarden Secrets Manager mediated; do not literal in YAML. |
| DeepSeek | `api` | V | Phase1 | `GET api.deepseek.com/user/balance` Bearer. Env via BWS (likely `DEEPSEEK_API_KEY`). |
| MiniMax | `cli` (`mmx quota show`) → else `meter`/stub | V cli / I meter | Phase1 via mmx | `mmx quota show` is the path of least resistance. `MINIMAX_BASE_URL` already in ss dotenv. Fallback: meter spend if `MINIMAX_API_KEY` available; else stub. No public usage REST. |
| Nous Research | `dash` (XHR reverse) + `meter` | V | Phase1 stub / Phase1+ dash | No public balance endpoint. Portal UI shows balance; reverse XHR or scrape. Phase1 = stub with TODO. Meter via chat/completions token counts possible. |
| NVIDIA NIM | `api` | I | Phase1 stub | `NIM_BASE_URL` present in ss dotenv — suggests an endpoint is configured, but key/header convention unverified. Phase1: probe with env-detect, stub if no balance endpoint found. |
| Google AI Studio / Gemini | `api` (meter) / `dash` (stub) | I | Phase1 stub | No public credits endpoint for AI Studio quotas. Meter token usage; rate-limit headroom unknown. Phase1 = stub. |
| Cerebras | `api` (meter) / `dash` (stub) | I | Phase1 stub | No public balance REST confirmed. Meter via inference API; dash deferred. |
| Cursor | `dash` (auth) | U | Phase1 stub | Subscription/quota lives behind auth portal; no documented REST. Stub. |
| Devin (Cognition) | `dash` / `api` | U | Phase1 stub | No public quota API discovered. Stub. |
| Droid (Factory) | `dash` / `api` | U | Phase1 stub | No public quota API discovered. Stub. |
| HuggingFace | `api` (meter) | I | Phase1 stub | Inference token spend meter possible; no public credits REST confirmed. |
| ai-gateway (LiteLLM/Portkey-style) | `api` (meter) | I | Phase1 stub | If provider is a gateway with admin endpoints, headroom varies; Phase1 stub unless concrete endpoint surfaces. |
| Z.ai (GLM) | `dash` | V | DEFER | Scrape deferred per spec. Stub only. |
| Local OpenAI-compat | `lp` | V | Phase1 | caut `localProbe` pattern. Probe `/v1/models` + infer from rate-limit headers. |
| Hermes Phase0 (DeepSeek + OpenRouter) | `api` | V | Phase1 (extend) | Skill already has stubs; wire to real endpoints in Phase1. |

**Phase1 in scope (P0):** Claude, Codex, OpenRouter, DeepSeek, MiniMax (via `mmx`), xAI (meter), Nous (stub→meter), LocalProbe, Hermes stubs promoted.

**Phase1 stub-only (honest placeholder, no fake numbers):** NIM, Gemini, Cerebras, HF, ai-gateway, Cursor, Devin, Droid, Z.ai.

**Environment key handling (V):** All provider keys flow via BWS on ss — `.env` only carries `BWS_ACCESS_TOKEN` and base URLs (`MINIMAX_BASE_URL`, `NIM_BASE_URL`). Never literal API keys in repo, skill YAML, or this matrix.


---

## Live environment notes (ss @ 2026-09-15 overnight sprint) [VERIFIED]

### BWS secret key NAMES present (values never logged/committed)
- **YES:** `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY`, `MINIMAX_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `NVIDIA_API_KEY`, `NIM_API_KEY_1..3`, `HF_TOKEN`, `AI_GATEWAY_API_KEY`, `DARKBLOOM_API_KEY`, `COPILOT_GITHUB_TOKEN`
- **NOT observed as BWS keys:** `ANTHROPIC_API_KEY`, `CEREBRAS_API_KEY`, `NOUS_API_KEY`, `CURSOR_*`, `DEVIN_*`, `DROID_*` (Claude may use OAuth/CLI; Nous/Cursor/Devin/Droid remain stub/meter)

### ss dotenv (non-secret / infra)
- `BWS_ACCESS_TOKEN`, `MINIMAX_BASE_URL`, `NIM_BASE_URL`, `DARKBLOOM_LOCAL_API_KEY`, `OPENAI_MODEL`, `OPENAI_USERNAME`

### auth.json OAuth blobs (structure only)
- `minimax-oauth`, `xai-oauth` present

### Tooling gaps on ss
- No `rustup`/`cargo`/`rustc`, no `caut` binary, no `mmx` on PATH
- Hermes skill Phase0 live at `~/.hermes/skills/devops/inference-quota-radar/scripts/radar.py` (OpenRouter+DeepSeek only)

### Box (GrokBot Linux) tooling
- rustup installed overnight; toolchain `nightly-2026-08-31` present; `cargo check` may still need std/sysroot validation (see BLOCKERS.md)
- `mmx` available at `/home/box/.local/bin/mmx`; `mmx quota show` works (returns interval/weekly remaining %)
