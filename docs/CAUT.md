# Building `caut` (Claude / Codex subscription usage)

`caut` ([coding_agent_usage_tracker](https://github.com/Dicklesworthstone/coding_agent_usage_tracker)) is the preferred path for **Claude Code OAuth** and **Codex** subscription usage windows. The Hermes skill (`radar.py`) shells out to `caut usage --json` when a binary is on `PATH` (providers `claude_oauth` and `codex`).

This is **optional** for Phase 1 skill smoke: OpenRouter / DeepSeek / MiniMax (`mmx`) do not need `caut`.

## Toolchain pin

Upstream pins **`nightly-2026-08-31`** via `rust-toolchain.toml`. Use that exact channel (not floating nightly) so `-D warnings` clippy gates stay stable.

```bash
# Install rustup if needed: https://rustup.rs
rustup toolchain install nightly-2026-08-31 --component rustfmt,clippy
rustup default nightly-2026-08-31
rustc --version   # expect nightly with 2026-08-30/31 date
cargo --version
```

On Apple Silicon Homebrew hosts, put rustup ahead of Homebrew `rustc`:

```bash
export PATH="/opt/homebrew/opt/rustup/bin:/opt/homebrew/bin:$PATH"
```

## Clone and build

```bash
# Public upstream (MIT + Restricted-Parties rider). Upstream accepts no PRs → fork-and-own if needed.
git clone https://github.com/Dicklesworthstone/coding_agent_usage_tracker.git caut
cd caut
# Optional: add your private fork remote later (do not commit secrets)
# git remote add fork git@github.com:YOUR_ORG/caut-hermes.git

cargo check          # fast validate
cargo build --release
./target/release/caut --help
./target/release/caut doctor
./target/release/caut usage --json
```

Place the binary on `PATH` (example):

```bash
mkdir -p "$HOME/bin"
cp target/release/caut "$HOME/bin/caut"
export PATH="$HOME/bin:$PATH"
```

## Wire into Inference Quota Radar

```bash
# From this repo root (with caut on PATH):
python3 hermes-skill/scripts/radar.py --only claude_oauth codex --json
```

- `claude_oauth` → `caut usage --json --provider claude`
- `codex` → `caut usage --json --provider codex`

If `caut` is missing, those rows are honest **STUB** (`error_class=NO_PUBLIC_API`) — never fabricated percentages.

## Box work-tree note (2026-09-15)

On the shared Grok Bot box, a checked-out tree may exist at:

`/workspace/inference-quota-radar-work/caut-hermes`

- `cargo check` **PASSED** on pin `nightly-2026-08-31` (commit `0f45409`).
- **`target/release/caut` binary was not present** after overnight work (release artifacts incomplete / not finished). Do **not** assume a long `cargo build --release` is required for morning skill smoke.
- If/when built, expected path: `/workspace/inference-quota-radar-work/caut-hermes/target/release/caut` — `radar.py` will also look there as a fallback.

## Optional vendor later

Vendoring `caut` into this repo (subtree / submodule) is deferred. Prefer:

1. Documented clone + build (this file).
2. Private fork under `shagghiesuperstar` if patches are needed.
3. Submodule / vendor only after MCP thin-wrapper scope is locked.

## Secrets

- Claude / Codex auth stays in OS keychain / caut’s local store — **never** commit cookies, HAR, or tokens.
- Do not put production API keys into caut’s token-account store until at-rest encryption is audited.
