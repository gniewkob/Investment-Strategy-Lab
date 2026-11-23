# Offline equity reference bridge

`scripts.paper_equity_reference_bridge.compare_with_equity_marks(manifest, marks)`
connects caller-supplied monthly EUR equity marks and PLN per EUR reference FX
to ASSET_A in the v0.2 paper engine. It is an experimental research bridge,
not a verified Vanguard adapter. It does not download, authenticate, license,
or distribute market data. It accepts only `UNVERIFIED_EXTERNAL` manifests;
the other two assets, strategy weights and fees remain caller-supplied and
unverified. The same-month dates may differ by up to seven calendar days;
there is no exchange calendar, month-end, completeness or publication-time
verification. The product is a hypothetical reference mark, not a trade fill.
The input and mark fingerprints prove neither provenance nor usage rights.
The result stays retrospective, non-executable and non-PIT; 100 PLN per month
is specified in the manifest, not a live account instruction. Taxes, spreads,
FX execution, liquidity and market timing are not represented.

The issuer's Dutch professional product page separates USD NAV from EUR market
price and lists a EUR VWCE quotation on multiple exchanges, while the fund's
base currency is USD. Its share-class inception date is 23 July 2019. The page
also shows 25 July 2019 as a general listing date and 16 February 2023 next
to its EUR historical price table. These dates do not establish the first
available observation for any particular exchange. The displayed download
count alone does not prove an uninterrupted market-price series, file format,
exchange attribution or availability on the historic decision date.

Vanguard Netherlands terms permit certain personal, informational,
non-commercial use but also restrict copying and derivative works and repeated
automated access. Permission for this project's calculation and distribution
is not established. No issuer data is included in this repository. Before
claiming a verified adapter, establish applicable rights for the intended use,
obtain a legitimately accessible original file, verify its format, exchange,
currency, date coverage and price semantics against issuer documentation, and
test parsing and receipts without publishing restricted data. Also establish a
permitted FX source and aligned dates. Later downloads do not establish PIT.

Source references: issuer homepage https://www.nl.vanguard/ (product 9679 and
terms and conditions); https://www.ecb.europa.eu/ (euro reference rates are
informational rather than transaction rates).
