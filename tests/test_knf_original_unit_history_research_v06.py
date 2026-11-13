"""Single primary KNF share-class historic NAV audit: strict offline negative tests."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import Mock

from scripts.knf_original_unit_history_research_v06 import (
    evaluate_sample, observe_once, _url,
    Blocked, KNF_URLS,
)

NOW=datetime(2026,11,13,tzinfo=timezone.utc)
UNIT_ID="12345678-1234-1234-1234-123456789abc"
KID_ID="12345678-1234-1234-1234-123456789abd"


def raw(x): return json.dumps(x,sort_keys=True).encode()

def sample():
    initial={
        "content":[
            {"fundId":None,"subfundId":210,"unit":"A","isPrimary":True,
             "currency":"PLN","valuationUnitUuid":UNIT_ID,
             "date":"2026-09-30","valuation":100.50}
        ],
        "page":{"size":3,"number":0,"totalElements":1}
    }
    kid_page={
        "content":[
            {"fundId":None,"subfundId":200,"documentUuid":KID_ID,
             "publicationDate":"2026-09-09","currency":"PLN","unit":"A"}
        ],
        "page":{"size":2,"number":0,"totalElements":1}
    }
    history={
        "content":[
            {"fundId":None,"subfundId":210,"unit":"A","isPrimary":True,
             "currency":"PLN","date":d,"valuation":v}
            for d,v in [("2026-09-02",100.0),("2026-09-17",99.90),("2026-09-30",100.5)]
        ],
        "page":{"size":30,"number":0,"totalElements":3}
    }
    kid_detail={
        "fundId":None,"subfundId":200,"documentUuid":KID_ID,
        "publicationDate":"2026-09-09","riskLevel":4,
        "maxEntryFeeRate":0.01,"maxExitFeeRate":0,
        "managementAndOtherFeesRate":0.018,"transactionCostsRate":0.001,
        "scenarios":[{"name":"test future scenario","results":[{"returnRate":0.5}]}]
    }
    return initial,kid_page,history,kid_detail


def evaluate(a=None,b=None,c=None,d=None):
    defaults=sample()
    return evaluate_sample(*[
        raw(x if x is not None else defaults[i])
        for i,x in enumerate((a,b,c,d))
    ],at=NOW)


class KNFSingleShareClassTests(unittest.TestCase):
    def test_actual_source_shape_research_semantics(self):
        x=evaluate()
        self.assertEqual(x["daily_same_class_observations"],3)
        self.assertEqual(x["selected_currency"],"PLN")
        self.assertTrue(x["selected_primary_share_class"])
        self.assertEqual(x["observed_nav_level_change_pct_not_total_return"],"0.5000")
        self.assertEqual(x["kid_risk_level_descriptive_not_recommendation"],4)
        self.assertEqual(x["kid_stated_costs_rates_not_actual_fees"]["managementAndOtherFeesRate"],"0.018")
        self.assertFalse(x["cash_distributions_verified"])
        self.assertFalse(x["fund_holding_period_total_return_qualified"])
        self.assertFalse(x["historical_pit_certified"])
        self.assertEqual(x["orders_sent"],0)
        self.assertEqual(x["financial_operations"],0)
        self.assertEqual(len(x["source_documents"]),4)
        self.assertNotIn("test future scenario",json.dumps(x))
    def test_filter_url_only_one_primary_unit(self):
        a=sample()[0]["content"][0]
        u=_url("history",a)
        self.assertIn("subfundId=210",u)
        self.assertIn("isPrimary=true",u)
        self.assertIn("currency=PLN",u)
        self.assertIn("page=0",u)
        self.assertIn("size=30",u)
    def test_untrusted_unit_class_blocks(self):
        a=sample()[0]["content"][0]
        a["unit"]="A\nmalicious&fundId=123"
        with self.assertRaisesRegex(Blocked,"FUND_UNIT_CLASS_UNSAFE"):
            _url("history",a)
    def test_identity_must_be_exclusive(self):
        a=sample()[0]["content"][0]
        a["fundId"]=101
        with self.assertRaisesRegex(Blocked,"FUND_IDENTITY_NOT_EXCLUSIVE"):
            _url("history",a)
    def test_kid_document_id_checked(self):
        d=sample()[1]["content"][0]
        d["documentUuid"]="../../etc/passwd"
        with self.assertRaisesRegex(Blocked,"KID_DOC_ID_INVALID"):
            _url("kid",d)
    def test_history_wrong_fund_unit_blocks(self):
        a,b,c,d=sample()
        c["content"][1]["unit"]="X"
        with self.assertRaisesRegex(Blocked,"HISTORY_DIFFERENT_FUND_UNIT"):
            evaluate(a,b,c,d)
    def test_history_wrong_currency_blocks(self):
        a,b,c,d=sample()
        c["content"][1]["currency"]="USD"
        with self.assertRaisesRegex(Blocked,"HISTORY_DIFFERENT_FUND_UNIT"):
            evaluate(a,b,c,d)
    def test_history_incomplete_page_blocks(self):
        a,b,c,d=sample()
        c["page"]["totalElements"]=34
        with self.assertRaisesRegex(Blocked,"HISTORY_INCOMPLETE"):
            evaluate(a,b,c,d)
    def test_duplicate_date_blocks(self):
        a,b,c,d=sample()
        c["content"][1]["date"]=c["content"][0]["date"]
        with self.assertRaisesRegex(Blocked,"DUPLICATE"):
            evaluate(a,b,c,d)
    def test_nonnumeric_and_zero_nav_rejected(self):
        for bad in (0,-1,float("nan"),True,"abc"):
            a,b,c,d=sample()
            c["content"][1]["valuation"]=bad
            with self.subTest(bad=str(bad)),self.assertRaises(Blocked):
                evaluate(a,b,c,d)
    def test_wrong_kid_detail_blocks(self):
        a,b,c,d=sample()
        d["documentUuid"]=UNIT_ID
        with self.assertRaisesRegex(Blocked,"KID_DETAIL_IDENTITY_CHANGED"):
            evaluate(a,b,c,d)
    def test_kid_risk_invalid_blocks(self):
        a,b,c,d=sample()
        d["riskLevel"]=9
        with self.assertRaisesRegex(Blocked,"KID_RISK_LEVEL_INVALID"):
            evaluate(a,b,c,d)
    def test_kid_cost_as_fraction_not_percent(self):
        a,b,c,d=sample()
        d["maxEntryFeeRate"]=10
        with self.assertRaises(Blocked):
            evaluate(a,b,c,d)
    def test_explicit_fetch_and_bounded_requests(self):
        with self.assertRaisesRegex(Blocked,"EXPLICIT"):
            observe_once(fetch=None)
        a,b,c,d=sample()
        source={KNF_URLS["primary_pln_valuations"]:raw(a),
                KNF_URLS["kid_units"]:raw(b),
                _url("history",a["content"][0]):raw(c),
                _url("kid",b["content"][0]):raw(d)}
        calls=[]
        def fetch(url):
            calls.append(url)
            return source[url]
        x=observe_once(fetch=fetch,clock=lambda:NOW)
        self.assertEqual(len(calls),4)
        self.assertEqual(x["daily_same_class_observations"],3)
