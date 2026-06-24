#!/usr/bin/env python3
"""Fetch .bank.in subdomains from crt.sh Certificate Transparency logs.

Features:
- Dual search types: Identity (CN+SAN) + dNSName (SAN-only)
- Expiry filtering (excludeExpired=on) with option to include expired
- Pre-cert/leaf deduplication (deduplicate=on)
- Retry with exponential backoff
- Per-bank deep queries for top institutions
- Organization (O) search for major banks
- CA-specific queries for major issuers
- Persistent seen_certs.json for cross-run deduplication
- Enriched output with full cert metadata
- Separate tracking of expired certificates for historical analysis
"""
import argparse
import asyncio
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
SEEN_DB = DATA_DIR / "ct_seen.json"
EXPIRED_DB = DATA_DIR / "ct_expired.json"
INSTITUTIONS_FILE = HERE / "institutions.txt"

# crt.sh base URL with recommended flags
CRTSH_BASE = "https://crt.sh/?q={}&output=json"

# Dual search types for maximum coverage
SEARCH_TYPES = [
    ("Identity", ""),      # Default: CN + SAN
    ("dNSName", "&searchtype=dNSName"),  # SAN-only
]

# Per-bank deep enumeration (top 20 by subdomain count)
TOP_INSTITUTIONS = [
    "axis", "sbi", "hdfc", "icici", "kotak", "bob", "boi", "pnb",
    "canara", "union", "indian", "iob", "uco", "central", "bom",
    "indusind", "yes", "federal", "kvb", "tmb",
]

# Major Indian banks for Organization search
ORG_SEARCH_TERMS = [
    "Axis Bank",
    "State Bank of India",
    "HDFC Bank",
    "ICICI Bank",
    "Kotak Mahindra Bank",
    "Bank of Baroda",
    "Bank of India",
    "Punjab National Bank",
    "Canara Bank",
    "Union Bank of India",
    "Indian Bank",
    "Indian Overseas Bank",
    "UCO Bank",
    "Central Bank of India",
    "Bank of Maharashtra",
    "IndusInd Bank",
    "YES Bank",
    "Federal Bank",
    "Karur Vysya Bank",
    "Tamilnad Mercantile Bank",
    "IDFC FIRST Bank",
    "RBL Bank",
    "South Indian Bank",
    "Ujjivan Small Finance Bank",
    "Equitas Small Finance Bank",
    "ESAF Small Finance Bank",
    "Fino Payments Bank",
    "Paytm Payments Bank",
]

# Major CAs for .bank.in (from existing data)
MAJOR_CA_IDS = [
    "295809",  # Let's Encrypt E8
    "295813",  # Let's Encrypt E7
    "295814",  # Let's Encrypt R10
    "295817",  # Let's Encrypt R13
    "295819",  # Let's Encrypt E6
    "286236",  # Google Trust Services WE1
    "286242",  # Google Trust Services WR1
    "185752",  # DigiCert Global G2
    "176209",  # GeoTrust EV RSA CA G2
    "62123",   # GeoTrust TLS RSA CA G1
    "365075",  # Entrust OV TLS Issuing RSA CA 1
    "385515",  # Entrust DV TLS Issuing ECC CA 2
    "422998",  # GlobalSign Atlas R3 DV TLS CA 2025 Q4
]

# URL builder with all flags
def build_url(query: str, search_type_param: str = "", exclude_expired: bool = True, deduplicate: bool = True) -> str:
    """Build properly encoded crt.sh URL with optional flags."""
    encoded_query = urllib.parse.quote(query)
    url = CRTSH_BASE.format(encoded_query) + search_type_param
    if exclude_expired:
        url += "&excludeExpired=on"
    if deduplicate:
        url += "&deduplicate=on"
    return url


def load_seen() -> set:
    """Load persistent seen database."""
    if SEEN_DB.exists():
        try:
            return set(json.loads(SEEN_DB.read_text()))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def save_seen(seen: set) -> None:
    """Save persistent seen database."""
    DATA_DIR.mkdir(exist_ok=True)
    SEEN_DB.write_text(json.dumps(sorted(seen)))


def load_expired() -> set:
    """Load persistent expired certificates database."""
    if EXPIRED_DB.exists():
        try:
            return set(json.loads(EXPIRED_DB.read_text()))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def save_expired(expired: set) -> None:
    """Save persistent expired certificates database."""
    DATA_DIR.mkdir(exist_ok=True)
    EXPIRED_DB.write_text(json.dumps(sorted(expired)))


def fetch_with_retry(url: str, max_retries: int = 3, base_delay: float = 10.0) -> list:
    """Fetch JSON from crt.sh with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "bank-in-domains/1.0 (+https://github.com/CCAgentOrg/bank-in-domains)"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    return data
                return []
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            if attempt == max_retries - 1:
                print(f"  Failed after {max_retries} retries: {e}")
                return []
            delay = base_delay * (2 ** attempt)
            print(f"  Attempt {attempt + 1} failed: {e}. Retrying in {delay:.0f}s...")
            time.sleep(delay)
    return []


def extract_subdomains(ct_data: list, search_type: str) -> list:
    """Extract enriched subdomain records from crt.sh JSON."""
    subs = []
    for row in ct_data:
        name_value = row.get("name_value", "")
        for name in name_value.split("\n"):
            name = name.strip().lower().lstrip("*.")
            if name.endswith(".bank.in"):
                subs.append({
                    "domain": name,
                    "ct_search_type": search_type,
                    "ct_issuer_ca_id": row.get("issuer_ca_id"),
                    "ct_issuer_name": row.get("issuer_name"),
                    "ct_not_before": row.get("not_before"),
                    "ct_not_after": row.get("not_after"),
                    "ct_serial_number": row.get("serial_number"),
                    "ct_entry_timestamp": row.get("entry_timestamp"),
                    "ct_id": row.get("id"),
                })
    return subs


async def fetch_global_wildcard(seen: set) -> list:
    """Fetch global %.bank.in with dual search types."""
    all_new = []
    for search_type, param in SEARCH_TYPES:
        url = build_url("%.bank.in", param)
        print(f"Fetching global %.bank.in [{search_type}]...")
        data = fetch_with_retry(url)
        for sub in extract_subdomains(data, search_type):
            key = f"{sub['domain']}|{sub['ct_id']}"
            if key not in seen:
                seen.add(key)
                all_new.append(sub)
        await asyncio.sleep(1)  # be nice to crt.sh
    return all_new


async def fetch_per_bank(seen: set) -> list:
    """Fetch per-bank deep queries for top institutions."""
    all_new = []
    for inst in TOP_INSTITUTIONS:
        query = f"%.{inst}.bank.in"
        url = build_url(query)
        print(f"Fetching {query}...")
        try:
            data = fetch_with_retry(url)
            for sub in extract_subdomains(data, "Identity"):
                key = f"{sub['domain']}|{sub['ct_id']}"
                if key not in seen:
                    seen.add(key)
                    all_new.append(sub)
        except Exception as e:
            print(f"  {inst}: {e}")
        await asyncio.sleep(1)  # rate limit courtesy
    return all_new


async def fetch_org_search(seen: set) -> list:
    """Fetch certificates by Organization (O) field for major banks."""
    all_new = []
    for org in ORG_SEARCH_TERMS:
        query = org
        url = build_url(query, "&searchtype=O")
        print(f"Fetching Organization: {org}...")
        try:
            data = fetch_with_retry(url)
            for sub in extract_subdomains(data, "Organization"):
                key = f"{sub['domain']}|{sub['ct_id']}"
                if key not in seen:
                    seen.add(key)
                    all_new.append(sub)
        except Exception as e:
            print(f"  {org}: {e}")
        await asyncio.sleep(2)  # rate limit - org searches are heavier
    return all_new


async def fetch_ca_search(seen: set) -> list:
    """Fetch certificates by CA ID for major issuers."""
    all_new = []
    for ca_id in MAJOR_CA_IDS:
        query = ca_id
        url = build_url(query, "&searchtype=CAID")
        print(f"Fetching CA ID: {ca_id}...")
        try:
            data = fetch_with_retry(url)
            for sub in extract_subdomains(data, "CAID"):
                key = f"{sub['domain']}|{sub['ct_id']}"
                if key not in seen:
                    seen.add(key)
                    all_new.append(sub)
        except Exception as e:
            print(f"  CA {ca_id}: {e}")
        await asyncio.sleep(1)
    return all_new


async def fetch_expired_certs(seen: set, expired_seen: set) -> list:
    """Fetch expired certificates for historical tracking (without excludeExpired)."""
    all_expired = []
    for search_type, param in SEARCH_TYPES:
        url = build_url("%.bank.in", param, exclude_expired=False)
        print(f"Fetching EXPIRED %.bank.in [{search_type}]...")
        data = fetch_with_retry(url)
        for sub in extract_subdomains(data, search_type + "-expired"):
            key = f"{sub['domain']}|{sub['ct_id']}"
            if key not in expired_seen:
                expired_seen.add(key)
                all_expired.append(sub)
        await asyncio.sleep(1)
    return all_expired


async def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch .bank.in subdomains from crt.sh CT logs")
    parser.add_argument("--include-expired", action="store_true",
                        help="Also fetch expired certificates (separate output)")
    parser.add_argument("--org-search", action="store_true",
                        help="Include Organization (O) field search for major banks")
    parser.add_argument("--ca-search", action="store_true",
                        help="Include CA-specific search for major issuers")
    parser.add_argument("--mode", choices=["default", "full", "expired-only"],
                        default="default", help="Preset mode: default, full (all searches), expired-only")
    args = parser.parse_args()

    # Mode presets
    if args.mode == "full":
        args.org_search = True
        args.ca_search = True
        args.include_expired = True
    elif args.mode == "expired-only":
        args.include_expired = True
        args.org_search = False
        args.ca_search = False

    print("=== crt.sh CT Log Discovery for .bank.in ===")
    seen = load_seen()
    print(f"Loaded {len(seen)} previously seen certificates")

    all_new = []
    all_new.extend(await fetch_global_wildcard(seen))
    all_new.extend(await fetch_per_bank(seen))

    if args.org_search:
        all_new.extend(await fetch_org_search(seen))

    if args.ca_search:
        all_new.extend(await fetch_ca_search(seen))

    # Handle expired certificates
    if args.include_expired:
        expired_seen = load_expired()
        print(f"Loaded {len(expired_seen)} previously seen expired certificates")
        all_expired = await fetch_expired_certs(seen, expired_seen)
        if all_expired:
            out_file = DATA_DIR / "ct_expired_subdomains.csv"
            fieldnames = list(all_expired[0].keys())
            with open(out_file, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(all_expired)
            print(f"\nFound {len(all_expired)} expired subdomains -> {out_file}")
        else:
            print("\nNo new expired subdomains found")
            (DATA_DIR / "ct_expired_subdomains.csv").write_text("")
        save_expired(expired_seen)
        print(f"Saved {len(expired_seen)} total expired certificates to {EXPIRED_DB}")

    if all_new:
        out_file = DATA_DIR / "ct_new_subdomains.csv"
        fieldnames = list(all_new[0].keys())
        with open(out_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_new)
        print(f"\nFound {len(all_new)} new subdomains -> {out_file}")
    else:
        print("\nNo new subdomains found")
        (DATA_DIR / "ct_new_subdomains.csv").write_text("")

    save_seen(seen)
    print(f"Saved {len(seen)} total seen certificates to {SEEN_DB}")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)