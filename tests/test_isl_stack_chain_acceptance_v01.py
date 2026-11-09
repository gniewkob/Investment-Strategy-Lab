"""Synthetic offline acceptance contract: exact blobs, no unexplained drift."""
from hashlib import sha1
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.isl_stack_chain_acceptance_v01 import (
    ChainBlocked, EXPECTED_BLOBS, SUITES, V09_PATH, _bounded_file,
    git_blob_sha, verify_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]


class StackedSourceIdentityTests(unittest.TestCase):
    def test_git_blob_sha_matches_known_canonical_blob(self):
        self.assertEqual(
            git_blob_sha(b"hello\n"),
            "ce013625030ba8dba906f756967f9e9ca394464a",
        )
        self.assertNotEqual(git_blob_sha(b"hello"), git_blob_sha(b"hello\n"))

    def test_complete_current_overlay_matches_exact_a2_b1_c1_source_blobs(self):
        receipt = verify_snapshot(ROOT)
        self.assertEqual(receipt["a2_pinned_files"], 12)
        self.assertEqual(receipt["inherited_b1_c1_spot_checks"], 2)
        self.assertEqual(receipt["checked_blobs"], 14)
        self.assertTrue(receipt["v09_sha256_verified"])
        self.assertFalse(receipt["trading_authorized"])

    def test_injected_source_change_is_blocked_without_deleting_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (*EXPECTED_BLOBS, V09_PATH):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            target = root / "scripts/nbp_reference_capture.py"
            target.write_bytes(target.read_bytes() + b"\n# injected\n")
            with self.assertRaisesRegex(ChainBlocked, "source blob changed"):
                verify_snapshot(root)
            self.assertNotIn(b"# injected", (ROOT / "scripts/nbp_reference_capture.py").read_bytes())

    def test_symlinked_candidate_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "actual.txt"
            source.write_text("example")
            link = root / "link.txt"
            link.symlink_to(source)
            with self.assertRaisesRegex(ChainBlocked, "symlinked source"):
                _bounded_file(root, "link.txt")

    def test_all_four_layer_suites_are_unique_and_count_pinned(self):
        names = [m for _, modules in SUITES.values() for m in modules]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(SUITES), {"A2", "B1", "C1", "C2"})
        self.assertEqual(sum(count for count, _ in SUITES.values()), 158)


if __name__ == "__main__":
    unittest.main()
