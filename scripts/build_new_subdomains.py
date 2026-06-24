#!/usr/bin/env python3
"""Build new subdomain list by diffing discovered domains against existing CSV.

Usage:
    python3 scripts/build_new_subdomains.py \\
        --existing out/bank_domains_status.csv \\
        --discovered out/discovered.txt > out/new_subdomains.txt
"""
import argparse
import csv
import sys
from pathlib import Path


def load_existing(csv_path: Path) -> set[str]:
    existing = set()
    with open(csv_path, newline="") as f:
        for r in csv.DictReader(f):
            existing.add(r["domain"].strip().lower())
    return existing


def load_discovered(txt_path: Path) -> set[str]:
    discovered = set()
    with open(txt_path) as f:
        for line in f:
            line = line.strip().lower()
            if line and line.endswith(".bank.in"):
                discovered.add(line)
    return discovered


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diff discovered domains against existing probe CSV"
    )
    parser.add_argument("--existing", required=True, help="Existing bank_domains_status.csv")
    parser.add_argument("--discovered", required=True, help="Discovered domains file (one per line)")
    args = parser.parse_args()

    existing_csv = Path(args.existing)
    discovered_txt = Path(args.discovered)

    if not existing_csv.exists():
        print(f"Existing CSV not found: {existing_csv}", file=sys.stderr)
        return 1
    if not discovered_txt.exists():
        print(f"Discovered file not found: {discovered_txt}", file=sys.stderr)
        return 1

    existing = load_existing(existing_csv)
    discovered = load_discovered(discovered_txt)
    new = sorted(discovered - existing)

    for d in new:
        print(d)
    print(f"New: {len(new)} subdomains", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
