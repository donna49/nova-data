# AGENTS.md

Instructions for coding agents (Codex and others) working in this repo.

## What this repo is

This repo is an inventory of public property-record sources for six Northern Virginia jurisdictions:

- Arlington County
- Fairfax County
- Loudoun County
- City of Alexandria
- City of Falls Church
- City of Fairfax

The catalog lives in `inventory/sources/*.yaml`, one entry per dataset.

**Your job:** download every free bulk/API source in full to the local machine, recording which official office each dataset came from. A separate agent will later load the downloaded files into Postgres. Do not build a database here.

## Setup

- Python 3.10+.
- Work on branch `claude/laughing-darwin-3tydzg` unless it has been merged to `main`. `main` may be empty.
- Install dependencies and validate the catalog:

```sh
pip install -r requirements.txt
python3 scripts/pull_samples.py --validate      # catalog must validate before anything else
```

- The machine needs open HTTPS access to these county, city and state sites:
  - `*.arcgis.com`
  - `*.arlingtonva.us`
  - `*.alexandriava.gov`
  - `*.fairfaxcounty.gov`
  - `*.fairfaxva.gov`
  - `*.loudoun.gov`
  - `*.fallschurchva.gov`
  - `*.virginia.gov`
  - `gis.mwcog.org`
- Plan for about 10 GB of free disk. The largest pulls are:
  - Fairfax sales and dwelling-addition tables (about 1.5M rows each)
  - VGIN parcels for the six localities (about 601K features with geometry)
  - Loudoun permits (568K)
  - Arlington's 138 MB payment file

## Run the download

```sh
python3 scripts/download_all.py --list                     # plan: 65 sources to GET, the rest SKIP with a reason
python3 scripts/download_all.py --out ~/nova-data-raw      # full run (resumable)
python3 scripts/download_all.py --out ~/nova-data-raw --jurisdiction loudoun
python3 scripts/download_all.py --out ~/nova-data-raw --only fairfax_county_dta_re_sales
python3 scripts/download_all.py --out ~/nova-data-raw --force   # re-download everything
```

- **Resumable.** Sources with `status: ok` in their `_source.json` are skipped. Re-run after a failure and only the unfinished ones run.
- **Exit code.** It is non-zero if any source failed. Failures are recorded in `_source.json` (`status: failed`, `error`) and in `manifest.csv`. Do not hide them. Retry once; if a source keeps failing, report it with the error text.
- **Politeness.** Keep the default `--delay 0.3` or slower. These are small county servers, so run large pulls off-peak.
- **Never commit downloaded data.** `data/` is in `.gitignore`. Prefer an `--out` path outside the repo.

## Output contract (what the database agent receives)

```
<out>/manifest.csv                                one row per downloaded source
<out>/<jurisdiction>/<source_id>/_source.json     provenance for that source
<out>/<jurisdiction>/<source_id>/<data files>
```

`manifest.csv` / `_source.json` fields:

| Field | Meaning |
|---|---|
| `source_id` | Unique ID, matches `inventory/sources/*.yaml` |
| `jurisdiction` | One of the six slugs, or `virginia_state` / `regional` |
| `official_source` | **The office or department that holds the records**, e.g. "Loudoun County Commissioner of the Revenue". This is the provenance to carry into the database. No URLs are recorded, by design. `unknown` if not known. |
| `dataset_name` | Name of the dataset |
| `quoin_sections` | Which of the 13 property sections the data covers |
| `parcel_key` | The join key (RPC, PARID, PIN, MCPI, account number, …) |
| `status` | `ok` or `failed` |
| `record_count` | Rows written (blank for original files) |
| `record_format` | See below |
| `files` | Data files written; `_source.json` also has `bytes` and `sha256` per file |
| `retrieved_at` | UTC timestamp of the download |
| `error` | Error text if `status` is `failed` |

`record_format` values:

| Value | Meaning |
|---|---|
| `geojson-features-ndjson` | `records.ndjson`, one GeoJSON Feature per line (WGS84 / EPSG:4326). Tables have `geometry: null`. |
| `esri-json-features-ndjson` | One Esri JSON feature (`attributes`, `geometry`) per line, used where a server lacks GeoJSON |
| `json-records-ndjson` | Arlington datahub API rows, one JSON object per line. One `.ndjson` per endpoint (e.g. `ImprovementInterior.ndjson`). |
| `original-files` | The publisher's file, unchanged: XLSX, CSV, PDF, ZIP or pipe-delimited `.txt.gz` |

### Data quirks the database agent must know

- **Loudoun sales spreadsheets** (`loudoun_cor_sales_cumulative`, `sales_2013.xlsx` … `sales_2024.xlsx`): older years start with a disclaimer row before the header, and the column layout differs by year. Map each year separately.
- **Arlington owner names:**
  - The Property API returns `Redacted` for owner names. Use `PropertyOwnerName` in `arlington_permit_bulk_file`, or `granteeName` in `arlington_re_sales_history`.
  - The Property API's owner mailing addresses are present.
- **Arlington bulk text files** (`*.txt.gz`) are pipe-delimited with quoted headers.
- **Owner privacy flags.** Honor these, and do not publish names that are flagged:
  - Loudoun: `Hide Name` in `loudoun_cor_owner_legal_address_xlsx`
  - City of Fairfax: `isprivateownerflag` in `fairfax_city_property_owners`
  - Arlington: `maskOwnerAddressInd`
- **Current-year-only sources** have no history; keep each run's copy dated to build history over time:
  - Fairfax assessed values (current and prior year)
  - Loudoun 2026 values
  - City of Fairfax PropertyOwners
  - Alexandria parcels
- **VGIN statewide parcels** are already filtered to the six localities (`query_where` on FIPS 51013, 51059, 51107, 51510, 51600, 51610).
- **Proxy datasets.** Footprints (Alexandria, Falls Church) are planning or GIS attributes, not assessor records. Arlington buyer names stand in for the current owner.

## Rules (do not break these)

1. **Only download what `download_all.py` selects.** It refuses `portal_search`, `request_only`, `paid`, and anything with `collection: blocked` or `collection: robots_disallowed`. Do not write scrapers for those.
2. **Never bypass access controls**: no CAPTCHA solving, WAF/bot-challenge evasion, logins, or credentials embedded in apps. Specifically, do not use:
   - the Fairfax DevelopmentTracker `utility.arcgis.com` proxy
   - Fairfax `gisint1/.../PLUSGISRecords`, which looks internal
   - `actdatascout.com` (Falls Church)
   - `realestate.alexandriava.gov`, whose robots.txt says `Disallow: /`
3. **Keep provenance.** Every dataset must keep its `official_source`. When you add a source, fill `official_source` in the YAML (validation requires it).
4. **Do not commit** downloaded data, credentials or personal data.

## Manual items (a human must download these in a browser)

These sites block scripts, so the downloader skips them. Ask the user to download them. Then place each file under `<out>/<jurisdiction>/<source_id>/` and write a matching `_source.json` by hand, using the same fields as above, with `status: ok` and `record_format: original-files`.

| source_id | What | Official source |
|---|---|---|
| `va_abc_licensees` | Virginia ABC licensee spreadsheet ("Find a License" page) | Virginia Alcoholic Beverage Control Authority |
| `fairfax_city_delinquent_taxpayer_lists` | Real estate delinquent accounts PDF (quarterly; latest as of 2026-04-03) | City of Fairfax Treasurer |

## Not obtainable by download (FOIA / records requests, not agent tasks)

These need a records request from a person. They are listed in `inventory/lookup_alternatives.md` ("Round 3"):

| Jurisdiction | What's missing |
|---|---|
| Fairfax County | Owner names, delinquent list, code cases |
| Alexandria | Sales history, assessment history, building records, delinquent list |
| Falls Church | Land book, sales, tax, permits |
| City of Fairfax | Sales history, code cases |

## Other scripts

```sh
python3 scripts/pull_samples.py                 # re-sample 100 rows per source into samples/ (repo copy)
python3 scripts/build_coverage.py               # regenerate inventory/coverage_matrix.md after editing the YAML
```

Catalog entry fields are documented in `README.md`. These download hints are optional:

| Field | Purpose |
|---|---|
| `download_urls` | List of `{name, url}` for multi-file sources |
| `session_url` | Fetched first to obtain cookies |
| `list_url` + `list_pattern` | Directory listing; the downloader fetches every matching file |
| `extra_endpoints` | Sibling API endpoints |
| `query_where` | ArcGIS filter |
