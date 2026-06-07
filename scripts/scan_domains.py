#!/usr/bin/env python3
"""Scan financial domain namespaces in India.

Expands the .bank.in scan to .fin.in and .insurance.in for the same prefixes,
plus a curated list of additional financial-domain prefixes.
"""
import asyncio
import csv
import socket
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

USER_AGENT = "Mozilla/5.0 (compatible; CashlessConsumer-DomainAudit/1.0)"
TIMEOUT_DNS = 3
TIMEOUT_HTTP = 6


def dns_resolves(domain: str) -> Tuple[bool, str]:
    try:
        info = socket.getaddrinfo(domain, 443, type=socket.SOCK_STREAM)
        ip = info[0][4][0]
        return True, ip
    except (socket.gaierror, OSError, UnicodeError):
        return False, ""


def http_get(domain: str, scheme: str) -> Tuple[bool, int, str, str, str, str]:
    """Returns (ok, status_code, title, final_url, error, https_or_http_works)."""
    url = f"{scheme}://{domain}/"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT_HTTP, context=ctx)
        body = resp.read(65536)
        try:
            text = body.decode("utf-8", errors="replace")
        except Exception:
            text = ""
        title = ""
        if text:
            import re
            m = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
            if m:
                title = m.group(1).strip()[:200]
        return True, resp.status, title, resp.geturl(), "", "True"
    except urllib.error.HTTPError as e:
        return False, e.code, "", url, f"HTTP {e.code}", "False"
    except urllib.error.URLError as e:
        return False, 0, "", url, str(e.reason)[:200], "False"
    except (socket.timeout, TimeoutError, OSError, ssl.SSLError) as e:
        return False, 0, "", url, str(e)[:200], "False"
    except Exception as e:
        return False, 0, "", url, str(e)[:200], "False"


def check_domain(domain: str) -> dict:
    resolves, ip = dns_resolves(domain)
    https_works, sc, title, final_url, err, https_flag = http_get(domain, "https")
    http_works, sc2, title2, final_url2, err2, http_flag = http_get(domain, "http")
    if not https_works and not http_works:
        # keep the first error and status
        if not resolves:
            return {
                "domain": domain, "dns_resolves": "False", "ip_address": "",
                "https_works": "False", "http_works": "False",
                "status_code": "", "title": "", "final_url": "", "error": err or err2,
            }
        return {
            "domain": domain, "dns_resolves": "True", "ip_address": ip,
            "https_works": "False", "http_works": "False",
            "status_code": sc or sc2 or "", "title": "",
            "final_url": final_url or final_url2 or "", "error": err or err2,
        }
    # If https works, use that; else use http
    if https_works:
        return {
            "domain": domain, "dns_resolves": "True", "ip_address": ip,
            "https_works": "True", "http_works": http_flag,
            "status_code": sc, "title": title, "final_url": final_url, "error": "",
        }
    return {
        "domain": domain, "dns_resolves": "True", "ip_address": ip,
        "https_works": "False", "http_works": "True",
        "status_code": sc2, "title": title2, "final_url": final_url2, "error": err2,
    }


async def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--in-csv", required=True)
    p.add_argument("--root", required=True, help="Target root TLD, e.g. fin.in or insurance.in")
    p.add_argument("--out-csv", required=True)
    p.add_argument("--extra-prefixes", default="", help="Comma-separated extra prefixes to probe")
    p.add_argument("--concurrency", type=int, default=20)
    args = p.parse_args()

    # Read prefixes from existing bank.in CSV (always strip .bank.in)
    prefixes = set()
    with open(args.in_csv, newline="") as f:
        for row in csv.DictReader(f):
            d = row["domain"]
            if d.endswith(".bank.in"):
                prefixes.add(d[: -len(".bank.in")])
    if args.extra_prefixes:
        for x in args.extra_prefixes.split(","):
            x = x.strip().lower()
            if x:
                prefixes.add(x)

    # Also include a small curated set of large financial players that might
    # exist on .fin.in but not under .bank.in (e.g. NBFCs, fintech, AMCs).
    curated = {
        # Payments / Fintech
        "paytm", "phonepe", "gpay", "googlepay", "mobikwik", "freecharge",
        "cred", "razorpay", "cashfree", "juspay", "payu", "billdesk",
        "ccavenue", "instamojo", "zaakpay", "easebuzz", "pinelabs", "mswipe",
        # NBFCs
        "bajaj", "bajajfinserv", "muthoot", "manappuram", "cholamandalam",
        "shriram", "shriramfinance", "mahindrafinance", "tvscredit", "hdfccredit",
        "icicisecurities", "motilal", "motilaloswal", "iifl", "kotaksecurities",
        "sharekhan", "angelone", "angel", "zerodha", "upstox", "groww",
        "paytmmoney", "smallcase", "kuvera", "kuvera",
        # AMCs / Insurance
        "hdfclife", "icicilombard", "icicipru", "iciciprudential", "sbilife",
        "maxlife", "bajajallianz", "tataaig", "tataamc", "nippon", "reliancegeneral",
        "reliancelife", "starhealth", "manipalcigna", "digit", "acko", "carehealth",
        "newindia", "oriental", "national", "unitedindia",
        # Major exchanges / utilities
        "nse", "bse", "mcx", "cdsl", "nsdl", "karvy", "cams", "kfintech",
        "kfin", "mufg", "mufgin", "hsbc", "citibank", "citi", "amex",
        "amexbank", "barclays", "standardchartered", "deutschebank",
        "jpmorgan", "goldmansachs", "morganstanley",
    }
    prefixes |= curated

    prefixes = sorted(prefixes)
    domains = [f"{p}.{args.root}" for p in prefixes]
    print(f"Probing {len(domains)} domains under .{args.root}", file=sys.stderr)

    sem = asyncio.Semaphore(args.concurrency)
    loop = asyncio.get_event_loop()

    def run_one(d):
        return loop.run_in_executor(None, check_domain, d)

    async def throttled(d):
        async with sem:
            return await run_one(d)

    results = await asyncio.gather(*[throttled(d) for d in domains])

    cols = ["domain", "dns_resolves", "ip_address", "https_works", "http_works",
            "status_code", "title", "final_url", "error"]
    with open(args.out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in sorted(results, key=lambda x: x["domain"]):
            w.writerow(r)
    print(f"Wrote {len(results)} rows to {args.out_csv}", file=sys.stderr)

    # quick summary
    resolves = sum(1 for r in results if r["dns_resolves"] == "True")
    live = sum(1 for r in results if r["https_works"] == "True" or r["http_works"] == "True")
    print(f"  resolves: {resolves}/{len(results)}  live: {live}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
