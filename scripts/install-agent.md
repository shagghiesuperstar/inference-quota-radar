# Install for any agent (Hermes, Grok Bot, Claude Code, …)

## Option A — Hermes skill (recommended for Hermes Desktop/CLI)
```bash
git clone https://github.com/shagghiesuperstar/inference-quota-radar.git
cd inference-quota-radar
./scripts/install-hermes-skill.sh
# with secrets already in env / Bitwarden:
python3 ~/.hermes/skills/devops/inference-quota-radar/scripts/radar.py --json
```

## Option B — Run the Python radar without Hermes
```bash
git clone https://github.com/shagghiesuperstar/inference-quota-radar.git
cd inference-quota-radar
export OPENROUTER_API_KEY=…   # etc — never commit
python3 hermes-skill/scripts/radar.py --json
```

## Option C — Rust `caut` CLI (subscription usage for Claude/Codex + fork roadmap)
Requires rustup toolchain `nightly-2026-08-31` (see `rust-toolchain.toml` in the caut tree when vendored).
```bash
# after caut sources are in ./caut (see README)
export PATH="$HOME/.cargo/bin:/opt/homebrew/opt/rustup/bin:$PATH"
cd caut && cargo build --release
./target/release/caut usage --json
```

## Rules for agents
1. This tool reports **headroom / burn / reset** — do **not** use it to maximize spend.
2. Never write API keys into the repo, skill YAML, or caut token stores until encryption-at-rest is audited.
3. Prefer honest `stub` / `partial` over invented numbers.
4. Shadow mode: advise model selection; do not hard-gate workflows until operator enables that.
