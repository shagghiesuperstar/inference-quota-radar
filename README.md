# Inference Quota Radar

**Watch inference quota headroom, burn rate, and reset windows** across providers so agents pick who still has juice.

This is **not** a spend maximizer. Do not rename it or describe it as one.

| | |
|---|---|
| **Slug** | `inference-quota-radar` |
| **Org** | [`shagghiesuperstar`](https://github.com/shagghiesuperstar) (AI infra) |
| **Upstream vehicle** | Fork of [`Dicklesworthstone/coding_agent_usage_tracker`](https://github.com/Dicklesworthstone/coding_agent_usage_tracker) (`caut`) — MIT + Restricted-Parties rider; upstream accepts no PRs → fork-and-own |
| **Agent surfaces** | Hermes skill (`radar.py`) now; thin semantic MCP later (`headroom`, `eta_to_limit`, `safe_for_overnight`) |

## Who this is for
Any agent that spends cloud inference — **Hermes**, **Grok Bot**, Claude Code, Cursor agents — on a machine that already has provider API keys in env / Bitwarden / OS keychain.

## Quick start (any agent)
```bash
git clone https://github.com/shagghiesuperstar/inference-quota-radar.git
cd inference-quota-radar
./scripts/install-hermes-skill.sh   # Hermes path; or run python3 hermes-skill/scripts/radar.py directly
python3 hermes-skill/scripts/radar.py --json
```
Full install paths: [`scripts/install-agent.md`](scripts/install-agent.md).

## What works today (Phase 1 — honest matrix)
See [`docs/PROVIDER_MATRIX.md`](docs/PROVIDER_MATRIX.md).

**Live / partial HTTP or CLI fetch (env keys):** OpenRouter, DeepSeek, MiniMax (`mmx quota show` preferred), OpenAI (liveness), Anthropic (partial), xAI (partial), NVIDIA NIM (partial), Gemini (partial), Cerebras (partial), Hugging Face (partial).

**Reuse upstream caut when built:** Claude OAuth/subscription usage, Codex dashboard/CLI.

**Honest stubs (no fake numbers):** Nous portal, Cursor, Devin/Cognition, Droid, and others without a public remaining-quota API.

## Ship order
1. **CLI + Hermes skill** with real provider JSON ← you are here  
2. Thin **MCP** on top of caut (semantic tools — not a raw `caut usage` pipe)  
3. Optional `caut serve` / `watch` for always-on headroom on a localhost bind only  

## Secrets
- Keys stay in the host secret path (env, Bitwarden Secrets Manager, OS keychain).
- **Never** commit `.env`, tokens, cookies, or HAR dumps with credentials.
- Do not put production keys in caut’s token-account store until at-rest encryption is audited.

## Build `caut` (optional, for Claude/Codex subscription windows)
```bash
# Toolchain: rustup nightly-2026-08-31 (see upstream rust-toolchain.toml)
cargo build --release
./target/release/caut usage --json
./target/release/caut doctor
```
On Apple Silicon Homebrew hosts, put rustup ahead of Homebrew rustc:
`export PATH="/opt/homebrew/opt/rustup/bin:/opt/homebrew/bin:$PATH"`.

## Verify
```bash
python3 hermes-skill/scripts/radar.py --json | head
# after caut build:
caut usage --json | head
test -f "$HOME/.hermes/skills/devops/inference-quota-radar/SKILL.md"
```

## License
Upstream `caut` is MIT with a Restricted-Parties rider (OpenAI LLC / Anthropic PBC barred from using that software). Carry `LICENSE` forward from the fork. This repo’s Hermes skill scripts are provided for operator/agent use under the same spirit: no warranty; you own your keys and rate limits.

## Status
Phase 1 skill + docs. Public README may land before every Rust provider fetcher exists — coverage is labeled honestly in the matrix. MCP is intentionally **not** shipped before radar returns real numbers for at least one documented API path.
