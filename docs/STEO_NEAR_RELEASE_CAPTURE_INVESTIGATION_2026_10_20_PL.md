# STEO independent near-release capture investigation — 2026-10-20

## Purpose / boundary
Read-only investigation of **independently timestamped original XLSX captures close to actual STEO publication days**. This note does not certify first-release bytes, claim a tradable backtest, change any strategies, or write Neon. No old models re-fitted. `M1–M3=HOLD_NO_CHANGE`.

## Baseline (already proved, NOT new near-day evidence)
The existing [36/36 report](STEO_INDEPENDENT_ZENODO_36_BYTE_MATCH_2026_10_20_PL.md), [real run 39444963696](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963696), and [Catalyst Cooperative Zenodo record 15386905](https://zenodo.org/records/15386905) demonstrate May-2025 independent ZIP copies identical at original XLSX SHA-256 level to the files downloaded from EIA in October 2026. They do **not** establish raw bytes as actually published on the original 2022–24 release days.

## Candidates reviewed 2026-10-20
| Issue | Official EIA release date | First-issue original SHA-256 from near-day independent capture | WTI/Brent Table 2 comparison | Outcome |
| --- | --- | --- | --- | --- |
| `nov23` | 2023-11-07 | Not recovered | Not possible without captured original workbook | **UNKNOWN** |
| `jan24` | 2024-01-09 | Not recovered | Not possible without captured original workbook | **UNKNOWN** |
| `jan25` | To be independently reconfirmed before acceptance | Not recovered | Not possible without captured original workbook | **UNKNOWN** |

The [official EIA STEO archive](https://www.eia.gov/outlooks/steo/outlook.php) exposes release dates and XLSX links, but contemporaneous web pages are **not** independently timestamped original file captures. The 2023 November notice documents reposting of other tables, without establishing unchanged WTI/Brent Table 2 or original XLSX byte status; see [notice register](STEO_OFFICIAL_ERRATA_PROVENANCE_2026_10_20_PL.md).

**Internet Archive Wayback CDX**: attempted public index URL query for `jan24_base.xlsx`; client returned *not accessible*. **Not evidence that no capture exists**. No replay WARC/HTTP body, timestamp, or binary SHA-256 recovered. Therefore no hash equality or WTI/Brent equivalence conclusion.

**Common Crawl**: [official index catalogue](https://index.commoncrawl.org/collinfo.json) and [format/access documentation](https://www.commoncrawl.org/get-started) confirmed that 2023–2024 index and WARC collections exist and expose timestamped crawls in principle. Attempted `CC-MAIN-2024-10-index` query for the `jan24_base.xlsx` exact URL, but the index query endpoint was not accessible in this browsing client. The mere existence of a crawl index is **not evidence it contains this Excel attachment**. No relevant index record, WARC payload, SHA-256, or Table 2 values were obtained.

A discovered third-party GitHub STEO scraping project contains processed artefacts, not a verified dated original-month XLSX capture with independent binary receipt. It has **not** been treated as original byte evidence.

## Acceptance gates for any future promotion from UNKNOWN
1. Verify curator independence, actual immutable archive/capture timestamp and canonical captured target URL against official EIA release day; distinguish dated index metadata, redirect, link-only HTML and genuine binary HTTP 200 payload.
2. Retrieve the **actual archived XLSX response body**, not today's live EIA bytes or a regenerated workbook. Preserve response metadata, exact byte length and SHA-256, and evidence URL/record ID.
3. Compare with the published original-source SHA list in [36/36 report](STEO_INDEPENDENT_ZENODO_36_BYTE_MATCH_2026_10_20_PL.md), then parse `2tab` for `WTIPUUS` and `BREPUUS` values using the existing source reader; record distinct byte and semantic comparison outcomes.
4. Only record `PASS` for the narrowly supported claim (for instance, first independently archived copy **after** release), never infer exact day-one publication authenticity from a capture days/weeks later.
5. A missing, unavailable or metadata-only capture stays `UNKNOWN` rather than `PASS` or `FAIL`. Keep historical `PIT_CERTIFIED=false` unless a defensible issue-day provenance chain truly exists.

## End-of-session operational facts
Initial repo head inspected: `fe986b23b47d080302b253eb87bbf7a10a93b0d4`; recent listed actual [source workflow 39444963696](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963696) SUCCESS; [main regression 39444963465](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963465) SUCCESS; [PR CI 39444788790](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444788790) SUCCESS. At inspection, open PR #1; open issues #2, #3, #4, #22. No new data-source CI run launched, no file hash claims invented. This research note is documentation-only, submitted through PR for review. No Neon writes, no permissions/secrets/schedules/paid services, no trades or model tuning. Closed MyDevil+Mac backup unchanged.
