"""Offline failure-injection tests: no network, keys, real wallets or account data."""
import json
from io import BytesIO
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from scripts import operational_read_only as m
from scripts import autonomous_portfolio as portfolio


class Response:
    status = 200
    def __init__(self, url, payload): self.url, self.payload = url, payload
    def geturl(self): return self.url
    def read(self, limit): return self.payload[:limit]
    def __enter__(self): return self
    def __exit__(self, *args): pass


def success(req, timeout):
    return Response(req.full_url, b'{"jsonrpc":"2.0","id":1,"result":"0x1"}')


class MetadataTests(unittest.TestCase):
    def test_successful_retry_retains_429_without_private_data(self):
        count = 0
        def upstream(req, timeout):
            nonlocal count
            count += 1
            if count == 1:
                raise HTTPError(req.full_url, 429, 'PRIVATE', {'Retry-After': '0'}, BytesIO(b'PRIVATE'))
            return success(req, timeout)
        with m.capture_rpc_metadata():
            self.assertEqual(m.rpc_read(1,'eth_chainId',[],opener=upstream,sleep=lambda _:None),'0x1')
            snapshot = m.rpc_metadata_snapshot()
        counters = snapshot['chains']['1']
        self.assertEqual((counters['requests'],counters['http_429'],counters['http_200'],counters['retries']),(2,1,1,1))
        self.assertNotIn('PRIVATE',json.dumps(snapshot))
        self.assertNotIn('https',json.dumps(snapshot))
        self.assertIsNone(m.rpc_metadata_snapshot())

    def test_retry_budget_and_chain_separation(self):
        def limited(req, timeout): raise HTTPError(req.full_url,429,'PRIVATE',{},None)
        with m.capture_rpc_metadata():
            with self.assertRaises(m.ReadOnlyError):
                m.rpc_read(8453,'eth_chainId',[],opener=limited,sleep=lambda _:None)
            snapshot=m.rpc_metadata_snapshot()
        self.assertEqual(snapshot['chains']['8453']['http_429'],3)
        self.assertEqual(snapshot['chains']['8453']['retries'],2)
        self.assertEqual(snapshot['chains']['1']['requests'],0)

    def test_network_capacity_and_invalid_responses_are_distinct(self):
        def network(req, timeout): raise URLError('PRIVATE')
        def capacity(req, timeout):
            return Response(req.full_url,b'{"jsonrpc":"2.0","id":1,"error":{"code":-32005,"message":"PRIVATE"}}')
        def invalid(req, timeout): return Response(req.full_url,b'PRIVATE')
        for opener,counter,expected in [(network,'network_errors',3),(capacity,'rpc_capacity_errors',3),(invalid,'rejected_responses',1)]:
            with self.subTest(counter=counter), m.capture_rpc_metadata():
                with self.assertRaises(m.ReadOnlyError):
                    m.rpc_read(1,'eth_chainId',[],opener=opener,sleep=lambda _:None)
                snapshot=m.rpc_metadata_snapshot()
                self.assertEqual(snapshot['chains']['1'][counter],expected)
                self.assertNotIn('PRIVATE',json.dumps(snapshot))

    def test_other_http_error_does_not_retry(self):
        def denied(req,timeout):raise HTTPError(req.full_url,403,'PRIVATE',{},None)
        with m.capture_rpc_metadata():
            with self.assertRaises(m.ReadOnlyError):m.rpc_read(1,'eth_chainId',[],opener=denied)
            counts=m.rpc_metadata_snapshot()['chains']['1']
            self.assertEqual((counts['http_other'],counts['requests'],counts['retries']),(1,1,0))

    def test_forbidden_method_fails_before_transport_and_telemetry(self):
        with m.capture_rpc_metadata(), patch.object(m,'build_opener') as transport:
            with self.assertRaises(m.ReadOnlyError):m.rpc_read(1,'eth_sendRawTransaction',[])
            transport.assert_not_called()
            self.assertEqual(m.rpc_metadata_snapshot()['chains']['1']['requests'],0)

    def test_context_resets_on_exception_and_nested_capture(self):
        with m.capture_rpc_metadata():
            m.rpc_read(1,'eth_chainId',[],opener=success)
            with m.capture_rpc_metadata():
                self.assertEqual(m.rpc_metadata_snapshot()['chains']['1']['requests'],0)
            self.assertEqual(m.rpc_metadata_snapshot()['chains']['1']['requests'],1)
        with self.assertRaises(ValueError), m.capture_rpc_metadata():raise ValueError('synthetic')
        self.assertIsNone(m.rpc_metadata_snapshot())

    def test_supervisor_scope_includes_current_cycle_only(self):
        def synthetic(*args,**kwargs):
            m.rpc_read(1,'eth_chainId',[],opener=success)
            return {'rpc_diagnostics':m.rpc_metadata_snapshot()}
        with patch.object(portfolio,'_cycle',side_effect=synthetic):
            first=portfolio.cycle({},None,None)
            second=portfolio.cycle({},None,None)
        self.assertEqual(first['rpc_diagnostics']['chains']['1']['requests'],1)
        self.assertEqual(second['rpc_diagnostics']['chains']['1']['requests'],1)
        self.assertIsNone(m.rpc_metadata_snapshot())

    def test_invalid_retry_after_closes_http_response(self):
        response=BytesIO(b'PRIVATE')
        def invalid(req,timeout):raise HTTPError(req.full_url,429,'PRIVATE',{'Retry-After':'invalid'},response)
        with m.capture_rpc_metadata():
            with self.assertRaises(m.ReadOnlyError):m.rpc_read(1,'eth_chainId',[],opener=invalid)
            self.assertEqual(m.rpc_metadata_snapshot()['chains']['1']['http_429'],1)
        self.assertTrue(response.closed)


if __name__=='__main__':unittest.main()
