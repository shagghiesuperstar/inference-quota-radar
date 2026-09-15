# Provider Matrix — IQR Phase1

Legend: **V** = VERIFIED (in spec/box), **I** = INFERRED (reasonable but unproven), **U** = UNKNOWN (needs probe/reverse).

Mechanism tags: `api` = token REST, `cli` = local binary, `oauth` = OAuth/keyring, `web` = browser/HTML, `lp` = LocalProbe (OpenAI-compat), `meter` = token-spend estimation, `stub` = honest placeholder, `dash` = web dashboard scrape.

Status values from `radar.py`: **OK** (real `pct_remaining`), **PARTIAL** (live probe, no remaining %), **STUB** (no public API — `pct_remaining` always null), **ERROR** (with `error_class`).

**Honesty rule:** never fabricate quota percentages. STUB/PARTIAL rows must leave `pct_remaining` as `null` unless derived from a documented response field.

| radar id | Provider | Mechanism | Conf | Phase | Notes |
|---|---|---|---|---|---|
| `claude_oauth` | Claude subscription (Anthropic) | `oauth` / `cli` (caut) | V | Phase1 (reuse caut) | Prefer `caut usage --provider claude`. See `docs/CAUT.md`. |
| `anthropic` | Anthropic API key | `api` (liveness) | I | Phase1 PARTIAL | Models probe only — no simple remaining-quota REST for all plans. |
| `codex` | OpenAI Codex / ChatGPT usage | `web` + `cli` (caut) | V | Phase1 (reuse caut) | Prefer caut `webDashboard` / CLI-RPC. |
| `openai` | OpenAI API key | `api` (liveness) | I | Phase1 PARTIAL | `/v1/models` proves key; Usage API + budget later. |
| `xai` | xAI / Grok | `api` (meter) + liveness | V | Phase1 PARTIAL/meter | No public credits REST. Meter spend vs budget. |
| `openrouter` | OpenRouter | `api` | V | Phase1 | `GET /api/v1/key` → limit / limit_remaining. Env: `OPENROUTER_API_KEY`. |
| `deepseek` | DeepSeek | `api` | V | Phase1 | `GET /user/balance`. Optional `DEEPSEEK_BUDGET_USD` for %. |
| `minimax` | MiniMax | `cli` (`mmx quota show`) → else meter/stub | V cli / I meter | Phase1 | No public usage REST. |
| `nous` | Nous Research | `stub` / meter | V | Phase1 stub | No public balance API. |
| `nvidia` | NVIDIA NIM | `api` (liveness) | I | Phase1 PARTIAL/stub | Models probe; no verified credits API. |
| `gemini` | Google AI Studio / Gemini | `api` (liveness) / meter | I | Phase1 PARTIAL/stub | Console/project quotas — no simple credits REST. |
| `cerebras` | Cerebras | `api` (liveness) / stub | I | Phase1 PARTIAL/stub | No verified balance REST. |
| `huggingface` | Hugging Face | `api` (whoami) | I | Phase1 PARTIAL | Identity OK; credit APIs vary by product. |
| `cursor` | Cursor | `stub` | U | Phase1 stub | Auth portal only. |
| `devin` | Devin | `stub` | U | Phase1 stub | No public quota API. |
| `cognition` | Cognition | `stub` | U | Phase1 stub | Same family as Devin. |
| `droid` | Factory Droid | `stub` | U | Phase1 stub | No public quota API. |
| `ai-gateway` | ai-gateway | `stub` / meter | U | Phase1 stub | Aggregator usage UNKNOWN. |
| *(local-\*)* | Local OpenAI-compat | `lp` | V | Phase1 | `LOCAL_PROBE_URLS` → `/models` reachability. |

**Phase1 live/partial (env keys):** `openrouter`, `deepseek`, `minimax`, `xai`, `openai`, `anthropic`, `nvidia`, `gemini`, `cerebras`, `huggingface`.

**Phase1 stubs (no fake numbers):** `nous`, `cursor`, `codex` (until caut), `claude_oauth` (until caut), `devin`, `droid`, `cognition`.

**error_class taxonomy:** `KEY_UNSET`, `AUTH_FAILED`, `FORBIDDEN`, `RATE_LIMITED`, `TIMEOUT`, `NETWORK`, `HTTP_ERROR`, `PARSE`, `CLI_MISSING`, `CLI_FAILED`, `NO_PUBLIC_API`, `UNHANDLED`.

**Environment key handling (V):** Provider keys via BWS / Hermes env inject. Never literal API keys in repo, skill YAML, or this matrix.

---

## Live environment notes (ss @ 2026-09-15 overnight sprint) [VERIFIED]

### BWS secret key NAMES present (values never logged/committed)
- **YES:** `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY`, `MINIMAX_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `NVIDIA_API_KEY`, `NIM_API_KEY_1..3`, `HF_TOKEN`, `AI_GATEWAY_API_KEY`, `DARKBLOOM_API_KEY`, `COPILOT_GITHUB_TOKEN`
- **NOT observed as BWS keys:** `ANTHROPIC_API_KEY`, `CEREBRAS_API_KEY`, `NOUS_API_KEY`, `CURSOR_*`, `DEVIN_*`, `DROID_*` (Claude subscription → `claude_oauth`/caut; Nous/Cursor/Devin/Droid remain stub/meter)

### ss dotenv (non-secret / infra)
- `BWS_ACCESS_TOKEN`, `MINIMAX_BASE_URL`, `NIM_BASE_URL`, `DARKBLOOM_LOCAL_API_KEY`, `OPENAI_MODEL`, `OPENAI_USERNAME`

### auth.json OAuth blobs (structure only)
- `minimax-oauth`, `xai-oauth` present

### Tooling gaps on ss
- No `rustup`/`cargo`/`rustc`, no `caut` binary, no `mmx` on PATH
- Hermes skill Phase0 may still be OpenRouter+DeepSeek-only until this branch is deployed

### Box (GrokBot Linux) tooling
- rustup + `nightly-2026-08-31`; `cargo check` passed on caut-hermes — **release binary not required for skill smoke** (see `docs/CAUT.md`)
- `mmx` at `/home/box/.local/bin/mmx`; `mmx quota show` returns interval remaining %
