#!/usr/bin/env python3
"""Scan a list of bank.in subdomains and write status CSV.

Reuses the same probe functions as the audit_financial_tlds script.
Designed for incremental scanning: appends only rows for the supplied
subdomain list (won't touch the original bank_domains_status.csv).
"""
import argparse
import asyncio
import csv
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

import dns.asyncresolver
import dns.exception
import dns.resolver

RESOLVER = dns.asyncresolver.Resolver()
RESOLVER.nameservers = ["1.1.1.1", "8.8.8.8"]
RESOLVER.timeout = 3.0
RESOLVER.lifetime = 4.0


async def check_dns(domain: str) -> Optional[str]:
    try:
        ans = await RESOLVER.resolve(domain, "A")
        for r in ans.rrset:
            return r.to_text()
    except (dns.exception.DNSException, Exception):
        return None
    return None


def check_http(domain: str) -> tuple[bool, bool, int, str, str, str]:
    https_works = http_works = False
    status_code = 0
    title = ""
    final_url = ""
    error = ""
    ctx = None
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    except Exception:
        pass
    try:
        req = urllib.request.Request(
            f"https://{domain}/", headers={"User-Agent": "Mozilla/5.0 bank-in-scan/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
            https_works = True
            status_code = r.status
            final_url = r.geturl()
            body = r.read(40000)
            try:
                body_text = body.decode("utf-8", errors="ignore")
            except Exception:
                body_text = ""
            import re
            m = re.search(r"<title[^>]*>(.*?)</title>", body_text, re.IGNORECASE | re.DOTALL)
            if m:
                title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
    except urllib.error.HTTPError as e:
        https_works = True
        status_code = e.code
        try:
            final_url = e.geturl() if hasattr(e, "geturl") else ""
        except Exception:
            pass
    except Exception as e:
        error = f"{type(e).__name__}: {str(e)[:200]}"
    return https_works, http_works, status_code, title, final_url, error


async def probe(domain: str, sem: asyncio.Semaphore) -> dict:
    async with sem:
        ip = await check_dns(domain)
        if not ip:
            return {
                "domain": domain, "dns_resolves": "False", "ip_address": "",
                "https_works": "False", "http_works": "False", "status_code": "",
                "title": "", "final_url": "", "error": "",
            }
        https_works, http_works, status_code, title, final_url, error = check_http(domain)
        return {
            "domain": domain, "dns_resolves": "True", "ip_address": ip,
            "https_works": str(https_works), "http_works": str(http_works),
            "status_code": status_code, "title": title, "final_url": final_url,
            "error": error,
        }


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-list", required=True, help="File with one subdomain per line")
    ap.add_argument("--out-csv", required=True)
    ap.add_argument("--concurrency", type=int, default=40)
    ap.add_argument("--max", type=int, default=0, help="Cap rows for testing")
    args = ap.parse_args()

    domains = [l.strip().lower() for l in Path(args.in_list).read_text().splitlines() if l.strip()]
    if args.max:
        domains = domains[: args.max]
    print(f"Probing {len(domains)} subdomains...", flush=True)

    sem = asyncio.Semaphore(args.concurrency)
    tasks = [probe(d, sem) for d in domains]

    results = []
    done = 0
    for fut in asyncio.as_completed(tasks):
        r = await fut
        results.append(r)
        done += 1
        if done % 100 == 0 or done == len(tasks):
            live = sum(1 for r2 in results if r2["dns_resolves"] == "True")
            print(f"  {done}/{len(tasks)}  live: {live}", flush=True)

    rows = sorted(results, key=lambda x: x["domain"])
    with open(args.out_csv, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["domain", "dns_resolves", "ip_address", "https_works",
                        "http_works", "status_code", "title", "final_url", "error"],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.out_csv}")


if __name__ == "__main__":
    asyncio.run(main())
