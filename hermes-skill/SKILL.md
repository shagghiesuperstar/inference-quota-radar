---
name: inference-quota-radar
description: >-
  Use when checking inference quota/credit headroom across providers before
  sprints or model selection (shadow mode — advise only, never gate). Not a
  spend maximizer.
---
# Inference Quota Radar

Install this folder to `~/.hermes/skills/devops/inference-quota-radar/` (or your Hermes skills root).

```bash
python ~/.hermes/skills/devops/inference-quota-radar/scripts/radar.py --json
```

Keys from environment / secret manager only. See repo README for full install and provider coverage.
