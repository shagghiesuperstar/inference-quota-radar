# Agent notes — Inference Quota Radar

- Product name: **Inference Quota Radar**. Never call it a maximizer.
- Org: `shagghiesuperstar` only (not LAMBODOG).
- Phase 1 skill must stay secret-free; extend `hermes-skill/scripts/radar.py` with documented APIs; stub honestly.
- Adding a Rust caut provider = 6 touchpoints (enum, budgets parse, providers/<name>, pipeline, mod.rs, tests+TOML). Templates: claude, codex.
- Do not ship MCP before live JSON headroom works.
- Mark VERIFIED vs INFERRED in docs; never invent quota numbers.
