# bank-in-domains

Audit of Indian financial TLDs (`.bank.in`, `.fin.in`, `.insurance.in`, `.nbfc.in`,
`.npci.in`, `.bank`) — DNS resolution, HTTPS reachability, status codes, page titles,
and final URL. Data and scripts published for reproducibility. **Updated daily** via
GitHub Actions.

> Why this exists: `.bank.in` is the de-facto namespace for Indian bank web
> presences (222+ subdomains). Is the same true for the newer Indian financial
> TLDs? This audit answers that — and exposes it as a flat data file.

## Data

| File | Rows | Description |
|---|---|---|
| `data/bank_domains_status.csv` | 1349 | All `*.bank.in` subdomains. DNS, IP, HTTPS, status, title |
| `data/bank_domains_ct_expansion.csv` | 1127 | 1127 subdomains discovered via Wayback + urlscan + HackerTarget (not in the original audit) |
| `data/bank_tld_domains_status.csv` | 268 | Probes of `<institution>.bank` (global fTLD gTLD) |
| `data/fin_in_domains_status.csv` | 376 | `*.fin.in` — TLD exists, no real subdomains |
| `data/insurance_in_domains_status.csv` | 376 | `*.insurance.in` — apex parked, no subdomains |
| `data/nbfc_in_domains_status.csv` | 376 | `*.nbfc.in` — apex parked, 1 subdomain |
| `data/npci_in_domains_status.csv` | 376 | `*.npci.in` — wildcard catch-all (no real signal) |
| `data/new_subdomains.txt` | 1127 | Plain-text subdomain list (input to `scan_subdomains.py`) |

All CSVs share the same schema:

```csv
domain,dns_resolves,ip_address,https_works,http_works,status_code,title,final_url,error
```

## Quick stats (last run)

| Namespace | Probed | Resolves | HTTP 200 |
|---|---:|---:|---:|
| `*.bank.in` | 1349 | 1025 | 756 |
| `*.bank` (global) | 268 | 12 | 9 |
| `*.fin.in` | 376 | 0 | 0 |
| `*.insurance.in` | 376 | 0 | 0 |
| `*.nbfc.in` | 376 | 1 | 0 |
| `*.npci.in` | 376 | 352 (wildcard) | 352 (parked) |

## Scripts

| Script | Purpose |
|---|---|
| `scripts/scan_subdomains.py` | Probe a list of domains (DNS + HTTPS) and write status CSV |
| `scripts/scan_domains.py` | Probe every prefix from the bank.in list across one root TLD |
| `scripts/audit_financial_tlds.py` | Full audit: parallel probe of all financial TLDs in one pass |
| `scripts/scan_global_bank.py` | Probe the global `.bank` gTLD with bank.in prefixes |
| `scripts/build_subdomain_list.py` | Merge Wayback + urlscan + HackerTarget discovery outputs |
| `scripts/institutions.txt` | Curated list of Indian financial institution prefixes |

## How to reproduce

```bash
# Install deps
pip install dnspython

# Probe a list of subdomains
python3 scripts/scan_subdomains.py \
  --in-list data/new_subdomains.txt \
  --out-csv out.csv --concurrency 50

# Full audit (all TLDs)
python3 scripts/audit_financial_tlds.py
```

## CI / CD

- `.github/workflows/refresh.yml` — daily refresh of subdomain discovery +
  full re-probe; commits updated CSVs back to `main`.
- `.github/workflows/flat-data.yml` — publishes the data folder to a
  `flat-data` branch for [flatgithub.com](https://flatgithub.com) consumption.

## Flat data API

This repo is exposed as a flat data API at:

> **https://flatgithub.com/CCAgentOrg/bank-in-domains**

Browse `data/` as a directory, view individual files, or hit the GitHub raw
content. Useful for quick lookups and pipelines.

## Sources consulted

- **Wayback Machine CDX** (largest — 1034 subdomains)
- **urlscan.io** (most recent — 100 result cap on free tier)
- **HackerTarget** `hostsearch` API (50 result cap)
- **RBI website** (initial prefix list)

## License

MIT
