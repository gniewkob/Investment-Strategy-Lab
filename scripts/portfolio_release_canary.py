"""Private local deployment preflight and post-release canary (read-only).

Never logs/returns account values, addresses, paths or credentials. No network,
orders, wallet operations, writes, notification triggers or service restart.
A local JSON report is not cryptographic proof of an authenticated provider.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import stat
import subprocess

from scripts import history_coverage
from scripts.private_wallet_chain_monitor import _private_config
from scripts.operational_read_only import read_private

SHA = re.compile(r"[0-9a-f]{40}\Z")
ALLOWED_STATUS = {"OBSERVATION_OK", "PARTIAL", "UNAVAILABLE"}
BACKFILL_STATUS = {"NO_ELIGIBLE_GAP", "RECOVERED_WINDOW", "UNAVAILABLE"}


class ReleaseRejected(ValueError):
    pass


def require(ok):
    if not ok:
        raise ReleaseRejected("PRIVATE_RELEASE_CANARY_REJECTED")


def _private_path(path, *, file=False):
    require(isinstance(path, str) and bool(path) and Path(path).is_absolute())
    raw = Path(path)
    # No dereferencing final symlink. Reject unsafe mode and incorrect owner.
    try:
        details = raw.lstat()
        require(details.st_uid == os.getuid() and not details.st_mode & 0o077)
        if file:
            require(stat.S_ISREG(details.st_mode) and 0 < details.st_size <= 2_000_000)
        else:
            require(stat.S_ISDIR(details.st_mode))
    except OSError:
        raise ReleaseRejected("PRIVATE_RELEASE_CANARY_REJECTED") from None
    return raw


def _time(value):
    require(isinstance(value, str) and len(value) <= 40)
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise ReleaseRejected("PRIVATE_RELEASE_CANARY_REJECTED") from None
    require(date.tzinfo is not None and date.utcoffset() == timedelta(0))
    return date


def local_code_attestation(expected, root):
    """Check actual local checkout HEAD and worktree, without exposing paths."""
    require(isinstance(expected, str) and SHA.fullmatch(expected) is not None)
    root = Path(root)
    require(root.is_dir())
    # Import locally: m1_predeploy_readiness imports this module for its
    # pre-release canary, so a top-level import would introduce a cycle.
    # Both the standalone canary and M1 must use the SAME hardened Git path;
    # a bare git process would re-enable fsmonitor/filter execution via
    # inherited GIT_DIR, GIT_WORK_TREE or redirected local config.
    try:
        from scripts import m1_predeploy_readiness as guarded_git
        guarded_git.assert_trusted_git_checkout(root, os.getuid())
        head = guarded_git.command(
            "git", "-C", str(root), "rev-parse", "--verify", "HEAD")
        dirty = guarded_git.command(
            "git", "-C", str(root), "status", "--porcelain",
            "--untracked-files=all", "--ignore-submodules=all")
    except Exception:
        raise ReleaseRejected("PRIVATE_RELEASE_CANARY_REJECTED") from None
    require(head == expected and dirty == "")
    return True


def inspect(config_path, expected, phase, now, *, git_probe=local_code_attestation,
            repository_root=None):
    """Validate local release state. Does not touch credentials or call providers."""
    require(phase in {"before", "after"} and isinstance(now, datetime)
            and now.tzinfo is not None and now.utcoffset() == timedelta(0))
    require(isinstance(expected, str) and SHA.fullmatch(expected) is not None)
    root = Path(repository_root or Path(__file__).resolve().parents[1])
    require(git_probe(expected, root) is True)
    config_file = _private_path(str(config_path), file=True)
    _private_path(str(config_file.parent))
    config = read_private(config_file)
    require(set(config) == {"credentials_file", "portfolio_id", "watchlist_file",
                            "state_directory", "interval_seconds"})
    require(isinstance(config["portfolio_id"], str) and re.fullmatch(
        r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}",
        config["portfolio_id"]) is not None)
    require(type(config["interval_seconds"]) is int and
            300 <= config["interval_seconds"] <= 86400)
    state_dir = _private_path(config["state_directory"])
    _private_path(str(state_dir.parent))
    secret = _private_path(config["credentials_file"], file=True)
    watch_path = _private_path(config["watchlist_file"], file=True)
    for location in (config_file, secret, watch_path, state_dir):
        require(not location.resolve().is_relative_to(root.resolve()))
    _private_path(str(secret.parent))
    _private_path(str(watch_path.parent))
    watch = read_private(watch_path)
    entries = _private_config(watch)
    require(len(entries) > 0)
    result = {
        "mode": "PRIVATE_PORTFOLIO_RELEASE_CANARY_V1",
        "phase": phase,
        "source_commit_matches_clean_checkout": True,
        "private_config_permissions_valid": True,
        "watched_chain_entries": len(entries),
        "financial_operations": 0,
        "network_requests": 0,
        "credentials_opened": False,
        "provider_response_authenticated_by_canary": False,
        "local_daemon_running_verified": False,
        "onchain_full_history_certified": False,
        "full_portfolio_valuation_certified": False,
    }
    if phase == "before":
        result["result"] = "READY_FOR_CONTROLLED_READ_ONLY_CANARY"
        return result
    portfolio = read_private(_private_path(str(state_dir / "portfolio.json"), file=True))
    health = read_private(_private_path(str(state_dir / "health.json"), file=True))
    require(portfolio.get("mode") == "PRIVATE_AUTONOMOUS_PORTFOLIO_V1"
            and portfolio.get("financial_operations") == 0
            and type(portfolio.get("financial_operations")) is int)
    require(health.get("financial_operations") == 0
            and type(health.get("financial_operations")) is int)
    for field in ("status", "checked_at_utc", "expires_at_utc", "alerts"):
        require(portfolio.get(field) == health.get(field))
    require(portfolio["status"] in {"OBSERVATION_OK", "PARTIAL"}
            and isinstance(portfolio["alerts"], list)
            and all(isinstance(a, str) and len(a) <= 90 for a in portfolio["alerts"]))
    checked, expires = _time(portfolio["checked_at_utc"]), _time(portfolio["expires_at_utc"])
    require(now - timedelta(seconds=5) <= expires
            and checked <= now + timedelta(seconds=5)
            and checked < expires <= checked + timedelta(minutes=30)
            and now - checked <= timedelta(minutes=30))
    sources = portfolio.get("sources")
    require(isinstance(sources, dict) and "exchange" in sources
            and "market" in sources and "usdpln" in sources
            and all(isinstance(s, dict) and s.get("status") in
                    {"OK", "PARTIAL", "UNAVAILABLE"} for s in sources.values()))
    coverage = portfolio.get("history_coverage")
    require(isinstance(coverage, dict)
            and coverage.get("mode") == history_coverage.MODE
            and coverage.get("financial_operations") == 0
            and coverage.get("complete_chain_history_certified") is False
            and coverage.get("account_to_chain_linkage_certified") is False
            and isinstance(coverage.get("streams"), dict))
    expected_keys = {f"chain_{label}_{chain}" for chain, address, label, contracts in entries}
    require(set(coverage["streams"]) == expected_keys)
    for chain, address, label, contracts in entries:
        key = f"chain_{label}_{chain}"
        record = history_coverage._record(coverage["streams"][key])
        require(record["identity_sha256"] == history_coverage._identity(
            chain, address, contracts)
            and key in sources)
    require(coverage.get("latest_source_incomplete") is
            any(r["latest_status"] != "COMPLETE_RANGE"
                for r in coverage["streams"].values()))
    require(coverage.get("gap_range_count") ==
            sum(len(r["gap_ranges"]) for r in coverage["streams"].values()))
    require(coverage.get("historical_gap_detected") is
            any(r["gap_ranges"] or r["gap_range_overflow"]
                for r in coverage["streams"].values()))
    backfill = portfolio.get("history_backfill")
    require(isinstance(backfill, dict) and backfill.get("status") in BACKFILL_STATUS
            and backfill.get("financial_operations") == 0
            and type(backfill.get("recovered_block_count")) is int
            and 0 <= backfill["recovered_block_count"] <= 80
            and type(backfill.get("events_saved")) is int
            and 0 <= backfill["events_saved"] <= 1000)
    # A supposedly healthy report must not conceal a failed upstream source,
    # an outstanding gap, or a failed historical repair attempt.
    if portfolio["status"] == "OBSERVATION_OK":
        require(not portfolio["alerts"]
                and all(source["status"] == "OK" for source in sources.values())
                and not coverage["latest_source_incomplete"]
                and not coverage["historical_gap_detected"]
                and backfill["status"] != "UNAVAILABLE")
    require((backfill["status"] == "RECOVERED_WINDOW"
             and 1 <= backfill["recovered_block_count"] <= 80)
            or (backfill["status"] != "RECOVERED_WINDOW"
                and backfill["recovered_block_count"] == 0
                and backfill["events_saved"] == 0))
    result["observed_source_count"] = len(sources)
    result["gap_range_count"] = coverage["gap_range_count"]
    result["gap_or_overflow_detected"] = coverage["historical_gap_detected"]
    result["last_cycle_status"] = portfolio["status"]
    result["last_backfill_status"] = backfill["status"]
    result["result"] = (
        "LOCAL_METADATA_CANARY_OK_NOT_PROVIDER_ATTESTED"
        if portfolio["status"] == "OBSERVATION_OK" and
           not coverage["historical_gap_detected"] else
        "LOCAL_METADATA_CANARY_PARTIAL")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private offline portfolio release canary")
    parser.add_argument("--config", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--phase", required=True, choices=("before", "after"))
    args = parser.parse_args(argv)
    try:
        data = inspect(args.config, args.expected_commit, args.phase,
                       datetime.now(timezone.utc))
        print(json.dumps(data, sort_keys=True, separators=(",", ":")))
        return 0 if data["result"] != "LOCAL_METADATA_CANARY_PARTIAL" else 3
    except Exception:
        # Not even the offending file path, secret, address or provider body.
        print("PRIVATE_RELEASE_CANARY_REJECTED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
