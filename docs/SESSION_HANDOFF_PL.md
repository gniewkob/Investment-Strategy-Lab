## 2026-10-24 — Opcjonalne powiadomienia ntfy na osobnym kanale (lokalna poprawka)

Użytkownik wybrał osobny kanał ntfy dla Investment Strategy Lab. Moduł
`scripts.ntfy_notifications` dostarcza stałe komunikaty o awarii, nieaktualności
i przywróceniu działania historii Coinbase oraz monitoringu portfela. Brak sald,
adresów, identyfikatorów kont, transakcji i surowych błędów w treści wiadomości.
Kontrakt: POST UTF-8 na `https://ntfy.sh/<topic>`, tytuł aplikacji, priorytet high
dla problemów/default dla recovery i testu, timeout 8 s, brak proxy/przekierowań.
Wymagane HTTP 200 oraz ograniczone potwierdzenie JSON event/topic/id.
Dokumentacja dostawcy: https://docs.ntfy.sh/publish/ . Orbit discovery nie
zwrócił pasującego API ntfy; kontrakt sprawdzono w oficjalnej dokumentacji.

Konfiguracja zawiera wyłącznie `topic`, jest prywatnym plikiem 0600 poza Git.
Inicjalizacja generuje nowy losowy kanał z 192 bitami losowości, bez nadpisywania
pliku. To kanał anonimowy: znajomość jego nazwy umożliwia dostęp, więc nazwa
pozostaje lokalnie, nigdy w logach, czacie, repo lub argumentach procesu.
Nie kopiujemy kanału ani sekretów OpenBrain.

Po zatwierdzeniu aktywacji i przejściu istniejącej bramki PR/CI operator:

```sh
# /PRIVATE oznacza istniejący katalog 0700 poza repozytorium.
python -m scripts.ntfy_notifications --config /PRIVATE/ntfy.json --init
```

Operator odczytuje `topic` lokalnie w prywatnym pliku i dodaje subskrypcję
w ntfy iOS (serwer `https://ntfy.sh`). Następnie wykonuje:

```sh
python -m scripts.ntfy_notifications --config /PRIVATE/ntfy.json --test
```

`NTFY_SERVER_ACCEPTED_TEST` potwierdza akceptację serwera; odbiór na iOS wymaga
potwierdzenia na urządzeniu. Do istniejących poleceń watchdogów
`scripts.autonomous_history_watchdog` i `scripts.autonomous_portfolio --check-health`
dodać `--ntfy-config /PRIVATE/ntfy.json`. Zachować wszystkie dotychczasowe argumenty,
runtime i harmonogramy. Bez tej opcji działanie pozostaje lokalne, jak dotąd.

Deduplicacja korzysta z istniejącego znacznika każdego watchdoga: cicho przy
niezmienionym stanie, komunikat przy zmianie i recovery. Błąd ntfy nie zatwierdza
znacznika, więc następna kontrola ponowi próbę; lokalny alert nadal jest wywoływany.
Awaria Notification Center nie blokuje udanej wysyłki ntfy. Możliwe powtórzenie
po utracie odpowiedzi HTTP lub błędzie zapisu znacznika (brak gwarancji exactly-once).
Rollback: usunąć wyłącznie `--ntfy-config` z poleceń watchdogów, zachować stan.

Weryfikacja lokalna obejmuje syntetyczny transport HTTP, prywatne uprawnienia,
odrzucanie przekierowań, redakcję błędów, CLI, retry, deduplicację i recovery obu
watchdogów. Wynik: 42/42 testy integracji i watchdogów PASS; pełny zestaw
w tymczasowej czystej kopii Git i Python 3.14 z zależnością psycopg zgodną z CI:
549 testów, OK (1 pominięty). Czysta kopia była potrzebna istniejącemu testowi
atestacji wydania, który celowo odrzuca checkout z niezapisanymi zmianami.
Aktywacja, kanał rzeczywisty, zmiany LaunchAgents, live POST, odbiór
na iPhonie, publikacja poprawki i CI dla tej poprawki pozostają PENDING.
Nie wykonano operacji finansowych ani odczytu kluczy lub konfiguracji kont.

## 2026-10-23 — Live schema handling: preserve generic tx events as unclassified

The read-only BTC polling service and independent health agent were activated
after PR #69 merge `0373914242e9dd8395e9a3401d8966b64b80f2d8`; an unattended
second 300-second live cycle and second watchdog check passed. Sanitized
deployment evidence is recorded in PR #69 and the private local deployment receipt.

Next source review identified a schema gap: documented Coinbase generic `tx`
events must not disappear when filtering receive-only history. New importer
output retains them as UNCLASSIFIED_ACCOUNT_EVENT with signed account direction,
without deposit/funding/trading inference. Old capture tx amounts omitted by the
previous minimizer stay null/UNKNOWN, never zero. New runtime retains minimized
amount/currency for tx and signals source_schema_status. Receive comparison
explicitly remains RECEIVE_ONLY; generic records are not a new-funding ledger.

476 offline tests PASS locally, including seven new generic-event/legacy-upgrade
tests. Final PR CI and a private live upgrade must pass before claiming deployment.
No account values, transaction examples, keys or IDs are included here.
Blockchain linkage remains unestablished; no hash/network/recipient is guessed.
Existing single-account scope, view-only gate and zero financial operations remain.

## 2026-10-23 — First BTC history live canary PASS; health supervision prepared

User completed native private setup and selected the BTC account. The waiting
controller returned `PRIVATE_SETUP_COMPLETED_RUNNING_LIVE_CANARY` and
`LIVE_CANARY_PASS`. Sanitized inspection confirms private config/checkpoint/health
files (0600) and `HISTORY_READ_OK`. Zero financial operations. No secret, account
ID or transaction data entered chat, logs or GitHub. Do not request connection
authorization or key provisioning again; they are complete.

Next step under the user's autonomous-system goal is supervised 300-second
history polling and an independent freshness watchdog. A separate evidence and
alerting review is recorded in the runbook before LaunchAgent activation.
Watchdog detects failed/stale/invalid health, is quiet for stable health and
notifies locally on meaningful change/recovery. It never reads config,
credentials or checkpoint. 469 offline tests PASS locally (five new watchdog
tests). Final CI and actual service status must be checked before claiming
installation/autostart. Runbook: [autonomous reader](AUTONOMOUS_READ_ONLY_HISTORY_PL.md).
Scope remains the single selected BTC account. Blockchain evidence is
NOT_CONFIGURED; full autonomous blockchain/exchange reconciliation remains false.

## 2026-10-23 — Live read-only activation authorized; local secret provisioning required

User explicitly answered YES to local Coinbase connection with view only,
without trade/transfer or secrets in chat. **Do not ask for that permission again.**
Typical local runtime/config/export locations and Coinbase/CDP environment names
were checked without reading secret values; no existing key/config was found.
An exact merged PR #67 checkout and pinned SDK environment were provisioned under
the user's private Application Support runtime. No account access or service
startup has yet occurred; an operator-managed key file remains required.

Follow-up adds native local file/account selection, strict view-only preflight,
bounded GET /v2/accounts discovery and private config/key copy. Discovery retains
only UUID/currency locally, never balances/names in console/chat. Existing config
is not overwritten; cancellation/invalid account/broad key abort setup. Managed
copy is rolled back if config creation fails. No key is created in the portal.
464/464 tests PASS locally (seven new setup tests); final CI must pass before
deploying this setup revision. Next: choose the ECDSA view-only export locally,
complete setup, run one live canary, then verify supervised polling/health.
No real transfer/order, DB write or privilege change performed.

## 2026-10-23 — Autonomous read-only polling prepared; live activation pending

[PR #66](https://github.com/gniewkob/Investment-Strategy-Lab/pull/66) merged as
`9234e6c77bc348869499eaa20ca7c15162f8f0dd` after 446 local offline tests and
[CI success](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39927574920).

User clarified the goal is a working autonomous system. Official docs confirm
Coinbase App GET transactions with view permission; the chat connector lacks
that operation. A new local polling runtime is prepared with exact GET-path
allowlisting, view-only/expected-portfolio preflight before every cycle,
bounded pagination, local ECDSA P-256 SDK signing, atomic private checkpoint,
health expiry, process lock, restart comparison and recovery after failed reads.
No actual account credentials have been connected or created. Live access is
disabled unless the explicit runtime flag and private operator config are supplied.

**457/457 offline tests PASS locally**, including 11 new runtime tests and real
SDK signing with an ephemeral test key. Separate synthetic 3-cycle canary PASS:
success/outage/recovery, state preserved, zero real HTTP/financial operations.
No claim of live Coinbase verification, deployed daemon/autostart or authenticated
blockchain-to-exchange linkage. `full_autonomous_reconciliation_ready=false`.
See [deployment gate, contracts and rollback](AUTONOMOUS_READ_ONLY_HISTORY_PL.md).

Next: pass final PR CI, approve the concrete live read-only activation separately
under AGENTS.md's credential/network boundary, configure a restricted key privately,
verify one live cycle, then supervise polling and stale-health alerting. Do not
ask for secrets in chat or reuse connector credentials. No trades/transfers,
database changes, role changes or system schedule were performed.

## 2026-10-23 — Bidirectional coverage merged; compare private receive captures

[PR #65](https://github.com/gniewkob/Investment-Strategy-Lab/pull/65) merged as
`57cedf61c986ec4dbdeb3f7a5f795ab5b6680dff` after **439/439 tests passed locally**
and [CI succeeded on head 3e2a34d](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39926731774).
GitGuardian passed; no review comments were present at the merge check.

Follow-up adds optional `--previous-history` to the private offline review CLI.
Both captures validate independently and must belong to the same account with
strictly increasing capture times. Stable receive IDs distinguish unchanged
records, newly observed records, records absent from the newer capture, status
changes and conflicts in amount/asset/event time. Decimal/time formatting alone
does not create changes. Newly observed never means new external funding;
missing never means deleted; no balance adjustments or ledger entries occur.
The old report is unchanged without the optional argument.

**446/446 local offline tests passed**, including seven new comparison/CLI tests.
The follow-up CI must pass on its own head before merging. Contract, privacy,
limitations and rollback: [deposit evidence runbook](DEPOSIT_EVIDENCE_RECONCILIATION_PL.md).
Authenticated live history and receive-to-chain linkage remain **PENDING**.
No account calls, transfers/trades, DB writes, secrets/ACL changes or schedules.

## 2026-10-23 — Coinbase history review fixed; bidirectional evidence coverage

[PR #64](https://github.com/gniewkob/Investment-Strategy-Lab/pull/64) merged as
`b785291022f1c9dc005246f20dacdfd7d582c994` after correcting provider timestamp
offsets raised in review. Provider event dates normalize to UTC; naive/future
events remain rejected. **433/433 offline tests passed locally** and
[CI passed on reviewed head 0724f68](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39926339744).

Follow-up: `reconcile_inventory()` preserves the existing `reconcile()` output
and adds operator deposit records with no supplied chain/hash counterpart,
explicit statuses and record-coverage counts. The private CLI adds
`operator_evidence_coverage`, preserving `operator_evidence_reconciliation`.
Shared chain/hash counts do not imply amount/recipient agreement; different
networks remain unpaired. Receive-history records never fill evidence gaps.
**439/439 offline tests passed locally**, including six new coverage/regression
tests; CI for the follow-up must pass on its own head before merging.
See [contract and rollback](DEPOSIT_EVIDENCE_RECONCILIATION_PL.md).

Authenticated live deposit access and receive-to-chain linkage remain **PENDING**.
No account calls, financial operations, DB writes, credentials, ACL changes or
schedules. All inputs/results are operator supplied and provenance unverified;
unmatched records are never classified as new external funding or added to balances.

## 2026-10-23 — Deposit reconciliation reviewed; private history import

[PR #63](https://github.com/gniewkob/Investment-Strategy-Lab/pull/63) merged as
`bb3cce78b28a655ad6ea5b00933ebd8ab3e9cffd` after input-validation fixes,
**420/420 local offline tests** and [full PR CI success](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39925195281)
on head b94e452; GitGuardian passed. Initial local run without psycopg failed;
the successful rerun used a temporary environment with the existing CI dependency.
No live DB or Coinbase check is implied by that result.

The follow-up adds `scripts/coinbase_deposit_history.py`: private **offline**
Coinbase App List Transactions capture validation, receive-only minimized output
and a separate operator-evidence reconciliation section. See
[contract, private CLI and limitations](DEPOSIT_EVIDENCE_RECONCILIATION_PL.md).
Current connector catalog lacks deposit-history reads. Provider docs do not
guarantee network hash/name for receive; no address/network/symbol mapping is
invented. Automated authenticated history access and receive-to-chain linkage
remain **PENDING**, with provenance always unverified. Do not substitute balances,
fills, Coinbase Exchange APIs or operator assertions for authenticated credit proof.
No account calls, financial operations, Neon writes, secret/ACL changes or schedules.
Private source captures/reports must never enter this public repository or Actions.
Rollback: revert the follow-up; PR #63 comparator remains independent.

## 2026-10-20 — HANDOFF PERSISTED TO OPENBRAIN_REMOTE + AGENT RESUME DOC

User explicitly requested durable state both in GitHub and **OpenBrain_remote** (not the local OpenBrain connector). OpenBrain_remote domain `build` memory **`5a8bd21b-f2a6-4bda-9349-2ccb11bdb86f`** titled **Investment Strategy Lab — verified STEO source provenance & agent handoff (2026-10-20)** was written successfully. When resuming, use OpenBrain_remote `brain_get` ID above or `brain_search` domain build. It covers confirmed prior 58 EIA STEO historical editions, 316 retrospective WTI/Brent forecast-reference pairs, 104 as-of walkforward, and most recent **36/36 byte-identical original XLSX** 2022–24 in independent May-2025 Catalyst Cooperative Zenodo archive compared with Oct-2026 EIA, plus strict no historical first-publication-day PIT certification.

**Canonical, copyable agent instructions:** [docs/AGENT_RESUME_PROMPT_2026_10_20_PL.md](AGENT_RESUME_PROMPT_2026_10_20_PL.md). It points to the actual GitHub docs/source SHA/run evidence in reading order, all safety boundaries and the next source-provenance task. **Always read actual `main` and CI before acting; do not rely on this snapshot as evidence that future repo state is unchanged.** Closed user-confirmed MyDevil/Mac EIA backup stays CLOSED, M1–M3 `HOLD_NO_CHANGE`; research/paper only, no real orders, Neon writes, account roles/ACL, new secrets, schedules, paid WORM or re-fitting historical labels.


## 2026-10-20 — INDEPENDENT THIRD-PARTY 2025 DEPOSIT CONFIRMS 36/36 ORIGINAL EIA STEO XLSX BYTES

**MAJOR VERIFIED NEW SOURCE EVIDENCE:** Catalyst Cooperative's independent [Zenodo EIA STEO raw archive v2.0.0, record 15386905](https://zenodo.org/records/15386905), **published May 26, 2025**, contains untouched original monthly EIA XLSX raw binaries (separate PDF + XLSX for each month) in annual ZIP partitions for 2022, 2023, 2024. [Real May2025-vs-Oct2026 original-source pilot #39443655584](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39443655584) PASS; PR #50 merged `70150d417242fbe828292090070a67dc5ea6d248`. Jan24/Nov24/Dec24 EIA original XLSX SHA-256 EXACT MATCH to independent older 2025 depositor copies.

**Full result:** [PR #51](https://github.com/gniewkob/Investment-Strategy-Lab/pull/51) merged `f4a6bc3f396b6b09c12e98adac700fd3e43c11a2`; [PR CI #39444788790](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444788790) **290/290 pure offline tests PASS + 3/3 disposable PostgreSQL PASS**, post-merge main regression [#39444963465](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963465) SUCCESS. [Actual source job #39444963696](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39444963696) **SUCCESS**: **3 independent Zenodo 2025 original annual ZIP archives** source years 2022, 2023, 2024, **all 3 declared 2025 ZIP MD5 match**, exact original XLSX SHA equality to the separately previously captured EIA Oct2026 raw binaries: **2022 12/12, 2023 12/12, 2024 12/12 = 36/36 BYTE IDENTICAL, ZERO DIFFERENCES**. [Full 36 original XLSX relative member names, original SHA, 3 ZIP digests and proof limitations](STEO_INDEPENDENT_ZENODO_36_BYTE_MATCH_2026_10_20_PL.md). New no-side-effect `scripts/steo_zenodo_vintage_crosscheck.py` + synthetic offline source-integrity/tamper/anti-PIT tests; one-shot real-source workflow no persistence.

**DON'T OVERSTATE:** 2025-deposited exact source bytes prove independent **2025 snapshot original XLSX equality to October 2026 EIA**; they **DO NOT prove these bytes were public on exact official 2022–2024 original release days**, and an original vintage may have been revised before May2025. Original historical publication bytes `PIT_CERTIFIED=false`. Neither matching SHA nor EIA errata notices can promote 316 historic STEO forecast/reference comparisons from retrospective descriptive research to investable trading backtest. No Neptune/Neon writes, roles, secrets, schedules, orders, new paid WORM or changes to user-confirmed CLOSED MyDevil+Mac original EIA spot backup. M1/M2/M3 `HOLD_NO_CHANGE`. Further evidence only independent issue-day/near-day source snapshots or truly prospective dated acquisition, not more retrospective model-fitting.


## 2026-10-20 — Official STEO errata notices corroborated; source-vintage historical first-publication PIT still NOT certified

**NEW RESEARCH FINDING / PR #49 MERGED:** [PR #49](https://github.com/gniewkob/Investment-Strategy-Lab/pull/49) squash `f99058fd95c290d2a16381bb5e88a6e1ece14d31`, [PR CI #39441141723](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39441141723) **283/283 offline synthetic tests PASS + 3/3 isolated PostgreSQL PASS**. Added `scripts/steo_official_notice_audit.py`, a strictly OFFLINE **9 hand-verified official EIA notice** register for known Jan2022–Oct2026 **58 archived STEO issues**. Manual source review located hard evidence that EIA **reposted earlier reports** with corrections: Nov2023 Tables 4a/3a/3d ([official](https://www.eia.gov/outlooks/steo/archives/notice_data_11_09_2023.php)); Jun2024 Table10b ([official](https://www.eia.gov/outlooks/steo/archives/notice_data_06_27_2024.php)); Nov2024 Table10b ([official](https://www.eia.gov/outlooks/steo/archives/notice_data_11_14_2024.php)); Jan2025 Table3e and Jan15 report repost ([official](https://www.eia.gov/outlooks/steo/archives/notice_data_01_15_2025.php)). Other EIA notices cover textual republications, Feb2025 PDF-only correction and Dec2025 error planned for next release. **No notice reviewed establishes WTI `WTIPUUS` / Brent `BREPUUS` Table2 change**, yet neither does this certify Table2 unchanged. An archived file under a 2022/2024 month URL today is NOT proof of the exact original byte version publicly accessible on that issue's listed release date.

[Grounded issue/date/url/scope report](STEO_OFFICIAL_ERRATA_PROVENANCE_2026_10_20_PL.md) and offline CLI `python3 -m scripts.steo_official_notice_audit --issue nov23`. All editions report `historical_point_in_time_certified=false`; NO independent historical exact-source XLSX byte snapshot has been verified in this workstream (a public Wayback/CDX lookup could not be accessed from browsing environment — **not** proof there are no such snapshots). Do not infer XLSX republishes from report or PDF-only notice; no known curated notice is not evidence of no revisions. Historical 316 forecast/reference source pairs retain **RECONSTRUCTED/DESCRIPTIVE** evidence status, do NOT recalculate/tune on same samples, no investment return claims.

**Scope/invariants:** no Neon DB reads/writes/migrations, no new role/ACL/secrets, no paid WORM, no scheduled jobs, no real orders, no virtual M1/M2/M3 allocation changes. Operational MyDevil+Mac 6-file source backup previously USER-CONFIRMED CLOSED remains untouched. Next potential evidence task: separately obtain actual time-anchored independent 2022/2023/2024 XLSX original snapshot bytes (Wayback/other legitimate archival curator) and compare RAW+Table2 semantics; otherwise `UNKNOWN` and never certify PIT.

## 2026-10-20 — REAL untouched older 2022–23 STEO regime-stress research SUCCESS (24 old issues + 8 reference-only, 144 pairs)

**Source result:** [official EIA one-time 32-XLSX run #39433488201](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39433488201) **SUCCESS**. Frozen, earlier-unused 24 monthly STEO editions Jan2022–Dec2023 were source-verified and scored, plus exactly 8 Jan–Aug2024 **reference-only** editions for late2023 targets. Original 2024–Oct2026 study unchanged. **144/144** true public archived-XLSX WTI/Brent (+1/+3/+6 month) comparison pairs, 8/8 2024 bridge raw SHA matches prior actual original Oct2026 download receipts (NOT historically first-issued PIT). PRs [#45](https://github.com/gniewkob/Investment-Strategy-Lab/pull/45) compatibility, [#46](https://github.com/gniewkob/Investment-Strategy-Lab/pull/46) older-period evaluation, [#47](https://github.com/gniewkob/Investment-Strategy-Lab/pull/47) old row-3 structural probe, [#48](https://github.com/gniewkob/Investment-Strategy-Lab/pull/48) fixed 2018–2023 year-header validation. [CI #39433327315](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39433327315) 276/276 offline + 3/3 isolated PG PASS. [Complete durable real-source SHA receipts, MAE by 2022/2023](STEO_REAL_2022_2023_FROZEN_HISTORY_2026_10_20_PL.md).

**Frozen source EIA vs same-issue previous-month naive MAE USD/bbl, n24 each:** WTI +1 7.61 vs 9.19, +3 10.44 vs 12.59, +6 10.71 vs 11.82. Brent +1 7.77 vs 9.98, +3 10.77 vs 12.74, +6 11.03 vs 13.06. **Crucial regime instability:** 2022 EIA better in 6/6 asset/horizon groups, but 2023 EIA better **only in 2/6 one-month groups**, naive better in 4/6 longer-horizon groups, consistent with the later 2024–2026 pattern. Thus pooled 2022–23 EIA wins all 6 but **cannot be promoted as timeless, future-predictive edge**. This older set is a previously-unused *past* epoch, not a future chronological holdout, and source bytes retrieved 20-Oct-2026 not independent original as-published PIT. Spot USD/bbl ≠ investable PLN returns; overlapping future months not independent. **No trades, no Neon writes/ACL/roles, no new schedules, paper M1/M2/M3 HOLD_NO_CHANGE.** Existing MyDevil/Mac EIA backup USER-CONFIRMED CLOSED. Avoid further overfitting of prior labels; next research should audit original publication bytes / source QA / future prospective evidence.

## 20.10.2026 — actual source-backed 34/34 STEO robustness PASS: 104 strict matured-label walkforward; dynamic chooser NOT demonstrably better

**LATEST COMPLETE ACTUAL PUBLIC SOURCE RUN:** [GitHub Actions #39428981358](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39428981358) **SUCCESS**, 34/34 real official monthly archived 2024–Oct2026 XLSX, **34/34 original SHA-256 identical to independently acquired earlier 20-Oct EIA source XLSX**; 172 source forecast/reference pairs but only 62 distinct (instrument,target month), 58 reused across horizons. **104 strict as-of admissible walk-forward evaluations** (min 6 past outcomes whose EIA source reference edition was published STRICTLY before evaluated source forecast edition); no future label introduced as a training input by the code.

[PR #44](https://github.com/gniewkob/Investment-Strategy-Lab/pull/44) merged `30867061830e00f1a62ebb8cdf05fe3a8d4ad18e` (269/269 offline + 3/3 isolated PostgreSQL PASS, post-merge CI PASS), adding pure no-side-effect `scripts/steo_robustness_audit.py` and one-off public-source no-persistence workflow. Results **MAE USD/bbl dynamic / fixed EIA / fixed naive**: WTI +1 month **7.10/7.10/8.31 n22**, +3 **12.46/13.53/12.33 n18**, +6 **17.48/23.21/17.48 n12**; Brent +1 **9.20/8.79/9.81 n22**, +3 **14.09/15.25/14.09 n18**, +6 **18.45/25.60/18.45 n12**. **Dynamic historical method-switcher never strictly beat both static methods in any source+horizon group** (worse than better fixed method in 2 of 6). DO NOT promote to predictive/investment edge, portfolio rebalance or live trading.

Later-archived source reference sensitivity: Brent 0 changes across all forecast/horizon groups; WTI 1 changed pair in +1mo and 1 in +3mo, max 0.10 USD/bbl each — no proof they refer to distinct (or the same) target month. Source byte identity matches only two October-2026 acquisitions, **NOT original first-publication byte PIT from 2024–2026**. Monthly WTI/Brent spot reference price USD/bbl != investable PLN total-return, 0 Neon writes and 0 orders, no schedule or secrets. M1/M2/M3 HOLD_NO_CHANGE, previously user-confirmed MyDevil/Mac daily EIA backup CLOSED.

[Permanent exact real-source 34/34 audit and 12-row results](STEO_REAL_WALKFORWARD_ROBUSTNESS_2026_10_20_PL.md); [older full 172-forecast source report](STEO_FULL_34_REAL_RESULTS_2026_10_20_PL.md). **Next:** do not keep tuning dynamic switchers on same historical data; focus documented prospective validation and independent original-publication evidence or separate data-source quality; maintain research-only scope.

## 20.10.2026 — FULL 34/34 rzeczywistych historycznych STEO XLSX: COMPLETE, 172 forecast pairs; no PIT/portfolio action

**NEWEST REAL VERIFIED RESULT:** [GitHub Actions #39426001269](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39426001269) **SUCCESS**: all 34 *actual official archived monthly XLSX editions* Jan2024–Oct2026 retrieved and parsed from public EIA; 34 distinct actual RAW XLSX SHA-256 and listed release days, 72 WTI/Brent monthly reference cells per edition validated; **172 paired forecast–later-edition reference points** evaluated across 2 assets × horizons 1/3/6 months: WTI 86 and Brent 86; by horizon **31+29+26** paired points per asset. **Permanent real SHA/proof plus 18 year/instrument/horizon groups:** [docs/STEO_FULL_34_REAL_RESULTS_2026_10_20_PL.md](STEO_FULL_34_REAL_RESULTS_2026_10_20_PL.md).

**Genuine descriptive USD/bbl EIA vs same-source-edition previous-month naive MAE**:
- **WTI:** 1mo EIA `6.44` vs naive `7.46`; 3mo EIA `10.87` vs naive `10.18`; 6mo EIA `15.53` vs naive `12.21`.
- **Brent:** 1mo EIA `7.76` vs naive `8.58`; 3mo EIA `12.21` vs naive `10.89`; 6mo EIA `16.99` vs naive `12.56`.

**Critical reversal:** an earlier real 12-pair pilot favored EIA all 6 instrument/horizon groups; full 34-issue history reverses **four of six group rankings**. Avoid pilot cherry-pick and overinterpretation; 2026 short +6mo has n=2 per asset and target observations overlap; not independent samples. Source XLSX historical listed release day is known, but exact downloaded 2026 XLSX bytes may have been revised after original publication, **no independent original PIT byte certification**. Reference is later STEO monthly spot-price reference, not final market tradeable fill nor portfolio PLN total return. **NO proven predictive edge**.

**PRs:** [PR #42](https://github.com/gniewkob/Investment-Strategy-Lab/pull/42) real vintage-aware extractor merged, 262/262 offline +3/3 disposable PostgreSQL PASS; [PR #43](https://github.com/gniewkob/Investment-Strategy-Lab/pull/43) 34-vintage one-shot workflow merged, same regression CI PASS. The full original XLSX lives only transiently in CI RAM and is **NOT** committed to GitHub, source SHA only in proof logs/docs; no user secrets, Neon writes, new permissions, accounts, schedules, orders or trades. User-confirmed MyDevil/Mac original EIA spot source backup remains CLOSED. Simulated M1/M2/M3 HOLD_NO_CHANGE.

**Next helpful research:** repeat source-aware walk-forward comparisons with nonoverlapping target months and a truly predeclared untouched evaluation period, verify additional issue-original source bytes if available, investigate source revision and unusually elevated 2026 forecast errors, and separately research data for educational PLN total-return portfolios. Don't repeat 34 GET solely to confirm current already successful one-shot evidence.

## 20.10.2026 — historyczne real EIA STEO prognozy WTI/Brent: 12 par POLICZONE; 34-edition full job W TRAKCIE

**Pierwsza realna historyczna ewaluacja**: [PR #42](https://github.com/gniewkob/Investment-Strategy-Lab/pull/42) MERGED (`aa4dffd7adc2431d5d06787935feaee053e0dfd8`), **262/262** offline synthetic tests PASS i **3/3** disposable PostgreSQL integration PASS. [Rzeczywisty publiczny STEO source job #39425055719](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39425055719) **SUCCESS**: pobrano i zinterpretowano **3 prawdziwe archiwalne XLSX** EIA `jan24`, `jan25`, `oct26`, odczytano 12 par prognoza/kolejna referencja w `2tab` dla **WTI, Brent** i horyzontów **1/3/6 miesięcy**. EIA forecast MAE versus same-edition previous-month naive USD/bbl: WTI 1mo `0.86 vs 3.38`, 3mo `6.16 vs 10.01`, 6mo `2.96 vs 5.81`; Brent 1mo `0.52 vs 3.72`, 3mo `5.90 vs 9.02`, 6mo `3.05 vs 5.17`. `n=2` each horizon/commodity and underlying individual examples show EIA sometimes worse than naive — **NO PREDICTIVE EDGE**. [Immutable project analysis report (source is public)](STEO_REAL_FORECAST_ERRORS_2026_10_20_PL.md). Historic original publication BYTE authenticity still NOT independently PIT certified. Reference is later published archived STEO historical price, NOT tradable close or final total-return.

**Expansion**: [PR #43](https://github.com/gniewkob/Investment-Strategy-Lab/pull/43) MERGED `fc342697d97d6fbcc717abe1654edb2d75f94eb1`, **262/262 offline + 3/3 isolated PostgreSQL PASS**. Added [one-time read-only public-source 34-edition Jan2024-Oct2026 workflow](../.github/workflows/steo-full-archived-research-once.yml), and `STEO Table 2` cent precision normalization to avoid XLSX `71.900000000000006` cache noise (ORIGINAL raw SHA preserved). **Actual full 34 job** [GitHub Actions #39426001269](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39426001269) **IN PROGRESS** at time of this note. Do NOT claim that all 34 XLSX have been downloaded/scored until actual job success and parsed last line `STEO_REAL_34_RELEASE_HISTORICAL_FORECAST_RESULT`. Full 34 workflow fails closed on any bad/missing source, no tricks to count fewer results as 34. If succeeds, record the real metrics by horizon/year. If fails, get logs and diagnose release source issue; do NOT guess/ invent values. All XLSX in transient CI RAM, no artifacts / Github stored source bytes. [Full protocol](STEO_FULL_34_HISTORICAL_RESEARCH_PL.md).

**INVARIANTS:** No Neon source/version writes, no schema/ACL/role or secrets, no real orders, no virtual rebalance, M1/M2/M3 `HOLD_NO_CHANGE`; dated original EIA MyDevil/Mac backup already CLOSED/USER-CONFIRMED and remains unmodified. Historical as-published STEO byte immutability `false`, old observation `PIT_CERTIFIED=false`. Full later-edition referential MAE is descriptive and not a legitimate investment profit/backtest.

## 20.10.2026 — ARCHIWALNE RAPORTY EIA STEO: 34 wydania katalogowane, 3 realne XLSX sprawdzone, WTI/Brent Table 2 zidentyfikowane (historical research teraz)

**NOWY PRIORYTET:** nie czekać na nowe EIA, by badać retrospektywne historyczne ceny i datowane wydania dawnych prognoz. Po realnym, read-only zapytaniu do Neon: **3746 rekordów `price_observations` w 12 seriach** (WTI 695, Brent 706, Henry Hub 695, BTC/ETH po 381, NBP GOLD/EURPLN/USDPLN po 264, 4 surowce WB monthly po 24), `geopolitical_events=2`, `scenario_forecasts=8`, `forecast_evaluations=0`, `research_runs=0`. Rzeczywiste historyczne współczynniki korelacji dziennych log-return na wspólnych dniach: BTC/ETH 0.908 (380 par), WTI/Brent 0.773 (683), WTI/HenryHub 0.036 (691). To DESKRYPTYWNY research, nie predykcyjna przewaga ani wyniki inwestycyjne; źródłowe stare daty publikacji cen nadal niezweryfikowane. Henry Hub w legacy zawiera skoki 319.0% i 264.8% w 2024/2026 — niezależnie zweryfikować EIA zanim modelować.

[PR #39](https://github.com/gniewkob/Investment-Strategy-Lab/pull/39) merged `39fad7e37275ba68e9fb40409a2986ab334f756d`, 251/251 offline + 3/3 disposable PG PASS, current main CI [#39409557235](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39409557235) PASS. New `scripts/steo_historical_archive.py`: allowlist **34 oficjalnych, datowanych archiwalnych miesięcznych STEO XLSX (styczeń 2024–październik 2026)**, `catalog` OFFLINE, jawny `capture --issues jan24,jan25,oct26 --archive-root PRIVATE_ROOT` HTTPS do EIA z hash SHA i prywatnym manifestem, `verify` offline. Nie wykonywano `capture` na prywatnym MyDevil ani Mac w tej sesji, backup poprzednich dziennych cen użytkownik zamknął i jest nienaruszony. W GitHub **nie utrwalać RAW XLSX**.

[PR #40](https://github.com/gniewkob/Investment-Strategy-Lab/pull/40) merged `d1ea00135d7e9eaadf9313d6c71b00878c5b4118`: jednorazowa publiczna sonda GitHub Actions. [Real EIA XLSX run #39409917300](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39409917300) SUCCESS: real `jan24`, `jan25`, `oct26` XLSX retrieved over official allowlisted HTTPS, structural OOXML PASS, hashes `663ee3c648d2e88dad48dd1efd2557df99c811afe4afcc2094ed92c988fb53a9`, `67f9f24b6f0bd074bcc92e47f8f5ea23594f2dd6ccbf31b2dff912621bbb5b22`, `54989362410da4aff5673580396380c3a8f4f111fa6d01c6d4fab05ef90efbf4` respectively, sheets 24/28/28. Source XLSX bytes were **NOT permanently archived** by the run, only hashes/sheet metadata.

[PR #41](https://github.com/gniewkob/Investment-Strategy-Lab/pull/41) merged `54bb51023ce75775f8f113b815c5c42826f4a245`, 254/254 offline + 3/3 disposable PG PASS. Added `scripts/steo_xlsx_label_probe.py`: parses OOXML workbook rels/shared strings `2tab` labels safely without logging prices/formulas, and one-time probe on the same 3 historical official XLSX. [Second real STEO source probe #39410674417](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39410674417) SUCCESS. `2tab` has WTI `A6=WTIPUUS,B6=West Texas Intermediate Spot Average`, Brent `A7=BREPUUS,B7=Brent Spot Average`, YEAR numeric at row3 and month header labels at row4; years shift columns across editions (jan24 year2024 `AY3`, jan25 year2025 `AY3`, oct26 year2026 `AY3`). **Important: workbook A4 is Forecast date/completed day, several days BEFORE actual report release day; NEVER use A4 as public information availability time!** Current schema probe cap of 90 labels was exhausted by month headers before finding Henry Hub label; exact Henry Hub row remains unverified. [Grounded dated real source evidence](STEO_REAL_PUBLIC_XLSX_PILOT_2026_10_20_PL.md).

**NEXT:** design true source-semantic WTI/Brent monthly price-forecast extractor from `2tab`: year in row 3, month in row 4, labels row 6/7, numeric cells not yet extracted. Respect official RELEASE DAY (earliest conservative availability next day) not internal Forecast Completed. Only after genuine data extraction evaluate forecast errors vs later-published realized reference (same target month/horizon) and same-issue naive persistence; never extrapolate to investable total-return returns. `original_historical_publication_bytes_certified=false` even if today a PDF/XLSX resides under 2024 edition; files may have been revised after issuance, so explicitly remain historical PIT unverified. No source XLSX saved in GitHub or Neon, no real order, no agent role/ACL/schedule, M1/M2/M3 HOLD_NO_CHANGE.

## 20.10.2026 — Backup CLOSED/USER-CONFIRMED; PR #38 prospective EIA archive research merged; only paper research

**No more backup purchase/provisioning blocker.** Operator confirmed backup protection and explicitly requested close: [EIA_BACKUP_ACCEPTANCE_2026_10_20_PL.md](EIA_BACKUP_ACCEPTANCE_2026_10_20_PL.md) documents **MyDevil 3 independently offline VERIFIED EIA HTML+receipts**, **dated Mac 6-file copy**, **3/3 original SHA-256** and Mac `MAC_BACKUP_INTEGRITY_PASS`. **Backup operationally CLOSED and USER-CONFIRMED.** No independent WORM/Time Machine actual destination/restore test evidence (do not mislabel these as verified), but no need to procure OVH for current educational activity. [GitHub Issue #2 operator closure comment](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2#issuecomment-6288511342).

[PR #38](https://github.com/gniewkob/Investment-Strategy-Lab/pull/38) squash merged to main at `d22a90f09b4aa0cbe7b2eb5ca9f04f1da2b2b108`. [PR CI #39406305271](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39406305271) **242/242** offline synthetic tests PASS, **3/3** disposable PostgreSQL integration tests PASS; manual-public-EIA job SKIPPED as expected on PR. Added [`scripts/eia_prospective_archive_research.py`](../scripts/eia_prospective_archive_research.py): **READ-ONLY** independent verification of saved ORIGINAL EIA HTML and exact timestamped manifests for all 3 sources, safe bounded 128 receipts per series, fails on original hash/semantic SHA/source/timestamp/manifest corruption, and compares overlapping observed dates between successive real acquisition vintages. It differentiates layout-only raw HTML SHA drift vs rolling window changes vs actual revised prices on shared dates; outputs counts, source SHA and timestamps only — no raw HTML/prices/path/secrets in JSON, no network/DB/file writes/orders/schedules/reallocations. First 2026-10-20 capture for each source = `FIRST_SOURCE_CAPTURE_BASELINE_ONLY` and `RESEARCH_ONLY_HOLD_NO_CHANGE`, NOT historical PIT certification.

**Next operator READ-ONLY actual test on Mac backup**, from up-to-date Investment Strategy Lab working dir:
```bash
python3 -m scripts.eia_prospective_archive_research --archive-root "$HOME/.isl-eia-backups/20261020T093647Z"
```
Expect 3 source series, one captured vintage each, first-source baseline only, zero revisions, zero DB/actions, not yet executed on user's private Mac by this session. No new capture needed immediately.

Separate data strategy gate unchanged: previous Neon STAGING docs EIA 0, versions EIA 0, EIA writer absent; **no new role/ACL/secret/Neon INSERT** granted by backup confirmation or PR #38. The copied 20-Oct EIA spot prices are not independently known on their old observed dates, so retrospective PIT `MARKET_DATA_NOT_READY`. M1/M2/M3 paper `HOLD_NO_CHANGE`; no real orders or investable allocation performance claims.

## 20.10.2026 — REAL 3/3 private EIA original-byte archive CAPTURE complete (MyDevil); WTI independent offline verification PASS

**Current newest operational state:** operator ran `python3 -m scripts.eia_archive_local capture` for WTI, Brent, Henry Hub in their preflight-PASS private local POSIX MyDevil archive; **all 3 returned `EIA_RAW_HTML_ARCHIVED_LOCAL_STAGING_NOT_WORM`, `object_created=true`, `receipt_created=true`, `immediate_independent_replay=true`, `database_connections=0`, `database_writes=0`**. This is proven by operator stdout, **not direct SSH access** by assistant, which remains unavailable here.

Operator's exact new UTC acquisitions:
- WTI `2026-10-20T09:17:01.691564+00:00`, original SHA `4ecd9261dbc6fe1ba583d017af72fb37d2a33d626a11b4ab7940227d1122f489`, semantic SHA `648f3ff4403a2d1ea0232eb1f8ce9b90ae6e41fc31963fc3f59864858c036002`. **Separate offline `verify` succeeded** with `EIA_RAW_HTML_ARCHIVE_INDEPENDENT_OFFLINE_VERIFIED`.
- Brent `2026-10-20T09:19:15.240752+00:00`, raw SHA `be659c06a7f497afa0e49c976defa774cd70814d04bda7a20afac890d566f2ca`, semantic `d5746347f4d6371f9df882ce134bdd8280c226dcb2e557a3627a45537c3a9cd9`. Immediate replay PASS; separate manual offline `verify` pending.
- Henry Hub `2026-10-20T09:19:22.087511+00:00`, raw SHA `70b294c14f1deafbcd9c4b898d5c94ab971857013852197315616a67199d01fc`, semantic `0f226a4119e91d39d0117ff43f4dfded58d002ae1cc47d35a8306347cf3293c5`. Immediate replay PASS; separate manual offline `verify` pending.

**Permanent aggregate receipt record:** [docs/EIA_MYDEVIL_ACTUAL_ARCHIVE_RECEIPTS_2026_10_20_PL.md](EIA_MYDEVIL_ACTUAL_ARCHIVE_RECEIPTS_2026_10_20_PL.md). No original HTML/quote tables are stored in GitHub; they remain in MyDevil private archive. Earlier notes saying “no real EIA bytes captured yet” are **OBSOLETE** for these new 20.10.2026 receipts, but **still true for 19.10.2026 manual GitHub live runs** (their original bytes cannot be reconstructed from hash). Brent semantic digest equals 19.10 previous live; WTI and Henry Hub differ, consistent with rolling 420-day cutoff shift (Aug25→Aug26) but not yet a verified quote-revision comparison.

**Next safe actions:** (1) separate offline `verify` for Brent/Henry Hub; (2) read-only metadata summary from manifests to document observation count/start/end and release day and explain semantic drift; (3) separately approved independent WORM/Object Lock copy with retention and GET/VersionId/SHA proofs; (4) separately authorized Neon STAGING writer role/ACL/credential + strictly bounded first current snapshot INSERT only after controls. **NOT WORM**, no source_documents/price_observation_versions Neon inserts, no new role/secrets/schedules/real trades, never retrodate PIT. `MARKET_DATA_NOT_READY` and paper M1/M2/M3 `HOLD_NO_CHANGE`. Known MyDevil account limit 50 GB, used 28.4 GB as last reported; shared ZFS `fstatvfs` free 995037 MiB is NOT the user's account available space.

## 20.10.2026 — PR #37 merged: read-only MyDevil private-archive root metadata probe + OVHcloud WORM design; remote not touched

**Latest completed change:** [PR #37](https://github.com/gniewkob/Investment-Strategy-Lab/pull/37) squash-merged to `main` at `c6c9c2f13a3699a85fed191d44532ea3595f785c`. [PR CI #39345255007](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39345255007): **235/235** synthetic offline suite PASS and **3/3** disposable PostgreSQL integration PASS. Real source job correctly SKIPPED for PR. Post-merge main CI [#39345354629](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39345354629) was in progress during initial post-merge read-only SQL; inspect before calling it green.

Added [`scripts/eia_archive_storage_preflight.py`](../scripts/eia_archive_storage_preflight.py): operator-selected **already existing** absolute private 0700 POSIX archive root; read-only `open/fstat/fstatvfs`, O_NOFOLLOW, ensure not inside Git, inspect absent/existing private `objects`/`receipts` WITHOUT creating them. Redacted JSON returns no path/host/credentials/quotes, uses minimal 64 MiB free blocks threshold. Metadata PASS **does not prove quota, durable mounting, ability to write, backup restore, ZFS retention, Object Lock/WORM or Neon writer approval**; all those flags remain FALSE. No MyDevil SSH access/SSH alias available in the current runtime (even `ssh` binary absent); **NO remote command was executed**, NO path was guessed, no real archive directory created or filled. Running probe locally on MyDevil after its owner selects and verifies existing root is still PENDING.

[Polish MyDevil + OVHcloud Object Lock operational plan](EIA_MYDEVIL_OVH_ARCHIVE_READINESS_PL.md) distinguishes MyDevil workspace from independently immutable proof. Official OVHcloud Object Storage supports S3 Object Lock on eligible classes; **Cold Archive class excluded** in OVH FAQ; S3 Object Lock requires versioned object-level retention. Nothing was provisioned with OVHcloud. Next actions: authorized SSH metadata read, verify actual long-lived MyDevil directory/quotas/permissions and Python runtime, local probe (no writes), private fresh `capture+verify` under distinct explicit permission, then independently protected WORM version GET/hash/retention validation under a separately approved provider account/bucket. Do not misrepresent MyDevil ZFS snapshots as WORM. Operator still needs to choose real paths/retention/keys; do not create permissions or credentials without approval.

**Post-merge independent Neon STAGING SELECT:** WTI=**695**, Brent=**706**, versioned EIA source documents=**0**, versioned EIA prices=**0**, proposed `isl_eia_pit_staging_writer` role count=**0**. No DB insert, Neon ACL/role/secret change, hosting mutation, storage write, schedule or production operation. Two real source validations from [#39330376388](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330376388) and [#39330400127](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330400127) had already PASSED; no need to repeat them solely because preflight code changed. Live HTML from those earlier jobs was not retained; any later capture creates an honest NEW timestamp. Remain `MARKET_DATA_NOT_READY`, historical PIT original releases UNVERIFIED, M1/M2/M3 `HOLD_NO_CHANGE`.

## 19.10.2026 — PR #36 scalony: oryginalne bajty EIA + prywatne archiwum odbiorów, weryfikacja OFFLINE; to NIE WORM

[PR #36](https://github.com/gniewkob/Investment-Strategy-Lab/pull/36) scalony do `main` jako `d3607c64f50f7871cd511c586b332e2d7b7aaa9d`. [PR CI #39332083259](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39332083259): **228/228** testów całego projektu offline PASS, **3/3** testy integracyjne disposable PostgreSQL 16 PASS. Job `manual-public-eia-only` w PR celowo SKIPPED, co jest zgodne z bramką manualną. Wcześniejsze wersje testów odrzucanych manifestów miały zbyt specyficzne oczekiwania komunikatu błędu, zostały naprawione; **ostatni SHA/head jest zielony**.

Dodano [`src/isl_v2/eia_raw_archive.py`](../src/isl_v2/eia_raw_archive.py) i [`scripts/eia_archive_local.py`](../scripts/eia_archive_local.py):
- Operator musi wskazać **istniejący prywatny absolutny katalog 0700 poza Git repo** na trwałym POSIX filesystemie. Nie uruchamiać na ephemeral GitHub runner jako jedynej kopii.
- `capture --source wti|brent|henry_hub --archive-root /PRIVATE/ARCHIVE` pobiera NOWE oryginalne bajty EIA po oficjalnym HTTPS z czasem completion, tworzy tylko lokalne `objects/<RAW_SHA>.html` i oddzielne `receipts/<SOURCE>/<RETRIEVED_AT>_<RAW_SHA>.json`. Unika przypadkowego nadpisania przez `O_EXCL`, `O_NOFOLLOW`, 0600/0700, fsync; ponowne pobranie identycznego HTML ma osobny receipt, bez duplikowania obiektu.
- Manifest zawiera autentyczny raw/semantic SHA, liczbę i zakres obserwacji, jawny `retrieved_at`, `Release Date` z precyzją DAY, `current_snapshot_available_not_before`, `UNVERIFIED_HISTORICAL_PUBLICATION`. Nie ujawnia cen ani ścieżek logom. Po zapisie aplikacja automatycznie uruchamia niezależną weryfikację odczytanego z dysku HTML i manifestu.
- `verify --source ... --archive-root ... --sha256 <z capture> --retrieved-at <ISO>` działa offline, **bez oryginalnego IngestionPlan i bez EIA/Neon**, reparsuje oryginalne lokalne bajty w oryginalnym oknie czasowym i kontroluje raw/semantic SHA, manifest i daty. Testy: uszkodzenie obiektu/manifestu, zmiana ceny, zmiana szablonu HTML, prywatne uprawnienia, symlink, root w Git i idempotencja.
- **UWAGA: archiwum jest private local append-once z poziomu adaptera, NIE certyfikowane WORM ani legalnie uzgodniona polityka retencji.** Właściciel filesystemu może zmienić/usunąć bajty; do trwałej niezależnej gwarancji wymagana odrębna konfiguracja np. S3 Object Lock lub rzeczywista niezmienna retencja + GET/sha po zapisie. Nie dodano żadnego archiwum raw EIA w GitHub Actions i nie zapisano do operatorowego prywatnego wolumenu; realne wcześniejsze HTML z [#39330376388](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330376388) i [#39330400127](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330400127) nie są możliwe do bitowego odtworzenia z samych SHA. Przyszły `capture` tworzy dopiero nowy snapshot z nowym rzeczywistym czasem.
- **ŻADNY Neon WRITE/role/ACL/secret/schedule/produkcja/transakcja** nie był przedmiotem PR #36. Nadal wersjonowane EIA rows=0, `isl_eia_pit_staging_writer` nie utworzona, retrospektywne pierwsze daty publikacji nie są uwierzytelnione, `MARKET_DATA_NOT_READY`, modele M1/M2/M3 `HOLD_NO_CHANGE`.
- [Runbook archiwizacji](EIA_ORIGINAL_HTML_ARCHIVE_PL.md) i [pełne live źródłowe receipty](EIA_LIVE_RECEIPTS_2026_10_19_PL.md). Kolejne dopuszczenie: operator wskazuje naprawdę trwały prywatny katalog, wykonuje manualny `capture+verify`, następnie wybiera WORM i osobno zatwierdza nową rolę STAGING i pierwszy ograniczony `INSERT`. Nie wymaga ponawiania dwóch manualnych audytów już zakończonych sukcesem.

## 19.10.2026 godz. 21:48–21:49 UTC — OBA RĘCZNE LIVE EIA AUDYTY WYKONANE: SUCCESS

**NAJNOWSZY KONKRETNY STAN:** Użytkownik potwierdził „Poszło”, a GitHub Actions potwierdził prawdziwe dwa `workflow_dispatch` na `main`, HEAD `33c08aed1a8482902cc6ba50b0f96945a5202b81`, nie tylko PR CI:
- [WTI EIA↔Neon run #39330376388](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330376388): `SUCCESS`, manualne połączenie po roli SELECT-only, **695 EIA = 695 Neon, 695 identycznych dat i cen, 0 braków, 0 różnic**, poprzednie 660 SHA `2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8`, 35 backfilled 19.10, release 15.10.2026, raw HTML `43723196ad327134040a1718ba5f3d3598bb949c154a6642c5b71c623c4f8981`, odczyt 21:48:50.066187 UTC, `database_reads=1`, `database_writes=0`, `PIT_certified=false`. [Artifact #12224256765](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330376388/artifacts/12224256765) dostępny do 26.10.2026 21:48:50 UTC.
- [Public official EIA run #39330400127](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39330400127): `SUCCESS` także dla live public HTTP, offline tests i disposable PG. WTI **285** (RAW HTML SHA `90056f802fdc1023695abdf53c6400e24649c60e74f5399b0078b21ece1e87fa`, semantic SHA `999e76f1d392df75212454a7e149631681104608f9c3b9fe80d623daf17af0dd`, pobrano 21:48:56.987993 UTC), Brent **289** (pobrano 21:48:57.495438), Henry Hub **283** (pobrano 21:48:57.929006), wszystkie oficjalne `Release Date 2026-10-15`, `database_connections=0`, `database_writes=0`. Liczba WTI 285 dotyczy ruchomego 420-dniowego okna tego workflow, a 695 dotyczy dłuższego pełnego okna audytu A. Osobne oryginalne bajty dwóch żądań EIA dały różne HTML SHA, nie należy z tego wnioskować rewizji cen.
- Niezależny po-audycie SELECT Neon STAGING: WTI **695**, Brent **706**, `source_documents=3` (EIA=0), `price_observation_versions=3` (EIA=0), `isl_eia_pit_staging_writer` liczba **0**. Nic nie zapisano/nie zmieniano, brak nowej roli, produkcji, schedule lub transakcji.

**Pełne trwałe dowody: [docs/EIA_LIVE_RECEIPTS_2026_10_19_PL.md](EIA_LIVE_RECEIPTS_2026_10_19_PL.md)** (dwa raw SHA, trzy semantic SHA, rzeczywiste timestamps, artifact i granice PIT). **Historyczne indywidualne data-first-publication nadal NIEZWERYFIKOWANE**; nie ogłaszać historycznych backtestów ani wyników modelu na podstawie tego odczytu. `MARKET_DATA_NOT_READY` w PIT, M1/M2/M3 `HOLD_NO_CHANGE`.

**Następny P0:** przed jakąkolwiek osobno zatwierdzoną zmianą ACL / uprawnieniami roli lub pierwszym realnym `INSERT` przygotować trwałą, odtwarzalną archiwizację ORYGINALNYCH RAW HTML EIA wraz z realnymi SHA/retrieved_at (dotychczasowe raporty zapisują SHA, ale nie oryginalne bajty), następnie przegląd precyzyjnej izolacji gałęzi i roli least-privilege STAGING. Oba wymagane manualne audyty są już ZAKOŃCZONE; stare instrukcje niżej „nieuruchomione” są teraz wyłącznie HISTORYCZNE i nie powtarzać ich jako aktualnego statusu.

## 19.10.2026 — PR #35 merged: rzeczywiste STAGING EIA pierwszego snapshotu = lokalne PASS / import NO-GO (wyłącznie SELECT)

Po jednoznacznym „Ok go” użytkownika, nie naruszając wcześniejszych zasad manualnych source-receipts i oddzielnej zgody na uprawnienia/pierwszy write, ponownie sprawdzono wszystkie GitHub Actions. Jedyny dotychczasowy `workflow_dispatch` w ostatnich 50 workflow runs dotyczy **archiwalnego** audytu sprzed importu [#39305643778](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39305643778); **NIE** wykonano aktualnego LIVE WTI 695/695 ani manualnego publicznego dry-run EIA. GitHub connector nie posiada workflow dispatch; NIE obchodzić tego przez `push`, `schedule` lub retry `SKIPPED`.

[PR #35](https://github.com/gniewkob/Investment-Strategy-Lab/pull/35) scalony do `main` jako `bb7034fc1bc5048acdfcf65c1975fff70e93ad8f`. [CI #39329040177](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39329040177) **SUCCESS**: **216/216** testów offline oraz **3/3** integracyjne disposable PostgreSQL 16, `manual-public-eia-only=SKIPPED` (prawidłowo). Nowe pliki [`db/verify_eia_first_snapshot_READONLY.sql`](../db/verify_eia_first_snapshot_READONLY.sql), [runbook](EIA_FIRST_SNAPSHOT_GO_NO_GO_PL.md) i testy gwarantują pojedynczy SELECT-only i stały niezależny wynik `NO_GO_PENDING_LIVE_SOURCE_AND_EXPLICIT_WRITER_APPROVAL` nawet przy lokalnym PASS. Wykonano **dokładnie to SQL** na izolowanej gałęzi `red-lake-53043722 / br-wandering-union-ba6ogf6l` baza `investment_lab` przez Neon `run_sql`, **0 zapisów**.

**Rzeczywisty Neon raport (SELECT):** `local_reference_integrity=REFERENCE_DATA_PREFLIGHT_PASS`; 3/3 oficjalne katalogi źródeł i instrumentów (w tym `HENRY_HUB_USD_MMBTU`), STAGING canary 1 `agent_cycles` + 3 `HOLD_CASH`, WTI 695/695 unikatowych 02.01.2024–14.10.2026, 35 późniejszych, frozen pierwotne 660 SHA `2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8`, Brent 706, 3 `source_documents` (wszystkie `nbp_gold`, EIA=0), 3 `price_observation_versions` (EIA=0), rola `isl_eia_pit_staging_writer` 0. Publiczne real EIA HTTP SHA i świeża chronologia: `FALSE` (ten SQL nie ma dostępu); manualny receipt w Actions: `FALSE`. Historyczne oryginalne publication vintages: `FALSE`. Nie zmieniono Neon, ACL, sekretów, schedule, produkcji lub inwestycji.

**Operacyjne blokady:** manual [EIA WTI 695/695](https://github.com/gniewkob/Investment-Strategy-Lab/actions/workflows/eia-wti-staging-receipt.yml) → `Run workflow / main`; manual [EIA public 3 sources](https://github.com/gniewkob/Investment-Strategy-Lab/actions/workflows/eia-versioned-ingest.yml) → `Run workflow / main`. Po aktualnych przejściach przed jakimikolwiek INSERT/CREATE ROLE osobno zatwierdzić minimalną rolę, TLS, STAGING branch i archiwizację oryginalnych bajtów źródła. Pozostają `MARKET_DATA_NOT_READY`, `UNVERIFIED_HISTORICAL_PUBLICATION`, M1/M2/M3 `HOLD_NO_CHANGE`. Issue #2 OPEN.

## 19.10.2026 — PR #34 SCALONY: rzeczywisty `retrieved_at` dopiero PO pełnym HTTPS, oba moduły EIA

**Aktualizacja:** [PR #34](https://github.com/gniewkob/Investment-Strategy-Lab/pull/34) scalony na `main` jako `2c9a70d0900ae6fe33dbc98796eddc6807d861c6`. [PR CI #39327691674](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39327691674) = SUCCESS **213/213 syntetycznych testów offline + 3/3 rzeczywiste testy disposable PostgreSQL 16**. Pozostałe PR CI walidacji źródła i postimport WTI także SUCCESS (joby live pominięte). Po merge push CI runner #39327841465 i EIA verify #39327841336 potwierdzone SUCCESS, pipeline EIA planning #39327841429 trwał w chwili finalnego SQL SELECT (sprawdzić wynik przy wznowieniu).

**Naprawiony defekt dowodowy:** Wcześniej `fetch_plan(source, fetched_at)` w importerze wersjonowanych źródeł i `fetch_official(source, at)` w audycie read-only nazywały `downloaded_at` czasem wywołania **przed** faktycznym pobraniem odpowiedzi HTTPS. Nie spełniało to rygoru realnej daty pozyskania dokumentu. Teraz przyjmują pre-request timestamp jako **początek przedziału**, a faktyczny `downloaded_at/retrieved_at` ustalają **dopiero po pełnym `read()` i zamknięciu response**. Nie dopuszczają clock rollback, naïve datetime, ani pobierania trwającego ponad 120 s. Względny `available_at` dla przyszłego `price_observation_versions` jest nie wcześniejszy niż moment ukończenia HTTP i bezpieczna konserwatywna data EIA release-day+1. Testy potwierdzają, że `source_documents.retrieved_at` i `price_observation_versions.available_at` przyszłych operacji dostały nowy czas, że faktyczny fetch jest po close oraz że nie emitowano cen, sekretów i nie tworzono połączeń DB przez CLI. **Nie jest to certyfikat historycznej pierwszej publikacji starszych notowań.**

**Potwierdzony rzeczywisty tylko odczyt Neon STAGING po merge:** WTI **695**, Brent **706**, `source_documents=3`, `price_observation_versions=3`, `isl_eia_pit_staging_writer` count **0**. Nowych bazowych insertów/rol/ACL/sekretów, schedule, produkcji i transakcji brak. M1/M2/M3 `HOLD_NO_CHANGE`; `MARKET_DATA_NOT_READY`, autentyczne wcześniejsze PIT nadal niezweryfikowane.

**Dwa manualne live działania nadal nie wykonane:** GitHub Actions [postimport 695/695 read-only](../.github/workflows/eia-wti-staging-receipt.yml) i [publiczno-źródłowy dry-run EIA](../.github/workflows/eia-versioned-ingest.yml) uruchamiane tylko przez operatora z `main`. Dostępne narzędzia GitHub umożliwiają odczyt workflow/PR, ale nie `workflow_dispatch`; NIE zgłaszać, że live wykonany. Następny P0: niezależny realny read-only source receipt; następnie plan niezmiennego lokalnego archiwum oryginalnego HTML, a dopiero później zatwierdzona minimalna rola STAGING i odrębna zgoda na zapis.

## 19.10.2026 — PR #33 SCALONY: EIA semantic hash, freshness i blokada UPDATE/DELETE/TRUNCATE; Neon bez zapisów

**Najświeższy potwierdzony postęp:** [PR #33](https://github.com/gniewkob/Investment-Strategy-Lab/pull/33) squash-merged do `main` jako `5c9c07ef99ee0ad5dd8e454bbb79b9aa1c760abd`. [CI #39322916970](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39322916970) zakończone `SUCCESS`: **210/210** testów jednostkowych/offline i **3/3** integracyjnych na sztucznym jednorazowym PostgreSQL 16 (bez Neon, bez rzeczywistych danych lub sekretów). Wcześniejsza wersja testu #39322698701 odkryła błędne oczekiwanie wobec poprawnej chronologicznej blokady EIA, poprawiono tylko test i ponowiono pełny suite na finalnym kodzie.

Nowy moduł [`src/isl_v2/eia_semantic_evidence.py`](../src/isl_v2/eia_semantic_evidence.py) oddziela **SHA-256 dokładnych oryginalnych bajtów HTML** od deterministycznego SHA-256 **uporządkowanych dat + kanonicznych Decimal cen + identyfikatora źródła/jednostki**. Kosmetyczna zmiana HTML, a także `101.10` vs `101.1000`, nie oznaczają zmian cen; prawdziwa różnica ceny zmienia semantic SHA. Raport publicznego CLI i metadane PRZYSZŁEGO dokumentu zawierają agregaty i semantic SHA, nigdy surowe ceny/HTML. Aktualny importer [`src/isl_v2/eia_versioned_ingest.py`](../src/isl_v2/eia_versioned_ingest.py) odrzuca **bieżące snapshoty EIA, jeśli ostatnia obserwacja lub data wydania jest starsza o >14 dni od rzeczywistego pobrania**, oraz przyszłego writer-a z dowolnym `UPDATE/DELETE/TRUNCATE` na `source_documents` lub `price_observation_versions`. Dodatkowy test na prawdziwym disposable PG potwierdził odmowę po nadaniu `UPDATE`.

**Nadal nierozwiązane:** brak trwałego, autentycznego archiwum oryginalnych HTML do odtworzenia source SHA; dziś baza PIT zapisuje planowane URL/SHA/metadata, ale nie oryginalne bajty. Wersjonowany importer NIE był uruchomiony w Neon. 695 legacy WTI i 706 Brent niezmienione, `source_documents=3`, `price_observation_versions=3`, brak nowej roli `isl_eia_pit_staging_writer` (ostateczny niezależny SELECT sprawdzić przy kontynuacji). Wszystkie trzy wcześniejsze source docs należą do `nbp_gold`; **dokładnie jeden `metadata.synthetic=true`, dwa nie mają tego znacznika** — nie uznawać tych dwóch automatycznie za historycznie autentyczne obserwacje PIT. Brak autentycznych dat wcześniejszej publikacji EIA, nadal `MARKET_DATA_NOT_READY`; M1/M2/M3 `HOLD_NO_CHANGE`.

**Manualne zadania:** (1) rzeczywisty `workflow_dispatch` read-only [WTI 695/695](../.github/workflows/eia-wti-staging-receipt.yml) z `main` nie został jeszcze uruchomiony po PR #31; (2) manualny dry-run publiczny HTML EIA [`eia-versioned-ingest.yml`](../.github/workflows/eia-versioned-ingest.yml); (3) dopiero po osobnym wyraźnym zatwierdzeniu nowa rola/ACL/sekret na właściwej gałęzi STAGING i pierwszy kontrolowany PIT snapshot, bez produkcji i bez transakcji inwestycyjnych. [Issue #2](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2) pozostaje OPEN. `docs/EIA_VERSIONED_INGEST_GATE_PL.md` zawiera aktualne zasady.

## 19.10.2026 — P0 EIA wersjonowanie: PR #32 SCALONY, testy REALNEGO disposable PostgreSQL PASS, Neon bez zmian

[PR #32](https://github.com/gniewkob/Investment-Strategy-Lab/pull/32) scalony do `main` jako `554a503661087462c563eb002c587de0e17b48b6`. [Main CI #39311349708](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39311349708) = SUCCESS; PR CI [#39311167151](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39311167151) **204/204 jednostkowe offline PASS oraz 2/2 integracyjne PostgreSQL 16 disposable PASS** (sztuczny lokalny serwis, migracja 007 test fixture, rzeczywiste wykonanie tylko skryptu roli REVIEW ONLY na disposable PostgreSQL, test idempotencji, jednej poprawki ceny, cutoff PIT i wykrycia nadmiernych uprawnień). Pełne CI runner #39311349396 także SUCCESS.

Dodano [`src/isl_v2/eia_versioned_ingest.py`](../src/isl_v2/eia_versioned_ingest.py): parsuje rzeczywiste bajty oryginalnego HTML oficjalnego EIA WTI/Brent/Henry Hub (allowlist HTTPS, brak redirect, max 8MB), oblicza hash dokładnie na tych samych bajtach, konserwatywna dostępność TYLKO **bieżącego snapshotu** `max(realnie_pobrano, release_DAY+1 o 00 UTC)`. CLI jest WYŁĄCZNIE dry-run bez DB i bez `--write`, wypisuje wyłącznie agregaty/hash, nie ceny. `apply_plan(cursor,plan)` jest osobną funkcją zapisu append-only, odrzuca sfałszowany plan przez ponowne parsowanie oryginalnych bajtów, wymaga przyszłej odrębnej tożsamości `isl_eia_pit_staging_writer` i szczegółowej kontroli ACL, NIE łączy się do Neon ani nie wykonuje `COMMIT`. Obsługuje deduplikację tego samego dokumentu, nowy hash bez zmiany cen oraz nową rewizję dla zmienionej ceny. **Ta ścieżka w Neon NIE była wykonana.**

Dodano [`db/security/eia_pit_staging_writer_REVIEW_ONLY.sql`](../db/security/eia_pit_staging_writer_REVIEW_ONLY.sql) z izolującym canary gałęzi, `NOLOGIN` i minimalnymi propozycjami SELECT/INSERT tylko na `source_documents`/`price_observation_versions`. Test w PostgreSQL disposable NIE JEST zgodą na uruchomienie SQL w Neon. [Dokument warunków zatwierdzenia](EIA_VERSIONED_INGEST_GATE_PL.md). **Potwierdzony READ ONLY SQL na prawdziwym Neon STAGING po scaleniu:** WTI **695**, Brent **706**, `source_documents=3`, `price_observation_versions=3` (tylko wcześniejsze syntetyczne fixture), `isl_eia_pit_staging_writer` **nie istnieje**. Nie dodano roli, haseł, ACL, produkcji, harmonogramu ani nie wykonano jakiegokolwiek nowego zapisu/importu w Neon. Zero certyfikowanych historycznych publication vintages; `MARKET_DATA_NOT_READY`, `UNVERIFIED_HISTORICAL_PUBLICATION`, M1/M2/M3 `HOLD_NO_CHANGE`.

**Następne kroki wymagające operatora:** (1) ręczny publiczny EIA dry-run workflow [`.github/workflows/eia-versioned-ingest.yml`](../.github/workflows/eia-versioned-ingest.yml) (bez sekretów i Neon); (2) nadal nieuruchomiony manualny 695/695 EIA→Neon read-only z PR #31; (3) osobny przegląd minimalnej roli i bezpiecznego połączenia ONLY STAGING oraz wyraźna zgoda użytkownika, zanim powstanie nowa rola/sekret lub dojdzie do pierwszego INSERT realnych source PIT. Historyczny wyciąg z obecnej strony EIA w 2026 r. nie tworzy dowodu jego dostępności w 2024 r. [Issue #2](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2#issuecomment-6275522045) pozostaje otwarty.

## 19.10.2026 — PR #31: aktualny audyt 695 WTI wdrożony do main; live manual jeszcze nie wykonany

Po fizycznym uzupełnieniu 35 WTI do izolowanego Neon STAGING, stary zamrożony kontrakt `660/695/35` stał się historyczny. [PR #31](https://github.com/gniewkob/Investment-Strategy-Lab/pull/31) został **scalony** do `main` jako `96d9662c7ba961fa95d2f9f6711426fa4bf3ac91`. Zmienił manualny workflow [`.github/workflows/eia-wti-staging-receipt.yml`](../.github/workflows/eia-wti-staging-receipt.yml), aby od tej chwili uruchamiał NOWY `scripts/eia_wti_postimport_receipt.py` (a nie archiwalny `scripts/eia_wti_staging_receipt.py`). [CI #39308251783](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39308251783) = **SUCCESS**, pełny suite **195/195 testów offline**. `manual-staging-read-only` z PR celowo **SKIPPED**.

Nowy kontrakt oczekuje **695/695** dokładnych dopasowań dat i cen EIA Cushing WTI do aktualnej historii Neon STAGING za 02.01.2024–14.10.2026, **0** braków/rozbieżności, **660 oryginalnych** rekordów o niezmienionym hashu `2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8`, **35 dopisanych 19.10.2026** (żaden nie antydatowany) i historyczną bieżącą edycję źródła EIA `Release Date=15.10.2026`. W jednym kontrolowanym odczycie aktualny SHA **oryginalnego HTML EIA** oraz **tymczasowej lokalnej referencji 695 cen**; połączenie role/TLS/ACL sprawdzane ponownie, `SET TRANSACTION READ ONLY`. Log/artifact tylko agregaty, daty, SHA, bez cen/sekretów. Brak zapisów Neon, uprawnień, produkcji, harmonogramów i transakcji. Brak źródłowo uwierzytelnionego historycznego PIT i żadnych wersjonowanych rekordów dodatkowych: `UNVERIFIED_HISTORICAL_PUBLICATION`, `MARKET_DATA_NOT_READY`; M1/M2/M3 `HOLD_NO_CHANGE`.

**WAŻNE: CI POTWIERDZA TYLKO TESTY SYNTETYCZNE.** W tym etapie NIE wykonano jeszcze nowego `workflow_dispatch` na rzeczywistym EIA+STAGING dla kodu PR #31 (manualny live job nie może zostać uruchomiony przez udostępniony konektor GitHub). Operator ręcznie uruchamia z `main` workflow **Post-import WTI EIA and Neon STAGING 695-day receipt — MANUAL READ ONLY**, następnie sprawdza `WTI_POSTIMPORT_EIA_STAGING_695_MATCH_READ_ONLY` i liczby w artefakcie. Instrukcja: [WTI_POSTIMPORT_RECEIPT_PL.md](WTI_POSTIMPORT_RECEIPT_PL.md). Jeśli EIA zmieni wydanie, zamrożony odbiór odrzuci nowy stan i potrzebny będzie kolejny jawnie uzgodniony zakres; nie zmieniać po cichu definicji sukcesu.

**Następny niezałatwiony P0 #2:** źródłowo wersjonowany import `source_documents` i `price_observation_versions` z rzeczywistym snapshotem i czasem jego pozyskania, niezależną rolą tylko STAGING, idempotencją, ochroną przed retrospektywnym look-ahead i osobną zgodą na zapis. Najnowsza zidentyfikowana historia legacy NIE zostaje magicznie PIT ze względu na wykonanie późniejszego backfillu. W `docs/WTI_POSTIMPORT_RECEIPT_PL.md` opisano model obecnego source-receipt, konserwatywny `available_not_before` i następną bramkę PIT. Issue #2 otwarte.

## 19.10.2026 — KONTROLOWANY IMPORT 35 WTI DO NEON STAGING WYKONANY (NIE PIT)

**Najświeższy stan: luka WTI w LEGACY tabeli `price_observations` została fizycznie uzupełniona 19 października 2026 po jednoznacznej zgodzie użytkownika: „Ok działaj z importem”.** Poprzednie wpisy w tym pliku o *35 nadal brakujących w STAGING* są ARCHIWALNYMI stanami przed operacją; nie uruchamiać ponownie historycznego zamrożonego audytu `eia_wti_staging_receipt.py` z konfiguracją „expected 660 / missing 35” jako bieżącej walidacji, bo zgodnie z jego kontraktem odrzuci **nowe** 695 rekordów.

**Źródło:** oficjalna bieżąca tabela EIA [Cushing WTI, spot, USD/bbl](https://www.eia.gov/dnav/pet/hist/RWTCd.htm), dostępna wersja `Release Date: 10/15/2026`, z której odczytano 35 brakujących obserwacji 26.08–14.10.2026. Wcześniejszy prawdziwy wspólny odczyt EIA HTML + Neon [run #39305643778](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39305643778) poświadczył 695 obecnych w EIA / 660 istniejących zgodnych / 35 braków / 0 różnic oraz odrębne rzeczywiste SHA-256. **Nie utożsamiać** hasha pierwotnego HTML z nowym odczytem tekstowym tabeli wartości w tej sesji. Nie utworzono wersjonowanych source documents ani nowego certyfikatu historycznych publication vintages.

**Dokładny zakres zapisu:** jedna atomowa transakcja SQL do `red-lake-53043722` / `br-wandering-union-ba6ogf6l` / `investment_lab`, WYŁĄCZNIE `INSERT` 35 wierszy do `investment_lab.price_observations` dla `WTI_EIA_USD_BBL`, `eia_wti_daily`, `1d`, `PRICE_ONLY` i oficjalnego `source_url`. `ingested_at` nadano **rzeczywisty czas zapisu 2026-10-19T18:56:07.722..723 UTC**; `observed_for` jest historyczną datą obserwacji, NIE data pierwszej publikacji. **Bez zmian** `source_documents`, `price_observation_versions`, logów badań, produkcji, ACL, sekretów, portfela, harmonogramów lub zleceń. Zastosowano transakcyjny fail-closed: walidacja bieżącej bazy i roli, znacznik STAGING, 660 początkowych unikalnych WTI, 706 Brent, daty/zakresy, 35 nieobecnych nowych kluczy oraz odrzucanie niezgodnej liczebności w całości.

**Niezależny po-commit SQL SELECT:** **WTI 695/695 unikalnych**, 35 rekordów w nowym przedziale i 35/35 dopasowań cen i dat do bieżącej tabeli EIA; **0** braków w wybranym przedziale, **0** rozbieżności wartości, **0** antydatowanych `ingested_at`, **0** błędów etykiet lub URL. Hash wcześniej zapisanych 660 rekordów WTI obliczony ponownie z uporządkowanego `observed_for::date,close_price::text`: `2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8` — identyczny z audytem przed importem. Brent nadal **706**; `price_observation_versions=3`, `source_documents=3` (tylko wcześniejsze syntetyczne fixture). Nie wykonywano drugiego importu lub UPDATE.

**UWAGA o dwóch różnych definicjach sukcesu:** naprawiono wyłącznie historyczną KOMPLETNOŚĆ istniejącej `legacy price_observations` do 14.10.2026. **NIE rozwiązano** braku prawdziwej wersjonowanej historii publikacji i retrieval dla poszczególnych notowań. Nie traktować 35 dopisanych bieżącym importem obserwacji jako widocznych dla agenta w sierpniu–październiku. `UNVERIFIED_HISTORICAL_PUBLICATION`, `independent_point_in_time_market_data_certified=false`, `MARKET_DATA_NOT_READY`, M1/M2/M3 `HOLD_NO_CHANGE`. Issue #2 (oryginalne data PIT) jest otwarte; Issue #22 może pozostać otwarte w zakresie ustalenia przyczyny historycznego ucięcia/niezweryfikowanego PIT, ale sama luka 35 legacy obserwacji jest już ZAMKNIĘTA na STAGING. Potrzebny nowy jawnie zaprojektowany post-import data-integrity checker zamiast starego `expected_missing=35`.

## 19.10.2026 — PIERWSZY WSPÓLNY LIVE AUDYT EIA WTI + Neon STAGING = PASS (READ ONLY)

**Krok wykonany, nie tylko przygotowany.** Operator uruchomił z `main` [manualny workflow #39305643778](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39305643778); status `SUCCESS` dla `offline-regression` i rzeczywistego `manual-staging-read-only`. [Artefakt JSON #12213896179](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39305643778/artifacts/12213896179) zawiera tylko liczby, daty, SHA, i flagi bezpieczeństwa (retencja do 26.10.2026). To wykonanie PR #30 na `main`, HEAD `fe695b58693fb2ebe275ee49e13bd05e4599b26b`.

**Spójne rzeczywiste dowody:** EIA WTI oryginalny HTML pobrany 19.10.2026 `18:48:52.280712Z`, strona release 15.10.2026, SHA-256 bajtów HTML `ea1cba43f3ab5ab00b29003f3f213f9fb7e5be086c0128635d6726503fff2731`; w tym samym processie SHA-256 dokładnych tymczasowych bajtów lokalnego price-only CSV z odczytu Neon STAGING `af37281ed15be78cf98289ee935055d4751f6679e65382108402e9447aac1158`. Zamrożone okno 02.01.2024–14.10.2026: **695** obserwacji EIA, **660** obserwacji w Neon zgodnych zarówno datą jak i wartością, **35** brakujących EIA 26.08–14.10.2026, **0** niezgodnych cen i **0** dodatkowych dat w Neon. Historyczne konto tylko do odczytu sprawdzone ACL; `database_connections=1`, `database_reads=1`, `database_writes=0`, `real_orders=0`, `schedule_enabled=false`. Dodatkowy niezależny SELECT w Neon po jobie: WTI **660 rekordów / 660 unikalnych dni**, `min=2024-01-02`, `max=2026-08-25`, **0 rekordów po cutoff**.

**Znaczenie:** luka WTI i integralność istniejących 660 cen są wykazane we wspólnym, prawdziwym przebiegu; **brakujące 35 NIE są uzupełnione**. Brak przyczyny oryginalnego ucięcia importu i prawdziwych wczesnych metadanych publikacji dla PIT: nadal `UNVERIFIED_HISTORICAL_PUBLICATION` / `MARKET_DATA_NOT_READY`. To nie jest dowód przewidywania rynku. [Issue #22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6274752434) nadal OPEN, podobnie #2. M1/M2/M3 `HOLD_NO_CHANGE`.

**Następna faza:** zaprojektować kontrolowany, ponownie recenzowany uzupełniający import 35 WTI **tylko STAGING**, jako nowy bieżący retrieval, bez antydatowania `published_at/retrieved_at/recorded_at` i bez udawania historycznego PIT. **Nie wykonać żadnego INSERT/UPDATE ani nowych uprawnień bez osobnej wyraźnej zgody użytkownika**. Audyt jest odczytowy i zakończony; nie trzeba ponownie wyzwalać workflow tylko po to, żeby go potwierdzić.

## 19.10.2026 — PR #30 scalony: jedna sesja EIA WTI + odczyt Neon STAGING (LIVE JESZCZE NIE URUCHOMIONY)

**Kod GOTOWY na `main`, audyt LIVE wciąż oczekuje na ręczne uruchomienie.** [PR #30](https://github.com/gniewkob/Investment-Strategy-Lab/pull/30) został squash-merged do `main` jako `2a08e977efb51c602439f1a0a85d4cbec6bcfef2`. [PR CI #39305170106](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39305170106) = `SUCCESS` dla pełnych **187/187 testów offline**; job `manual-staging-read-only` w tym PR celowo `SKIPPED`.

**Nowy workflow:** [`.github/workflows/eia-wti-staging-receipt.yml`](../.github/workflows/eia-wti-staging-receipt.yml). Wyłącznie `workflow_dispatch` z `main` w jobie LIVE i już istniejącym GitHub Environment `research-staging`; nie wprowadzono harmonogramu, nowego sekretu, zmian ACL, backfillu ani zapisu Neon. Skrypt `scripts/eia_wti_staging_receipt.py` łączy istniejący ograniczony SELECT (rola `isl_legacy_history_reader`, strict TLS, transakcja READ ONLY i audyt ACL) z rzeczywistym fetch oryginalnego HTML EIA, używa prywatnego ephemeral CSV 0600 tylko w czasie joba i wykorzystuje wcześniejszy fail-closed reviewer `eia_wti_gap_receipt.review_gap`. Udostępnia wyłącznie agregaty i hashe, bez cen lub haseł. Dokument: [WTI_NEON_STAGING_SINGLE_RUN_PL.md](WTI_NEON_STAGING_SINGLE_RUN_PL.md).

**Oczekiwane kryteria LIVE:** 660 istniejących WTI, 695 oficjalnych, 35 brakujących po 2026-08-25, 0 różnic cen, prawdziwe źródłowe `Release Date 2026-10-15`, osobne realne SHA oryginalnego HTML i lokalnego CSV, `database_reads=1`, `database_writes=0`; wszystkie M1/M2/M3 `HOLD_NO_CHANGE`. Jeśli EIA opublikuje nowy release, zamrożony kontrakt słusznie odmówi pozytywnej walidacji; najpierw nowy jawny review. Operator: GitHub Actions → **Frozen WTI EIA and Neon STAGING receipt — MANUAL READ ONLY** → Run workflow (`main`) → przeczytać bezpieczny raport JSON. Podłączone narzędzia GitHub w tej sesji **nie udostępniają dispatch nowego workflow**; nie zgłaszać, że LIVE już wykonał się.

**Zadania #2 i #22 nadal OTWARTE.** Nowy mechanizm nie naprawia 35 brakujących cen, nie certyfikuje autentycznej historycznej dostępności point-in-time i nie autoryzuje żadnego importu. Nadal `UNVERIFIED_HISTORICAL_PUBLICATION` / `MARKET_DATA_NOT_READY`; 0 zleceń, 0 zmian alokacji, 0 nowych zapisów Neon lub produkcji.

## 19.10.2026 — rzeczywisty RAW HTML EIA SHA i niezależny Neon SHA, nadal nie zamknięty PR #29 receipt

**Nowe pozytywne potwierdzenie:** bezpiecznie ponowiono JEDYNIE wcześniej sprawdzony publiczny `verify-eia` z historycznego workflow [#39158580349](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39158580349), nowy job `118231417846`; 3/3 oficjalne walidacje SUCCESS, `DRY_RUN_NO_DATABASE_WRITE`. WTI realnie pobrany RAW HTML w dn. 19.10.2026 o `18:27:18.526225+00:00`: `document_sha256=5f7d6bb8811775c478552f81c6a66b83feb19c714972eaac0e11d23cf7995cd7`, strona EIA wydanie 15.10.2026, parser 285 obserwacji 25.08.2025–14.10.2026. Brent w `18:27:18.101970 UTC`: HTML SHA `c962f670c53d24a8047aeb461b1cfd366cdeca9b1faf5ec097630491354bdb51`, 289 obserwacji. Henry Hub HTML SHA `5ef9c288bd8a9dbae5e6763b2b8ba2611d93766aabe13283d475b9f5f472642c`, 283 obserwacje. Brak Neon, zapisu i sekretów w jobie.

**Ważne:** EIA HTML SHA dla WTI był **inny** dzień wcześniej (18.10: `715bd983c39901256a5ff95bc3115c3840f3aaeb4d88e71d3756a8df1f2442ac`), mimo identycznej daty wydania strony 15.10 i liczby 285 obserwacji. Nie wnioskować, że zmieniły się ceny: oryginalne bajty HTML mogą zmienić się bez modyfikacji szeregu cen. W przyszłym raporcie warto oddzielić HASH RAW HTML od deterministycznego HASHA sparsowanych dat i wartości oraz zachować prawdziwy czas pobrania.

**Niezależne SQL SELECT na izolowanym Neon STAGING** policzyło SHA256 w DB z deterministycznej konkatenacji `observed_for::date || ',' || close_price::text` uporządkowanej datą (separator newline; NIE jest to sha lokalnego CSV): WTI 660/660 unikalnych dat, do 25.08.2026, data backfill 17.10.2026, `2014f2ca99491cae91eafe3807d87300305ff201f82e24793aec21b2839862f8`. Brent 706/706 do 14.10, data backfill 17.10, `8ab5ef9fa97760a6940064fa39dac2c59b1bc0616d1d402b2fe891a823715a1a`. 0 surowych cen opublikowanych poza DB. Ostatni pełny *data+wartość* audyt porównawczy: WTI 695 EIA / 660 match / 35 EIA-only po 25.08 / 0 mismatch, Brent 706/706.

**Nie fałszować statusu:** To dowodzi oddzielnie (a) autentycznego SHA RAW źródłowej strony EIA z publicznego joba i (b) kryptograficznego SHA zawartości bieżącej historii w Neon. **Nie wykonano jeszcze jednego spójnego uruchomienia `scripts/eia_wti_gap_receipt.py`**, ponieważ wymaga bezpiecznie dostępnego lokalnego CSV oraz bajtów EIA w tym samym procesie. Exa/web zwraca markdown, nie RAW HTML; container nie posiada obecnie łączności DNS z EIA. Nie importować danych, nie przekazywać prywatnych DSN ani eksportować surowych cen do publicznych artefaktów. Źródło `UNVERIFIED_HISTORICAL_PUBLICATION` i PIT `MARKET_DATA_NOT_READY` bez zmian.

Dowód i wszystkie hashe w [Issue #22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6274353997). Następna decyzja techniczna: zaakceptowane, kontrolowane **wspólne środowisko tylko READ-ONLY EIA + weryfikowany lokalny eksport referencyjny**, który uruchomi już obecny kontrakt bez uprawnień zapisu i bez wycieku surowych danych; do tego czasu #2 i #22 nadal OTWARTE. M1/M2/M3 `HOLD_NO_CHANGE`. 0 DB writes, 0 trades, 0 ACL/secret/schedule changes.

## 19.10.2026 — ponowna pełna kontrola EIA vs Neon po PR #29 (bez oryginalnego HTML SHA)

**WYKONANE tylko odczyt:** po PR #29 powtórzono porównanie całego przedziału 02.01.2024–14.10.2026, obecna oficjalna EIA WTI + Brent edition **Release Date 15.10.2026**, pełna lista dat i dokładne porównanie wartości numerycznych poprzez 2 SQL `SELECT` z `FULL OUTER JOIN` na izolowanym Neon STAGING (`br-wandering-union-ba6ogf6l`). Wynik zgodny z poprzednim audytem: **WTI EIA 695 / Neon 660 zgodnych / 35 braków (26.08–14.10.2026) / 0 mismatches / 0 extra**; **Brent 706 / 706 zgodnych / 0 braków / 0 mismatches**.

**Ważne ograniczenie dowodu:** obecny odczyt strony EIA został przetworzony przez narzędzie do tekstu/markdown, więc **nie ma SHA-256 faktycznych oryginalnych bajtów HTML** z tego odczytu; nie podstawiać hasha poprzedniego workflow. Nie uruchomiono też nowego `scripts/eia_wti_gap_receipt.py` z lokalnym autoryzowanym CSV ani ręcznego GitHub `workflow_dispatch`. To niezależny audyt EIA data+cena vs aktualna STAGING, **nie** wykonanie całego zamrożonego kontraktu z oryginalnym source HTML SHA, ani potwierdzenie per-dzień historycznych publication vintages.

Kompletne wyniki, 35 konkretnych dat i metodologia: [Issue #22 komentarz #6274202100](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6274202100). Issue #22 nadal OTWARTE; Issue #2 nadal OTWARTE, gdyż brak autentycznych real PIT observation versions. Brak przyczyny historycznego ucięcia importu; dane do ewentualnego backfillu wymagają osobnej zgody na zapis i zaświadczenia bieżącego pobrania oryginalnego EIA HTML. **W tej sesji: 0 zapisów Neon, 0 produkcji, 0 zmian ACL/sekretów, 0 portfolio/trades/schedules**; `UNVERIFIED_HISTORICAL_PUBLICATION`, M1/M2/M3 `HOLD_NO_CHANGE`.

## 19.10.2026 — zamrożony kontrakt kontroli 35 braków WTI / PR #29

**Dostarczone na `main`:** [PR #29](https://github.com/gniewkob/Investment-Strategy-Lab/pull/29), squash `437b66f9a4f66b7c4d0d4f35e3549a55f52e62f0`. Przegląd oficjalnej historii EIA WTI względem **lokalnie dostarczonego** publicznego wyciągu cen, tylko odczyt, z wcześniej zamrożonym oknem 02.01.2024–14.10.2026, ostatnią zapisaną datą 25.08.2026, oczekiwanym wydaniem EIA 15.10.2026 i liczbą **35 braków**. Nie utożsamiać z importem/notowaniami point-in-time.

- Dodano `scripts/eia_wti_gap_receipt.py`, który ponownie wykorzystuje dotychczasowy parser EIA z `src/isl_v2/eia_sources.py` i `compare_dates_prices` z `scripts/eia_readonly_audit.py`. Kontrakt **fail closed**: brak kompletnego oficjalnego zakresu, różnica nawet jednej istniejącej wartości, luka przed odcięciem, niezgodność kalendarza lub liczby braków, nowy dzień wydania EIA albo inny opcjonalnie przypięty hash źródła ⇒ błąd, bez żadnego zapisu.
- `read_local_reference_with_digest` czyta raz maksymalnie 1MB lokalnego 3-kolumnowego CSV, wykorzystuje te same bajty do parsowania i SHA-256, odrzuca dodatkowe/brakujące kolumny/daty niespełniające ISO. Raport zawiera **daty i agregaty, nie ceny**, faktyczny retrieval timestamp, dzień wydania obecnego EIA, SHA256 prawdziwie pobranego HTML i dokładnego lokalnego pliku. Hash nie potwierdza oryginalnej daty pierwszej publikacji.
- **CI PR:** [#39300976366](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39300976366) = SUCCESS **180/180** testów offline, kontrola `EIA_VALIDATION_HAS_NO_DATABASE_WRITE_PATH`. **CI main:** [#39301117638](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39301117638) = SUCCESS **180/180**. Live HTTPS w nowym jobie pozostawało pominięte (tylko manualny `workflow_dispatch`). NIE wykonano w ramach tego PR nowego faktycznego eksportu CSV z Neon ani nowego manualnego źródłowego porównania.
- **Dostępne instrukcje:** [WTI_SOURCE_COVERAGE_RECEIPT_PL.md](WTI_SOURCE_COVERAGE_RECEIPT_PL.md). [Issue #22 — wynik i ograniczenia](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6274106670), [Issue #2 — pochodzenie i PIT](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2#issuecomment-6274107649). Oba pozostają **OTWARTE**, gdyż brak prawdziwych poświadczonych historycznych publikacji i lokalnie potwierdzonego uzupełnienia WTI.
- **Zachować ograniczenia:** historyczne 35 braków udowodnione wcześniej wyłącznie w porównaniu obecnej tabeli EIA vs STAGING; `UNVERIFIED_HISTORICAL_PUBLICATION`, 0 rzeczywistych niezależnie zweryfikowanych PIT, `MARKET_DATA_NOT_READY`, M1/M2/M3 `HOLD_NO_CHANGE`, brak upoważnienia do backfillu, brak wszelkich zapisów Neon/produkcji, kredencjałów, ACL, transakcji, harmonogramów i zmiany alokacji.

## 19.10.2026 — paired benchmark descriptive gate / PR #28

**Dostarczone do `main`:** [PR #28](https://github.com/gniewkob/Investment-Strategy-Lab/pull/28) squash `de1922e3bc3f62ab3f8fc0e9254f1a44be31f3c4`. [PR CI run #39298153706](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39298153706) = SUCCESS, **165/165** syntetycznych testów, pełny edukacyjny pipeline (bez sekretów, bazy i transakcji) przechodzi.

- Nowy `scripts/paired_research_evidence.py` czyta tylko istniejące **zagregowane metadane** `nonoverlap_validation.json` i liczy zdarzenia ocenione na dokładnie tych samych datach: oba trafione, oba błędne, tylko radar, tylko naiwny znak poprzedniego baru. Zwraca jedynie liczniki i parowaną różnicę procentowych punktów, bez cen, bez baz i działań. Zwraca `PAIRED_BASELINE_DESCRIPTIVE_ONLY` i `NO_PREDICTIVE_ADVANTAGE_OR_EQUIVALENCE_CLAIM`, nie estymuje przewagi na rynku.
- **Fail closed**: `robustness.json` dla serii zawiera ostatnie max 12 zdarzeń. Przy większej liczbie niż 12 pełnych zdarzeń skrypt odmawia wyliczenia wyniku na niekompletnym wycinku; testy wykrywają też sfałszowane liczniki/polityki, duplikaty dat i niezgodne horyzonty.
- Naprawiony tekst w `scripts/opportunity_research_pipeline.py`: przy 0 zdarzeń makro informuje, że nie dostarczono niezależnych dowodów zamiast błędnie sugerować obecność oficjalnych dat i kontrargumentów. Rozszerzone CI emituje tylko **syntetyczny** `paired_baseline_diagnostic.json`.
- [Protokół prospektywnej walidacji](PAIRED_BASELINE_PROTOCOL_PL.md) zabrania nazywania wcześniej oglądanych wyników 2024–2026 nowym nietkniętym holdoutem; wymagane są przyszłe rzeczywiste vintages publikacji, wcześniej zamrożone reguły, porównanie parowane oraz kontrola wielokrotnego testowania i zależności szeregowej.
- **Stan realnych danych nadal bez zmian:** ostatnia rzeczywista manualna analiza v0.2 [#39245012461](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39245012461) pokazała 0pp dodatkowej zgodności kierunku względem naiwnej reguły na tych samych zdarzeniach dla wszystkich 8 serii. Nie wykonano po tym PR nowej manualnej analizy rzeczywistych danych; 0 zweryfikowanych rzeczywistych source-vintage PIT (przy 3 testowych wersjach), 35 brakujących cen WTI. Issue #2 i #22 otwarte; #21 i #23 zamknięte.
- **Bezpieczna granica:** wszystkie M1/M2/M3 `HOLD_NO_CHANGE`, źródło `UNVERIFIED_HISTORICAL_PUBLICATION`, nie zmieniano Neon, produkcji, sekretów, ról, schedule, portfela czy zleceń. [Dowód w Issue #4](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4#issuecomment-6273707505).

## 19.10.2026 — Issue #21 zamknięte: pełna historia anomalii BTC/ETH, PR #27

**Działa na `main`:** [PR #27](https://github.com/gniewkob/Investment-Strategy-Lab/pull/27), squash `d3fc37e993150912c4671a1b93e1681fc5c31b03`. Problem P1 `reference_data_quality._extreme_relative_moves` polegał na **zależności warstwy bezpieczeństwa danych od listy ostatnich 10 zdarzeń przeznaczonej tylko do wyświetlania** (`radar.cross_market_btc_eth.recent_divergence_events`). Skutkiem mogło być usunięcie starego skrajnego ostrzeżenia po wystąpieniu 11 późniejszych umiarkowanych odchyleń.

Poprawka liczy |z| ≥ 8 **od nowa na całej poprawnie zwalidowanej historii wspólnych dat BTC/ETH**, ze średnią i populacyjnym odchyleniem standardowym z wyłącznie **20 poprzednich okresów**; 20-bar MAD pozostaje dodatkową diagnostyką. Fingerprint danych i flagi `SOURCE_REVALIDATION_REQUIRED` pozostają, żadne przyszłe obserwacje nie wpływają na starszą punktową wartość. Istniejące podsumowanie `recent_divergence_events` nadal może pokazywać ostatnich 10 — nie ma już roli źródła prawdy dla blokady.

- **Regresje offline syntetyczne:** 1 wczesna skrajna rozbieżność + 11 późniejszych umiarkowanych; stara zostaje pominięta na ekranowej liście 10, lecz jest nadal wykrywana przez quality. Dodatkowo test pustej/sfałszowanej listy prezentacyjnej, braku wpływu przyszłych dat na wcześniejszą punktową ocenę oraz braku fałszywej anomalii dla identycznych ruchów cen.
- **PR CI:** [bridge #39293026553](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39293026553) i [research pipeline #39293026063](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39293026063), oba `SUCCESS`, **154 testy PASS** każdy. **CI po merge na `main`**: [bridge #39293158234](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39293158234) oraz [pipeline #39293158350](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39293158350) oba `SUCCESS`.
- [Issue #21](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21#issuecomment-6273021199) zamknięte `completed`. Użytkownik **nie uruchomił** jeszcze od tego merge nowego rzeczywistego `legacy-history-research.yml`; **nie deklarować** zmierzonych nowych liczników jakości na STAGING z v0.3.
- Wcześniej równolegle [PR #26](https://github.com/gniewkob/Investment-Strategy-Lab/pull/26) scalił silniejszy PIT-fixture gate. Nasz konfliktujący [PR #25](https://github.com/gniewkob/Investment-Strategy-Lab/pull/25) przeszedł CI po poprawce testu, lecz został **zamknięty bez merge** (duplikat). [Issue #23](https://github.com/gniewkob/Investment-Strategy-Lab/issues/23#issuecomment-6273033657) zamknięte jako wykonane w zakresie wiarygodności raportowania, **nie** gotowości realnych danych.
- **Nadal otwarte:** [Issue #22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22) — 35 brakujących notowań WTI 26.08–14.10.2026 wobec EIA, bez backfillu; [Issue #2](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2) — prawdziwe oryginalne źródła PIT, **0 wersjonowanych obserwacji źródłowo zweryfikowanych**. Samo zgodne EIA archiwum nie dowodzi daty pierwszej publikacji.
- **Granica:** badania edukacyjne, `UNVERIFIED_HISTORICAL_PUBLICATION`, 0 nowych zapisów Neon/ACL/sekretów/produkcji, 0 zleceń, 0 zmian wirtualnych alokacji, brak harmonogramów. M1/M2/M3 nadal `HOLD_NO_CHANGE`.

## 19.10.2026 — wskaźniki PIT syntetyczne vs zweryfikowane (PR #26)

**WDROŻONE na `main`:** [PR #26](https://github.com/gniewkob/Investment-Strategy-Lab/pull/26), squash `238b3316581cca992da33ff0d89a08008b7a9a74`. Zmieniono tylko `scripts/staging_data_audit.py` i `tests/test_staging_data_audit.py` w badawczym audycie jakości danych. CI [#39287318533](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39287318533) **SUCCESS**, pełny zestaw **152/152 testów PASS** (w tym nowe testy wykluczania syntetycznych fixture).

- `pit_eligible_rows` jest nadal **techniczną widocznością**, nie liczbą źródłowo uwierzytelnionych obserwacji. Dodano `pit_fixture_rows`, `pit_nonfixture_unverified_rows`, `pit_verified_market_rows` i ostrzeżenia `SYNTHETIC_PIT_FIXTURE_NOT_MARKET_DATA` / `NO_VERIFIED_POINT_IN_TIME_MARKET_EVIDENCE`.
- Odczytowe SQL identyfikuje `metadata.synthetic=true` lub `metadata.fixture_only=true`; źródła bez potwierdzenia nie mogą wypełnić zweryfikowanego minimum. Brak obecnie niezależnego per-row certyfikatu oryginalnej publikacji, dlatego `read_snapshot` zachowawczo przypisuje 0 prawdziwych zweryfikowanych źródeł i pustą serię jakościowo certyfikowaną, bez sztucznego podnoszenia gotowości.
- Niezależny READ-ONLY SQL na odizolowanym Neon STAGING potwierdził `prices_asof(now())=1` technicznie dostępny, dokładnie **1 syntetyczny**, **0 niesyntetycznych**, **0 zweryfikowanych źródłowo**. Historyczna tabela 3711 legacy obserwacji nadal `UNVERIFIED_HISTORICAL_PUBLICATION`. Wcześniejszy przyszły znacznik w jednym z trzech fixture jest zamierzonym testem, **nie usuwać go**.
- `MARKET_DATA_NOT_READY`, 0 zleceń, 0 zapisu bazy, brak harmonogramu, wszystkie M1/M2/M3 `HOLD_NO_CHANGE`. [Issue #23 status weryfikacji](https://github.com/gniewkob/Investment-Strategy-Lab/issues/23#issuecomment-6272267236). **Ręczny realny workflow staging-data-audit po tym commicie nie był jeszcze uruchamiany**, CI jest offline. Po nowym manualnym audycie sprawdzić `audit.json` i `audit.md` oraz liczniki. Issue #2 nadal dotyczy źródłowo uwierzytelnionych realnych PIT.

# Investment Strategy Lab — pełne przekazanie kontekstu nowej sesji agenta

> **Snapshot: 19 października 2026, około 07:11 UTC.** Ta strona opisuje stan **zweryfikowany w GitHub oraz Neon**, odróżnia go od planów. Stan może się później zmienić — przed zapisem albo wykonaniem operacji odczytaj aktualny `main`, Issues, PR-y, uprawnienia i historię workflow.  
> **Pierwsza lektura nowego agenta:** [`../AGENTS.md`](../AGENTS.md), potem niniejszy plik, [`HISTORICAL_REFERENCE_BRIDGE_PL.md`](HISTORICAL_REFERENCE_BRIDGE_PL.md) oraz [`OPPORTUNITY_RADAR_PL.md`](OPPORTUNITY_RADAR_PL.md).  
> **Status:** system badawczy / edukacyjne symulacje. **Nie ma zleceń, handlu, realnych inwestycji ani rekomendacji zakupowych.**

## 19.10.2026 — wydzielony parser EIA bez importu scalony do main (PR #24)

**WDROŻONE NA MAIN:** [PR #24](https://github.com/gniewkob/Investment-Strategy-Lab/pull/24), squash commit `db981d4639d5bc8ed0e5c5e1567bc41f32a982c8`. Reuse istniejącego parsera EIA z Draft PR #1 (`src/isl_v2/eia_sources.py`) i testów, bez kopiowania potencjalnie zapisującego do Neon `eia_ingest.py --write`.

- Nowy wyłącznie odczytowy `scripts/eia_readonly_audit.py`: HTTPS z allowlisty EIA, weryfikacja stałego adresu docelowego, Content-Type HTML, limit 8 MB, oryginalny SHA-256 rzeczywiście pobranego HTML, prawdziwy czas pobrania. Opcjonalne porównanie po dacie i Decimal do LOKALNEGO, publicznego pliku 3 kolumn `instrument_code,observed_for,close_price`, bez bazy, bez zewnętrznego wysyłania cen; wypisuje agregaty i daty różnic, nie ceny.
- Nowe testy syntetyczne `tests/test_eia_readonly_audit.py`; workflow `.github/workflows/eia-readonly-validation.yml` odpala pełną offline suite przy PR/push na main. Żywe zewnętrzne HTTPS do EIA uruchamia WYŁĄCZNIE manualny `workflow_dispatch`, bez sekretów i bez publikacji raw artifacts. **Nie uruchomiono jeszcze tego workflow manualnego na nowym kodzie**; CI PR używało fixture.
- **CI zweryfikowane:** [read-only PR #39276159521](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39276159521) i [full runner PR #39276159468](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39276159468) = PASS; pełny test suite **149/149 PASS**, kontrola statyczna `EIA_VALIDATION_HAS_NO_DATABASE_WRITE_PATH`. Nowy przewodnik [EIA_READ_ONLY_AUDIT_PL.md](EIA_READ_ONLY_AUDIT_PL.md).
- Wykonane wcześniej porównanie EIA vs Neon: WTI oficjalnie 695, zgodne 660, brak 35, różnic wartości 0; Brent 706/706 zgodne. Nie oznacza to gotowości oryginalnych historycznych publikacji ani pozwolenia na ingest. [Issue #22 zapis finalny](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6270654753), [Issue #2 status źródeł](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2#issuecomment-6270658965).
- **OTWARTE:** Issue #21 (radar BTC/ETH lista ucięta do ostatnich 10), Issue #22 (brakujących 35 cen WTI NIE UZUPEŁNIONO), Issue #23 (wszystkie 3 wersjonowane źródła są testowym fixture), Issue #2 (wersjonowane rzeczywiste PIT). Bez zmian Neon, sekretów, ACL, produkcji, harmonogramów, wirtualnych alokacji, bez transakcji. `UNVERIFIED_HISTORICAL_PUBLICATION`, M1/M2/M3 `HOLD_NO_CHANGE`.

## 19.10.2026 — pełna kontrola dzień/cena EIA vs Neon WTI i Brent

**WYKONANE, tylko odczyt:** pobrano opublikowane tabele dzienne EIA WTI Cushing i Brent (obie z nagłówkiem `Release Date: 10/15/2026`), rozpisano faktyczne wiersze tygodniowe na daty dzienne (bez domyślania brakujących komórek), wykonano `FULL OUTER JOIN` po `observed_for::date` i porównano dokładne wartości numeryczne `close_price` z oficjalnymi cenami przy tolerancji 1e-7 w Neon STAGING `br-wandering-union-ba6ogf6l`. Zakres 02.01.2024–14.10.2026:
- **WTI:** 695 dni w obecnej tabeli EIA, 660 dni Neon **zgodnych datą i ceną**, **35 dat EIA tylko** (26.08.2026–14.10.2026), 0 dni Neon tylko, **0 rozbieżnych cen**.
- **Brent:** 706 dni EIA, **706 zgodnych** dat i cen w Neon, **0** braków i rozbieżności.
- Łącznie: **1401** EIA, **1366** zgodnych obecnych w Neon, **35** braków WTI, **0** rozbieżnych cen.
- Bieżąca publiczna strona EIA nie potwierdza źródłowej daty pierwotnej publikacji **każdego** historycznego kursu; nie posiada tu utrwalonego hasha **oryginalnej reprezentacji HTML pobranej w tym audycie**. Nie wolno przypisywać mu historycznej dostepności point-in-time ani SHA-256 wcześniejszego GitHub Actions. Powyższe dowody to audyt **obecnego** oficjalnego archiwum vs **obecna** baza.
- Repo posiada już parser źródeł EIA w niepołączonym Draft PR #1 (testy HTTPS CI, bez DB). Wykorzystać parser w osobnym *reviewed* source-provenance dry-run; **nie** uruchamiać `--write`, nie tworzyć równoległego ETL ani automatycznego backfillu bez osobnej zgody.
- Dokładny wynik i metodologia: [Issue #22 — 2026-10-19 full-date matching](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6270375923). Audyt nie rozstrzyga **przyczyny** ucięcia dawnego wsadu z 17.10; brak dowodu, że WTI było publikowane w obecnej postaci w każdej historycznej dacie obserwacji.
- Dotychczasowe blokady v0.2 `STALE_DATA`, `PEER_COVERAGE_GAP` oraz `UNVERIFIED_HISTORICAL_PUBLICATION` pozostają. **Nie zmieniano** bazy (0 insert/update), uprawnień, produkcji, kodu radaru, sekretów, harmonogramów ani strategii. Wszystkie M1/M2/M3 `HOLD_NO_CHANGE`. Problem prezentacyjnej listy 10 anomalii w Issue #21 nadal nierozwiązany.

## Aktualizacja 19.10.2026 — istniejący parser EIA i potwierdzony deficyt 35 WTI

**Odkrycie:** w [Draft PR #1](https://github.com/gniewkob/Investment-Strategy-Lab/pull/1), poza aktualnym `main`, znajduje się gotowy, przetestowany parser oficjalnego EIA `src/isl_v2/eia_sources.py`, odczytowy CLI `src/isl_v2/eia_ingest.py`, testy i workflow `official-eia-source-validation.yml`. Parser domyślnie analizuje 420 dni, waliduje stronę, datę `Release Date`, kalendarz, wartości i hash SHA256. Odrębna ścieżka `--write` **nie jest zatwierdzona ani uruchomiona na Neon**; nie przenosić jej automatycznie, nie zakładać że wykonała poprzedni import 3711 rekordów.

Wcześniejszy prawdziwy, wyłącznie HTTPS i bez zapisu do bazy [GitHub Actions run #39158580349](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39158580349), 18.10.2026, **SUCCESS**: WTI 285 zweryfikowanych rekordów od 25.08.2025 do 14.10.2026 (source `Release Date=2026-10-15`, SHA256 oryginalnego HTML `715bd983c39901256a5ff95bc3115c3840f3aaeb4d88e71d3756a8df1f2442ac`), Brent 289, Henry Hub 283; wszystkie `DRY_RUN_NO_DATABASE_WRITE`. Test potwierdza, że źródło pozwala odczytać zakres brakujący w historycznej tabeli Neon.

Niezależne **SQL SELECT**, dla identycznego okna 25.08.2025–14.10.2026, w izolowanym Neon STAGING: Brent **289** zapisanych (zgodność *liczebności* ze źródłem, bez potwierdzonej zgodności każdego rekordu), WTI **250** zapisanych (ostatnia data 25.08.2026) vs **285** u parsera EIA, więc **deficyt netto 35 rekordów**. Osobno porównano 10 konkretnych dat EIA: 2 zgodne, 8 następnych nieobecnych. Nie jest znana pierwotna przyczyna ucięcia starego importu; do pełnego dowodu potrzebne porównanie *data-w-data*, bo WTI i Brent mogą różnić się kalendarzem publikacji. [Issue #22 — dowody](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6269888952), [Issue #2 — istniejący parser PIT](https://github.com/gniewkob/Investment-Strategy-Lab/issues/2).

**Rekomendowana ścieżka:** wykorzystać/reviewować istniejący parser EIA wyłącznie w dry-run read-only, z odrębnym jawnie zabezpieczonym etapem przyszłego importu po osobnej zgodzie, poprawnym źródłowym hash i rzeczywistych datach pobrania. Nie backdatować `published_at`, `retrieved_at` ani `recorded_at`. Dane nadal `UNVERIFIED_HISTORICAL_PUBLICATION`. Brak zleceń, alokacji, harmonogramów, zmian Neon i produkcji.

## Aktualizacja 19.10.2026 — syntetyczne źródła PIT, nie błąd przyszłej daty

**Nowy zweryfikowany stan (Neon STAGING, tylko odczyt):** sprawdzono oryginalną implementację `investment_lab.prices_asof(cutoff)`, trzy wpisy `price_observation_versions` oraz trzy powiązane `source_documents`. Wszystkie 3 dokumenty mają w `metadata` jawny znacznik `synthetic` albo `fixture_only`. Wszystkie trzy ceny `GOLD_NBP_PLN_G` są **syntetycznymi przykładami testującymi**; notatki na rekordach to między innymi „Synthetic late ingest PIT fixture; NOT a real market price” oraz „Synthetic data, test branch only…”. Wynik SQL: `total_documents=3`, `fixture_documents=3`, `total_versioned_rows=3`, `fixture_versioned_rows=3`, **`non_fixture_versioned_rows=0`**.

**Korekta wcześniejszej interpretacji:** `retrieved_at=2026-10-20T10:00Z` oraz `recorded_at=2026-10-20T10:00Z` są **celowo przyszłe**, aby testować odrzucanie spóźnionych/przyszłych informacji. To **nie jest wykryty błąd datowania realnych danych** i NIE należy go poprawiać. `prices_asof` stosuje konserwatywne `GREATEST(available_at, published_at+opóźnienie dla DAY, recorded_at, retrieved_at) <= cutoff`. Wyniki `prices_asof` na 28.08 i 30.09 = **0**; na 17.10 i `now()` = **1**, ale to **jedna technicznie widoczna próbka testowa, nie zweryfikowane notowanie**.

**Nowy priorytet jakości:** `scripts/staging_data_audit.py` liczy `pit_eligible_rows=1` bez odróżnienia syntetycznych fixture od realnego pochodzenia. Wymagamy osobnych metryk realnych i technicznie dopuszczonych danych; [Issue #23](https://github.com/gniewkob/Investment-Strategy-Lab/issues/23). Zadanie [#22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6269776862) skorygowano o fakt celowej syntetyczności. Dotychczasowy problem importu WTI i [#21](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21) (ucina 10 zdarzeń w module jakości) pozostają otwarte. Przed jakimkolwiek twierdzeniem o point-in-time dla **prawdziwych** danych konieczne jest rekordowe pochodzenie, data publikacji i retrieval — **0 realnych wersjonowanych obserwacji aktualnie spełnia tę bazę**. Legacy `price_observations=3711` nadal `UNVERIFIED_HISTORICAL_PUBLICATION`.

Nie zmieniano danych, ról, ACL, sekretów, produkcji, harmonogramów, kodu analitycznego, transakcji ani żadnych alokacji. Badania wyłącznie edukacyjne, M1/M2/M3 `HOLD_NO_CHANGE`.

## Kontynuacja P1 — 19.10.2026: diagnostyka read-only bez backfill

Po ponownym sprawdzeniu `main` (przed dopisaniem tej sekcji HEAD `b085d665`) issue [#21](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21) i [#22](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22) nadal `OPEN`, brak PR wdrażającego usunięcie błędu i brak zmian w `reference_data_quality.py`. Nie próbować obchodzić poprzedniego zablokowanego zapisu kodu.

**Nowe twarde dowody:**
- Niezależny read-only SQL policzył **15** różnic BTC/ETH z |z| ≥ 2.5 (20 wcześniejszych okresów); radar pokazuje tylko ostatnie **10**; **5** nie jest wyświetlanych. **Jeden** skrajny |z| ≥ 8 (19.08.2026, 16.2658) nadal znajduje się na miejscu **2** najnowszych alarmów; **0** skrajnych zostało dotąd faktycznie pominiętych. Błąd listy 10 jest **potencjalnym przyszłym false negative**, nie udowodnioną aktualną awarią. Pełny dowód w [Issue #21 komentarz](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21#issuecomment-6269596457).
- Oficjalny [EIA Cushing WTI daily](https://www.eia.gov/dnav/pet/hist/RWTCD.htm) vs SELECT LEFT JOIN na Neon STAGING: 24.08 = 86.34 i 25.08 = 83.90 **zgadzają się**; 26.08 = 83.46, 27.08 = 84.81, 28.08 = 84.57, 31.08 = 87.03, 01.09 = 91.48, 02.09 = 92.15, 03.09 = 92.55, 04.09 = 92.69 **brakuje** w Neon. Na 10 porównanych dat: 2 dopasowania, 8 braków; **ZERO insert/update**. Dowód w [Issue #22 komentarz](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22#issuecomment-6269597149).
- Sprawdzono drzewo `main` (61 pozycji) i GitHub code search: **nie ma w obecnym repo skryptu źródłowego importu/ETL WTI**. Znalezione odniesienia WTI są jedynie w module jakości, radarze, bridge oraz teście. Dlatego **nie ustalono jeszcze przyczyny** ucięcia ETL i nie ma bezpiecznej podstawy do samoczynnego backfillu. Wymagane odnalezienie oryginalnego procesu importu/źródła spoza obecnego kodu, nie tworzenie nowego zapisu w ciemno.
- Wersjonowane provenance dalej: 3 `source_documents`, 3 `price_observation_versions` (wszystkie `nbp_gold`), `prices_asof(now())` = 1, jedna próbka ze znacznikiem `retrieved_at` w przyszłości względem aktualnego czasu serwera, legacy 3711 rekordów bez potwierdzenia PIT. `UNVERIFIED_HISTORICAL_PUBLICATION` bez zmian.

**Granica:** żadnych zapisów bazy, sekretów, schematów, produkcji, uzupełnienia cen, wdrażania strategii, harmonogramów ani handlu. M1/M2/M3 `HOLD_NO_CHANGE`. Priorytet naprawy to rozdzielenie pełnej populacji anomaliów od listy prezentacyjnej i odtworzenie ETL z niezależnym provenance. Nie wolno deklarować CI PASS dla niewdrożonej poprawki.

## Aktualizacja — 19.10.2026, audyt źródeł i blokery P1 (tylko odczyt)

Po pierwszym udanym v0.2 przebiegu ponownie przeprowadzono **wyłącznie odczyt** na izolowanym Neon STAGING `br-wandering-union-ba6ogf6l`; bez zmian produkcji, danych, uprawnień, tokenów, alokacji, harmonogramów i zleceń.

- **Provenance vs legacy:** `investment_lab.price_observations` = 3711 historycznych cen (backfill 17.10), natomiast `source_documents` = 3 oraz `price_observation_versions` = 3, wszystkie wyłącznie `nbp_gold`. `prices_asof(now())` zwróciło **1** dopuszczalny rekord, **1** wersjonowana obserwacja posiada znacznik `retrieved_at > now()` (najpóźniej 20.10.2026), `source_code` mismatch = 0. Prawidłowa walidacja PIT dla historycznego BTC/ETH, ropy i gazu jest nadal **niemożliwa**.
- **WTI:** lokalna tabela zawiera 660 punktów do 25.08.2026; Brent 706 do 14.10.2026. 56 dat Brent nie ma w WTI, z czego 35 po odcięciu serii. Oficjalna [EIA Cushing WTI](https://www.eia.gov/dnav/pet/hist/RWTCD.htm) potwierdza 25.08 = 83.90, 26.08 = 83.46, 27.08 = 84.81 i 28.08 = 84.57 USD/bbl. Przyczyna ucięcia importu nieustalona. Porównanie do kalendarza Brent to proxy, nie kanoniczna lista publikacji WTI.
- **P1 code integrity:** `reference_data_quality._extreme_relative_moves` korzysta z `opportunity_radar._btc_eth_divergence().recent_divergence_events`, ograniczonych do ostatnich **10**. Stara skrajna anomalia może zniknąć z jakości po dodaniu dalszych zwykłych odchyleń. Kontrola jakości powinna badać pełne zweryfikowane wejście niezależnie od listy prezentacyjnej; wymagane synthetic regression, no look-ahead i fingerprint fail closed.
- **Blokada wdrożenia:** poprzednia próba zapisu poprawki do `scripts/reference_data_quality.py` została zablokowana przez mechanizm bezpieczeństwa narzędzia. Nie ma poprawki, testów nowego kodu ani PR/merge. Istnieje niedokończona gałąź `fix/complete-extreme-anomaly-quality-gate` bez poprawki; nie obchodzić blokady narzędzi.
- Dwa dedykowane zadania z wymaganiami odbioru: [Issue #21 — jakość nie może zależeć od listy przyciętej do 10 zdarzeń](https://github.com/gniewkob/Investment-Strategy-Lab/issues/21); [Issue #22 — WTI ETL/provenance/PIT, przyszły retrieval timestamp](https://github.com/gniewkob/Investment-Strategy-Lab/issues/22). W obu **brak zgody na zapisy do Neon i operacje finansowe**. Wszystkie modele M1/M2/M3 pozostają `HOLD_NO_CHANGE`, vintage `UNVERIFIED_HISTORICAL_PUBLICATION`.

## v0.2 — PIERWSZY REALNY STAGING RUN ZALICZONY (19.10.2026)

Po wdrożeniu PR #19 i #20 użytkownik ręcznie uruchomił [GitHub Actions run #39245012461](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39245012461) (commit `fc9c5a2`). Run **SUCCESS**; `LEGACY_HISTORY_RESEARCH_OK observations 3711 series 8 hypotheses_for_review 2 orders 0 database_writes 0`. Pobraną i niezależnie otwartą paczkę [artifact #12182926287](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39245012461/artifacts/12182926287) (ZIP SHA256 `5b02af2eac25e49ac181f6d81934acf53914a06fcc54ee9a8ed750d21f139d19`, 7 plików, expiry 26.10) sprawdzono pod kątem manifestu, quality, ledger i robustness.

- **Dane identyczne z v0.1:** fingerprint `5f2b7f788c9723be729ba6ab612751b0ce11b0901b73a78a0473f4129a6e7798`, 3711 obserwacji, 8 serii analizowanych, 62 anomalie, 47 niepokrywających się zdarzeń, 15 odrzuconych nałożeń. Hipotezy do dalszego badania spadły z **4 do 2** wyłącznie z powodu jakości.
- **Do badania:** Brent (12 niezależnych zdarzeń) i Henry Hub (6), wyłącznie `INVESTIGATE_RESEARCH_ONLY`. To NIE jest potwierdzona przewaga ani zakup.
- **`DATA_QUALITY_BLOCKED`:** WTI (STALE_DATA 55.479 dnia oraz PEER_COVERAGE_GAP: 56 brakujących dat względem Brent, z czego 35 po 25.08.2026), ETH i BTC (SOURCE_REVALIDATION_REQUIRED: rozbieżność 19.08.2026 z |z|=16.2658 i MAD robust |z|=18.32).
- **Niewystarczające dowody:** złoto NBP, EUR/PLN, USD/PLN; BTC miało za mało niezależnych zdarzeń również w poprzednim przebiegu.
- **Kluczowy wynik benchmarku:** naive last-bar sign na *identycznych datach* trafia dokładnie tyle samo co znak z-score dla **każdej z 8 serii**; `event_vs_same_date_naive_consistency_pp=0.0` we wszystkich. Brent 50/50%, Henry Hub 50/50%, ETH 66.67/66.67%, WTI 54.55/54.55%, BTC 75/75%. Na tym materiale **brak dowodu dodatkowej skuteczności kierunkowej ponad banalny znak poprzedniego ruchu**, brak istotności i efektu przyczynowego.
- **Bezpieczeństwo:** `UNVERIFIED_HISTORICAL_PUBLICATION`, 0 macro verified events, 0 writes, 0 orders, 0 virtual allocation changes, brak dostępu do prywatnych portfeli, brak surowych cen w artefakcie, brak scheduler; wszystkie M1/M2/M3 `HOLD_NO_CHANGE`. Test tylko odczytowy; bez zmian konfiguracji i produkcji.
- **Dalsze prace:** zweryfikować WTI z [EIA](https://www.eia.gov/dnav/pet/hist/RWTCD.htm), źródła BTC/ETH i autentyczne daty historycznej publikacji, dopiero potem holdout/cross-validation, bez dopasowywania do wyników in-sample. Nie deklarować przewagi, nie uruchamiać automatycznej alokacji. Szczegóły [Issue #4, zapis weryfikacji](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4#issuecomment-6266207530).

## Wdrożenie v0.2 — 19.10.2026

## 19.10.2026 — Opportunity Radar v0.2 Data Quality & Evidence Gate WDROŻONE (CI-only; live staging nieuruchomiony)

Scalono [PR #19](https://github.com/gniewkob/Investment-Strategy-Lab/pull/19) (squash commit `ff9891bdfaed3c7d92db7b5950db132efcb91dbb`) oraz follow-up [PR #20](https://github.com/gniewkob/Investment-Strategy-Lab/pull/20) (squash `db2da856a4d1a38dae79a4ea581b3321409e2163`). Są już na `main`.

- Nowy czysto offline `scripts/reference_data_quality.py` z kontrolą wieku danych względem `snapshot.as_of`: 4 dni dla dziennego BTC/ETH, 10 dni dla innych dziennych, 75 dni dla miesięcznych. To **lokalnie dobrane progi heurystyczne**, nie regulacyjne; „świeżość” nie potwierdza historycznej daty publikacji.
- Kontrola pokrycia kalendarza referencyjnego EIA WTI względem Brent: 56 dat Brent nieobecnych w WTI (w tym 35 po ostatniej dacie WTI 25.08.2026), niezależnie od przyczyny braku. `STALE_DATA` / `PEER_COVERAGE_GAP` blokują **promocję hipotez badawczych**, nie przeprowadzają importu.
- Ekstremalna rozbieżność BTC/ETH (|z|≥8) dodaje `SOURCE_REVALIDATION_REQUIRED` dla obu serii i diagnostykę odporną na anomalie (MAD). Wcześniejsza niezależna kontrola Neon obliczyła dla 19.08.2026 ok. klasyczne z = -16.266, odporne = -18.32; to nadal **nie jest zweryfikowany sygnał prognostyczny**.
- `evidence_decision_ledger.make_ledger` w pełnym pipeline odczytuje fingerprint-bound quality report i klasyfikuje takie hipotezy `DATA_QUALITY_BLOCKED` / `RESOLVE_DATA_QUALITY`, zamiast `INVESTIGATE_RESEARCH_ONLY`. Nie zmienia decyzji M1/M2/M3 `HOLD_NO_CHANGE`.
- Walidator niepokrywających się okien raportuje teraz banalny benchmark utrzymywania znaku ostatniego ruchu na **tych samych datach** co zdarzenia. Różnice są czysto opisowe, bez deklaracji przewagi lub efektu przyczynowego.
- `opportunity_research_pipeline` dodaje `reference_data_quality.json` i podsumowanie do raportu/manifestu; `legacy_history_bridge.run_and_report` też eksportuje tylko zagregowany `reference_data_quality.json` do istniejącego manualnego artefaktu. Nie publikuje surowych notowań ani sekretów.
- Rozbudowane testy syntetyczne, w tym kontrola WTI, anomalii BTC/ETH, fingerprint fail-closed, niezależności od alokacji i braków uprawnień. **128 testów PASS** w offline CI PR #19; cztery workflow CI na finalnym head oraz na `main` po merge #19 przeszły sukcesem. Uzupełniający bridge CI PR #20 PASS. Zlikwidowano istniejące SyntaxWarning w dwóch raportach Markdown.
- **Nie uruchomiono** po tych zmianach workflow `legacy-history-research.yml` na prawdziwym Neon STAGING. Nie zmieniano produkcji, bazy danych, ACL, ról, haseł, sekretów, cen, wirtualnych alokacji, harmonogramów ani zleceń. `UNVERIFIED_HISTORICAL_PUBLICATION` obowiązuje nadal.

**Kolejny krok:** manualny, osobno zatwierdzony jednorazowy przebieg `legacy-history-research.yml` na `main`, weryfikacja logów i agregatowego artefaktu quality; potem praca nad kompletnością źródła WTI i walidacją dat publikacji Coinbase/EIA. Żadnych zautomatyzowanych działań finansowych.

## STAN NAJNOWSZY — 19.10.2026, pierwszy historyczny bridge na STAGING wykonany pomyślnie

Użytkownik ręcznie uruchomił [Historical reference research bridge, GitHub Actions #39241685091](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39241685091) na `main`, commit `500d87895401d62bf68a7a6a872ffeb51850e166`. Workflow zakończył się **SUCCESS** i wypisał `LEGACY_HISTORY_RESEARCH_OK observations 3711 series 8 hypotheses_for_review 4 orders 0 database_writes 0`. To **rzeczywisty workflow w GitHub z połączeniem do STAGING**, a nie offline CI. Osobny sekret `NEON_HISTORICAL_READ_DATABASE_URL` zadziałał (bez odczytu jego wartości w rozmowie). Znalazł się w chronionym GitHub Environment `research-staging`, nie w repo.

Pobrano i przeanalizowano kompletny agregatowy [artefakt #12181127705](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39241685091/artifacts/12181127705), zawierający `manifest.json`, `radar.json`, `ledger.json`, `robustness.json`, `context.json`, `research_report.md`. Dane: 3711 wierszy, 12 serii referencyjnych, 8 analizowanych. 62 retrospektywne nietypowe zdarzenia, 47 niepokrywających się okien, 15 pominiętych nałożeń. **4 pytania badawcze**: Brent 15 raw/12 nonoverlap, WTI 13/11, Henry Hub 9/6, ETH 7/6. **INSUFFICIENT_EVIDENCE:** BTC 8/4, NBP gold 5/3, EUR/PLN 3/3, USD/PLN 2/2. Brak zweryfikowanych zdarzeń makro/geopolitycznych, brak dowodu na skuteczność predykcyjną. Klasyfikacja **INVESTIGATE_RESEARCH_ONLY to nie wskazanie inwestycyjne**.

Bezpieczeństwo: `source_vintage=UNVERIFIED_HISTORICAL_PUBLICATION`, `raw_price_exported_as_artifact=false`, `portfolio_tables_accessed=false`, `database_writes=0`, `real_orders=0`, `paper_fills=0`, `hypothetical_allocation_changes=0`, `schedule_enabled=false`. Trzy M1/M2/M3: `HOLD_NO_CHANGE`. Brak zmian produkcji, brak eskalacji ACL, brak dostępu do brokera. Artefakt ważny przez 7 dni, do 26.10.2026. Szczegóły i źródła: [Issue #4 — komentarz weryfikacyjny](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4#issuecomment-6265732022).

**Nowy blocker (zamiast credentials):** merytoryczna gotowość danych i metod: rzeczywista chronologia publikacji i wersjonowanie źródeł (legacy nadal unverified), opóźnione WTI (ostatnia data 25.08.2026), walidacja z-score 16+ przy rozbieżności BTC/ETH, zewnętrzne benchmarki/oos, kompletne szeregi PLN total-return i koszty. Sekret i połączenie **zadziałały**, ale nie oznacza to gotowości decyzji ani regularnej automatyzacji. W logach są niewstrzymujące `SyntaxWarning` (escape backticks) i Node20 deprecation GitHub Actions. Historyczne akapity poniżej dokumentują wcześniejsze blokady, aktualnie **rozwiązane**.

## NAJNOWSZY stan — 19.10.2026: skuteczna inicjalizacja pierwszego hasła historycznego czytnika

Użytkownik przypomniał sprawdzone rozwiązanie problemu resetu `PASSWORD NULL`. W [Issue #3](https://github.com/gniewkob/Investment-Strategy-Lab/issues/3) oraz w pierwotnej dokumentacji `NEON_LEAST_PRIVILEGE_PL.md` (gałąź Draft PR #1) odnotowano sukces dla `isl_agent_staging_limited` z 18.10.2026: jednokrotny `DO`, 3 × losowy `gen_random_uuid()` po stronie bazy, dynamiczny `ALTER ROLE`, kontrola `rolpassword IS NOT NULL`. Ten mechanizm **zastosowano teraz po wcześniejszej jawnej zgodzie na aktywację credentials** również do nowej `isl_legacy_history_reader` na staging `br-wandering-union-ba6ogf6l`.

Bezpośredni SQL postflight: `rolcanlogin=true`, **`rolpassword IS NOT NULL=true`**, `rolsuper=false`, `rolcreatedb=false`, `rolcreaterole=false`, `rolbypassrls=false`; SELECT na dokładnie jednym obiekcie `investment_lab.price_observations`, zero write/CREATE, brak `holding_snapshots` SELECT, istniejący agent nie dostał dostępu do legacy. Odczyt produkcji potwierdził brak tej roli na gałęzi `main`. Początkowe hasło jest niedostępne (nie zostało zwrócone, zapisane w repo/rozmowie ani przekazane do narzędzia).

**Blokada pierwszego hasła usunięta.** Wymagane: w Neon Console użyć **Reset password** istniejącej roli (tylko prywatnie), zapisać końcowe hasło w menedżerze, ustawić oddzielny chroniony GitHub Environment Secret `NEON_HISTORICAL_READ_DATABASE_URL`. Podłączony GitHub connector nie wspiera zapisu sekretu. Nie potwierdzono jeszcze finalnego resetu ani sekretu. Nie wysyłać hasła/DSN przez chat; nie przeprowadzać kolejnego bootstrapu. Manualny history bridge nieuruchomiony; brak harmonogramu, zleceń i zmian portfela. Instrukcja: [HISTORICAL_LOGIN_BOOTSTRAP_PL.md](HISTORICAL_LOGIN_BOOTSTRAP_PL.md).

## WCZEŚNIEJSZY stan — 19.10.2026, druga zgoda: LOGIN włączony, poświadczenie NIEGOTOWE

Po jawnej **drugiej zgodzie** użytkownika na aktywację roli i skonfigurowanie poświadczenia w GitHub, wykonano na izolowanej Neon STAGING gałęzi `br-wandering-union-ba6ogf6l` bezpieczny `ALTER ROLE isl_legacy_history_reader LOGIN` z pełnym sprawdzeniem dotychczasowych uprawnień. Bezpośredni odczyt `pg_authid` po operacji potwierdził:

- `rolcanlogin=true`;
- `rolpassword IS NOT NULL=false` (hasło **nie zostało ustawione**);
- pozostałe uprawnienia i bezpieczne ograniczenia bez zmian: SELECT tylko do legacy `price_observations`, brak SELECT do `holding_snapshots`, brak superuser/createdb/createrole/bypassrls.

Wywołanie interfejsu Neon `reset_postgres_role_password` nie powiodło się; późniejsza kontrola SQL potwierdziła brak hasła. Neon control-plane `get_postgres_role` nadal podawał `authentication_method=no_login` pomimo rzeczywistego `rolcanlogin=true`; potrzebna ostrożna weryfikacja tej niespójności przy konfiguracji hasła. GitHub connector nie zapewnia zapisu Environment Secrets, więc `NEON_HISTORICAL_READ_DATABASE_URL` **nie został skonfigurowany**, a żaden manualny workflow nie został uruchomiony. Nie wysyłać sekretów przez czat ani do repo.

Dalszy etap jest opisany w [HISTORICAL_LOGIN_BOOTSTRAP_PL.md](HISTORICAL_LOGIN_BOOTSTRAP_PL.md). **Nie resetować hasła ponownie przez API na ślepo, nie zmieniać ACL, nie uruchamiać bridge przed bezpieczną aktywacją i potwierdzeniem dostępu.** Poniższa sekcja `0. AKTUALIZACJA po snapshot` opisuje wcześniejszy etap `NOLOGIN` i jest zachowana jako historia.

## 0. AKTUALIZACJA po snapshot — 19.10.2026: staging reader utworzony

**To jest nowszy, obowiązujący stan niż poniższy historyczny snapshot z ok. 07:11 UTC.** Użytkownik udzielił jawnej zgody wyłącznie na stworzenie odizolowanej roli `isl_legacy_history_reader` `NOLOGIN` na Neon STAGING (`br-wandering-union-ba6ogf6l`; projekt `red-lake-53043722`; baza `investment_lab`). Zastosowano istniejący przejrzany `db/security/legacy_history_reader_STAGING_REVIEW.sql` jako pojedynczą transakcję PostgreSQL; wszystkie pięć instrukcji zakończyło się bez błędów.

- **Zweryfikowane po wykonaniu:** rola istnieje z `NOLOGIN`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOBYPASSRLS`. W schemacie `investment_lab` efektywny SELECT dotyczy dokładnie **jednej tabeli**: `price_observations`. Zero uprawnień modyfikacji tabel/widoków, brak `CREATE` na schemacie i bazie. Połączenie do bazy i USAGE schematu są przyznane zgodnie z projektem.
- Istniejący `isl_agent_staging_limited` nadal NIE MA SELECT na `price_observations` ani `holding_snapshots`; **na produkcyjnej gałęzi `br-shy-voice-badzlf0x` nowa rola nie istnieje**.
- Systemowa relacja `pg_auth_members`: `investment_lab_owner` jest administracyjnym członkiem nowej roli (grantor `cloud_admin`, `admin_option=true`, `inherit_option=false`, `set_option=false`). Nowa rola nie jest członkiem innych ról. Nie ustanowiono jej osobnego loginu.
- **NIE USTAWIONO** hasła, `LOGIN`, sekretu GitHub `NEON_HISTORICAL_READ_DATABASE_URL`, workflow historycznego, harmonogramu, zleceń, zapisów danych rynkowych ani wirtualnych zmian alokacji.
- Dziennik wykonania: [Issue #4, komentarz 6264735926](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4#issuecomment-6264735926).

**Nowy najbliższy krok:** Uzyskać **świeżą, odrębną zgodę użytkownika** na ewentualne uruchomienie loginu i bezpieczne skonfigurowanie oddzielnych danych uwierzytelniających do staging (nigdy owner DSN). Dopiero później — po ponownej weryfikacji praw/host/CA i sekrecie w chronionym GitHub Environment — możliwy jest **manualny** odczyt raportu z `legacy_history_bridge.py`. Nie wykonywać ponownie `CREATE ROLE`. Pozostałe części niniejszego dokumentu opisują **starszy snapshot**, więc wzmianki o „braku roli” nie są aktualne. Vintage `UNVERIFIED_HISTORICAL_PUBLICATION` pozostaje obowiązujące.

## 1. Co użytkownik faktycznie chce

Docelowy cel to **Opportunity & Decision Intelligence**, nie zwykły automat od równoważenia portfela.

- Identyfikować **potencjalnie interesujące anomalie i rozbieżności** na rynkach w sposób odtwarzalny.
- Łączyć historyczne zachowanie referencyjnych cen, publikowane dane ekonomiczne i udokumentowany kontekst geopolityczny.
- Stawiać **falsyfikowalne hipotezy badawcze**, zbierać dowody za/przeciw i porównywać je z prostymi benchmarkami i scenariuszem **HOLD_NO_CHANGE**.
- Dopiero przy odpowiedniej jakości danych analizować **alternatywne, wirtualne** alokacje i ich hipotetyczne konsekwencje; nie utożsamiać wysokiego z-score ze wskazaniem do zakupu.
- AI/LLM ma pomagać analizować i wyjaśniać dokumentację, **nie wymyślać cen, dat publikacji, prawdopodobieństw sukcesu ani transakcji**.

Wcześniejsza wizja: 3 modele M1/M2/M3, edukacyjny budżet symulacyjny 100 PLN/miesiąc, horyzont badawczy 3–5 lat. Kwota jest **wirtualna** i modele są **alternatywami**, nie trzema równoległymi wpłatami. Obecna wyższa preferencja użytkownika: **radar okazji + retrospektywne testy + uzasadnianie alternatyw**, zamiast sztywnego odtwarzania alokacji.

**Interpretacja klasyfikacji badawczych:** `OBSERVE`, `INVESTIGATE_RESEARCH_ONLY`, `INSUFFICIENT_EVIDENCE`, `HOLD_NO_CHANGE` to etykiety **badań**, nie sygnały finansowe. Obecny kod Opportunity Radar **nie zmienia nawet wirtualnej alokacji**.

## 2. Rejestr systemów i aktualny GitHub

| Komponent | Zweryfikowany stan |
| --- | --- |
| Repozytorium | https://github.com/gniewkob/Investment-Strategy-Lab — **publiczne** |
| `main` w chwili snapshotu | `9e64ae1190c6f9fb9a220bb8b9a4a4223dd6b7cf`, squash PR #17 |
| Pełny PR architektoniczny | [Draft PR #1](https://github.com/gniewkob/Investment-Strategy-Lab/pull/1), gałąź `feature/autonomous-agent-v2-review`, **nie scalony** |
| Główny backlog / dziennik | [Issue #4](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4), zawiera wcześniejsze decyzje i sekwencję PR |
| Kontrole roli i migracji | [Issue #3](https://github.com/gniewkob/Investment-Strategy-Lab/issues/3) |
| Technologia | Python 3.12, `psycopg` 3, GitHub Actions, Neon PostgreSQL, odtwarzalne JSON/Markdown |
| `main` zawiera | Preflight staging, manualny canary dziennika, manualny pełny runner, manualny audyt PIT, Opportunity Radar i evidence ledger, kontekst makro/geopolityczny, walidację niezależnych okien, read-only legacy history bridge oraz **tylko szkic SQL roli** |
| Ostatnie znane CI | [Run 39213233300](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39213233300) — sukces testów ACL na jednorazowym PostgreSQL |
| Automatyczne uruchamianie badanego agenta | **Wyłączone**. Istnieją ręczne `workflow_dispatch`; brak harmonogramu dla pełnego runnera i mostu historycznego. |

**Ważne:** `docs/` na `main` przed tym handoff zawiera `OPPORTUNITY_RADAR_PL.md` oraz `HISTORICAL_REFERENCE_BRIDGE_PL.md`. Inne pliki, np. `AUTONOMOUS_AGENT_V2_PL.md`, `EIA_SOURCE_INGEST_PL.md`, `NEON_LEAST_PRIVILEGE_PL.md`, żyją na **Draft PR #1**, nie udawaj, że są częścią `main`. Kluczowe moduły pełnego runnera przeniesiono na `main` odrębnym PR #10, lecz nie scalono całego PR #1.

## 3. Neon — stan POTWIERDZONY przez odczyt SQL

Projekt Neon: `red-lake-53043722`; baza `investment_lab`.

| Gałąź | ID | Stan |
| --- | --- | --- |
| **PRODUCTION / main** | `br-shy-voice-badzlf0x` | 16 tabel bazowych; **brak `agent_cycles` i schematu agenta v2**; NIE MODYFIKOWAĆ |
| **STAGING** | `br-wandering-union-ba6ogf6l` | 24 tabele; repozytorium prowadzi tu odczyty i kontrolowane eksperymenty |

Odczyt staging z **2026-10-19, 07:11 UTC**:

- `investment_lab.price_observations` — **3711** historycznych wierszy referencyjnych (legacy).
- `investment_lab.price_observation_versions` — **3** wersjonowane rekordy; `prices_asof(now())` — **1** kwalifikujący się rekord PIT.
- `agent_cycles` — **5** zapisanych eksperymentów; `agent_paper_decisions` — **15**; `agent_hypotheses` — **0**.
- `isl_agent_staging_limited` **istnieje** i ma ograniczone prawa do dziennika / źródeł PIT. **Nie ma** dostępu `SELECT` do legacy `price_observations` ani do prywatnych tabel portfeli. Nie zwiększać mu praw.
- `isl_legacy_history_reader` **NIE ISTNIEJE** — odczyt `pg_roles` to potwierdził. Nie zakładać, że istnieje sekret do historycznych danych.

Jedna wersja źródła staging ma `retrieved_at/recorded_at=2026-10-20T10:00:00Z`, czyli wartość **przyszłą** wobec wskazanego wyżej czasu odczytu. Filtr PIT ją wyłącza. To anomalia chronologiczna w danych testowych, a nie przyzwolenie na cofanie dat. Nie usuwać lub „naprawiać” rekordów bez osobnej analizy i zgody.

### Dostępne legacy history — zgrubna mapa pokrycia

| Seria | Liczba historycznych punktów | Typ |
| --- | ---: | --- |
| Brent | 706 | dzienny, referencyjna cena spot |
| WTI | 660 | dzienny, referencyjna cena spot |
| Henry Hub | 695 | dzienny, referencyjna cena spot |
| BTC/USD | 381 | dzienny, referencyjna cena spot |
| ETH/USD | 381 | dzienny, referencyjna cena spot |
| Złoto NBP PLN/g | 264 | dzienny, referencyjna cena/proxy |
| EUR/PLN, USD/PLN | po 264 | dzienny kurs walutowy |
| Miedź, aluminium, nikiel, srebro (World Bank) | po 24 | miesięczne wartości referencyjne |

Sumarycznie 3711 punktów legacy, zaimportowanych do starej tabeli **w październiku 2026**, bez autentycznie odtworzonych historycznych `published_at`/vintage. **Nie** jest to materiał do certyfikowanego PIT backtestu ani automatycznej decyzji o wirtualnej zmianie udziałów. Służy do **retrospektywnego opisu i testowania pytań badawczych**.

Oryginalne wirtualne modele M1/M2/M3 używają `EQUITY_TR_PLN`, `BONDS_TR_PLN`, `GOLD_TR_PLN` i wymagają walidowanych **PLN total-return**. Legacy `PRICE_ONLY` dla BTC/złota/ropy oraz World Bank monthly average nie są takimi szeregami. Również obecny constraint `value_concept` w v2 **nie zawiera** `TOTAL_RETURN_INDEX`; wymaga osobnego przeglądu kontraktu/schema. Nie maskować tego przemianowaniem pól.

## 4. Co już naprawdę działało na staging (historyczne dowody)

Wszystkie poniższe próby wykonano ręcznie, na TESTOWEJ gałęzi i bez brokerów:

1. **Preflight SSL i ACL**, [run #39157477363](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39157477363): `READ_ONLY_TLS_VALIDATED`, `staging_marker_verified=true`, 1 obserwacja PIT, zero zapisów.
2. **Syntetyczny dziennik SQL**, `staging-paper-smoke-2026-10-18-v2`: ograniczona rola dopisała trzy `HOLD_CASH`, zero transakcji, idempotentny replay bez duplikatu.
3. **GitHub syntetyczny canary**, [run #39159505268](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39159505268): wpis `github-staging-canary-2026-10-18-utc07-v1`, 3 `HOLD_CASH`, replay 0 duplikatów, `paper_fills=0`, `real_orders=0`; artefakt raportu.
4. **Rzeczywisty `agent_runner.execute()`**, [run #39160519453](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39160519453): dwa przebiegi przy stałym cutoff `2026-10-18T07:00:00Z`, `daily-research-2026-10-18`, 1 obserwacja PIT, 3 `HOLD_CASH`, 0 hipotez, 0 fills, 0 orders, 0 duplikatów. Raport `cycle.json`, `report.md`, `manifest.json`.
5. **PIT quality audit**, [run #39161607764](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39161607764): workflow technicznie SUCCESS, ale diagnoza **`MARKET_DATA_NOT_READY`**, 1 rekord PIT, 1 przyszła data ingestu i 3 ostrzeżenia. Sukces audytu NIE oznacza gotowości danych do modelowania.

Pozostają NIEPOTWIERDZONE: automatyczny import wiarygodnych vintage, regularne dane typu total-return, 14 niezależnie obserwowanych cykli, aktywne alerty, wiarygodna skuteczność predykcyjna, rzeczywisty historyczny bridge z dedykowaną rolą. **Nie twierdzić, że produkcyjny agent albo autonomiczna strategia są gotowe.**

## 5. Opportunity & Decision Intelligence na `main`

Istniejące moduły, których nowa sesja nie powinna pisać od zera:

| Moduł | Funkcja |
| --- | --- |
| `scripts/opportunity_radar.py` | retrospektywny opis anomalii, chronologiczne okna, bazowy z-score i porównanie referencyjnych zmian |
| `scripts/nonoverlap_validation.py` | ogranicza nachodzenie pięciobarowych okien, porównuje z naiwnym kierunkiem i siatką benchmarku |
| `scripts/evidence_decision_ledger.py` | klasyfikuje **pytania do badania** na podstawie siły dowodów i ich braków |
| `scripts/economic_geopolitical_context.py` | waliduje zadane źródła, daty, kategorie makro/geopolityczne, kontrargumenty; **nie pobiera newsów sam** |
| `scripts/opportunity_research_pipeline.py` | spójny manifest, hash, radar, walidacja, evidence ledger, kontekst, Markdown |
| `scripts/opportunity_demo_fixture.py` | **fikcyjne** deterministyczne ceny do bezpiecznego testu offline |
| `scripts/legacy_history_bridge.py` | odrębny, staging-only, **read-only** most do starszych cen; obecnie zablokowany brakiem dedykowanego konta |
| `scripts/staging_preflight.py` / `staging_data_audit.py` | bramka połączenia/ACL/CA oraz diagnostyka jakości PIT |
| `src/isl_v2/agent_runner.py` i `autonomous_agent.py` | istniejący manualny, ograniczony runner v2 z testowym `HOLD_CASH` |

Wersja Radar v0.1: `20` wcześniejszych stóp zmian, próg `abs(z)>=2.5`, horyzont `5` barów, opisowy podział chronologiczny ok. 65/35. Ledger wymaga min. **5 niepokrywających się zdarzeń** i **12 niezależnych okien gridu** (oraz wcześniej ustalonych progów raw/holdout) do samego priorytetu `INVESTIGATE_RESEARCH_ONLY`. Ani ten próg, ani retrospektywny holdout **nie dowodzą przewagi nad benchmarkiem lub zdolności prognozowania**. Brak prawdziwych cen wykonania, opłat, weryfikowanych vintage i pełnych total-return.

Pipeline z syntetycznym fixture wykazał w CI 2 serie, 8 surowych zdarzeń, **0** pytań przechodzących bramkę odporności, **0** zmian udziałów, 0 DB writes i 0 orders. To fikcyjne testy, nie bieżące odkrycia rynkowe. Osobny diagnostyczny odczyt SQL na realnym legacy policzył historyczne odstępstwa (m.in. Brent 16/243 okien; BTC 8/129; ETH 8/129), **bez dowodu prognostycznej skuteczności**.

### Uruchomienie wyłącznie offline — bez kont i sekretów

```bash
python -m unittest discover -s tests -v
python -m scripts.opportunity_demo_fixture --output /tmp/isl-synthetic-snapshot.json
python -m scripts.opportunity_research_pipeline --input /tmp/isl-synthetic-snapshot.json --out-dir /tmp/isl-educational-report
```

Pliki wyjścia: `radar.json`, `decision_ledger.json`, `economic_geopolitical_context.json`, `nonoverlap_validation.json`, `manifest.json`, `research_report.md`. To **fałszywe ceny**, bez rzeczywistych danych. Nie kopiować raw history z Neon do publicznego repo ani GitHub artifacts.

## 6. Chronologia kluczowych PR i dowodów CI

- **PR #1**: historyczny duży beta pakiet v2 — **Draft, unmerged**.
- **PR #5–8**: preflight i poprawki (dokładny endpoint, pełny TLS z CA, Neon TLS proxy) — przeniesione do `main`.
- **PR #9**: ręczny syntetyczny test zapisu dziennika — merged.
- **PR #10**: wydzielony rzeczywisty runner staging, nadal manualny — merged; 47 testów offline [run #39160285215](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39160285215).
- **PR #11**: manualny data-quality audit — merged, 59 testów offline [run #39161440655](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39161440655).
- **PR #12–15**: Opportunity Radar → ledger → zdarzenia makro/geopolityczne → walidacja niepokrywających się okien — merged; 110 testów pipeline [run #39182839391](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39182839391).
- **PR #16**: `legacy_history_bridge.py`, nowy ręczny workflow i osobny sekret — merged; 121 offline tests [run #39211363418](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39211363418). **Nie uruchomiono przeciw Neon z historyczną rolą**.
- **PR #17**: `db/security/legacy_history_reader_STAGING_REVIEW.sql`, testy ACL wyłącznie na jednorazowym PostgreSQL; merged `9e64ae1`; [run #39213233300](https://github.com/gniewkob/Investment-Strategy-Lab/actions/runs/39213233300) success. **Nie tworzy żadnej roli w Neon.**

Wcześniej wykonane kroki są w opisach PR oraz [Issue #4](https://github.com/gniewkob/Investment-Strategy-Lab/issues/4). Lista powyżej nie upoważnia do wykonywania migracji ani ustawiania sekretów.

## 7. Tożsamości i zasady bezpieczeństwa — NIE NEGOCJOWAĆ

**Publiczny GitHub:** żadnych haseł, prywatnych URL zawierających credentials, kluczy, seed phrase/walletów, realnych sald/portfolio, cen surowych na cudzej licencji, tokenów lub zrzutów poufnych logów.

- GitHub Environment `research-staging`: `NEON_RESEARCH_DATABASE_URL` jest skonfigurowany przez użytkownika (dowodem są udane staging workflows). Nie pobierać ani nie wypisywać wartości. To ograniczony `isl_agent_staging_limited`, nie owner.
- Zaplanowany `NEON_HISTORICAL_READ_DATABASE_URL` jest **oddzielnym** sekretem do `isl_legacy_history_reader`; jego konfiguracja **nie została potwierdzona**, ponieważ sama rola nie istnieje.
- Neon staging direct compute jest zakodowany/allowlistowany w kodzie. Wymagany `sslmode=verify-full`, root CA i host-check; **nie obniżać do `sslmode=require`**. Sekrety wyłącznie w uprawnionym, chronionym środowisku, nie w PR/push.
- `isl_agent_staging_limited` pozostaje bez `SELECT` na legacy `price_observations`; bez zapisu do source evidence i prywatnych tabel. NIE GRANTOWAĆ mu dodatkowych uprawnień.
- PR #17 **jedynie proponuje** `isl_legacy_history_reader NOLOGIN` z SELECT na market reference legacy. `db/security/legacy_history_reader_STAGING_REVIEW.sql` nie jest zaaplikowany do Neon.
- **Osobne, jawne upoważnienie użytkownika** wymagane przed użyciem tego SQL na konkretnym staging, utworzeniem loginu, zmianą haseł, konfiguracją środowiskowego sekretu albo dowolną zmianą ACL. Brak zgody nie oznacza zgody domyślnej.
- Po osobnej autoryzacji sprawdzić ACL przeciw prywatnym `holding_snapshots`, `valuations`, `paper_events`, prawom `CREATE/INSERT/UPDATE/DELETE` oraz staging-only host. Rola read-only nie powinna mieć dostępu do tradingu ani realnych pozycji.
- `production/main` Neon nie jest środowiskiem testowym; nie wykonywać w nim SQL DDL/DML bez zupełnie oddzielnego procesu przeglądu.
- Żadnych integracji do składania zleceń, real-money dynamic allocations, sugestii wykonania inwestycji lub schedulera tradingu. Tylko edukacyjne symulacje i badania.

## 8. Jaki jest **następny**, rzeczywiście otwarty krok?

**Najbliższa bramka: dostęp do historii dla oddzielnej roli bez podnoszenia uprawnień istniejącego agenta.**

1. **Najpierw zapytać użytkownika o osobne zatwierdzenie** utworzenia ograniczonego historycznego konta na staging. Nie utożsamiać `kontynuuj` z wcześniejszym zatwierdzeniem modyfikacji ACL; wskazać, że propozycja SQL i testy są już gotowe, a wymagane jest jawne potwierdzenie.
2. Po zatwierdzeniu: ponownie sprawdzić wskazaną gałąź Neon i aktualne ACL. Użyć wyłącznie recenzowanego skryptu [`../db/security/legacy_history_reader_STAGING_REVIEW.sql`](../db/security/legacy_history_reader_STAGING_REVIEW.sql), wdrażać **wyłącznie na staging** przez uprawniony kanał. Nie wyświetlać haseł. Pamiętać, że to `NOLOGIN`; login/password i secret to osobne, wymagające zgody kroki administracyjne.
3. Gdy dostęp jest realnie gotowy: uruchomić RĘCZNIE z `main` [`Historical reference research bridge`](../.github/workflows/legacy-history-research.yml). Sprawdzić log `LEGACY_HISTORY_RESEARCH_OK`, liczby serii, brak SQL writes, `real_orders=0`, brak surowej historii w artefaktach.
4. Przejrzeć wyniki na realnym legacy: wykryte nietypowe ruchy są **retrospektywnym opisem**, status `UNVERIFIED_HISTORICAL_PUBLICATION`, nie porady ani walidowane sygnały. Zestawić wyniki z baseline, sprawdzić niską liczebność prób, nachodzenie okien, out-of-sample i niepewność.
5. Oddzielny projekt na dalszy etap: autentyczne vintage od oficjalnych dostawców (NBP/EIA/World Bank/ECB, gdy dostępne), weryfikowalne indeksy **total-return** oraz właściwy kontrakt źródeł/ograniczenia schematu. Dopiero na dobrej jakości danych możliwa analiza alternatywnych **wirtualnych** alokacji. Nie cofać `retrieved_at/recorded_at` do fikcyjnych dat.
6. Dopiero po prawdziwym sprawdzeniu systemu błędów/alertów i szeregu niezależnych walidowanych uruchomień rozważyć **badawczy** monitoring cykliczny. Dziś harmonogram jest wyłączony.

### Definicja sukcesu następnego etapu

- Oddzielny staging-only, least-privilege reader zatwierdzony i poprawnie sprawdzony, agent `isl_agent_staging_limited` bez zmian.
- Jednorazowy ręczny history bridge kończy się sukcesem, raportuje ilość danych i hash wejścia, nie ujawnia cen surowych ani sekretów.
- Wyniki dają listę **pytań badawczych** z kontrargumentami, benchmarkiem, liczebnością i ostrzeżeniami.
- W raportach jawnie: `UNVERIFIED_HISTORICAL_PUBLICATION`, `real_orders=0`, `database_writes=0`, `hypothetical_allocation_changes=0`.
- Brak automatycznego planu transakcyjnego; kolejny agent nie „odblokowuje” modelu poprzez pominięcie provenance.

## 9. Przekazanie nowej sesji — gotowy prompt

> Kontynuuj repozytorium `gniewkob/Investment-Strategy-Lab`. Najpierw przeczytaj `AGENTS.md`, następnie `docs/SESSION_HANDOFF_PL.md`, `docs/HISTORICAL_REFERENCE_BRIDGE_PL.md`, `docs/OPPORTUNITY_RADAR_PL.md` i Issue #4. Zweryfikuj aktualny `main` i Neon staging; nie używaj starych statystyk bez ponownego odczytu. Celem jest edukacyjne Opportunity & Decision Intelligence (radar, hipotezy, benchmarki, argumenty za/przeciw, klasyfikacja OBSERVE/INVESTIGATE/HOLD); żadnych rzeczywistych transakcji. Nie duplikuj gotowych modułów PR #12–17. Najbliższa bramka to odrębna rola read-only do legacy na staging, jednak **NIE wykonuj SQL ani nie ustawiaj uprawnień/sekretów bez mojej odrębnej, jawnej zgody**. PR #1 nadal Draft, produkcyjnego Neon nie dotykaj. Zaproponuj najbezpieczniejszy kolejny krok i pokaż wymagane zatwierdzenia.

## 10. Zasady aktualizowania tej strony

- Po każdej większej zmianie dołącz datowany aneks w Issue #4 **i zaktualizuj niniejszy dokument**, szczególnie tabelę aktualnego stanu, rzeczywisty blocker oraz wyniki testów. Nie nadpisuj historycznych dowodów nowymi przypuszczeniami.
- Zawsze linkuj **konkretny GitHub run/PR/commit**; rozdzielaj „offline CI passed” od „rzeczywisty staging workflow przeszedł”. Test CI na disposable PostgreSQL **nie oznacza** uruchomienia SQL na Neon.
- Jeśli aktualny HEAD jest nowszy niż snapshot, sprawdź zmiany i popraw dokument zamiast w ciemno wykonywać kroki.
- Nie wrzucaj prywatnych źródeł lub sekretów do publicznej dokumentacji.
