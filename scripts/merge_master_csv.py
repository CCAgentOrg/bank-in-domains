#!/usr/bin/env python3
"""Merge new probe results into the master bank_domains_status.csv.

Usage:
    # From refresh workflow (may have both sources + CT expansion)
    python3 scripts/merge_master_csv.py

    # From ct-refresh workflow (only CT expansion)
    python3 scripts/merge_master_csv.py --ct-only
"""
import argparse
import csv
import os
import sys
from pathlib import Path

DATA_DIR = Path("data")
OUT_DIR = Path("out")
MASTER_CSV = DATA_DIR / "bank_domains_status.csv"


def load_master(path: Path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    return rows, fieldnames


def load_csv(path: Path):
    if not path.exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def dedupe_merge(existing: list, new_rows: list, fieldnames: list) -> list:
    seen = {r["domain"] for r in existing}
    for r in new_rows:
        if r["domain"] not in seen:
            existing.append(r)
            seen.add(r["domain"])
    existing.sort(key=lambda r: r["domain"])
    return existing


def write_master(rows: list, fieldnames: list, path: Path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge new probe results into master bank_domains_status.csv"
    )
    parser.add_argument("--ct-only", action="store_true",
                        help="Only merge CT expansion (skip new_probed)")
    args = parser.parse_args()

    if not MASTER_CSV.exists():
        print(f"Master CSV not found: {MASTER_CSV}", file=sys.stderr)
        return 1

    existing, fieldnames = load_master(MASTER_CSV)

    new_rows = []

    if not args.ct_only:
        new_probed = load_csv(OUT_DIR / "bank_domains_new_probed.csv")
        new_rows.extend(new_probed)
        print(f"New probed (Wayback/urlscan/HT): {len(new_probed)}", file=sys.stderr)

    ct_expansion = load_csv(OUT_DIR / "bank_domains_ct_expansion.csv")
    new_rows.extend(ct_expansion)
    print(f"CT expansion: {len(ct_expansion)}", file=sys.stderr)

    merged = dedupe_merge(existing, new_rows, fieldnames)
    write_master(merged, fieldnames, MASTER_CSV)

    live = sum(1 for r in merged if r.get("dns_resolves") == "True")
    ok = sum(1 for r in merged if r.get("status_code") == "200")
    print(f"Merged: {len(merged)} total, {live} live, {ok} HTTP 200")
    return 0


if __name__ == "__main__":
    sys.exit(main())
