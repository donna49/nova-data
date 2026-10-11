# nova-data

This is an inventory of public property-record sources for six Northern Virginia jurisdictions:

- Arlington County
- Fairfax County
- Loudoun County
- City of Alexandria
- City of Falls Church
- City of Fairfax

Every source is mapped to the 13 property sections that [Quoin](https://app.quoindata.com) provides for Washington, D.C.:

| Section | Section | Section |
|---|---|---|
| identity | ownership | license |
| assessment | transfer | inspection_enforcement |
| tax | deed_reference | building |
| delinquency_tax_sale | permit | land |
| special_assessment | | |

The goal is to know what has to be collected before building a NoVA equivalent.

## Status (2026-10-11)

- **Discovery is done, but only from web search.** The environment's network policy blocks the jurisdictions' websites, so no URL has been opened or sampled yet. Every entry has `verified_at: null`.
- **Sample pulls are pending.** They need these domains allowed in the environment's network settings:
  - `*.arcgis.com`
  - `*.arlingtonva.us`
  - `*.alexandriava.gov`
  - `*.fairfaxcounty.gov`
  - `*.fairfaxva.gov`
  - `*.loudoun.gov`
  - `*.fallschurchva.gov`
  - `*.virginia.gov`
  - `*.vims.edu`
  - `gis.mwcog.org`

## Layout

| Path | What |
|---|---|
| `inventory/sources/*.yaml` | The catalog: one entry per dataset or system, split by jurisdiction group |
| `inventory/coverage_matrix.md` | Best available access for each jurisdiction and section. Generated; do not edit. |
| `scripts/pull_samples.py` | Validates the catalog and pulls 100-row samples from bulk/API entries into `samples/<source_id>/` |
| `scripts/build_coverage.py` | Regenerates the coverage matrix |

```sh
pip install -r requirements.txt
python3 scripts/pull_samples.py --validate     # check the catalog
python3 scripts/pull_samples.py                # pull samples (needs network access)
python3 scripts/build_coverage.py              # rebuild the matrix
```

### Entry fields

These are modeled on Quoin's own source catalog.

| Field | Meaning |
|---|---|
| `source_id` | Unique ID for the entry |
| `jurisdiction` | One of the six slugs, or `virginia_state` / `regional` |
| `covers` | The local jurisdictions a state or regional entry applies to. If absent, it applies to all six. |
| `custodian` | The office that holds the records |
| `dataset_name` | Name of the dataset or system |
| `quoin_sections` | Which of the 13 sections it supplies |
| `access_type` | How the data can be obtained (see below) |
| `cost` | What access costs |
| `format` | File or API format |
| `landing_url` | Human-facing page |
| `endpoint_url` | The data or API URL `pull_samples.py` fetches. Null when not yet known. |
| `parcel_key` | The identifier used to join records to parcels |
| `update_frequency` | How often the custodian refreshes it |
| `history_start` | How far back the records go |
| `terms` | License or terms of use |
| `notes` | Caveats |
| `evidence_urls` | The search results the entry is based on |
| `in_matrix` | When `false`, the entry is left out of the matrix (aggregates, non-public, or unverified columns) |
| `verified_at` | When the entry was last checked against the live source |

`access_type` takes one of these values:

| Value | Meaning |
|---|---|
| `bulk` | Free download |
| `api` | Free queryable service |
| `portal_search` | Web lookup, one parcel at a time |
| `paid` | Subscription or per-page fee |
| `request_only` | FOIA or email request |

## Key findings

**Parcel IDs differ by jurisdiction**:

| Jurisdiction | Parcel ID |
|---|---|
| Arlington and Falls Church | RPC |
| Fairfax County | PARID / tax map number |
| Loudoun | PIN / MCPI |
| Alexandria | PID (map-block-parcel) |
| City of Fairfax | Tax map / account number |

Statewide, VGIN parcels add `VGIN_QPID`, which can serve as a cross-jurisdiction key.

**Arlington is the strongest source.** Its open data API (`datahub-v2.arlingtonva.us/api/...`) publishes the following, all keyed by RPC:

- property
- historical assessments
- sales history
- residential characteristics
- tax payments since 2015
- exemptions
- all permit applications and their history
- stop-work and unsafe-building notices
- active business licenses

There are gaps:
- no commercial-building characteristics
- no general code-enforcement cases
- owner fields may be redacted in the bulk file

**Fairfax County is close behind.** Its Department of Tax Administration (DTA) publishes nine real estate tables, joined on PARID and roughly equivalent to D.C.'s appraisal (CAMA) files:

- parcels
- assessed values
- sales
- owner
- legal
- land
- dwelling
- additions
- commercial

The county also publishes:
- a nightly building-permit and certificate-of-occupancy feed
- special tax district boundaries
- zoning

There are gaps:
- tax bills must be derived from assessments and published rates
- no delinquent list is published
- no business license data

**Loudoun has good GIS layers but its assessment data is mostly per-parcel.** GIS covers parcels, zoning, address points and the Metrorail districts. Assessment, sales and deed data comes mainly from a per-parcel search (iasWorld). The exceptions are the annual Land Book detail PDFs and the Route 28 district parcel PDFs, which are bulk but need PDF parsing. Bulk CAMA data would need a FOIA request.

**Alexandria has GIS bulk data but no CAMA bulk data.** Assessments, sales and APEX permits are lookup-only. The parcels layer includes instrument numbers. Land records are on the state's paid Secure Remote Access (SRA) system.

**Falls Church and the City of Fairfax are lookup-only.** Both have per-parcel assessment search and Accela/Vision portals. The City of Fairfax is the only one of the six that publishes a delinquent taxpayer list (quarterly).

**Deeds are behind paywalls everywhere.** Each circuit court runs its own system:

| Court | System | Cost | Also serves |
|---|---|---|---|
| Arlington | GovOS | Free index, paid images, or $50/mo | Falls Church (records from 1988 on) |
| Fairfax | CPAN | Subscription | City of Fairfax, and Falls Church records before 1988 |
| Loudoun | Its own LRMS | Free index, or $262/yr | — |
| Alexandria | SRA/COVERS | $50/mo | — |

None offers a bulk feed. The deed book/page and instrument numbers in the assessor sales tables are the practical way to get deed references.

**Licenses come mainly from the state.** The Virginia ABC licensee spreadsheet (statewide, free) replaces D.C.'s alcohol license data (ABCA). Local business licenses (BPOL) are confidential under Va. Code 58.1-3 everywhere except Arlington, which publishes active licenses. Virginia has not issued adult-use cannabis retail licenses.

## Next steps

1. Open network access to the domains listed above, then run `pull_samples.py` and fill in `verified_at`.
2. Resolve the remaining unknown endpoints:
   - layer IDs for the Fairfax `OpenData_A5` tables
   - the Alexandria, City of Fairfax and Loudoun Hub item URLs
   - Arlington zoning
3. Send FOIA requests for bulk CAMA data to Alexandria, Loudoun, Falls Church and the City of Fairfax.
