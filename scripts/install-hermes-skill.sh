#!/usr/bin/env bash
set -euo pipefail
DEST="${HERMES_SKILL_DIR:-$HOME/.hermes/skills/devops/inference-quota-radar}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$DEST/scripts"
cp -a "$ROOT/hermes-skill/SKILL.md" "$DEST/SKILL.md"
cp -a "$ROOT/hermes-skill/scripts/radar.py" "$DEST/scripts/radar.py"
chmod +x "$DEST/scripts/radar.py"
echo "Installed Inference Quota Radar skill → $DEST"
echo "Smoke: python3 \"$DEST/scripts/radar.py\" --json"
