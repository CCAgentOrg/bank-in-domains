# bank-in-domains

## What This Is

Daily-audited inventory of Indian financial TLD subdomains (`.bank.in`, `.fin.in`, `.insurance.in`, `.nbfc.in`, `.npci.in`, `.bank`). Probes DNS resolution, HTTPS reachability, status codes, and page titles. Published as flat CSVs with scripts for reproducibility.

## Key Files

| File | Role |
|---|---|
| `data/bank_domains_status.csv` | **Master** — all known `*.bank.in` subdomains with probe results (4199 entries) |
| `data/bank_domains_ct_expansion.csv` | New subdomains discovered via crt.sh CT logs (2839 entries) |
| `data/bank_tld_domains_status.csv` | Global `*.bank` (fTLD) probes |
| `data/fin_in_domains_status.csv` | `*.fin.in` audit |
| `data/insurance_in_domains_status.csv` | `*.insurance.in` audit |
| `data/nbfc_in_domains_status.csv` | `*.nbfc.in` audit |
| `data/npci_in_domains_status.csv` | `*.npci.in` audit |
| `data/new_subdomains.txt` | Flat list of all discovered subdomains (input to `scan_subdomains.py`) |
| `scripts/scan_subdomains.py` | Probe a list of domains (DNS + HTTPS) → status CSV |
| `scripts/audit_financial_tlds.py` | Multi-TLD sweep |
| `scripts/scan_domains.py` | Prefix-brute-force across a root TLD |
| `scripts/scan_global_bank.py` | Global `.bank` gTLD probe |
| `scripts/build_subdomain_list.py` | Merge discovery sources (Wayback, urlscan, HackerTarget) |
| `scripts/institutions.txt` | Curated Indian financial institution prefixes |

## Data Sources

- **crt.sh** (Certificate Transparency logs) — largest source (currently 2839 subdomains, this repo's primary expansion source)
- **Wayback Machine CDX** — historical crawl data
- **urlscan.io** — recent scan results (100-result free-tier cap)
- **HackerTarget hostsearch** — DNS-based discovery (50-result cap)
- **RBI website** — initial institution prefix list

## Schema

All CSVs share this schema:
```
domain           — Fully-qualified subdomain (e.g. netbanking.axis.bank.in)
dns_resolves     — True/False, whether A record resolves
ip_address       — Resolved IPv4 address (first A record)
https_works      — True/False, whether HTTPS request succeeded
http_works       — True/False, whether HTTP request succeeded
status_code      — HTTP status code if available
title            — Page <title> content (truncated to 200 chars)
final_url        — Final redirect destination URL
error            — Error message if request failed
```

## Workflows

- `.github/workflows/refresh.yml` — Daily: discover new subdomains from Wayback/urlscan/HackerTarget/CT/subfinder → probe → merge → commit
- `.github/workflows/flat-data.yml` — Syncs `data/` to a `flat-data` branch for flatgithub.com consumption

The daily refresh pipeline now includes crt.sh CT logs and subfinder (20+ passive sources) alongside Wayback, urlscan, and HackerTarget.

## Data Release

Tagged releases (`2026.06`, etc.) are published to GitHub Releases with the dataset in multiple formats (CSV, JSONL, SQLite, Parquet). Also available via zo.pub at `https://zo.pub/cashlessconsumer/bank-domains-status`.

## Naming Convention

All active probe CSVs follow `{namespace}_domains_status.csv`. Expansion/discovery files use descriptive names without the `_status` suffix.
