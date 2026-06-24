#!/usr/bin/env python3
"""Audit: probe parallel Indian financial TLDs for active subdomain registration.

Compares:
  - .bank.in (baseline — 223+ subs)
  - .fin.in
  - .insurance.in
  - .nbfc.in
  - .npci.in

Uses the 222 prefixes extracted from the existing bank.in scan
plus a curated list of real Indian financial institutions.
"""
import asyncio
import csv
import socket
import ssl
import sys
import urllib.error
import urllib.request
from typing import Optional, Tuple
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (compatible; CashlessConsumer-Audit/1.0)"
TIMEOUT = 8

# TLDs to scan
TLDS = ["fin.in", "insurance.in", "nbfc.in", "npci.in"]

# Curated financial institution prefixes (banks, NBFCs, fintech, insurers, regulators, infra)
CURATED = Path(__file__).parent / "institutions.txt"
BANK_IN_CSV = Path(__file__).parent.parent / "data" / "bank_domains_status.csv"


def load_prefixes() -> list[str]:
    prefixes: set[str] = set()
    # 1. From existing bank.in scan
    with open(BANK_IN_CSV, newline="") as f:
        for row in csv.DictReader(f):
            d = row["domain"].strip().lower()
            if d.endswith(".bank.in"):
                prefixes.add(d[: -len(".bank.in")])
    # 2. From curated list
    for line in CURATED.read_text().splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            prefixes.add(line)
    return sorted(prefixes)


async def check_dns(domain: str) -> Optional[str]:
    loop = asyncio.get_event_loop()
    try:
        infos = await loop.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
        for info in infos:
            return info[4][0]
    except (socket.gaierror, Exception):
        return None
    return None


def check_http(domain: str) -> tuple[bool, bool, int, str, str, str]:
    """Return (https_works, http_works, status, title, final_url, error)."""
    title = ""
    final_url = ""
    status = ""
    err = ""
    https_works = False
    http_works = False

    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/"
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
                if scheme == "https":
                    https_works = True
                else:
                    http_works = True
                status = str(r.status)
                final_url = r.geturl()
                raw = r.read(8000)
                if b"<title" in raw.lower():
                    try:
                        s = raw.decode(r.headers.get_content_charset() or "utf-8", "replace")
                        i = s.lower().find("<title")
                        j = s.find(">", i) + 1
                        k = s.lower().find("</title>", j)
                        if k > j:
                            title = s[j:k].strip()
                    except Exception:
                        pass
            break
        except urllib.error.HTTPError as e:
            if scheme == "https":
                https_works = True
            else:
                http_works = True
            status = str(e.code)
            final_url = e.url or url
            if e.code in (200, 301, 302, 307, 308, 400, 401, 403, 404, 502, 503):
                break
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:200]
            continue

    return https_works, http_works, status, title, final_url, err


async def scan(sem: asyncio.Semaphore, domain: str) -> dict:
    async with sem:
        ip = await check_dns(domain)
        if not ip:
            return {
                "domain": domain, "dns_resolves": False, "ip_address": "",
                "https_works": False, "http_works": False, "status_code": "",
                "title": "", "final_url": "", "error": "",
            }
        https_w, http_w, status, title, final_url, err = check_http(domain)
        return {
            "domain": domain, "dns_resolves": True, "ip_address": ip,
            "https_works": https_w, "http_works": http_w, "status_code": status,
            "title": title[:200], "final_url": final_url, "error": err,
        }


async def main():
    prefixes = load_prefixes()
    print(f"Loaded {len(prefixes)} unique prefixes", file=sys.stderr)

    out_dir = Path("/home/workspace/bank-in-research")
    for tld in TLDS:
        out_path = out_dir / f"{tld.replace('.', '_')}_domains_status.csv"
        domains = [f"{p}.{tld}" for p in prefixes]
        sem = asyncio.Semaphore(30)
        tasks = [scan(sem, d) for d in domains]
        results: list[dict] = []
        for i, fut in enumerate(asyncio.as_completed(tasks), 1):
            r = await fut
            results.append(r)
            if i % 50 == 0:
                print(f"  {tld}: {i}/{len(domains)}", file=sys.stderr)
        results.sort(key=lambda x: x["domain"])
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "domain", "dns_resolves", "ip_address", "https_works",
                "http_works", "status_code", "title", "final_url", "error",
            ])
            w.writeheader()
            w.writerows(results)
        live = sum(1 for r in results if r["dns_resolves"])
        print(f"  {tld}: probed {len(results)}, resolves: {live}, -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
