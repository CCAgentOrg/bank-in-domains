#!/usr/bin/env python3
"""Extract or merge CT-discovered subdomain metadata with probe results.

No leading-whitespace issues — written as a proper script, not inline Python.

Usage:
    # Extract domain list for probing (pipe to file)
    python3 scripts/merge_ct_results.py --extract-domains \
        --ct-csv data/ct_new_subdomains.csv > out/ct_domains_to_probe.txt

    # Merge probe results with CT metadata
    python3 scripts/merge_ct_results.py \
        --ct-csv data/ct_new_subdomains.csv \
        --probe-csv out/ct_probed.csv \
        --out-csv out/bank_domains_ct_expansion.csv
"""
import argparse
import csv
import sys
from pathlib import Path


def extract_domains(ct_csv: Path) -> list[str]:
    with open(ct_csv, newline="") as f:
        reader = csv.DictReader(f)
        domains = sorted(set(row["domain"] for row in reader))
    return domains


def merge_results(ct_csv: Path, probe_csv: Path, out_csv: Path) -> None:
    # Load CT metadata keyed by domain
    ct_meta: dict[str, dict] = {}
    with open(ct_csv, newline="") as f:
        for row in csv.DictReader(f):
            ct_meta[row["domain"]] = row

    # Merge with probe results
    merged: list[dict] = []
    with open(probe_csv, newline="") as f:
        for row in csv.DictReader(f):
            domain = row["domain"]
            if domain in ct_meta:
                for k, v in ct_meta[domain].items():
                    if k not in row:
                        row[k] = v
            merged.append(row)

    if not merged:
        # Write empty file with rich fieldnames
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(out_csv, "w", newline="") as f:
            pass
        print("No merged results to write", file=sys.stderr)
        return

    # Use superset of all fieldnames across merged rows
    fieldnames = list(merged[0].keys())
    for row in merged[1:]:
        for k in row:
            if k not in fieldnames:
                fieldnames.append(k)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(merged)
    print(f"Merged {len(merged)} rows -> {out_csv}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract or merge CT-discovered subdomain metadata with probe results"
    )
    parser.add_argument("--extract-domains", action="store_true",
                        help="Extract domain list for probing (stdout)")
    parser.add_argument("--ct-csv", required=True,
                        help="Path to ct_new_subdomains.csv")
    parser.add_argument("--probe-csv",
                        help="Path to probe results CSV (required for merge)")
    parser.add_argument("--out-csv",
                        help="Path to output merged CSV (required for merge)")
    args = parser.parse_args()

    ct_csv = Path(args.ct_csv)

    if args.extract_domains:
        if not ct_csv.exists():
            print(f"CT CSV not found: {ct_csv}", file=sys.stderr)
            return 1
        for domain in extract_domains(ct_csv):
            print(domain)
        return 0

    if args.probe_csv and args.out_csv:
        probe_csv = Path(args.probe_csv)
        out_csv = Path(args.out_csv)
        if not ct_csv.exists():
            print(f"CT CSV not found: {ct_csv}", file=sys.stderr)
            return 1
        if not probe_csv.exists():
            print(f"Probe CSV not found: {probe_csv}", file=sys.stderr)
            return 1
        merge_results(ct_csv, probe_csv, out_csv)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
