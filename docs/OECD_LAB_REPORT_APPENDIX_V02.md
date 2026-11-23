# OECD POL share-price index — offline appendix for ISL reports (v0.2)

**Status:** `NON_EXECUTABLE_RESEARCH_BENCHMARK`. This extends the existing
`oecd_pol_benchmark.py` parser; it **does not** make the OECD series suitable for
M1/M2/M3 or attest source rights. It generates local aggregate-only JSON and
an independent Markdown report, optionally appending the benchmark to an
existing ISL research report **without modifying the original file**.

## Data contract

- Exactly 48 monthly observations, 2022-01 through 2025-12; country `POL`,
  `MEASURE=SHARE`, `UNIT_MEASURE=IX`, `BASE_PER=2015`, not seasonally adjusted.
- Index units are dimensionless. The 100 PLN/month calculation is a fictional
  *index-unit equivalent*, **not** a tradable Polish-share instrument or a PLN
  transaction price; no dividends/total-return, taxes, FX, fees, historical
  execution fill or historical first-publication proof are supplied.
- Input is an original, independently acquired local OECD SDMX CSV, not network
  data. Both the supplied SHA-256 and the original parser's metadata/coverage
  validation are mandatory. A SHA is byte identity **only**, not an authenticity,
  rights or timestamp certificate. Caller supplies the **actual UTC** retrieval
  timestamp; no dates are backfilled.
- All outputs explicitly set `rights_specific_to_series_verified=false`,
  `upstream_owner_verified=false`, `actual_aggregation_method_verified=false`,
  `historical_point_in_time_certified=false`, `qualified_asset_series=[]`,
  `m1_m2_m3=INSUFFICIENT_DATA_HOLD_CASH`, and zero orders/database writes.
- Never publish the raw 48 observations as part of the generated report.

## Manual offline workflow (only with locally acquired data and appropriate rights)

```bash
python3 -m scripts.oecd_lab_report_v02 \
  --input /private/oecd-pol-2022-2025.csv \
  --raw-sha256 '<independently verified SHA-256 of exact local CSV bytes>' \
  --retrieved-at-utc '2026-11-23T12:00:00Z' \
  --base-report /private/existing-lab-research_report.md \
  --out-dir /private/isl-oecd-lab-appendix
```

Replace the illustrative timestamp and all local paths with **actual** values.
The output directory must not exist. It contains only
`oecd_research_appendix.json` and `research_report.md`. The optional original
lab report is read-only; omitting `--base-report` creates a standalone benchmark.
The input file and original report are bounded and may not be symlinks.

## Rights and methodological evidence

- OECD indicator **Share prices**, [definition](https://www.oecd.org/en/data/indicators/share-prices.html):
  an index of share **prices**, not dividends-inclusive return; monthly data are
  **usually**, not necessarily for each national series, arithmetic averages
  of daily observations. **Classification:** source methodology/general guidance,
  not proof of POL's exact upstream method.
- OECD [Terms & Conditions, section 3 Data](https://www.oecd.org/en/about/terms-conditions.html):
  reuse is generally permitted with attribution **subject to specific
  restrictions and third-party rights**; users must examine metadata/source.
  **Classification:** contractual policy, conditional general permission, not
  a series-specific licence clearance.
- FRED secondary [SPASTT01PLM661N metadata](https://fred.stlouisfed.org/series/SPASTT01PLM661N):
  confirms `POL`, `SHARE`, `IX`, monthly, 2015=100 and OECD source attribution;
  does **not** independently establish 2022–2025 source bytes, publication
  vintages, POL upstream ownership or the exact aggregation method.
- Expected source URL is fixed by `scripts.oecd_pol_benchmark.URL`. A previous
  independent observation reported a 12,619-byte original CSV with SHA-256
  `d7ece9e69cff2af2709ffb5220e2521c7eb75ac12a636bcf6a87e6a04e607a5b`.
  **This iteration did not reacquire those bytes:** OECD endpoint access through
  this environment failed at DNS / browser cache, not a verified 403 or a
  parser failure. No source-backed value is computed or published here.

Before actual-source processing or redistribution, verify the source tab of the
specific OECD POL series and obtain any required owner permission. Merely
showing a public web URL, mirrored FRED series or historical SHA is insufficient.

## Verification in this iteration

- Existing `scripts/oecd_pol_benchmark.py` original Git blob SHA-1 reproduced
  exactly in offline test workspace: `456cb8c7359c1c69119576d38754ba9dd6c8f0b9`.
- New appendix: **8 synthetic offline tests PASS**, including CLI round-trip,
  source SHA mismatch, missing/incorrect series, bad timestamp, symlink,
  preexisting output and nonmutation of original research report.
- No original OECD observations tested. Full repository regression and GitHub
  hosted exact-SHA CI remain separate release gates. Do not mark actual-source
  research, model admission, merge or deployment DONE based on these tests.
