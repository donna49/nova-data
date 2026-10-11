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

- **The catalog has 110 entries.** 105 are verified: the landing page resolves or the endpoint was sampled. The other 5 are sites that block automated requests or pages that no longer exist; their notes say which.
- **All 39 queryable API sources returned data.** For each one, `samples/<source_id>/` holds 100 rows plus `schema.json` (fields, types, reported row count, sha256).
- **Live discovery replaced several web-search guesses:**
  - Fairfax County's real estate tables are standalone `Tax_Administration_Real_Estate_*` services.
  - Fairfax's DevelopmentTracker permit layers require a token. `Building_Records_PLUS` is the anonymous alternative.
  - Alexandria's parcel layer carries owners and assessed values.
  - Loudoun's parcels are layer 5, not layer 0.
  - VGIN moved hosts.
  - The parcel layers for Falls Church and the City of Fairfax were found on ArcGIS Online.

## Layout

| Path | What |
|---|---|
| `inventory/sources/*.yaml` | The catalog: one entry per dataset or system, split by jurisdiction group |
| `inventory/coverage_matrix.md` | Best available access for each jurisdiction and section. Generated; do not edit. |
| `scripts/pull_samples.py` | Validates the catalog and pulls 100-row samples from bulk/API entries into `samples/<source_id>/` |
| `scripts/build_coverage.py` | Regenerates the coverage matrix |
| `inventory/lookup_alternatives.md` | Bulk and scripted alternatives for each lookup-only site, with verdicts, volumes and constraints |

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
| `collection` | For lookup-only sources, how they can be collected: `bulk_alternative`, `scrape_feasible`, `robots_disallowed`, `blocked` or `request_only` |
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

**Arlington is the strongest source (verified).** Its open data API (`datahub-v2.arlingtonva.us/api/...`) publishes the following, all keyed by RPC:

- property
- historical assessments
- sales history
- residential characteristics
- tax payments since 2015
- exemptions
- all permit applications and their history
- stop-work and unsafe-building notices
- active business licenses

Confirmed in the samples:
- Sales carry deed book/page and a land-record document number.
- Permits are keyed by RPC.
- Payment rows include penalty and interest, which identify delinquent installments.

**Correction:** the Property API **redacts owner names**; owner mailing addresses are present. Sales-history buyer names are not redacted and stand in for the current owner. An earlier version of this README said otherwise.

There are gaps:
- no commercial-building characteristics (`ImprovementCommercial` returns 404)
- no general code-enforcement cases

**Fairfax County is close behind (verified).** Its Department of Tax Administration (DTA) publishes eight real estate tables, joined on PARID and roughly equivalent to D.C.'s appraisal (CAMA) files:

| Table | Rows |
|---|---|
| Parcels | 371K |
| Assessed values (current and prior year) | 369K |
| Sales, with deed BOOK/PAGE | 1.45M |
| Legal | 370K |
| Land | 372K |
| Dwelling | 341K |
| Additions | 1.5M |
| Commercial | 12K |

A ninth, the Owner table, is listed on Data.gov but no longer published, so owner names are only in iCARE lookups.

The county also publishes:
- 141K building permit records (`Building_Records_PLUS`)
- 130K site records
- zoning and zoning cases
- special tax district boundaries

The DevelopmentTracker permit and certificate-of-occupancy layers require a token.

There are gaps:
- tax bills must be derived from assessments and published rates
- no delinquent list is published
- no owner names in bulk
- no code-case data
- no business license data

**Loudoun has good GIS layers but its assessment data is mostly per-parcel.** GIS covers parcels, zoning, address points and the Metrorail districts. Assessment, sales and deed data comes mainly from a per-parcel search (iasWorld). The exceptions are the annual Land Book detail PDFs and the Route 28 district parcel PDFs, which are bulk but need PDF parsing. Bulk CAMA data would need a FOIA request.

**Alexandria is better than expected.** The `Real_Estate_Parcels` layer (25.5K rows) carries:
- owner name and mailing address
- current land, improvement and total assessed values
- zoning, land use and lot size
- the recorded INSTRUMENT number

It has no sales history and no building characteristics. Those, and APEX building permits, are lookup-only. Land records are on the state's paid Secure Remote Access (SRA) system.

**Falls Church and the City of Fairfax have parcel geometry only.**
- Falls Church: 3,889 parcels by RPC, plus zoning and land use.
- City of Fairfax: 9,742 parcels by PIN, with zoning and land use.

Values, owners and sales are lookup-only through their Accela and Vision portals. The City of Fairfax website blocks automated requests. The City of Fairfax is the only one of the six that publishes a delinquent taxpayer list (quarterly).

**Deeds are behind paywalls everywhere.** Each circuit court runs its own system:

| Court | System | Cost | Also serves |
|---|---|---|---|
| Arlington | GovOS | Free index, paid images, or $50/mo | Falls Church (records from 1988 on) |
| Fairfax | CPAN | Subscription | City of Fairfax, and Falls Church records before 1988 |
| Loudoun | Its own LRMS | Free index, or $262/yr | — |
| Alexandria | SRA/COVERS | $50/mo | — |

None offers a bulk feed. The deed book/page and instrument numbers in the assessor sales tables are the practical way to get deed references.

**Licenses come mainly from the state.** The Virginia ABC licensee spreadsheet (statewide, free) replaces D.C.'s alcohol license data (ABCA). Local business licenses (BPOL) are confidential under Va. Code 58.1-3 everywhere except Arlington, which publishes active licenses. Virginia has not issued adult-use cannabis retail licenses.

## Lookup-only sites: alternatives found

The full write-up is in `inventory/lookup_alternatives.md`.

- **Loudoun:** a monthly Treasurer CSV of every parcel with owner name, tax and delinquent amounts. 568K permits from an anonymous ArcGIS table. Sales, deed and building data can be collected per parcel from iasWorld.
- **City of Fairfax:** the assessment app `realestate.fairfaxva.gov` returns every parcel in about 194 search pages (owner, value, year built, last sale with book-page). Accela permits have a CSV export.
- **Fairfax County:** owner names only by FOIA, or per-parcel collection from iCARE (about 370K pages).
- **Alexandria:** permits, inspections and code cases come from the APEX JSON search. Sales and history pages are robots-disallowed, so FOIA or permission is needed.
- **Falls Church:** blocked (WAF) and has no permit portal. FOIA.

## Next steps

1. Send FOIA or bulk-data requests for:
   - sales and building characteristics from Alexandria, Loudoun, Falls Church and the City of Fairfax
   - the Fairfax County Owner table
   - business license lists where a jurisdiction will release them
2. Download the Virginia ABC licensee spreadsheet manually (the site blocks scripts).
3. Decide how much history is needed. Several sources are current-year only (Fairfax assessed values, Alexandria parcels), so history has to come from saving periodic snapshots.
