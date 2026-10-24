"""Synthetic read-only RPC provider-selection and Base log capability tests."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import base_rpc_probe as p
from scripts import operational_read_only as m

NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
HASH = "0x" + "a"*64


def source(*, chain=8453, age=30, log_result=None, hash_changed=False):
    calls = []
    def rpc(c, method, params):
        calls.append((c, method, params))
        if method == "eth_chainId":
            return hex(chain)
        if method == "eth_getBlockByNumber":
            block = params[0]
            return {"number":"0x3e8",
                    "hash":("0x" + "b"*64 if hash_changed and block != "finalized" else HASH),
                    "timestamp":hex(int((NOW-timedelta(seconds=age)).timestamp()))}
        if method == "eth_getLogs":
            return [] if log_result is None else log_result
        raise AssertionError(method)
    return rpc, calls


class BaseRpcProbeTests(unittest.TestCase):
    def test_default_and_opt_in_sources_are_exact_allowlist(self):
        self.assertEqual(m.configured_rpc_urls("OFFICIAL")[8453],
                         "https://mainnet.base.org")
        self.assertEqual(m.configured_rpc_urls("PUBLICNODE")[8453],
                         "https://base-rpc.publicnode.com")
        self.assertEqual(m.configured_rpc_urls("PUBLICNODE")[1],
                         m.configured_rpc_urls("OFFICIAL")[1])
        for item in (None, False, "", "other", "https://evil.example", "publicnode",
                     "PUBLICNODE?key=private", ["PUBLICNODE"]):
            with self.subTest(item=str(item)), self.assertRaisesRegex(
                    ValueError, "BASE_RPC_SOURCE_NOT_ALLOWLISTED"):
                m.configured_rpc_urls(item)

    def test_import_fixes_provider_for_process_lifetime(self):
        for setting, expected in (
            ("OFFICIAL", "https://mainnet.base.org"),
            ("PUBLICNODE", "https://base-rpc.publicnode.com")):
            with self.subTest(source=setting):
                env = dict(os.environ, ISL_BASE_RPC_SOURCE=setting)
                result = subprocess.run([sys.executable, "-c",
                    "from scripts.operational_read_only import RPC_URLS; print(RPC_URLS[8453])"],
                    env=env, capture_output=True, text=True, timeout=12)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout.strip(), expected)
        env = dict(os.environ, ISL_BASE_RPC_SOURCE="unsafe")
        invalid = subprocess.run([sys.executable, "-c",
                "import scripts.operational_read_only"], env=env,
                capture_output=True, text=True, timeout=12)
        self.assertNotEqual(invalid.returncode, 0)

    def test_public_zero_address_two_filters_and_pinned_head(self):
        rpc,calls = source()
        result = p.probe(NOW, rpc=rpc)
        self.assertEqual(result["status"], "PUBLIC_BASE_READ_METHODS_AVAILABLE")
        self.assertEqual(result["blocks_tested"], 80)
        self.assertEqual(result["log_filter_count"], 2)
        self.assertFalse(result["wallet_identifiers_sent"])
        self.assertEqual(result["financial_operations"], 0)
        self.assertEqual([x[1] for x in calls], [
            "eth_chainId", "eth_getBlockByNumber", "eth_getLogs",
            "eth_getLogs", "eth_getBlockByNumber"])
        for c,method,args in calls:
            self.assertEqual(c, 8453)
            self.assertNotIn("eth_send",method)
            if method == "eth_getLogs":
                query=args[0]
                self.assertEqual(query["fromBlock"],hex(921))
                self.assertEqual(query["toBlock"],hex(1000))
                self.assertEqual(query["address"],next(iter(m.TOKENS[8453])))
                self.assertEqual(query["topics"][-1],p.ZERO_ADDRESS_TOPIC)
        self.assertNotIn("0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", json.dumps(result))

    def test_wrong_chain_stale_hash_reorg_or_limited_logs_fail_closed(self):
        cases=(dict(chain=1),dict(age=2*3600),dict(hash_changed=True),
               dict(log_result=[{}]*5001),dict(log_result={}))
        for option in cases:
            with self.subTest(option=option):
                rpc,calls = source(**option)
                with self.assertRaises(p.ProbeError):
                    p.probe(NOW,rpc=rpc)
        rpc,calls=source()
        with self.assertRaises(p.ProbeError):
            p.probe(NOW.replace(tzinfo=None),rpc=rpc)

    def test_rate_limit_unavailability_does_not_switch_hosts(self):
        fake, calls = source()
        def limited(c,method,params):
            if method=="eth_getLogs":
                raise m.ReadOnlyError("RPC_HTTP_FAILURE")
            return fake(c,method,params)
        with self.assertRaises(m.ReadOnlyError):
            p.probe(NOW,rpc=limited)
        self.assertNotIn("eth_sendRawTransaction",json.dumps(calls))

    def test_https_response_origin_is_exactly_selected_backend(self):
        alternate=m.BASE_RPC_SOURCES["PUBLICNODE"]
        class Response(BytesIO):
            status=200
            def geturl(self): return alternate
        with patch.dict(m.RPC_URLS,{8453:alternate}):
            def get(req,timeout):
                self.assertEqual(req.full_url,alternate)
                self.assertEqual(req.get_method(),"POST")
                return Response(b'{"jsonrpc":"2.0","id":1,"result":"0x2105"}')
            self.assertEqual(m.rpc_read(8453,"eth_chainId",[],opener=get),"0x2105")
            with self.assertRaises(m.ReadOnlyError):
                m.rpc_read(8453,"eth_sendRawTransaction",[],opener=get)
        # Existing origin validation blocks redirects to a different host.
        with patch.dict(m.RPC_URLS,{8453:alternate}):
            class Wrong(Response):
                def geturl(self):return "https://mainnet.base.org"
            with self.assertRaises(m.ReadOnlyError):
                m.rpc_read(8453,"eth_chainId",[],opener=lambda req,timeout:
                    Wrong(b'{"jsonrpc":"2.0","id":1,"result":"0x2105"}'))

    def test_cli_requires_opt_in_and_has_fixed_redacted_errors(self):
        out=StringIO()
        with redirect_stdout(out):
            code=p.main([])
        self.assertEqual(code,2)
        self.assertEqual(out.getvalue().strip(),"BASE_READ_PROBE_OPT_IN_REQUIRED")
        out=StringIO()
        with patch.object(p,"probe",side_effect=RuntimeError("SECRET_WALLET_ADDRESS")),redirect_stdout(out):
            code=p.main(["--allow-public-network-probe"])
        self.assertEqual(code,2)
        self.assertEqual(out.getvalue().strip(),"BASE_READ_PROBE_UNAVAILABLE_OR_REJECTED")

    def test_official_provider_is_unchanged_by_default(self):
        # Existing runtime behavior is kept unless the operator opts in.
        self.assertEqual(m.RPC_URLS[8453],m.BASE_RPC_SOURCES[
            os.environ.get("ISL_BASE_RPC_SOURCE","OFFICIAL")])


if __name__=="__main__":
    unittest.main()
