#!/usr/bin/env python3
"""Fetch .bank.in subdomains from crt.sh Certificate Transparency logs.

Features:
- Dual search types: Identity (CN+SAN) + dNSName (SAN-only)
- Expiry filtering (excludeExpired=on)
- Pre-cert/leaf deduplication (deduplicate=on)
- Retry with exponential backoff
- Per-bank deep queries for top institutions
- Persistent seen_certs.json for cross-run deduplication
- Enriched output with full cert metadata
"""
import asyncio
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
DATA_DIR = HERE.parent / "data"
SEEN_DB = DATA_DIR / "ct_seen.json"
INSTITUTIONS_FILE = HERE / "institutions.txt"

# crt.sh base URL with recommended flags
CRTSH_BASE = "https://crt.sh/?q={}&output=json&excludeExpired=on&deduplicate=on"

def build_url(query: str, search_type_param: str = "") -> str:
    """Build properly encoded crt.sh URL."""
    encoded_query = urllib.parse.quote(query)
    return CRTSH_BASE.format(encoded_query) + search_type_param

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


async def main() -> int:
    print("=== crt.sh CT Log Discovery for .bank.in ===")
    seen = load_seen()
    print(f"Loaded {len(seen)} previously seen certificates")

    all_new = []
    all_new.extend(await fetch_global_wildcard(seen))
    all_new.extend(await fetch_per_bank(seen))

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
        # Create empty file for workflow
        (DATA_DIR / "ct_new_subdomains.csv").write_text("")

    save_seen(seen)
    print(f"Saved {len(seen)} total seen certificates to {SEEN_DB}")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)