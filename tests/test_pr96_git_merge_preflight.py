"""Repository-isolated git merge-tree preflight unit tests."""
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from scripts.pr96_git_merge_preflight import preflight


def git(root, *args):
    result=subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("git setup failed: " + result.stderr)
    return result.stdout.strip()


def fixture(*, conflict=False):
    tmp=TemporaryDirectory()
    root=Path(tmp.name)
    git(root,"init")
    git(root,"config","user.email","test@example.invalid")
    git(root,"config","user.name","Research Test")
    git(root,"checkout","-b","main")
    (root/"shared.txt").write_text("original\n")
    git(root,"add",".")
    git(root,"commit","-m","base")
    git(root,"checkout","-b","feature")
    if conflict:
        (root/"shared.txt").write_text("feature version\n")
    else:
        (root/"module.py").write_text("RESEARCH_ONLY=True\n")
    git(root,"add",".")
    git(root,"commit","-m","feature")
    git(root,"checkout","main")
    if conflict:
        (root/"shared.txt").write_text("main version\n")
    else:
        (root/"daily.yml").write_text("schedule: disabled\n")
    git(root,"add",".")
    git(root,"commit","-m","main")
    return tmp,root


class GitMergePreflightTests(unittest.TestCase):
    def test_disjoint_branches_have_clean_merge_without_branch_checkout(self):
        tmp,root=fixture()
        with tmp:
            original_head=git(root,"rev-parse","HEAD")
            original_status=git(root,"status","--porcelain")
            r=preflight(root,left="main",right="feature")
            self.assertEqual(r["status"],"CLEAN_TREE_MERGE_ONLY_NOT_TESTED")
            self.assertEqual(r["overlapping_changed_paths"],[])
            self.assertEqual(r["merge_tree_exit_code"],0)
            self.assertTrue(r["result_tree_sha"])
            self.assertFalse(r["integration_approved"])
            self.assertEqual(r["financial_operations"],0)
            self.assertEqual(git(root,"rev-parse","HEAD"),original_head)
            self.assertEqual(git(root,"status","--porcelain"),original_status)

    def test_conflicting_branches_fail_closed_without_affecting_checkout(self):
        tmp,root=fixture(conflict=True)
        with tmp:
            original_head=git(root,"rev-parse","HEAD")
            r=preflight(root,left="main",right="feature")
            self.assertEqual(r["status"],"CONFLICTS_DETECTED_DO_NOT_MERGE")
            self.assertEqual(r["merge_tree_exit_code"],1)
            self.assertEqual(r["overlapping_changed_paths"],["shared.txt"])
            self.assertEqual(git(root,"rev-parse","HEAD"),original_head)
            self.assertEqual(git(root,"status","--porcelain"),"")

    def test_missing_ref_rejected_not_inferred(self):
        tmp,root=fixture()
        with tmp:
            with self.assertRaisesRegex(RuntimeError,"git command"):
                preflight(root,left="missing-branch",right="feature")

    def test_non_git_directory_rejected(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                preflight(d,left="main",right="feature")


if __name__=="__main__":
    unittest.main()
