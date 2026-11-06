#!/usr/bin/env bash
# Invoked locally. Original NAV XLSX stays outside git and is never uploaded.
# No declarations/consents, trading, Neon writes or portfolio operations.
set -euo pipefail
umask 077

if [[ $# -lt 1 || $# -gt 2 || ! -f "$1" ]]; then
  echo 'Usage: bash scripts/run_local_vanguard_nav_preflight_v04.sh "/path/original-vanguard-export.xlsx" [--fetch-exact-nbp]' >&2
  exit 2
fi
INPUT="$1"
FETCH="no"
if [[ $# -eq 2 ]]; then
  if [[ "$2" != "--fetch-exact-nbp" ]]; then
    echo 'Unsupported option. Use only --fetch-exact-nbp.' >&2
    exit 2
  fi
  FETCH="yes"
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT_BASE="$HOME/Library/Application Support/InvestmentStrategyLab/NavResearch"
mkdir -p "$OUT_BASE"
chmod 700 "$OUT_BASE"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$OUT_BASE/v04-$STAMP"
mkdir -m 700 "$OUTPUT"
NBP="$OUTPUT/nbp/nbp-research-evidence-202111-202610.json"
mkdir -m 700 "$OUTPUT/nbp"

# Fetch original public NBP source evidence from the verified GitHub run.
# If the artifact has expired, re-download from NBP official public API.
if command -v gh >/dev/null 2>&1; then
  if ! gh run download 42228167332 \
      --repo gniewkob/Investment-Strategy-Lab \
      --name nbp-5y-reference-202111-202610 \
      --dir "$OUTPUT/nbp"; then
    echo 'NBP GitHub artifact unavailable; regenerating from official NBP.' >&2
  fi
fi
if [[ ! -s "$NBP" ]]; then
  python3 -m scripts.nbp_long_history_monthly \
    --start-month 2021-11 --end-month 2026-10 \
    --out "$NBP"
fi

echo 'Original XLSX remains local, no GitHub/Neon upload.' >&2
if [[ "$FETCH" == "yes" ]]; then
  python3 -m scripts.vanguard_nav_intake_bundle_v04 \
    --xlsx "$INPUT" --nbp-archive "$NBP" \
    --first-month 2021-11 --last-month 2026-10 \
    --out "$OUTPUT/vanguard-nav-pln-candidate.json" \
    --fetch-exact-nbp
else
  python3 -m scripts.vanguard_nav_intake_bundle_v04 \
    --xlsx "$INPUT" --nbp-archive "$NBP" \
    --first-month 2021-11 --last-month 2026-10 \
    --out "$OUTPUT/vanguard-nav-pln-candidate.json"
fi
echo
echo "LOCAL_RESEARCH_RECEIPT=$OUTPUT/vanguard-nav-pln-candidate.json"
echo 'Research candidate only: no real returns certified, no trades, no financial operations.'
