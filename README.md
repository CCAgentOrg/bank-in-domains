# bank-in-domains

**Audit of Indian financial namespace TLDs**. Daily probes of `.bank.in`, `.fin.in`, `.insurance.in`, `.nbfc.in`, `.npci.in`, and the global `.bank` gTLD — DNS resolution, HTTPS reachability, status codes, page titles, and final URLs.

> Why this exists: `.bank.in` is the de-facto namespace for Indian banking web presences, but no authoritative registry publishes a subdomain list. This audit discovers and probes the full namespace — exposing it as flat data for security research, DNS monitoring, vendor attack-surface mapping, and digital public infrastructure transparency.

---

## Quick Stats

| Namespace | Probed | Resolves | HTTP 200 | HTTPS Works |
|---|---|---|---|---|
| `*.bank.in` (master) | **4,199** | **1,680** (40.0%) | **941** (22.4%) | **1,308** (31.2%) |
| `*.bank.in` (CT expansion) | 2,839 | 647 (22.8%) | 181 (6.4%) | — |
| `*.bank` (global fTLD) | 268 | 12 | 9 | — |
| `*.fin.in` | 376 | 0 | 0 | — |
| `*.insurance.in` | 376 | 0 | 0 | — |
| `*.nbfc.in` | 376 | 1 | 0 | — |
| `*.npci.in` | 376 | 352 (wildcard) | 352 (parked) | — |

## Top 20 Banks by Subdomain Count

| Bank | Subdomains | Live | Bank | Subdomains | Live |
|---|---|---|---|---|---|
| Axis | 421 | 125 | SBI | 291 | 71 |
| SBI (UAT) | 256 | 64 | HDFC (UAT) | 242 | 61 |
| IndusInd | 223 | 67 | HDFC | 169 | 60 |
| PNB | 151 | 50 | Bank of India | 145 | 46 |
| Indian Bank (UAT) | 83 | 15 | Yes Bank | 82 | 37 |
| PNB (UAT) | 70 | 18 | IDFC First | 65 | 34 |
| Yes Bank (UAT) | 60 | 40 | Bank of Baroda | 60 | 12 |
| ICICI | 58 | 32 | Kotak | 57 | 25 |
| South Indian Bank | 53 | 31 | Federal Bank | 47 | 24 |
| RBL | 45 | 28 | Ujjivan SFB | 44 | 18 |

## Certificate Issuers (from CT logs)

| Issuer | Certificates |
|---|---|
| DigiCert | 1,591 |
| Let's Encrypt / ZeroSSL | 602 |
| GlobalSign | 478 |
| Sectigo | 392 |
| Entrust | 205 |
| Google Trust Services | 201 |
| eMudhra (Indian CA) | 179 |
| Amazon | 114 |
| Other | 35 |

---

## Data Files

| File | Rows | Description |
|---|---|---|
| `data/bank_domains_status.csv` | 4,199 | **Master** — all known `*.bank.in` subdomains with full probe results |
| `data/bank_domains_ct_expansion.csv` | 2,839 | New subdomains from crt.sh CT logs (not in original audit sources) |
| `data/bank_tld_domains_status.csv` | 268 | Global `*.bank` (fTLD) probe results |
| `data/fin_in_domains_status.csv` | 376 | `*.fin.in` — TLD exists, zero real subdomains |
| `data/insurance_in_domains_status.csv` | 376 | `*.insurance.in` — apex parked, no subdomains |
| `data/nbfc_in_domains_status.csv` | 376 | `*.nbfc.in` — apex parked, 1 subdomain |
| `data/npci_in_domains_status.csv` | 376 | `*.npci.in` — wildcard catch-all (no real signal) |
| `data/new_subdomains.txt` | 3,376 | Flat subdomain list (input to `scan_subdomains.py`) |

### Schema

All CSVs share the same 9-column schema:

```
domain           — Fully-qualified subdomain (e.g. netbanking.axis.bank.in)
dns_resolves     — True/False, whether A/AAAA record resolves
ip_address       — Resolved IPv4 address (first A record)
https_works      — True/False, whether HTTPS request returned a response
http_works       — True/False, whether plain HTTP request returned a response
status_code      — HTTP status code (200, 301, 403, 503, etc.)
title            — Page `<title>` content (truncated to 200 characters)
final_url        — Final redirect destination if applicable
error            — Error message on probe failure (timeout, DNS failure, etc.)
```

---

## Methodology

### Discovery

Subdomains are gathered from multiple independent sources to maximise coverage:

1. **Certificate Transparency (crt.sh)** — Primary expansion source. Queries crt.sh for all `.bank.in`-signed certificates via its CSV export (`https://crt.sh/?q=%.bank.in&output=csv`). This surfaces every subdomain that has ever had a publicly logged TLS certificate — including UAT, dev, staging, and internal services. This is the largest single source (2,839 new entries).

2. **Wayback Machine CDX** — Historical web crawl index. Queries `http://web.archive.org/cdx/search/cdx?url=bank.in` for all crawled URLs ending in `.bank.in`. Provides deep historical coverage (~1,000+ subdomains) but misses domains that never had a public web presence.

3. **urlscan.io** — Recent scan results. Queries `urlscan.io/api/v1/search/?q=domain%3Abank.in`. Fresher than Wayback, but the free tier caps at 100 results.

4. **HackerTarget hostsearch** — DNS-based discovery. Queries `api.hackertarget.com/hostsearch/?q=bank.in`. Recency varies; capped at ~50 results on free tier.

5. **RBI website** — Initial curated list of institution prefixes used as seed data.

### Probing

Each discovered subdomain is probed in two phases:

1. **DNS resolution** — Asynchronous A-record lookup via `dnspython` against Cloudflare (`1.1.1.1`) and Google (`8.8.8.8`) resolvers with a 4-second lifetime. If no A record resolves, the domain is marked as non-resolving and skipped for HTTP probing.

2. **HTTPS check** — HTTP GET to `https://<domain>/` with a standard browser User-Agent, 8-second timeout, and certificate verification disabled (we're checking reachability, not security). Records status code, page title (via regex on `<title>`), and final redirect URL. Falls back gracefully on timeout or connection error.

Concurrency: 100 parallel probes (configurable via `--concurrency`). Full audit completes in approximately 5–10 minutes.

### Limitations

- **One-shot probe**: A single probe may fail due to transient network issues; retry logic is intentionally minimal to keep scan time bounded.
- **No content inspection**: We only check page title — not whether the page is functional or serves real content.
- **UAT/dev domains**: Many discovered subdomains are test/staging environments behind VPN or IP-restricted, so they resolve but return 403 or timeout on HTTPS.
- **Wildcard resolution**: `.npci.in` uses a wildcard DNS catch-all, so all subdomains "resolve" to a parked page, which is a DNS configuration signal rather than actual service deployment.
- **crt.sh coverage lags**: Newly provisioned certificates may take hours to appear in CT logs; revoked certificates may still be listed.

### Why This Matters

- **Security research**: Attack surface enumeration for India's financial sector. UAT/staging subdomains often lag behind production in security posture.
- **DPI transparency**: Monitoring the digital public infrastructure namespace (UPI, Aadhaar, BBPS enablers like NPCI, SBI, PNB) helps track digitalisation across India's banking sector.
- **Vendor due diligence**: Fintech companies working with banks can use this data for vendor risk assessment and infrastructure mapping.
- **DNS hygiene**: Subdomains that resolve but serve no content may indicate dangling DNS records (subdomain takeover risk).

---

## Scripts

| Script | Purpose |
|---|---|
| `scripts/scan_subdomains.py` | Probe a domain list (DNS + HTTPS), output status CSV. Async, configurable concurrency. |
| `scripts/scan_domains.py` | Cross-probe every institution prefix across a given TLD. |
| `scripts/audit_financial_tlds.py` | Full multi-TLD audit sweep in one pass. |
| `scripts/scan_global_bank.py` | Probe global `.bank` (fTLD) with `.bank.in` prefixes. |
| `scripts/build_subdomain_list.py` | Merge discovery outputs from Wayback, urlscan, HackerTarget. |

## Reproduce

```bash
pip install dnspython

# Probe a list of subdomains
python3 scripts/scan_subdomains.py \
  --in-list data/new_subdomains.txt \
  --out-csv out.csv --concurrency 50

# Full audit (all TLDs)
python3 scripts/audit_financial_tlds.py

# CT discovery (requires node or manual crt.sh export)
# curl -s 'https://crt.sh/?q=%.bank.in&output=csv' > ct_dump.csv
```

---

## Dataset Releases

Tagged versions of the full dataset are published in multiple formats:

| Format | File | Best For |
|---|---|---|
| CSV | `bank-domains-2026.06.csv` | Spreadsheets, simple imports |
| JSONL | `bank-domains-2026.06.jsonl` | Streaming, log processing |
| SQLite | `bank-domains-2026.06.sqlite` | SQL queries, DuckDB |
| Parquet | `bank-domains-2026.06.parquet` | Analytical workloads, Pandas |

Latest release: **[2026.06](https://github.com/CCAgentOrg/bank-in-domains/releases/tag/2026.06)**

Direct download (zo.pub):
- https://zo.pub/cashlessconsumer/bank-domains-status

## Flat Data API

The `data/` directory is available as a flat data API:

> **https://flatgithub.com/CCAgentOrg/bank-in-domains**

Browse individual files, view as tables, or fetch raw CSVs for pipelines.

---

## CI / CD

- `.github/workflows/refresh.yml` — Daily at 02:30 UTC (08:00 IST): discovers new subdomains from Wayback/urlscan/HackerTarget, probes them, merges into master CSV, commits.
- `.github/workflows/flat-data.yml` — Daily at 03:00 UTC: syncs `data/` to a `flat-data` branch for flatgithub.com.

---

## License

**CC0 1.0 Universal (Public Domain Dedication)**

This dataset is dedicated to the public domain. No copyright asserted. No restrictions on use — copy, transform, publish, or build products on top of it without attribution. Data is provided "as is" without warranty of any kind.

[Read the full license](https://creativecommons.org/publicdomain/zero/1.0/legalcode)

---

## Sources

- **crt.sh** — Certificate Transparency log aggregation
- **Wayback Machine CDX API** — Internet Archive's web crawl index
- **urlscan.io** — Website scanner and domain intelligence
- **HackerTarget hostsearch API** — DNS enumeration service
- **RBI website** — Initial institution prefix list

---

*Built for transparency. Updated daily. Maintained by [CashlessConsumer](https://github.com/CCAgentOrg).*
