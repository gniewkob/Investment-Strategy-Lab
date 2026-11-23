# Public global equity source audit — 2026-11-23

Decision: **no qualified monthly global-equity source selected yet**. This audit
is a source-screening result, not legal advice or a claim that the sources are
unusable for all purposes. No raw series was downloaded or redistributed.

| Candidate | Evidence and limitation | Decision |
| --- | --- | --- |
| [Vanguard FTSE All-World UCITS ETF](https://www.nl.vanguard/professional/product/etf/equity/9679/ftse-all-world-ucits) | Accumulating global equity fund; issuer distinguishes share-class NAV in USD from exchange prices in EUR. [Applicable site terms](https://www.nl.vanguard/professional/terms-and-conditions) restrict derivative use and repeated automated access. The original NAV series, format, coverage and permission for the intended processing and publication were not established. | Do not claim an authenticated NAV adapter or redistribute its data. |
| [Fama/French developed-market factors](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_3developed.html) | Monthly USD returns include capital gains and dividends. Market return can be derived from the market excess return plus the risk-free rate, but this is a developed-market research portfolio, not an ETF NAV or all-world investable total return. The [data library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) displays a copyright notice; an explicit licence for the intended processing and distribution was not identified. | Promising research alternative; rights and original-file validation remain open. |
| [World Bank S&P Global Equity Indices](https://data.worldbank.org/indicator/CM.MKT.INDX.ZG) | The indicator page states CC BY 4.0 and attributes the underlying index provider. It is **annual percentage change**, not a monthly NAV series. [Dataset terms](https://www.worldbank.org/ext/en/legal/terms-conditions/datasets) also apply and preserve exceptions for specially labelled datasets. | Inadequate for monthly contributions; do not interpolate months. |

[NBP API](https://api.nbp.pl/) exposes historical table A mean exchange rates.
A quoted PLN per USD rate would be needed for a USD NAV or USD research
portfolio; PLN per EUR must not be substituted merely because a fund is listed
in EUR. Reference rates are not execution rates. For a real adapter, verify
coverage, month boundaries and date alignment against actual responses, record
retrieval time and hashes, and keep source values within their permitted scope.

A date-only FX guard cannot establish that the rate was published before a NAV
or decision on the same day. Historical publication availability and source
revisions remain unverified; no PIT certification follows. Fund fees may be
reflected in NAV; broker charges, FX spreads, tax and executable market prices
are separate and must not be silently treated as included.
