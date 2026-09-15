#!/usr/bin/env bash
# smoke-radar.sh — Phase1 honest smoke for Inference Quota Radar
# Exits non-zero only when every provider row is ERROR (stubs/PARTIAL/OK are success).
# Never prints secret values. Keys must already be in the environment (bws run / Hermes).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RADAR="${ROOT}/hermes-skill/scripts/radar.py"
OUT_DIR="${IQR_SMOKE_OUT:-${ROOT}/.smoke-out}"
mkdir -p "${OUT_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
JSON_OUT="${OUT_DIR}/radar-${STAMP}.json"
MD_OUT="${OUT_DIR}/radar-${STAMP}.md"

if [[ ! -f "${RADAR}" ]]; then
  echo "ERROR: missing ${RADAR}" >&2
  exit 2
fi

echo "== inference-quota-radar smoke @ ${STAMP} =="
echo "radar: ${RADAR}"
echo "python: $(command -v python3)"
python3 --version

# Optional tooling presence (names only)
echo "-- tooling --"
echo "mmx: $(command -v mmx || echo MISSING)"
echo "caut: $(command -v caut || echo MISSING)"
if [[ -x /workspace/inference-quota-radar-work/caut-hermes/target/release/caut ]]; then
  echo "caut_work_release: /workspace/inference-quota-radar-work/caut-hermes/target/release/caut (present)"
else
  echo "caut_work_release: absent (see docs/CAUT.md)"
fi

# Env key NAMES present? (bool only — never values)
echo "-- env key presence (bool) --"
for v in \
  OPENROUTER_API_KEY DEEPSEEK_API_KEY MINIMAX_API_KEY XAI_API_KEY OPENAI_API_KEY \
  ANTHROPIC_API_KEY NVIDIA_API_KEY NIM_API_KEY_1 GOOGLE_API_KEY GEMINI_API_KEY \
  CEREBRAS_API_KEY HF_TOKEN HUGGINGFACEHUB_API_TOKEN AI_GATEWAY_API_KEY \
  DEEPSEEK_BUDGET_USD LOCAL_PROBE_URLS
do
  if [[ -n "${!v:-}" ]]; then
    _val="${!v}"
    echo "  ${v}=set len=${#_val}"
  else
    echo "  ${v}=unset"
  fi
done

echo "-- run radar --"
set +e
python3 "${RADAR}" --json > "${JSON_OUT}" 2>"${OUT_DIR}/radar-${STAMP}.err"
RC=$?
python3 "${RADAR}" > "${MD_OUT}" 2>>"${OUT_DIR}/radar-${STAMP}.err"
RC2=$?
set -e

# Summarize statuses without dumping raw payloads that might echo secrets
python3 - << PY
import json, sys
path = "${JSON_OUT}"
try:
    data = json.load(open(path))
except Exception as e:
    print(f"JSON parse failed: {e}", file=sys.stderr)
    sys.exit(1)
rows = data.get("providers") or []
from collections import Counter
c = Counter(r.get("status") for r in rows)
print("status_counts:", dict(c))
print("providers:", len(rows))
for r in rows:
    pct = r.get("pct_remaining")
    print(f"  - {r.get('provider')}: status={r.get('status')} err={r.get('error_class')} pct={pct}")
# integrity: never allow fabricated numeric remaining on STUB
bad = [r["provider"] for r in rows if r.get("status") == "STUB" and r.get("pct_remaining") is not None]
if bad:
    print("FAIL: STUB rows must not carry pct_remaining:", bad, file=sys.stderr)
    sys.exit(3)
PY

echo "wrote: ${JSON_OUT}"
echo "wrote: ${MD_OUT}"
# Prefer first run exit code; treat all-ERROR as failure
if [[ ${RC} -ne 0 ]]; then
  echo "SMOKE FAIL (radar exit ${RC})" >&2
  exit "${RC}"
fi
echo "SMOKE PASS"
exit 0
