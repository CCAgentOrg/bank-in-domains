#!/usr/bin/env python3
"""Scan the global `.bank` gTLD for Indian bank deployments."""
import asyncio
import csv
import sys
from pathlib import Path

from audit_financial_tlds import check_dns, check_http

CURATED_BANKS = [
    "sbi", "hdfc", "icici", "axis", "kotak", "bob", "boi", "pnb", "canara",
    "union", "indian", "iob", "uco", "central", "bom", "indusind", "yes",
    "federal", "kvb", "tmb", "cub", "dbs", "dhan", "sbm", "karnataka",
    "karur", "csb", "idfc", "idbi", "rbl", "bandhan", "au", "ujjivan",
    "equitas", "esaf", "suryoday", "utkarsh", "jana", "fino", "paytm",
    "airtel", "jio", "india1", "indus", "india",
    "sbilife", "hdfclife", "icicipru", "maxlife", "kotaklife", "bajajlife",
    "birla", "tataaia", "nippon", "indiafirst", "starhealth",
    "sc", "bnpparibas", "deutsche", "jpmorgan", "mashreq", "qnb", "citi",
    "citibank", "hsbc", "barclays", "amex", "american", "discover",
    "standard", "chartered", "rabobank", "mizuho", "mufg", "smbc", "smfg",
]


def load_prefixes() -> list[str]:
    """Combine existing bank.in prefixes with the curated list."""
    seen = set()
    bank_csv = Path("/home/workspace/bank-in-research/bank_domains_status.csv")
    if bank_csv.exists():
        with bank_csv.open() as f:
            for row in csv.DictReader(f):
                d = row["domain"]
                if d.endswith(".bank.in"):
                    seen.add(d[: -len(".bank.in")])
    for p in CURATED_BANKS:
        seen.add(p)
    return sorted(seen)


async def main() -> None:
    prefixes = load_prefixes()
    print(f"Probing {len(prefixes)} prefixes under .bank")
    rows = [["domain", "dns_resolves", "ip_address", "https_works", "http_works",
             "status_code", "title", "final_url", "error"]]
    live = 0
    for i, p in enumerate(prefixes, 1):
        domain = f"{p}.bank"
        ip = await check_dns(domain)
        if ip:
            live += 1
            https_ok, http_ok, code, title, final, err = check_http(domain)
            rows.append([domain, "True", ip, str(https_ok), str(http_ok),
                         str(code) if code else "", title, final, err])
        else:
            rows.append([domain, "False", "", "False", "False", "", "", "",
                         "DNS NXDOMAIN"])
        if i % 25 == 0 or i == len(prefixes):
            print(f"  .bank: {i}/{len(prefixes)}  (live: {live})")

    out = Path("/home/workspace/bank-in-research/bank_tld_domains_status.csv")
    with out.open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    print(f"  .bank: probed {len(rows) - 1}, resolves: {live}, -> {out}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)
