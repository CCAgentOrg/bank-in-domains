#!/usr/bin/env bash
# Zo-based refresh pipeline for bank-in-domains audit.
# Runs all discovery sources → probe → merge → push.
# Designed for Zo's no-timeout environment.
# Writes status markers to /tmp/ so agents can monitor progress.
set -uo pipefail

REPO_DIR="/home/workspace/Projects/bank-in-domains"
GIT_REMOTE="https://oauth2:${CC_ORG_GH_TOKEN}@github.com/CCAgentOrg/bank-in-domains.git"
MARKER_DIR="/tmp/bank-in-refresh"

mkdir -p "$MARKER_DIR"
rm -f "$MARKER_DIR"/*.done "$MARKER_DIR"/*.fail

log() { echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $*"; }
step_done() { touch "$MARKER_DIR/$1.done"; log "STEP DONE: $1"; }
step_fail() { touch "$MARKER_DIR/$1.fail"; log "STEP FAILED: $1"; }

cd "$REPO_DIR" || { step_fail "cd"; exit 1; }

# --- 0. Pull latest ---
log "Pulling latest from remote"
git remote set-url origin "$GIT_REMOTE"
git fetch origin main
git reset --hard origin/main || { step_fail "pull"; exit 1; }
step_done "pull"

mkdir -p out
cp data/bank_domains_status.csv out/bank_domains_status.csv 2>/dev/null || touch out/bank_domains_status.csv

# --- 1. Wayback CDX (incremental) ---
log "=== Wayback (incremental: last 7d) ==="
FROM_DATE=$(date -u -d '7 days ago' +%Y%m%d%H%M%S)
curl -sS --max-time 120 \
  "http://web.archive.org/cdx/search/cdx?url=bank.in&matchType=domain&collapse=urlkey&limit=50000&output=json&fl=original&from=${FROM_DATE}" \
  | python3 -c "
import json, sys, re
try:
    data = json.load(sys.stdin)
    for row in data[1:]:
        host = row[0].split('/')[2] if '://' in row[0] else row[0].split('/')[0]
        host = host.split(':')[0]
        if host.endswith('.bank.in'):
            print(host.lower())
except Exception as e:
    print(f'Wayback failed: {e}', file=sys.stderr)
" | sort -u > out/wayback.txt || touch out/wayback.txt
log "Wayback: $(wc -l < out/wayback.txt) hosts"
step_done "wayback"

# --- 2. urlscan.io ---
log "=== urlscan ==="
curl -sS --max-time 30 \
  "https://urlscan.io/api/v1/search/?q=domain%3Abank.in" \
  | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for r in d.get('results', []):
        dom = r.get('page', {}).get('domain', '')
        if dom.endswith('.bank.in'):
            print(dom.lower())
except Exception as e:
    print(f'urlscan failed: {e}', file=sys.stderr)
" | sort -u > out/urlscan.txt || touch out/urlscan.txt
log "urlscan: $(wc -l < out/urlscan.txt) hosts"
step_done "urlscan"

# --- 3. HackerTarget ---
log "=== HackerTarget ==="
curl -sS --max-time 60 \
  "https://api.hackertarget.com/hostsearch/?q=bank.in" \
  | awk -F, 'NF>=1 {print $1}' | sort -u > out/hackertarget.txt \
  || touch out/hackertarget.txt
log "HackerTarget: $(wc -l < out/hackertarget.txt) hosts"
step_done "hackertarget"

# --- 4. crt.sh CT Logs ---
log "=== crt.sh CT Logs ==="
python3 scripts/fetch_ct_subdomains.py || log "WARNING: CT fetch failed"
if [ -f data/ct_new_subdomains.csv ] && [ -s data/ct_new_subdomains.csv ]; then
  python3 scripts/merge_ct_results.py --extract-domains \
    --ct-csv data/ct_new_subdomains.csv | sort -u > out/ct.txt
  log "CT: $(wc -l < out/ct.txt) hosts"
else
  touch out/ct.txt
fi
step_done "ct"

# --- 5. subfinder ---
log "=== subfinder ==="
subfinder -d bank.in -all -silent -o out/subfinder.txt 2>/dev/null || touch out/subfinder.txt
log "subfinder: $(wc -l < out/subfinder.txt) hosts"
step_done "subfinder"

# --- 6. Merge all sources ---
log "=== Merge discovered ==="
cat out/wayback.txt out/urlscan.txt out/hackertarget.txt out/ct.txt out/subfinder.txt \
  | sort -u > out/discovered.txt
LOG_TOTAL=$(wc -l < out/discovered.txt)
log "Total discovered: $LOG_TOTAL"
step_done "merge"

# --- 7. Build new subdomain list ---
log "=== Build new subdomains ==="
python3 scripts/build_new_subdomains.py \
  --existing out/bank_domains_status.csv \
  --discovered out/discovered.txt > out/new_subdomains.txt
LOG_NEW=$(wc -l < out/new_subdomains.txt)
log "New: $LOG_NEW subdomains"
step_done "build_new"

# --- 8. Check if anything to do ---
HAS_NEW=false
[ -s out/new_subdomains.txt ] && HAS_NEW=true
[ -f data/ct_new_subdomains.csv ] && [ -s data/ct_new_subdomains.csv ] && HAS_NEW=true

if [ "$HAS_NEW" = "false" ]; then
  log "Nothing new — skipping probe, merge, and commit"
  echo "Nothing new" > "$MARKER_DIR/result.txt"
  step_done "complete"
  exit 0
fi

# --- 9. Probe new subdomains ---
log "=== Probe new subdomains ==="
if [ -s out/new_subdomains.txt ]; then
  python3 scripts/scan_subdomains.py \
    --in-list out/new_subdomains.txt \
    --out-csv out/bank_domains_new_probed.csv \
    --concurrency 200
else
  : > out/bank_domains_new_probed.csv
fi
step_done "probe_new"

# --- 10. Probe CT subdomains ---
log "=== Probe CT subdomains ==="
if [ -f data/ct_new_subdomains.csv ] && [ -s data/ct_new_subdomains.csv ]; then
  python3 scripts/merge_ct_results.py --extract-domains \
    --ct-csv data/ct_new_subdomains.csv > out/ct_domains_to_probe.txt
  python3 scripts/scan_subdomains.py \
    --in-list out/ct_domains_to_probe.txt \
    --out-csv out/ct_probed.csv \
    --concurrency 200
  python3 scripts/merge_ct_results.py \
    --ct-csv data/ct_new_subdomains.csv \
    --probe-csv out/ct_probed.csv \
    --out-csv out/bank_domains_ct_expansion.csv
else
  : > out/bank_domains_ct_expansion.csv
fi
step_done "probe_ct"

# --- 11. Merge master CSV ---
log "=== Merge master CSV ==="
python3 scripts/merge_master_csv.py || log "WARNING: merge failed"
step_done "merge_master"

# --- 12. Update discovered list ---
cat out/discovered.txt | sort -u > data/new_subdomains.txt
log "Updated data/new_subdomains.txt with $(wc -l < data/new_subdomains.txt) entries"
step_done "update_list"

# --- 13. Commit and push ---
log "=== Commit and push ==="
git config user.name "Zo bot"
git config user.email "cashlessconsumer@zo.computer"
if git diff --quiet data/; then
  log "No data changes to commit"
  echo "No changes" > "$MARKER_DIR/result.txt"
else
  git add data/
  git commit -m "chore: refresh bank.in audit ($(date -u +%F))"
  git push origin main 2>&1 || log "WARNING: push failed"
  log "Pushed to GitHub"
  echo "Pushed changes" > "$MARKER_DIR/result.txt"
fi

step_done "push"
step_done "complete"
log "=== Done ==="
echo "Complete" >> "$MARKER_DIR/result.txt"