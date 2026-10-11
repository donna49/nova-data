# Alternatives to one-parcel-at-a-time lookup sites

As of 2026-10-11.

**Question:** for each source we could only search one property at a time, is there another way to get the whole dataset? That could be an official bulk file, an API the site itself uses, or a way to collect the per-property pages by script. If it can't be collected, why not?

**How we checked:** three probe passes, one per jurisdiction group. Each made at most about 40 requests per host, at least 1 second apart. They were feasibility tests: nothing was bulk-downloaded, and no login, CAPTCHA, WAF challenge, token or bot block was worked around. Claims marked **V** were confirmed by fetching. Claims marked **I** are inferred.

## Bottom line

| Jurisdiction | What changed |
|---|---|
| Loudoun | Moves from mostly 🔎 to mostly ✅. The Treasurer publishes a monthly **bulk CSV of every parcel with owner name, tax and delinquent amounts**. LandMARC permits are an **anonymous ArcGIS table with 568K rows**. Sales, deed and building data can be collected per parcel from iasWorld (one GET per parcel, no session or CAPTCHA). |
| City of Fairfax | Moves from 🔎 to ✅/🔁. Its assessment app, `realestate.fairfaxva.gov`, is reachable even though the main city site blocks scripts. **About 194 search-result pages return every parcel**, with owner, value, year built, size and last sale with book-page. Accela permits have a working **CSV export**. The `GISCAMA` layer adds owner and values in bulk (Feb 2025 snapshot). |
| Fairfax County | Owner names, the one real gap, can be collected per parcel from iCARE (about 370K pages). A FOIA request for an owner extract is the cleaner route. The Master Address Repository (388K) and Approved Site Records (130K) are anonymous APIs. |
| Alexandria | Permits, inspections and code cases come through APEX's JSON search API (no login). Sales history, assessment history and building facts are on per-account pages, but the site's **robots.txt disallows all crawling**, so a FOIA request or the city's permission is needed. A building-footprint layer (year built, stories, size) is a bulk proxy. |
| Arlington | Already bulk. **Correction:** the Property API **redacts owner names**. Sales-history buyer names (`granteeName`) are not redacted and stand in for the current owner. The Property search and Treasurer sites block scripts, and nothing there is needed. |
| Falls Church | No change. The assessment site moved to actDataScout, which sits behind an Azure WAF JavaScript challenge. There is no permit portal at all, and the city's GIS has geometry only. A **FOIA request** to the Assessor is the route. |

## Per-source findings

| Source | Verdict | Method | Volume | Constraint |
|---|---|---|---|---|
| Loudoun parcel DB (iasWorld) | 🔁 scrape feasible (V) | `PrintDatalet.aspx?pin={MCPI}&gsp=PROFILEALL…` returns profile, values 2018+, sales with instrument and book/page, and dwelling | about 133K GETs (about 37 h at 1/s) | No robots.txt. No ToS clause. Banner says "updated weekly". |
| Loudoun Treasurer | ✅ bulk (V) | `interwapp22.loudoun.gov/TreasurerPublicFiles/public/` monthly CSV plus layout | 1 file, about 72 MB | Linked from the official taxes page |
| Loudoun tax history | 🔁 (V) | `loudounportal.com/PaymentHistoryPage/ViewPaymentHistory.aspx?PIN=` | about 133K | Only needed for history before the current year |
| Loudoun LandMARC | ✅ API (V) | `logis.loudoun.gov/.../LMARC/LandMARC_Permits/MapServer/1` | about 72 paged queries | Daily snapshot. No inspection detail. |
| Fairfax iCARE | 🔁 scrape feasible (V) | `icare.fairfaxcounty.gov/ffxcare/Datalets/PrintDatalet.aspx?pin=…` returns owner, deed, sales, values 2000+ | about 370K GETs (about 4.3 days) | No robots.txt. Owners can opt out of display. Ask DTA for a FOIA quote first. |
| Fairfax mailing-list GP tool | ✗ not recommended (V, metadata only) | Returns OWNER_FULL_NAME for a buffer around a point | — | Built for notice mailings; gridding the county with it would be misuse |
| Fairfax PLUS (Accela) | 🔁 (V) | Date-window search, then the "Download results" CSV | about 100 rows per search (I) | ASP.NET async postback. GIS layers already cover most of it. |
| Fairfax Development Tracker layers | 📨 (V) | Served only through an ArcGIS stored-credential proxy | — | Not used; that proxy is meant for the app only. Ask LDS for a public view. |
| Fairfax DCC cases | 🔁 but privacy-sensitive (V) | PLUS Enforcement module search and export | about 50 per day | Detail pages show owner names and complaint narratives, so prefer FOIA |
| Fairfax MAR | ✅ API (V) | `Master_Address_Repository/FeatureServer/0` | 388,032 rows | — |
| City of Fairfax assessments | 🔁 scrape feasible (V) | POST `realestate.fairfaxva.gov/SearchResults.asp` with a value range of 0–9,999,999,999, then page with `?page=N&PageChanged=1` | about 195 requests for every parcel. Full sales and assessment history adds about 19.4K. | No robots.txt. No CAPTCHA. Page states display is authorized by Va. Code 58.1-3122.2. |
| City of Fairfax GISCAMA | ✅ API (V) | `services2.arcgis.com/DANcyjLcCCpGk8Ri/.../GISCAMA/FeatureServer/0` | 9,696 rows | Snapshot from 2025-02-04 |
| City of Fairfax permits | 🔁 (V) | Accela search, then `Export2CSV.ashx` returns text/csv | about 3 requests per date window | The POST needs ordinary browser Referer/Origin headers (the form's CSRF check) |
| City of Fairfax tax portal | ✗ blocked (V) | Catalis Avalon; its API sits behind reCAPTCHA | — | FOIA |
| Alexandria assessment search | ✗ robots-disallowed (V) | `detail.php?accountno=` has full sales (to 1943), assessments 2000–2026 and building facts. `recent.php` has sales lists by study group. | 26–47K pages, or about 500–1,000 for recent sales | `robots.txt: User-Agent: * / Disallow: /`. Ask the city's permission or FOIA. |
| Alexandria tax history | ✗ robots-disallowed (V) | `tax_history.php?accountno=` | — | Same host. FOIA. |
| Alexandria APEX | ✅ unofficial API (V) | EnerGov `POST …/api/energov/search/search` (tenant APEX), keyword = account number | 26–47K POSTs. A date-only query is not working yet. | No robots.txt. Undocumented, so keep the rate low. |
| Alexandria buildings | ✅ API (V) | `geoportal…/Building/FeatureServer/1` (YEARBLT, STORIES, BSIZE, BUNITS) | 107,581 rows | Planning attributes, not CAMA. Needs a spatial join. |
| Arlington property search | ✗ blocked (V) | 403 from Azure Application Gateway | — | Not needed; datahub-v2 has the same data |
| Arlington CAPP | ✗ (V) | Stateful JS app | — | FOIA |
| Arlington Accela | 🔁 (V) | ACA search, then ExportCSV | per date window | datahub-v2 `api/Permit/Permit` already covers it |
| Falls Church assessment (actDataScout) | ✗ blocked (V) | Azure WAF JS challenge (403); old Vision URLs redirect there | — | FOIA to realestateassessor@fallschurchva.gov |
| Falls Church permits | ✗ none exists (V) | Applications are emailed as PDFs. A `PermitsROW` layer has 260 right-of-way permits from 2017. | — | FOIA |
| VGIN Local Schema Tables | Little help (V for the 2022 mirror, I for 2026) | The 373 MB official zip (item `523d89ebf23d4d84957f9fe5b9158bd9`, Sep 2026) | — | The 2022 tables carry only GIS parcel fields. Alexandria has owners. None has values or sales. |

## Evidence ledger (key claims)

| ID | Claim | Status | Source | Confidence |
|---|---|---|---|---|
| C1 | Loudoun publishes a monthly CSV of all parcels with owner and tax amounts | Fact | Directory listing at `interwapp22.loudoun.gov/TreasurerPublicFiles/public/`, re-checked directly. Partial (206) fetch of the CSV header plus the layout xlsx. | High |
| C2 | LandMARC Permits Issued has 568,228 rows, anonymous | Fact | `returnCountOnly`, re-checked directly | High |
| C3 | City of Fairfax search grid returns about 9.7K parcels in 194 pages with owner, value and last sale | Fact | One probe pass, page 1 fetched | Moderate. Repeated paging is untested; the session may expire. |
| C4 | Arlington Property API redacts owner names | Fact | Our own `samples/arlington_re_property` (100 of 100 rows "Redacted") | High. **Corrects the earlier README.** |
| C5 | Alexandria robots.txt disallows all | Fact | `realestate.alexandriava.gov/robots.txt`, re-checked directly | High |
| C6 | Fairfax iCARE has no robots.txt and needs no session | Fact (single pass) | Probe fetches | Moderate. Rate limits at volume are unknown. |
| C7 | Accela search results are capped at about 100 | Inference | The "100+" display text | Low. Test before relying on it. |
| C8 | The 2026 VGIN local-schema zip lacks values and sales for these six | Inference | The 2022 mirror tables match each city's GIS layer | Moderate. Download the zip to confirm. |

## Collection-ethics notes

- **Followed:** robots.txt, WAF challenges, reCAPTCHA, logins and app-embedded credentials (the Development Tracker proxy). Anything behind those is marked blocked or request-only.
- **Owner names:** iCARE and the Alexandria/City of Fairfax pages honor owner opt-outs. A scraped copy is a snapshot that won't pick up later opt-outs, so refresh it and honor removals.
- **Scale:** the per-parcel options (Loudoun 133K, Fairfax County 370K) put real load on small county servers. Run them off-peak at 1 request/s or slower with an identifying User-Agent. Ask the county first, or FOIA, where a bulk extract would serve better.

## Prioritized next steps

1. **Collect now (cheap, official):** the Loudoun Treasurer CSV, LandMARC permits, Fairfax MAR, Fairfax Approved Site Records, City of Fairfax GISCAMA, and Alexandria building footprints.
2. **Short scripted pulls (low volume):**
   - City of Fairfax assessment grid (about 195 requests)
   - City of Fairfax Accela CSV by month
3. **FOIA / permission requests:**
   - Alexandria: a sales and CAMA extract, or permission for the `recent.php` sweep
   - Falls Church: a CAMA and sales extract
   - Fairfax County: an owner extract, plus a public view of the Development Tracker layers
   - Treasurer files for Alexandria, Arlington and the City of Fairfax
4. **Large per-parcel crawls, only if FOIA fails:** Loudoun iasWorld (sales and building) and Fairfax iCARE (owners).
