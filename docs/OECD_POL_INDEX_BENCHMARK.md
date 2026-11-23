# Poland OECD share-index benchmark: offline research only

Status: **NON_EXECUTABLE_RESEARCH_BENCHMARK**. M1/M2/M3 remain HOLD_NO_CHANGE. The source is Polish equities, not global equities. Index levels are dimensionless (2015 = 100), not PLN prices, ETF NAV, execution prices or certified total returns. No FX is needed. This retrospective arithmetic assigns each hypothetical PLN 100 contribution `100 / index` notional units and marks their sum at the final monthly level. Cash is 4,800 PLN. It excludes dividends, costs, taxes and timing feasibility, and is not a strategy return or recommendation. Monthly averages cannot establish an executable price or when information was known; historical PIT is not certified.

## Source and rights

The fixed query selects `OECD.SDD.STES:DSD_STES@DF_FINMARK(4.0)`, `POL.M.SHARE.IX`, January 2022–December 2025. Current CSV metadata identifies Poland, monthly, share prices, index, national methodology, unit multiplier zero and base 2015. [OECD methodology](https://www.oecd.org/en/data/indicators/share-prices.html) describes monthly observations as **normally** simple averages of daily closing values; it does not, by itself, prove the aggregation method for this exact modern series. [Older OECD country metadata](https://www.oecd.org/content/dam/oecd/en/publications/reports/2000/08/main-economic-indicators-sources-and-definitions-2000_g1ghgf5c/9789264187900-en.pdf) describes an older Polish series sourced from the Bank of Poland and Warsaw Stock Exchange; do not assume it proves the current series provenance or rights.

[OECD terms](https://www.oecd.org/en/about/terms-conditions.html) permit data processing with attribution subject to series-specific restrictions and third-party ownership. **UNKNOWN:** the exact current Polish series' upstream ownership, third-party restrictions, and permission for the proposed processing and distribution. Public accessibility and a checksum do not establish those rights. Therefore no real-data benchmark is supplied or claimed. Confirm series-specific source metadata and obtain any required owner permission before processing or distributing actual observations. Citation when authorized: OECD (year), Financial market (DSD_STES@DF_FINMARK), share prices, source URL, accessed date; comply with any additional attribution or downstream terms.

## Bounded acquisition when rights are established

Manual one-shot transport, no retries, cookies, impersonation or 403 bypass; stop on a 403/429 or any error. Do not schedule. Record the actual UTC completion time and original bytes and SHA-256; never substitute an old receipt. The URL is fixed in `scripts.oecd_pol_benchmark.URL`. Example from the repository root:

```sh
url=$(python3 -c 'from scripts.oecd_pol_benchmark import URL; print(URL)')
curl --fail --silent --show-error --connect-timeout 10 --max-time 30 --max-filesize 1000000 "$url" -o oecd-pol.csv
shasum -a 256 oecd-pol.csv
python3 -m scripts.oecd_pol_benchmark --input oecd-pol.csv --retrieved-at-utc YYYY-MM-DDTHH:MM:SSZ
```

The timestamp is caller supplied and must be the actual UTC retrieval time, not the observation date. A hash proves only byte identity, not source authenticity, licensing or PIT. Protect acquired data according to confirmed rights; do not commit it automatically. A prior one-off retrieval on 2026-11-23 produced 12,619 bytes, SHA-256 `d7ece9e69cff2af2709ffb5220e2521c7eb75ac12a636bcf6a87e6a04e607a5b`; later responses may legitimately differ. The offline parser validates the fixed series metadata, exactly 48 unique months and finite positive index levels; it rejects changed metadata, missing periods, duplicates and invalid receipts. Parsing does not verify caller-provided provenance or permission.
