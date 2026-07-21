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

## Zo-based Refresh (alternative to GitHub Actions)

GitHub Actions has a 45-minute timeout and the pipeline routinely exceeds it.
A **Zo agent** runs the full pipeline on Zo and pushes to GitHub instead.

| File | Role |
|---|---|
| `scripts/zo_refresh.sh` | Zo-based runner: discovery → probe → merge → push |
| `/tmp/bank-in-refresh/` | Status markers written by the script (for agent monitoring) |

### How to run manually

```bash
bash /home/workspace/Projects/bank-in-domains/scripts/zo_refresh.sh
```

The script writes step-done markers to `/tmp/bank-in-refresh/*.done` and
a final result to `/tmp/bank-in-refresh/result.txt`.

### Automation

- **Name**: Bank.in Domain Refresh
- **Schedule**: Daily at 8:00 AM IST (02:30 UTC) — matches the old GH Actions time
- **Instruction**: see the Zo agent configuration
- **Model**: Zen DS4 Flash (b5700bd6)

If the agent run times out (10-min bash limit), the script continues in the
background via nohup; the next day's run will pick up any unfinished state.

## Data Release

Tagged releases (`2026.06`, etc.) are published to GitHub Releases with the dataset in multiple formats (CSV, JSONL, SQLite, Parquet). Also available via zo.pub at `https://zo.pub/cashlessconsumer/bank-domains-status`.

## Naming Convention

All active probe CSVs follow `{namespace}_domains_status.csv`. Expansion/discovery files use descriptive names without the `_status` suffix.

## Pipeline Architecture

### Daily (Zo Agent → commit → push)
- **What**: Runs `scripts/zo_refresh.sh` at 02:30 UTC (08:00 IST)
- **Sources**: Wayback CDX, urlscan.io, HackerTarget, crt.sh CT logs, subfinder (20+ passive sources)
- **Steps**: Discover → build new list → probe (ping/http/https/dns) → merge into main status CSV → commit
- **Output**: Updates `data/` files (CSV, seen cache, new subdomains list) and pushes to main
- **On no new data**: Skips probe/merge/commit entirely

### Weekly (GitHub Actions → Release)
- **What**: `release.yml` workflow runs Sunday 06:00 UTC
- **Tag format**: `v{year}.{month}.{release_n}` — auto-increments within the month (e.g. `v2026.7.1`)
- **Changelog**: Delta from last release: commits, files changed, new subdomains (with list), domain counts
- **Assets**: CSV data files + full tar.gz snapshot attached to release
- **Manual trigger**: Supports `workflow_dispatch` with optional `force_version` input

### Quick links
- [Daily refresh agent status](/?t=automations) — Zo agent
- [Release workflow](/.github/workflows/release.yml) — weekly GHA
- [Release history](https://github.com/CCAgentOrg/bank-in-domains/releases)

## Repo Structure

```
scripts/
├── zo_refresh.sh           # Zo-based daily pipeline entrypoint
├── fetch_ct_subdomains.py   # crt.sh certificate log fetching
├── build_subdomain_list.py  # CT+archival source merging
├── scan_subdomains.py       # Probe discovered domains
└── turso_client.py          # Turso/LibSQL database client

data/
├── bank_domains_status.csv       # Master inventory (committed)
├── bank_domains_ct_expansion.csv # CT expansion data
├── ct_seen.json                  # CT fetch cache (avoids re-fetch)
├── ct_new_subdomains.csv         # Newly discovered via CT logs
├── new_subdomains.txt            # New subdomains (probe input)
├── bank_tld_domains_status.csv   # Bank TLD .in domains
├── fin_in_domains_status.csv     # Financial .in domains
├── insurance_in_domains_status.csv
├── nbfc_in_domains_status.csv
└── npci_in_domains_status.csv
```
