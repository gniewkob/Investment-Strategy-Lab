"""Synthetic-only end-to-end wiring for the bounded public source runner."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from scripts.eurostat_hicp_macro_context_v01 import HICPContextError

from tests.test_public_first_market_research_v07 import three_source_receipts
from tests.test_public_first_multisource_macro_evidence_v05 import data_fixture
from tests.test_eurostat_pl_government_bond_yield_context_v04 import original_shape
from tests.test_nbp_table_a_archive_v09 import csv_sample

from scripts.public_first_one_shot_v08 import OneShotBlocked, run_once, main


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


def fake_sources(*, fail=None):
    """Offline adapters for the already-tested v0.7 cross-receipt contract."""
    fixtures = three_source_receipts()
    calls = []

    def knf_fetch(url):
        calls.append(("uknf", url))
        return ("uknf:" + str(len(calls))).encode()

    def knf_observe(*, fetch, clock):
        for index in range(3):
            fetch(f"https://synthetic.invalid/uknf/{index}")
        return deepcopy(fixtures["nav_original"])

    def nav_describe(preview, kid_page, history, kid_detail, *, observed_at):
        assert (preview, kid_page, history, kid_detail) == (
            b"uknf:1", b"uknf:2", b"uknf:3", None
        )
        assert observed_at == NOW
        return deepcopy(fixtures["nav_quality"])

    def mf_fetch(url):
        calls.append(("mf", url))
        if fail == "mf":
            raise OneShotBlocked("OFFICIAL_MF_UNAVAILABLE")
        return b"synthetic-mf"

    def macro_observe(*, nbp_fetch, hicp_fetch, yield_fetch, clock,
                      nbp_chunk_days=None):
        for n in range(6 if nbp_chunk_days == 10 else 2):
            nbp_fetch(f"https://synthetic.invalid/nbp/{n}")
        hicp_fetch("https://synthetic.invalid/eurostat/hicp")
        yield_fetch()
        return deepcopy(fixtures["macro_reference"])

    def nbp_reader(url):
        calls.append(("nbp", url))
        if fail == "macro":
            raise HTTPError(url, 404, "synthetic missing source", None, None)
        return b"nbp"

    kwargs = {
        "knf_fetch": knf_fetch,
        "mf_fetch": mf_fetch,
        "nbp_fetch": nbp_reader,
        "hicp_fetch": lambda url: calls.append(("hicp", url)) or data_fixture(),
        "yield_fetch": lambda: calls.append(("yield", None)) or json.dumps(original_shape()).encode(),
        "clock": lambda: NOW,
    }
    patches = (
        patch("scripts.public_first_one_shot_v08.observe_knf", knf_observe),
        patch("scripts.public_first_one_shot_v08.describe_unit_nav", nav_describe),
        patch("scripts.public_first_one_shot_v08.inspect_market_sheet",
              lambda raw, *, observed_at: deepcopy(fixtures["mf_schema"])),
        patch("scripts.public_first_one_shot_v08.analyze_mf_original",
              lambda raw, *, completed_at: deepcopy(fixtures["mf_turnover"])),
        patch("scripts.public_first_one_shot_v08.observe_macro", macro_observe),
    )
    return kwargs, patches, calls


class PublicFirstOneShotTests(unittest.TestCase):
    def test_nbp_api_404_can_preserve_verified_official_annual_fx_archive(self):
        kwargs, patches, _ = fake_sources(fail="macro")
        kwargs["nbp_archive_fetch"] = lambda url: csv_sample()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            out = run_once(**kwargs, allow_macro_unavailable=True)
        self.assertEqual(out["source_read_counts"]["nbp_archive_fx"], 1)
        archive = out["independent_descriptive_context"]
        self.assertEqual(archive["nbp_fx_archive_september_days"], 2)
        self.assertEqual(archive["nbp_fx_archive_latest_usdpln_mid"], "3.7423")
        self.assertEqual(archive["nbp_fx_archive_latest_eurpln_mid"], "4.3311")
        self.assertEqual(out["report"]["mode"], "SCHEMA_ONLY")

    def test_eurostat_network_error_after_nbp_failure_does_not_erase_mf(self):
        kwargs, patches, _ = fake_sources(fail="macro")
        def connection_error(_url):
            try:
                raise OSError("synthetic no transport")
            except OSError as cause:
                raise HICPContextError("Eurostat read-only fetch failed") from cause
        kwargs["hicp_fetch"] = connection_error
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            out = run_once(**kwargs, allow_macro_unavailable=True)
        self.assertEqual(out["status"], "PARTIAL_MACRO_HTTP_UNAVAILABLE")
        self.assertNotIn("eurostat_hicp_months", out["independent_descriptive_context"])
        self.assertEqual(out["independent_descriptive_context"]["eurostat_yield_months"], 59)
        self.assertEqual(out["source_read_attempts"]["eurostat_hicp"], 1)

    def test_nbp_http_failure_keeps_independently_verified_eurostat_evidence(self):
        kwargs, patches, _ = fake_sources(fail="macro")
        kwargs["hicp_fetch"] = lambda _: data_fixture()
        kwargs["yield_fetch"] = lambda: json.dumps(original_shape()).encode()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            out = run_once(**kwargs, allow_macro_unavailable=True)
        self.assertEqual(out["status"], "PARTIAL_MACRO_HTTP_UNAVAILABLE")
        self.assertEqual(out["source_read_counts"]["eurostat_hicp"], 1)
        self.assertEqual(out["source_read_counts"]["eurostat_yield"], 1)
        separate = out["independent_descriptive_context"]
        self.assertEqual(separate["eurostat_hicp_months"], 13)
        self.assertEqual(separate["eurostat_yield_months"], 59)
        self.assertEqual(separate["eurostat_pl_nominal_10y_yield_pct"], "4.58")
        self.assertEqual(separate["eurostat_trailing_12m_hicp_pct"], "4.8000")
        self.assertEqual(separate["eurostat_level_gap_pp_not_real_yield"], "-0.2200")
        self.assertEqual(out["report"]["mode"], "SCHEMA_ONLY")
        self.assertEqual(out["financial_operations"], 0)

    def test_official_hicp_reader_accepts_jsonstat_object_not_raw_bytes(self):
        kwargs, patches, _ = fake_sources()
        payload = {"version": "2.0", "class": "dataset", "source": "ESTAT"}
        kwargs["hicp_fetch"] = lambda _: payload
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            out = run_once(**kwargs)
        self.assertEqual(out["macro_source_status"], "VALIDATED")
        self.assertEqual(out["source_read_counts"]["eurostat_hicp"], 1)

    def test_one_shot_reads_three_independent_nbp_fragments_per_family(self):
        kwargs, patches, calls = fake_sources()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = run_once(**kwargs)
        self.assertEqual(result["source_read_counts"]["nbp"], 6)
        self.assertEqual(result["total_public_reads"], 12)
        self.assertEqual(len([name for name, _ in calls if name == "nbp"]), 6)

    def test_all_sources_join_and_no_financial_operations(self):
        kwargs, patches, calls = fake_sources()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = run_once(**kwargs)
        self.assertEqual(result["report"]["mode"], "DESCRIPTIVE_MARKET_CONTEXT")
        self.assertEqual(result["report"]["m1_m2_m3"], "INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual(result["source_read_counts"], {
            "uknf": 3, "mf": 1, "nbp": 6, "nbp_archive_fx": 0,
            "eurostat_hicp": 1,
            "eurostat_yield": 1,
        })
        self.assertEqual(len(calls), 12)
        self.assertEqual(result["original_market_bytes_saved"], 0)
        self.assertEqual(result["database_writes"], 0)
        self.assertEqual(result["financial_operations"], 0)
        self.assertEqual(result["orders_sent"], 0)
        self.assertFalse(result["historical_pit_certified"])
        self.assertEqual(result["report"]["source_readiness"]["source_families"], 3)

    def test_explicit_injected_fetchers_required_before_any_read(self):
        kwargs, _, calls = fake_sources()
        kwargs["mf_fetch"] = None
        with self.assertRaisesRegex(OneShotBlocked, "EXPLICIT_SOURCE_READERS_REQUIRED"):
            run_once(**kwargs)
        self.assertEqual(calls, [])

    def test_source_failure_keeps_report_unwritten(self):
        kwargs, patches, calls = fake_sources(fail="mf")
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "market-report"
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                with self.assertRaisesRegex(OneShotBlocked, "OFFICIAL_MF_UNAVAILABLE"):
                    main(["--allow-public-official-read", "--out-dir", str(out)],
                         runner=lambda **_: run_once(**kwargs))
            self.assertFalse(out.exists())
            self.assertEqual(len(calls), 4)

    def test_cli_requires_opt_in_even_with_injected_runner(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "uncreated"
            with self.assertRaises(SystemExit):
                main(["--out-dir", str(out)],
                     runner=lambda **_: self.fail("source fetch attempted"))
            self.assertFalse(out.exists())

    def test_successful_cli_writes_only_qualified_receipts_and_markdown(self):
        kwargs, patches, _ = fake_sources()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "out"
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                self.assertEqual(main(["--allow-public-official-read", "--out-dir",
                                       str(out)], runner=lambda **_: run_once(**kwargs)), 0)
            self.assertEqual({p.name for p in out.iterdir()}, {
                "market_research_v07.json", "market_research_v07.md",
                "public_source_run_v08.json",
            })
            report = json.loads((out / "market_research_v07.json").read_text())
            run_receipt = json.loads((out / "public_source_run_v08.json").read_text())
            self.assertEqual(run_receipt["market_report_sha256"], report["receipt_sha256"])
            self.assertIn("INSUFFICIENT_DATA_HOLD_CASH",
                          (out / "market_research_v07.md").read_text())
            self.assertNotIn("synthetic-mf", json.dumps(run_receipt))
            self.assertNotIn("uknf:1", json.dumps(run_receipt))
            with self.assertRaises(SystemExit):
                main(["--allow-public-official-read", "--out-dir", str(out)],
                     runner=lambda **_: self.fail("must refuse existing target first"))

    def test_utc_clock_must_be_valid_before_any_read(self):
        kwargs, _, calls = fake_sources()
        kwargs["clock"] = lambda: NOW.replace(tzinfo=None)
        with self.assertRaisesRegex(OneShotBlocked, "UTC_AWARE_CLOCK_REQUIRED"):
            run_once(**kwargs)
        self.assertEqual(calls, [])

    def test_invalid_response_bytes_fail_closed(self):
        kwargs, patches, calls = fake_sources()
        kwargs["mf_fetch"] = lambda url: "not bytes"
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            with self.assertRaisesRegex(OneShotBlocked, "SOURCE_BYTES_INVALID"):
                run_once(**kwargs)

    def test_missing_macro_http_source_is_blocked_by_default(self):
        kwargs, patches, _ = fake_sources(fail="macro")
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            with self.assertRaises(HTTPError):
                run_once(**kwargs)

    def test_explicit_partial_retains_independent_original_evidence(self):
        kwargs, patches, calls = fake_sources(fail="macro")
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            result = run_once(**kwargs, allow_macro_unavailable=True)
        self.assertEqual(result["status"], "PARTIAL_MACRO_HTTP_UNAVAILABLE")
        self.assertEqual(result["report"]["mode"], "SCHEMA_ONLY")
        self.assertIsNone(result["report"]["market_context"])
        self.assertEqual(result["macro_source_status"], "HTTP_UNAVAILABLE_NO_VALUES_FABRICATED")
        self.assertEqual(result["source_read_counts"]["nbp"], 0)
        self.assertEqual(result["source_read_counts"]["eurostat_hicp"], 1)
        self.assertEqual(result["source_read_counts"]["eurostat_yield"], 1)
        self.assertEqual(result["source_read_attempts"]["nbp"], 1)
        self.assertEqual(result["source_read_attempts"]["mf"], 1)
        self.assertEqual(result["independent_descriptive_context"]["mf_months"], 202)
        self.assertEqual(result["independent_descriptive_context"]["mf_latest_total_mln_pln"],
                         "3140385.25")
        self.assertEqual(result["financial_operations"], 0)
        self.assertEqual(result["database_writes"], 0)
        self.assertFalse(result["historical_pit_certified"])
        self.assertEqual(len(calls), 7)

    def test_partial_cli_is_visibly_partial_and_never_cross_joins(self):
        kwargs, patches, _ = fake_sources(fail="macro")
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "partial"
            with patches[0], patches[1], patches[2], patches[3], patches[4]:
                self.assertEqual(main(["--allow-public-official-read",
                                       "--allow-macro-unavailable",
                                       "--out-dir", str(out)],
                                      runner=lambda **_: run_once(
                                          **kwargs, allow_macro_unavailable=True)), 0)
            md = (out / "market_research_v07.md").read_text()
            receipt = json.loads((out / "public_source_run_v08.json").read_text())
            self.assertIn("Częściowy odczyt źródeł", md)
            self.assertIn("nie uzupełniono braków szacunkami", md)
            self.assertIn("Eurostat HICP: 13", md)
            self.assertEqual(receipt["status"], "PARTIAL_MACRO_HTTP_UNAVAILABLE")
            self.assertEqual(receipt["macro_source_status"],
                             "HTTP_UNAVAILABLE_NO_VALUES_FABRICATED")
            self.assertEqual(json.loads((out / "market_research_v07.json").read_text())[
                "mode"], "SCHEMA_ONLY")

    def test_knf_read_limit_precedes_fifth_http_request(self):
        kwargs, _, calls = fake_sources()
        def too_many_knf(*, fetch, clock):
            for index in range(5):
                fetch(f"https://synthetic.invalid/uknf/{index}")
        with patch("scripts.public_first_one_shot_v08.observe_knf", too_many_knf):
            with self.assertRaisesRegex(OneShotBlocked, "SOURCE_READ_LIMIT_EXCEEDED:uknf"):
                run_once(**kwargs)
        self.assertEqual(len(calls), 4)


if __name__ == "__main__":
    unittest.main()
