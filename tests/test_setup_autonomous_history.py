"""Private setup with synthetic placeholders and mocked Coinbase transport."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import setup_autonomous_history as s
from scripts import autonomous_coinbase_history as a
from scripts.operational_read_only import read_private, write_private
from tests.test_autonomous_coinbase_history import Provider, Response, PORTFOLIO
from tests.test_coinbase_deposit_history import ACCOUNT, SECOND


class SetupTests(unittest.TestCase):
    def prepare(self, directory, broad=False):
        root = Path(directory) / "runtime"
        key = Path(directory) / "synthetic-key.json"
        key.write_text(json.dumps({"name": "synthetic", "privateKey": "test-placeholder-not-a-key"}))
        key.chmod(0o644)
        calls = []
        def opener(request, timeout):
            calls.append(request.full_url)
            if request.full_url.endswith(a.PERMISSIONS):
                return Response(request.full_url, {"can_view": True, "can_trade": broad,
                    "can_transfer": False, "portfolio_uuid": PORTFOLIO})
            return Response(request.full_url, {"data": [{"id": ACCOUNT, "currency": {"code": "BTC"},
                "balance": "[PRIVATE_BALANCE]", "name": "[PRIVATE_NAME]"}], "pagination": {"next_uri": None}})
        def factory(account, portfolio, signer):
            return a.ReadOnlyClient(account, portfolio, signer, opener=opener)
        return root, key, calls, factory

    def configure(self, root, key, factory, select=lambda rows: ACCOUNT):
        return s.configure(root, key, select,
            signer_factory=lambda path: lambda method, path: "synthetic-token", client_factory=factory)

    def test_setup_discovers_locally_and_does_not_print_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root, key, calls, factory = self.prepare(directory)
            def select(options):
                self.assertEqual(options, [{"id": ACCOUNT, "currency": "BTC"}]); return ACCOUNT
            with redirect_stdout(StringIO()) as console:
                config_path = self.configure(root, key, factory, select)
            config = read_private(config_path)
            self.assertEqual(config["account_id"], ACCOUNT)
            self.assertEqual(config["portfolio_id"], PORTFOLIO)
            self.assertEqual(key.stat().st_mode & 0o777, 0o600)
            self.assertEqual(config_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(console.getvalue(), "")
            self.assertEqual(len(calls), 3)
            self.assertEqual(read_private(config["credentials_file"])["privateKey"], "test-placeholder-not-a-key")

    def test_broad_key_rejected_before_discovery_or_managed_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root, key, calls, factory = self.prepare(directory, broad=True)
            with self.assertRaises(ValueError): self.configure(root, key, factory)
            self.assertEqual(len(calls), 1)
            self.assertFalse((root / "reader-config.json").exists())
            self.assertFalse((root / "credentials/coinbase.secret.json").exists())

    def test_unknown_account_does_not_copy_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root, key, calls, factory = self.prepare(directory)
            with self.assertRaises(ValueError): self.configure(root, key, factory, lambda rows: SECOND)
            self.assertFalse((root / "credentials/coinbase.secret.json").exists())

    def test_existing_config_and_source_symlink_are_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root, key, calls, factory = self.prepare(directory)
            a.private_directory(root); write_private(root / "reader-config.json", {"existing": True})
            with self.assertRaises(ValueError): self.configure(root, key, factory)
            self.assertEqual(read_private(root / "reader-config.json"), {"existing": True})
            link = Path(directory) / "link"; link.symlink_to(key)
            with self.assertRaises(OSError): s.secure_source(link)

    def test_invalid_selected_file_is_not_chmodded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-a-key"; path.write_text('{"other":true}'); path.chmod(0o644)
            with self.assertRaises(ValueError): s.secure_source(path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_failed_config_write_rolls_back_new_managed_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root, key, calls, factory = self.prepare(directory)
            def write(path, data):
                if Path(path).name == "reader-config.json": raise OSError("synthetic failure")
                return write_private(path, data)
            with patch.object(s, "write_private", side_effect=write), self.assertRaises(OSError):
                self.configure(root, key, factory)
            self.assertTrue(key.exists())
            self.assertFalse((root / "credentials/coinbase.secret.json").exists())

    def test_discovery_client_cannot_read_individual_account_history(self):
        provider = Provider()
        client = a.ReadOnlyClient(None, PORTFOLIO, lambda method, path: "synthetic-token", opener=provider.open)
        self.assertEqual(client.path, "/v2/accounts")
        with self.assertRaises(ValueError): client.get(f"/v2/accounts/{ACCOUNT}/transactions")
        self.assertEqual(provider.calls, [])


if __name__ == "__main__": unittest.main()
