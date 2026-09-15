# Phase1 Plan — Morning DoD

Scope: get `radar.py` smoking for documented REST endpoints, ship honest stubs for the rest, set up overnight headroom-watching. NOT a spend maximizer.

## 1. What ships by morning

- [ ] Cargo toolchain ready on ss: `rustup default nightly-2026-08-31` and `cargo --version` confirms.
- [ ] `caut` fork buildable; binary at known path on ss PATH.
- [ ] `radar.py` skill (mmx-side) extended from Phase0:
  - [ ] OpenRouter: `GET openrouter.ai/api/v1/key` → headroom USD remaining.
  - [ ] DeepSeek: `GET api.deepseek.com/user/balance` → balance USD.
  - [ ] xAI: meter via token counts from `/v1/chat/completions` responses; flag tier RPS/TPM.
  - [ ] MiniMax: shell out to `mmx quota show` and parse; fallback meter if API key present.
  - [ ] Nous: stub entry with explicit TODO and zero fabricated numbers.
  - [ ] LocalProbe: reach `/v1/models` on configured base URL; report reachability.
- [ ] Reuse caut dispatch: Claude + Codex via existing `cli|web|oauth|apiToken|localProbe|webDashboard` branches — no rewrite.
- [ ] One honest stub row per unsupported provider (NIM, Gemini, Cerebras, HF, ai-gateway, Cursor, Devin, Droid, Z.ai) with mechanism tag and confidence tag.
- [ ] Smoke script: single command runs all Phase1 probes, exits non-zero only on hard failures (auth missing, network down), not on stubs.

## 2. What stays deferred

- Nous portal XHR reverse-engineering.
- Cursor / Devin / Droid / Z.ai dashboard scraping.
- NVIDIA NIM / Gemini / Cerebras balance endpoint discovery (probe in a later sprint).
- Headroom prediction / forecasting logic (Phase1 reports current state only).
- Alerting / scheduling beyond a manual smoke run.

## 3. Cargo / rustup status

- Box: `rustup` installed, `nightly-2026-08-31` toolchain available; **`cargo check` PASSED** on caut-hermes @ 0f45409.
- ss: missing `rustc`, `cargo`, `caut` binary.
- Action: install toolchain on ss, build fork, place binary on PATH.
- Verify: `rustc --version`, `cargo --version`, `caut --help`.

## 4. ss status

- `BWS_ACCESS_TOKEN` present (Bitwarden Secrets Manager handles literal keys).
- `MINIMAX_BASE_URL`, `NIM_BASE_URL` present (endpoints, not secrets).
- `DARKBLOOM_LOCAL_API_KEY` present — note name, do not inline; resolve at runtime via BWS if needed.
- `OPENROUTER_API_KEY` and `DEEPSEEK_API_KEY` **exist in BWS** [VERIFIED names-only]. Inject via `bws run` / Hermes env loader before smoke; not present as plain dotenv vars.
- Hermes skill Phase0 (DeepSeek + OpenRouter stubs) present and ready to extend.

## 5. Success criteria

- [ ] `radar.py` exits 0 on a clean run with at least 4 VERIFIED providers returning real numbers.
- [ ] All stub rows are tagged VERIFIED|INFERRED|UNKNOWN and mechanism-tagged; zero fabricated quota values.
- [ ] No literal API keys, tokens, or cookies in repo, skill YAML, or commit history.
- [ ] `caut` fork builds from a clean clone on ss nightly.
- [ ] Smoke output is diffable (JSON or stable text) so two runs can be compared.
- [ ] Headroom semantics documented: remaining capacity, not spend-to-date.

## 6. Secrets hygiene

- Repo: `.gitignore` covers `.env`, `*.key`, `auth.json` runtime copies.
- Skill YAML: only references env-var NAMES (`OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY`, `MINIMAX_API_KEY`, `BWS_ACCESS_TOKEN`, etc.).
- Runtime resolution: BWS on ss, keyring locally for Claude/Codex OAuth.
- This plan and the matrix contain no secret values — only key NAMES and endpoint URLs.

## Order of operations (overnight)

1. Install rustup toolchain on ss; verify versions.
2. Build `caut` fork; place on PATH.
3. Confirm BWS resolution for OpenRouter + DeepSeek keys.
4. Extend `radar.py` from Hermes Phase0 with the Phase1 providers above.
5. Add honest stubs with mechanism + confidence tags.
6. Wire smoke runner; run end-to-end.
7. Diff morning vs overnight snapshot; report headroom deltas only.


---

## Morning DoD checklist (operator)

1. [ ] Read `PROVIDER_MATRIX.md` + this plan in `/workspace/inference-quota-radar-work/`
2. [ ] Deploy draft skill from `/workspace/inference-quota-radar-work/skill/` → ss `~/.hermes/skills/devops/inference-quota-radar/` (backup Phase0 first)
3. [ ] On ss: `bws run -- python3 ~/.hermes/skills/devops/inference-quota-radar/scripts/radar.py --json` (or Hermes profile env inject)
4. [ ] Confirm OpenRouter + DeepSeek return real headroom numbers; MiniMax via `mmx quota` if installed; others stub/honest
5. [ ] Optional: install rustup+nightly on ss and `cargo build --release` caut — **not required for skill smoke**
6. [ ] Optional: install `mmx` on ss for MiniMax quota CLI
7. [ ] Shadow mode only — do NOT gate Kanban model picks yet
8. [ ] Secrets sweep: no values in git / skill YAML / commit diffs

