"""Offline, synthetic-only deposit reconciliation tests."""
import unittest
from scripts.deposit_evidence_reconciliation import reconcile, DepositEvidenceError

HASH = "0x" + "a" * 64
TO = "0x" + "b" * 40

def chain():
    return {"chain_id":8453, "tx_hash":HASH, "asset":"cbBTC",
            "amount":"0.00005000", "recipient":TO, "network":"FINALIZED"}

def deposit():
    return {"source":"COINBASE_DEPOSIT_RECORD_OPERATOR_SUPPLIED",
            "deposit_id":"synthetic123", "chain_id":8453, "tx_hash":HASH,
            "asset":"cbBTC", "amount":"0.00005", "recipient":TO,
            "status":"COMPLETED"}

class EvidenceTests(unittest.TestCase):
    def test_exact_match_never_claims_authenticated_provenance(self):
        result = reconcile([chain()], [deposit()])[0]
        self.assertEqual(result["classification"], "REPORTED_MATCH_SOURCE_UNVERIFIED")
        self.assertFalse(result["coinbase_provenance_verified"])
        self.assertFalse(result["balance_used_as_proof"])
    def test_no_record_is_not_proof(self):
        self.assertEqual(reconcile([chain()], [])[0]["classification"], "NO_MATCHING_DEPOSIT_RECORD")
    def test_mismatched_identity_or_amount_fails_closed(self):
        for k, v in (("recipient","0x"+"c"*40), ("amount","0.00006"), ("asset","ETH")):
            with self.subTest(field=k):
                d=deposit(); d[k]=v
                self.assertEqual(reconcile([chain()], [d])[0]["classification"], "CONFLICTING_DEPOSIT_RECORD")
    def test_pending_chain_or_exchange_cannot_be_reported_as_match(self):
        t=chain();t["network"]="INCLUDED"
        self.assertEqual(reconcile([t],[deposit()])[0]["classification"],"NETWORK_NOT_FINALIZED")
        d=deposit();d["status"]="PENDING"
        self.assertEqual(reconcile([chain()],[d])[0]["classification"],"DEPOSIT_NOT_COMPLETED")
    def test_duplicate_or_untrusted_input_rejected(self):
        for records in ([deposit(),deposit()], [{**deposit(),"source":"BALANCE_SNAPSHOT"}],
                        [{**deposit(),"extra":"secret"}]):
            with self.assertRaises(DepositEvidenceError):
                reconcile([chain()],records)
    def test_network_mismatch_is_not_a_match(self):
        d=deposit();d["chain_id"]=1
        self.assertEqual(reconcile([chain()],[d])[0]["classification"],"NO_MATCHING_DEPOSIT_RECORD")

    def test_malformed_values_fail_with_fixed_error_without_echoing_input(self):
        for factory, field in ((deposit, "asset"), (chain, "asset"), (chain, "network")):
            for value in ([], {}, None, True):
                with self.subTest(field=field, value=value):
                    row = factory(); row[field] = value
                    with self.assertRaisesRegex(DepositEvidenceError, "^DEPOSIT_EVIDENCE_REJECTED$"):
                        reconcile([row], []) if factory is chain else reconcile([], [row])

    def test_amounts_are_bounded_exact_and_not_exponents_or_nonfinite(self):
        for value in ("1" * 81, "1e-8", "NaN", "Infinity", "0", "-1", "0.000000001", 1, True):
            with self.subTest(value=value):
                with self.assertRaises(DepositEvidenceError):
                    reconcile([chain()], [{**deposit(), "amount": value}])

    def test_duplicate_chain_claims_are_ambiguous_and_inputs_unchanged(self):
        from copy import deepcopy
        t, d = chain(), deposit()
        before = deepcopy((t, d))
        reconcile([t], [d])
        self.assertEqual((t, d), before)
        with self.assertRaises(DepositEvidenceError):
            reconcile([t, t], [d])

if __name__ == "__main__":
    unittest.main()
