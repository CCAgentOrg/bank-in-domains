#!/usr/bin/env python3
"""Build a unified bank.in subdomain list from multiple CT/archival sources.

Sources (in priority order):
  1. Wayback Machine CDX (largest free, no-auth source)
  2. urlscan.io (most recent)
  3. HackerTarget (50 newest DNS-observed)

Deduplicates against the existing bank_domains_status.csv and outputs:
  - new_subdomains.txt  (one per line, sorted)
  - new_subdomains.csv  (with the same schema as bank_domains_status.csv)

Then optionally probes the new ones with the same checks as the
original CSV (DNS / HTTPS / status / title).
"""
import asyncio
import csv
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent

# ---- Step 1: load existing prefixes from the bank.in CSV -----------------
existing = set()
with open(HERE / "bank_domains_status.csv") as f:
    for row in csv.DictReader(f):
        existing.add(row["domain"].strip().lower())

# ---- Step 2: aggregate new subs from CT/archival sources ----------------
new_subs: set[str] = set()

# Wayback (we have /tmp/wayback_hosts.txt)
wb = Path("/tmp/wayback_hosts.txt")
if wb.exists():
    for line in wb.read_text().splitlines():
        line = line.strip().lower()
        if line.endswith(".bank.in") and line not in existing:
            new_subs.add(line)
        # also include apex-prefixes (some Wayback rows are 1-2-3 levels deep)

# urlscan first page
u0 = Path("/tmp/u0.json")
if u0.exists():
    data = json.loads(u0.read_text())
    for r in data.get("results", []):
        d = r.get("page", {}).get("domain", "").lower()
        if d.endswith(".bank.in") and d not in existing:
            new_subs.add(d)

# HackerTarget
ht = Path("/tmp/ht_hosts.txt")
if ht.exists():
    for line in ht.read_text().splitlines():
        line = line.strip().lower()
        if line.endswith(".bank.in") and line not in existing:
            new_subs.add(line)

# Output: simple list
out = HERE / "new_subdomains.txt"
out.write_text("\n".join(sorted(new_subs)) + "\n")
print(f"Total new unique subdomains: {len(new_subs)}")
print(f"Wrote: {out}")
