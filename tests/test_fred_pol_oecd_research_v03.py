"""Offline synthetic validations for FRED-republished OECD index, no network."""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.fred_pol_oecd_research_v03 import (
    MONTHS, SecondaryResearchBlocked, parse_fred_table,
    describe_secondary, reconcile_primary_secondary,
)
STAMP = "2026-11-23T15:00:00Z"


def fixture(values=None):
    vals = values if values is not None else ["100.000000"] * 48
    meta = ("Table Data - Financial Market: Share Prices for Poland\n"
            "Title Financial Market: Share Prices for Poland\n"
            "Series ID SPASTT01PLM661N\n"
            "Source Organization for Economic Co-operation and Development\n"
            "Seasonal Adjustment Not Seasonally Adjusted\n"
            "Frequency Monthly\nUnits Index 2015=100\n"
            "Notes OECD Data Filters:\nREF_AREA: POL\nMEASURE: SHARE\n"
            "UNIT_MEASURE: IX\nACTIVITY: _Z\nADJUSTMENT: _Z\n"
            "TRANSFORMATION: _Z\nTIME_HORIZ: _Z\nMETHODOLOGY: N\n"
            "FREQ: M\nDATE VALUE\n")
    return (meta + ''.join(f"{m}-01 {value}\n" for m,value in zip(MONTHS,vals))).encode()


class FREDSecondaryTests(unittest.TestCase):
    def test_full_48_month_validation_secondary_only(self):
        raw = fixture()
        parsed = parse_fred_table(raw, retrieved_at_utc=STAMP)
        result = describe_secondary(parsed)
        self.assertEqual(result["observation_count"], 48)
        self.assertEqual(result["index_unit_terminal_equivalent_pln"], "4800.00")
        self.assertEqual(result["fictional_contributions_pln"], "4800.00")
        self.assertFalse(result["source_receipt"]["provider_original_bytes_verified"])
        self.assertEqual(result["source_receipt"]["provided_text_sha256"],sha256(raw).hexdigest())
        self.assertIsNone(result["oecd_primary_reconciliation"])
        self.assertEqual(result["m1_m2_m3"], "INSUFFICIENT_DATA_HOLD_CASH")
        self.assertEqual(result["database_writes"], 0)
        self.assertEqual(result["orders_sent"], 0)

    def test_compound_monthly_index_units_correct(self):
        values = ["100.000000"] * 47 + ["200.000000"]
        result = describe_secondary(parse_fred_table(fixture(values),retrieved_at_utc=STAMP))
        self.assertEqual(result["index_unit_terminal_equivalent_pln"], "9500.00")
        self.assertEqual(result["index_change_first_to_last_pct"], "100.00")
        self.assertFalse(result["historical_pit_certified"])

    def test_bad_metadata_and_ambiguous_table(self):
        original = fixture()
        for mutated in (original.replace(b"REF_AREA: POL", b"REF_AREA: DEU"),
                        original.replace(b"SHARE", b"BOND"),
                        original.replace(b"2015=100", b"2020=100"),
                        original.replace(b"SPASTT01PLM661N", b"FAKE"),
                        original + b"DATE VALUE\n",
                        original.replace(b"Units Index 2015=100", b"Units Index 2015=100\nUnits Index 2015=100")):
            with self.subTest(mutated=mutated[:40]), self.assertRaises(SecondaryResearchBlocked):
                parse_fred_table(mutated, retrieved_at_utc=STAMP)

    def test_missing_duplicate_swapped_outside_months(self):
        original = fixture()
        for changed in (original.replace(b"2024-05-01", b"2024-06-01"),
                        original.replace(b"2023-10-01", b"2023-09-01"),
                        original.replace(b"2023-01-01", b"2026-01-01"),
                        original.replace(b"2024-10-01", b"2022-10-01"),
                        original.replace(b"2024-10-01 100.000000\n", b"")):
            with self.subTest(changed=changed[:60]), self.assertRaises(SecondaryResearchBlocked):
                parse_fred_table(changed, retrieved_at_utc=STAMP)

    def test_invalid_index_and_bad_timestamp(self):
        for bad in (b"NaN", b"0", b"-0.5", b"1E9", b"1000000000000000000000"):
            with self.subTest(bad=bad), self.assertRaises(SecondaryResearchBlocked):
                parse_fred_table(fixture().replace(b"100.000000",bad,1),retrieved_at_utc=STAMP)
        for value in ("2020-11-23T15:00:00Z", "2026-11-23T12:00:00+00:00", "2030-01-01T00:00:00Z", "x"):
            with self.subTest(value=value), self.assertRaises(SecondaryResearchBlocked):
                parse_fred_table(fixture(), retrieved_at_utc=value)

    def test_reconcile_48_months_tolerance_and_mismatch(self):
        levels = parse_fred_table(fixture(), retrieved_at_utc=STAMP)["levels"]
        other = dict(levels)
        other["2024-01"] = Decimal("100.0000005")
        result = reconcile_primary_secondary(levels, other)
        self.assertTrue(result["level_reconciliation_pass"])
        self.assertEqual(result["pair_count"], 48)
        other["2024-01"] = Decimal("100.01")
        mismatch = reconcile_primary_secondary(levels, other)
        self.assertEqual(mismatch["disagreements"], 1)
        self.assertFalse(mismatch["level_reconciliation_pass"])
        with self.assertRaises(SecondaryResearchBlocked):
            reconcile_primary_secondary(levels, {**other,"2026-01":Decimal("1")})
        with self.assertRaises(SecondaryResearchBlocked):
            reconcile_primary_secondary(levels, other,tolerance="0.1")

    def test_cli_and_existing_report_read_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "fred.txt"
            source.write_bytes(fixture())
            original = base / "report.md"
            original.write_text("# ISL research\n\nUnmodified original.\n",encoding="utf-8")
            out = base / "out"
            cmd = [sys.executable,"-m","scripts.fred_pol_oecd_research_v03",
                   "--fred-table-text",str(source),"--text-sha256",sha256(fixture()).hexdigest(),
                   "--retrieved-at-utc",STAMP,"--base-report",str(original),"--out-dir",str(out)]
            r=subprocess.run(cmd, capture_output=True,text=True,check=True)
            self.assertIn("SECONDARY_REAL_OBSERVATIONS_DESCRIPTIVE_NOT_EXECUTABLE",r.stdout)
            result=json.loads((out/"fred_oecd_secondary.json").read_text())
            self.assertEqual(result["index_unit_terminal_equivalent_pln"],"4800.00")
            self.assertIn("# ISL research",(out/"research_report.md").read_text())
            self.assertEqual(original.read_text(),"# ISL research\n\nUnmodified original.\n")
            retry=subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(retry.returncode,0)
            self.assertIn("OUT_DIR_ALREADY_EXISTS", retry.stderr)

    def test_cli_wrong_hash_bad_symlink_and_partial_oecd_options(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            src=root/"fred.txt"
            src.write_bytes(fixture())
            alias=root/"alias.txt"
            alias.symlink_to(src)
            cmd=[sys.executable,"-m","scripts.fred_pol_oecd_research_v03",
                "--fred-table-text",str(src),"--text-sha256",'0'*64,
                "--retrieved-at-utc",STAMP,"--out-dir",str(root/"output")]
            r=subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertFalse((root/"output").exists())
            cmd[cmd.index('0'*64)]=sha256(fixture()).hexdigest()
            cmd[cmd.index(str(src))]=str(alias)
            r=subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertFalse((root/"output").exists())
            cmd[cmd.index(str(alias))]=str(src)
            cmd+= ["--oecd-csv",str(root/"missing.csv")]
            r=subprocess.run(cmd,capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0)
            self.assertIn("ALL_OECD_ORIGINAL_RECEIPT_FIELDS_REQUIRED",r.stderr)

if __name__=="__main__":
    unittest.main()
