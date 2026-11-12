"""Network-free acceptance and negative gates for public NBP research lane."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from email.message import Message
from io import BytesIO
import json
from unittest import TestCase, main
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.request import BaseHandler, ProxyHandler, build_opener
from urllib.response import addinfourl

from scripts.public_first_nbp_reference_research_v01 import (
    PublicReferenceBlocked, research_public_nbp, official_fetch, _ranges,
    _NoRedirect,
)

TODAY = date(2026, 11, 12)
CLOCK = lambda: datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)


def _month_ends(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    days = []
    while (year, month) <= (ey, em):
        days.append(f"{year:04d}-{month:02d}-27")
        year, month = ((year + 1, 1) if month == 12 else (year, month + 1))
    return days


def mock_fetch(start="2021-11", end="2026-10", *,
               missing_gold=None, missing_eur=None, duplicate=None):
    days = _month_ends(start, end)
    def fetch(url):
        parsed = urlsplit(url)
        parts = parsed.path.strip("/").split("/")
        if parsed.netloc != "api.nbp.pl" or parsed.query != "format=json":
            raise AssertionError("Nonofficial API accessed")
        start_day, end_day = parts[-2:]
        selected = [d for d in days if start_day <= d <= end_day]
        if "cenyzlota" in parsed.path:
            data = [{"data": d, "cena": 250 + idx * 2}
                    for idx, d in enumerate(days) if d in selected
                    and d != missing_gold]
            if duplicate in selected:
                data.append({"data": duplicate, "cena": 251})
        else:
            data = [{"table":"A","no":f"012/A/NBP/{d[:4]}",
                     "effectiveDate":d,"rates": [
                        {"code":"USD","mid":4.10 + i * .001},
                        *([] if d == missing_eur else
                          [{"code":"EUR","mid":4.50 + i * .001}])
                     ]}
                    for i, d in enumerate(days) if d in selected]
        if not data:
            raise ValueError("EMPTY_SOURCE_SLICE")
        return json.dumps(data).encode()
    return fetch


def _stub_urllib_opener(*, status, payload, attempts, location=None):
    """Exercise urllib's *real* redirect machinery with zero network I/O."""
    class OfflineHTTPS(BaseHandler):
        handler_order = 100  # run before urllib's real HTTPSHandler

        def https_open(self, req):
            attempts.append(req.full_url)
            if len(attempts) != 1 or urlsplit(req.full_url).netloc != "api.nbp.pl":
                raise AssertionError("Unexpected redirected/outbound HTTP request")
            headers = Message()
            if location is not None:
                headers["Location"] = location
            response = addinfourl(BytesIO(payload), headers, req.full_url, status)
            response.msg = "OK" if status == 200 else "Redirect"  # urllib's HTTPErrorProcessor requires msg
            return response

    def factory(*handlers):
        if not any(isinstance(h, _NoRedirect) for h in handlers):
            raise AssertionError("NBP opener must explicitly prohibit redirects")
        return build_opener(OfflineHTTPS(), ProxyHandler({}), *handlers)

    return factory


class PublicFirstNBPTests(TestCase):
    def run_study(self, start="2021-11", end="2026-10", fetch=None):
        # Keep synthetic fixture creation independent of invalid input dates.
        # A mock cannot loop forever while testing an invalid YYYY-13 month.
        return research_public_nbp(
            start, end, fetch=fetch or mock_fetch("2021-10", "2026-10"),
            today=TODAY, clock=CLOCK)

    def test_sixty_complete_months_and_provenance(self):
        out = self.run_study()
        self.assertEqual((out["first_month"],out["last_month"]),
                         ("2021-11","2026-10"))
        self.assertEqual(out["complete_months"], 60)
        self.assertEqual(out["monthly_contribution_pln"], "100.00")
        self.assertEqual(out["status"],"PUBLIC_REFERENCE_RESEARCH_ONLY")
        self.assertEqual(len(out["scenarios"]), 7)
        self.assertEqual(len(out["monthly_selected_dates"]["gold"]),60)
        self.assertEqual(len(out["raw_source_receipts"])%2,0)
        self.assertGreaterEqual(len(out["raw_source_receipts"]),40)
        self.assertRegex(out["monthly_values_canonical_sha256"],"^[0-9a-f]{64}$")
        self.assertEqual(out["daily_counts"]["gold"],60)
        self.assertFalse(out["historical_source_vintage_certified"])
        self.assertFalse(out["historical_publication_hour_certified"])
        self.assertEqual(out["model_qualifications_granted"],[])
        self.assertEqual(out["financial_operations"],0)
        self.assertEqual(out["paper_events_created"],0)
        self.assertEqual(out["database_writes"],0)
        self.assertEqual(out["legacy_m1_m2_m3"],
                         "NOT_RUN_UNQUALIFIED_TOTAL_RETURN_SERIES")

    def test_deterministic_same_sources_same_results(self):
        self.assertEqual(self.run_study(), self.run_study())

    def test_no_fetch_no_implicit_network(self):
        with self.assertRaisesRegex(PublicReferenceBlocked, "EXPLICIT_PUBLIC_NBP"):
            research_public_nbp("2025-01","2025-12",today=TODAY)

    def test_cash_and_cost_stress_are_not_trades(self):
        out = self.run_study("2025-01","2025-12")
        cash,*others=out["scenarios"]
        self.assertEqual(cash["terminal_reference_value_pln"],"1200.00")
        self.assertEqual(cash["virtual_contributions_pln"],"1200.00")
        self.assertTrue(all(row["executable_asset"] is False for row in others))
        for i in (0,2,4):
            self.assertLess(Decimal(others[i+1]["terminal_reference_value_pln"]),
                            Decimal(others[i]["terminal_reference_value_pln"]))
            self.assertEqual(others[i+1]["assumed_one_way_cost_bps"],"30")

    def test_no_missing_month_fabrication(self):
        with self.assertRaisesRegex(PublicReferenceBlocked,
                                    "MISSING_LATE_MONTH_NBP_PUBLICATION"):
            self.run_study("2025-01","2025-12",
                           fetch=mock_fetch("2025-01","2025-12",
                                           missing_gold="2025-06-27"))

    def test_duplicate_publication_fails_closed(self):
        with self.assertRaisesRegex(PublicReferenceBlocked,"NBP_CHUNK_REJECTED"):
            self.run_study("2025-01","2025-12",
                           fetch=mock_fetch("2025-01","2025-12",
                                           duplicate="2025-04-27"))

    def test_missing_eur_fails_closed(self):
        with self.assertRaisesRegex(PublicReferenceBlocked,"NBP_CHUNK_REJECTED"):
            self.run_study("2025-01","2025-12",
                           fetch=mock_fetch("2025-01","2025-12",
                                           missing_eur="2025-04-27"))

    def test_wrong_source_date_cannot_be_synthesized(self):
        with self.assertRaisesRegex(PublicReferenceBlocked,
                                    "ONLY_COMPLETED_HISTORICAL_MONTHS"):
            self.run_study("2025-12","2026-11")

    def test_future_or_reversed_windows_not_supported(self):
        for start,end in (("2025-12","2025-01"),("2026-11","2026-11"),
                          ("2025-13","2026-01")):
            with self.subTest(start=start,end=end):
                with self.assertRaises(PublicReferenceBlocked):
                    self.run_study(start,end)

    def test_max_60_months(self):
        with self.assertRaisesRegex(PublicReferenceBlocked, "WINDOW_EXCEEDS_60"):
            self.run_study("2021-10","2026-10")

    def test_at_least_twelve_months(self):
        with self.assertRaisesRegex(PublicReferenceBlocked, "AT_LEAST_12_MONTHS"):
            self.run_study("2026-01","2026-10")

    def test_90_day_api_chunks_not_93_or_more(self):
        dates=list(_ranges(date(2021,11,1),date(2026,10,31)))
        self.assertGreater(len(dates),20)
        for a,b in dates:
            self.assertLessEqual((date.fromisoformat(b)-date.fromisoformat(a)).days+1,90)
        for i in range(1,len(dates)):
            self.assertEqual((date.fromisoformat(dates[i-1][1]) -
                              date.fromisoformat(dates[i][0])).days,-1)

    def test_official_fetch_blocks_untrusted_endpoints_without_network(self):
        with self.assertRaisesRegex(PublicReferenceBlocked,
                                    "NON_OFFICIAL_NBP_ENDPOINT"):
            official_fetch("https://evil.invalid/api/cenyzlota/2026-01-01/2026-01-31/?format=json")
        with self.assertRaisesRegex(PublicReferenceBlocked,
                                    "NON_OFFICIAL_NBP_ENDPOINT"):
            official_fetch("http://api.nbp.pl/api/cenyzlota/2026-01-01/2026-01-31/?format=json")

    def test_official_fetch_rejects_redirect_before_network_egress(self):
        url = ("https://api.nbp.pl/api/cenyzlota/"
               "2026-01-01/2026-01-31/?format=json")
        for status, target in ((302, "https://example.org/untrusted"),
                               (307, "https://api.nbp.pl/api/other?format=json")):
            with self.subTest(status=status, target=target):
                attempts = []
                with patch("scripts.public_first_nbp_reference_research_v01.build_opener",
                           side_effect=_stub_urllib_opener(
                               status=status, payload=b"redirect-body",
                               location=target, attempts=attempts)):
                    with self.assertRaisesRegex(PublicReferenceBlocked,
                                                "UNEXPECTED_NBP_REDIRECT"):
                        official_fetch(url)
                # Most important security invariant: redirect destination is
                # NEVER contacted, even once, before fail-closed rejection.
                self.assertEqual(attempts, [url])

    def test_official_fetch_valid_https_200_no_redirect(self):
        url = ("https://api.nbp.pl/api/cenyzlota/"
               "2026-01-01/2026-01-31/?format=json")
        attempts = []
        payload = b'[{"data":"2026-01-27","cena":320.25}]'
        with patch("scripts.public_first_nbp_reference_research_v01.build_opener",
                   side_effect=_stub_urllib_opener(
                       status=200, payload=payload, attempts=attempts)):
            self.assertEqual(official_fetch(url), payload)
        self.assertEqual(attempts, [url])


if __name__ == "__main__":
    main()
