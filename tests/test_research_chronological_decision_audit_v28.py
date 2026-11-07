"""v0.28 synthetic chronological snapshots, no performance and no trading."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import unittest

from scripts.research_chronological_decision_audit_v28 import audit, MODE
from scripts.shadow_decision_engine_v05 import ASSETS, EQUITY, GOLD, ShadowInputError
from tests.test_research_decision_controller_v15 import pair

M1="M1_GLOBAL_EQ"
M2="M2_DIVERSIFIED"
M3="M3_TACTICAL"


def snapshots(*, third=False, risk_off=False):
    current, previous = pair()
    items = [previous, current]
    if third:
        later = deepcopy(current)
        later["as_of_utc"] = "2026-12-06T20:00:00+00:00"
        for code in ASSETS:
            source = later["series"][code]
            source["retrieved_at"] = later["as_of_utc"]
            prior = source["observations"][-1]
            observed = date(2026, 11, 28)
            newest = {
                "month": "2026-11",
                "observed_for": observed.isoformat(),
                "first_usable_at": datetime.combine(
                    observed + timedelta(days=1), datetime.min.time(),
                    tzinfo=timezone.utc).isoformat(),
                "level_pln": ("400" if code == EQUITY and risk_off else
                              str(int(prior["level_pln"]) + 10)),
            }
            source["observations"].append(newest)
        items.append(later)
    return {"mode": MODE, "source_kind": "SYNTHETIC_FIXTURE",
            "snapshots": items}


class ChronologicalDecisionAuditV28Tests(unittest.TestCase):
    def test_two_consecutive_months_m3_confirmation_and_receipt_chain(self):
        out=audit(snapshots())
        self.assertEqual(out["decision_months"],2)
        self.assertEqual(out["adjacent_monthly_transitions"],1)
        self.assertEqual(out["model_counts"][M3]["hold_months"],1)
        self.assertEqual(out["model_counts"][M3]["candidate_months"],1)
        self.assertEqual(out["model_counts"][M3]["status_transitions"],1)
        self.assertEqual(out["model_counts"][M1]["candidate_months"],2)
        self.assertEqual(out["receipts"][0]["previous_audit_receipt_sha256"],"0"*64)
        self.assertEqual(out["receipts"][1]["previous_audit_receipt_sha256"],
                         out["receipts"][0]["audit_receipt_sha256"])
        self.assertFalse(out["forward_returns_evaluated"])
        self.assertFalse(out["market_turnover_measured"])
        self.assertEqual(out["financial_operations"],0)

    def test_three_months_stable_m3_candidate_and_no_churn(self):
        out=audit(snapshots(third=True))
        self.assertEqual(out["decision_months"],3)
        self.assertEqual(out["adjacent_monthly_transitions"],2)
        self.assertEqual(out["model_counts"][M3]["status_transitions"],1)
        self.assertEqual(out["model_counts"][M3]["candidate_months"],2)
        self.assertEqual(out["model_counts"][M3]["candidate_regime_changes"],0)
        self.assertEqual(out["model_counts"][M3]["target_changes"],1)

    def test_one_month_risk_off_transition_holds_m3(self):
        out=audit(snapshots(third=True,risk_off=True))
        self.assertEqual(out["model_counts"][M3]["hold_months"],2)
        self.assertEqual(out["model_counts"][M3]["candidate_months"],1)
        self.assertEqual(out["model_counts"][M3]["status_transitions"],2)
        self.assertEqual(out["receipts"][-1]["model_states"][M3]["reason"],
                         "REGIME_CHANGE_AWAIT_CONFIRMATION")
        self.assertEqual(out["model_counts"][M1]["candidate_months"],3)

    def test_revised_history_rejected_across_shared_series(self):
        doc=snapshots(third=True)
        doc["snapshots"][-1]["series"][EQUITY]["observations"][20]["level_pln"]="9999"
        with self.assertRaisesRegex(ShadowInputError,"historical prefix changed"):
            audit(doc)

    def test_source_absence_is_a_held_decision_not_fake_target(self):
        doc=snapshots()
        doc["snapshots"][1]["series"].pop(EQUITY)
        out=audit(doc)
        self.assertEqual(out["model_counts"][M1]["hold_months"],1)
        self.assertEqual(out["model_counts"][M3]["hold_months"],2)
        self.assertEqual(out["model_counts"][M3]["candidate_months"],0)

    def test_nonconsecutive_month_and_duplicate_order_rejected(self):
        doc=snapshots(third=True)
        doc["snapshots"][-1]["as_of_utc"]="2027-01-06T20:00:00+00:00"
        for source in doc["snapshots"][-1]["series"].values():
            source["retrieved_at"]="2027-01-06T20:00:00+00:00"
        with self.assertRaisesRegex(ShadowInputError,"consecutive decision months"):
            audit(doc)
        doc=snapshots()
        doc["snapshots"]=list(reversed(doc["snapshots"]))
        with self.assertRaises(ShadowInputError):
            audit(doc)

    def test_deterministic_and_unmodified_input(self):
        doc=snapshots(third=True)
        copy=deepcopy(doc)
        self.assertEqual(audit(doc),audit(copy))
        self.assertEqual(doc,copy)
        self.assertEqual(len(audit(doc)["audit_sha256"]),64)

    def test_live_mode_extra_keys_and_too_few_snapshots_rejected(self):
        for mutate in (
            lambda d: d.update(mode="LIVE_TRADING"),
            lambda d: d.update(real_orders=True),
            lambda d: d.update(snapshots=d["snapshots"][:1]),
        ):
            doc=snapshots()
            mutate(doc)
            with self.assertRaises(ShadowInputError):
                audit(doc)

    def test_snapshot_future_availability_rejected(self):
        doc=snapshots()
        doc["snapshots"][-1]["series"][GOLD]["retrieved_at"] = (
            "2026-12-30T20:00:00+00:00")
        with self.assertRaisesRegex(ShadowInputError,"future retrieval"):
            audit(doc)


if __name__=="__main__":
    unittest.main()
