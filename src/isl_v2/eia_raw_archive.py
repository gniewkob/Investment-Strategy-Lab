"""Private, content-addressed ORIGINAL EIA HTML acquisition archive (no Neon).

The archive is a POSIX filesystem staging adapter, NOT storage-level WORM:
O_EXCL + fsync prevents accidental overwrites by this application, but the
filesystem owner can still edit/remove the files. Require an independently
managed immutable storage backend with retention before a durable PIT GO.

Never publish raw HTML, full quote tables, user file paths, or secrets to
GitHub logs or artifacts. A manifest only proves current-snapshot retrieval,
not original publication timing of a historical market observation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from src.isl_v2.eia_semantic_evidence import semantic_evidence
from src.isl_v2.eia_sources import SOURCES, SourceFormatError
from src.isl_v2.eia_versioned_ingest import (
    IngestionPlan, MAX_SOURCE_BYTES, prepare,
)

SCHEMA = "EIA_ORIGINAL_HTML_CONTENT_ARCHIVE_V1"
UTC_STAMP = "%Y%m%dT%H%M%S.%fZ"
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC


def _root_fd(root: Path | str) -> int:
    # Require a preexisting, operator-controlled path. Never provision it
    # from GitHub Actions or silently create it inside the repository tree.
    if not isinstance(root, (Path, str)):
        raise SourceFormatError("Archive root must be a local filesystem path")
    path = Path(root)
    if not path.is_absolute() or path.is_symlink():
        raise SourceFormatError("Archive root must exist at an absolute non-symlink path")
    # Do not allow raw third-party HTML to leak into a Git checkout.
    # The operator must provide a path outside every Git worktree.
    resolved = path.resolve(strict=True)
    if any((ancestor / ".git").exists() for ancestor in (resolved, *resolved.parents)):
        raise SourceFormatError("Raw EIA archive must not live inside Git checkout")
    fd = os.open(path, DIR_FLAGS)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise SourceFormatError("Archive root must be private and owner-controlled")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _subdir(parent: int, name: str, *, create: bool = True) -> int:
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise SourceFormatError("Invalid archive directory")
    if create:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent)
            os.fsync(parent)
        except FileExistsError:
            pass
    fd = os.open(name, DIR_FLAGS, dir_fd=parent)
    try:
        st = os.fstat(fd)
        if (not stat.S_ISDIR(st.st_mode)
                or st.st_uid != os.getuid()
                or stat.S_IMODE(st.st_mode) & 0o077):
            raise SourceFormatError("Archive subdirectory is not private")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _write_once(parent: int, name: str, data: bytes) -> bool:
    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", name):
        raise SourceFormatError("Untrusted archive filename")
    try:
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=parent)
    except FileExistsError:
        existing = _read_exact(parent, name, len(data))
        if existing != data:
            raise SourceFormatError("Existing content-addressed archive entry differs")
        return False
    try:
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
        return True
    except BaseException:
        # Never replace a damaged existing archive object; a subsequent
        # retry must fail and require an operator's forensic intervention.
        raise


def _read_exact(parent: int, name: str, max_size: int) -> bytes:
    fd = os.open(name, FILE_FLAGS, dir_fd=parent)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(stream.fileno())
        if (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1
                or st.st_uid != os.getuid()
                or stat.S_IMODE(st.st_mode) & 0o077):
            raise SourceFormatError("Archive entry is not a private regular file")
        raw = stream.read(max_size + 1)
        if len(raw) > max_size:
            raise SourceFormatError("Archive entry is too large")
        return raw


def _validated_plan(plan: IngestionPlan) -> dict:
    if not isinstance(plan, IngestionPlan) or type(plan.original_html) is not bytes:
        raise SourceFormatError("No original EIA bytes in acquisition plan")
    snapshot = plan.snapshot
    source = next((k for k, v in SOURCES.items()
                   if v == (snapshot.instrument_code, snapshot.source_code,
                            snapshot.url)), None)
    if source is None:
        raise SourceFormatError("Unknown EIA source")
    # Never trust the caller's mutable reference alone: reparse the raw bytes,
    # verify every quote, true retrieval time and the precise parsing window.
    actual = prepare(source, plan.original_html, snapshot.downloaded_at,
                     max_age_days=plan.max_age_days)
    if (actual.snapshot != snapshot or actual.available_at != plan.available_at
            or actual.source_bytes_sha256 != plan.source_bytes_sha256):
        raise SourceFormatError("Archive plan does not match original EIA source bytes")
    moment = snapshot.downloaded_at.astimezone(timezone.utc)
    if moment.utcoffset() is None or moment.year < 2024:
        raise SourceFormatError("Invalid archive acquisition time")
    digest = hashlib.sha256(plan.original_html).hexdigest()
    if not DIGEST.fullmatch(digest):
        raise SourceFormatError("Invalid archive SHA")
    sem = semantic_evidence(snapshot)
    return {
        "archive_schema": SCHEMA,
        "instrument_code": snapshot.instrument_code,
        "source_code": snapshot.source_code,
        "canonical_source_url": snapshot.url,
        "original_html_sha256": digest,
        "raw_html_byte_count": len(plan.original_html),
        "semantic_schema": sem["semantic_schema"],
        "semantic_observations_sha256": sem["semantic_observations_sha256"],
        "semantic_observation_count": sem["semantic_observation_count"],
        "first_observed_for": sem["first_observed"],
        "last_observed_for": sem["last_observed"],
        "max_age_days": plan.max_age_days,
        "current_source_release_day": snapshot.release_day.isoformat(),
        "publication_precision": "DAY",
        "retrieved_at": moment.isoformat(),
        "current_source_available_not_before": plan.available_at.isoformat(),
        "source_vintage": "CURRENT_SNAPSHOT_UNVERIFIED_HISTORICAL_PUBLICATION",
        "independent_historical_publication_vintages_verified": False,
        "archive_backend": "PRIVATE_LOCAL_POSIX_STAGING_NOT_WORM",
        "immutable_object_storage_certified": False,
        "database_connections": 0,
        "database_writes": 0,
        "trading_enabled": False,
    }


def _paths(plan: IngestionPlan) -> tuple[str, str, str]:
    s = plan.snapshot
    source = s.source_code
    if source not in (v[1] for v in SOURCES.values()):
        raise SourceFormatError("Invalid EIA source archive key")
    digest = plan.source_bytes_sha256
    if not DIGEST.fullmatch(digest):
        raise SourceFormatError("Invalid archive hash")
    stamp = s.downloaded_at.astimezone(timezone.utc).strftime(UTC_STAMP)
    return source, f"{digest}.html", f"{stamp}_{digest}.json"


def archive_snapshot(root: Path | str, plan: IngestionPlan) -> dict:
    """Stage original bytes + acquisition manifest without overwrite.

    Each acquisition produces its OWN time-bound receipt, even if EIA HTML
    raw bytes are unchanged. Object dedup is by SHA-256 only. Any second
    write using the same key must have byte-for-byte identical content.
    Neither this local-only adapter nor chmod provides durable WORM retention.
    """
    receipt = _validated_plan(plan)
    source, object_name, receipt_name = _paths(plan)
    manifest = (json.dumps(receipt, sort_keys=True, separators=(",", ":"),
                           allow_nan=False) + "\n").encode("utf-8")
    rootfd = _root_fd(root)
    try:
        objects = _subdir(rootfd, "objects")
        try:
            receipts = _subdir(rootfd, "receipts")
            try:
                folder = _subdir(receipts, source)
                try:
                    object_created = _write_once(objects, object_name, plan.original_html)
                    # Read-back catches unexpected local filesystem corruption.
                    if hashlib.sha256(_read_exact(objects, object_name, MAX_SOURCE_BYTES)
                                      ).hexdigest() != receipt["original_html_sha256"]:
                        raise SourceFormatError("Raw EIA byte read-back fingerprint mismatch")
                    receipt_created = _write_once(folder, receipt_name, manifest)
                    if _read_exact(folder, receipt_name, 16_384) != manifest:
                        raise SourceFormatError("EIA acquisition manifest read-back mismatch")
                finally:
                    os.close(folder)
            finally:
                os.close(receipts)
        finally:
            os.close(objects)
    finally:
        os.close(rootfd)
    # Do not output raw bytes, absolute path, quote values or credentials.
    return {
        "status": "EIA_RAW_HTML_ARCHIVED_LOCAL_STAGING_NOT_WORM",
        "original_html_sha256": receipt["original_html_sha256"],
        "semantic_observations_sha256": receipt["semantic_observations_sha256"],
        "retrieved_at": receipt["retrieved_at"],
        "source_code": source,
        "object_created": object_created,
        "receipt_created": receipt_created,
        "archive_backend": receipt["archive_backend"],
        "immutable_object_storage_certified": False,
        "database_connections": 0,
        "database_writes": 0,
    }


def verify_snapshot(root: Path | str, plan: IngestionPlan) -> dict:
    """Verify archive against independently reparsed original bytes and manifest."""
    expected = _validated_plan(plan)
    source, object_name, receipt_name = _paths(plan)
    manifest = (json.dumps(expected, sort_keys=True, separators=(",", ":"),
                           allow_nan=False) + "\n").encode("utf-8")
    rootfd = _root_fd(root)
    try:
        objects = _subdir(rootfd, "objects", create=False)
        try:
            receipts = _subdir(rootfd, "receipts", create=False)
            try:
                folder = _subdir(receipts, source, create=False)
                try:
                    stored = _read_exact(objects, object_name, MAX_SOURCE_BYTES)
                    saved_manifest = _read_exact(folder, receipt_name, 16_384)
                finally:
                    os.close(folder)
            finally:
                os.close(receipts)
        finally:
            os.close(objects)
    finally:
        os.close(rootfd)
    if (stored != plan.original_html
            or hashlib.sha256(stored).hexdigest() != expected["original_html_sha256"]
            or saved_manifest != manifest):
        raise SourceFormatError("EIA archive raw HTML and acquisition receipt differ")
    return {
        "status": "EIA_RAW_HTML_ARCHIVE_LOCAL_READBACK_VALID",
        "source_code": source,
        "original_html_sha256": expected["original_html_sha256"],
        "retrieved_at": expected["retrieved_at"],
        "immutable_object_storage_certified": False,
        "database_writes": 0,
    }


def verify_receipt(root: Path | str, source_code: str, raw_sha256: str,
                   retrieved_at: datetime) -> dict:
    """Reconstruct and validate a previously archived acquisition OFFLINE.

    No original IngestionPlan, live EIA page, database, or credentials needed.
    Verify the on-disk bytes and manifest with the original recorded clock,
    parsing window, exact source identity and canonical hashes.
    """
    source = next((k for k, identity in SOURCES.items()
                   if identity[1] == source_code), None)
    if source is None or not isinstance(raw_sha256, str) or not DIGEST.fullmatch(raw_sha256):
        raise SourceFormatError("Unknown EIA receipt identity")
    if (not isinstance(retrieved_at, datetime) or retrieved_at.tzinfo is None
            or retrieved_at.utcoffset() is None):
        raise SourceFormatError("Invalid EIA archived retrieval time")
    at = retrieved_at.astimezone(timezone.utc)
    raw_name = f"{raw_sha256}.html"
    receipt_name = f"{at.strftime(UTC_STAMP)}_{raw_sha256}.json"
    rootfd = _root_fd(root)
    try:
        objects = _subdir(rootfd, "objects", create=False)
        try:
            receipts = _subdir(rootfd, "receipts", create=False)
            try:
                folder = _subdir(receipts, source_code, create=False)
                try:
                    raw = _read_exact(objects, raw_name, MAX_SOURCE_BYTES)
                    manifest = _read_exact(folder, receipt_name, 16_384)
                finally:
                    os.close(folder)
            finally:
                os.close(receipts)
        finally:
            os.close(objects)
    finally:
        os.close(rootfd)
    if hashlib.sha256(raw).hexdigest() != raw_sha256:
        raise SourceFormatError("Original EIA HTML archive SHA-256 does not match")
    try:
        decoded = json.loads(manifest.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceFormatError("Unreadable EIA acquisition manifest") from exc
    if (type(decoded) is not dict or decoded.get("max_age_days") is None
            or type(decoded["max_age_days"]) is not int
            or not 1 <= decoded["max_age_days"] <= 1500):
        raise SourceFormatError("Unrecognized archived source parsing window")
    regenerated = prepare(source, raw, at, max_age_days=decoded["max_age_days"])
    expected = _validated_plan(regenerated)
    if (expected != decoded
            or (json.dumps(expected, sort_keys=True, separators=(",", ":"),
                           allow_nan=False) + "\n").encode("utf-8") != manifest):
        raise SourceFormatError("Acquisition record no longer matches archived HTML")
    return {
        "status": "EIA_RAW_HTML_ARCHIVE_INDEPENDENT_OFFLINE_VERIFIED",
        "source_code": source_code,
        "original_html_sha256": raw_sha256,
        "semantic_observations_sha256": expected["semantic_observations_sha256"],
        "retrieved_at": at.isoformat(),
        "archive_backend": "PRIVATE_LOCAL_POSIX_STAGING_NOT_WORM",
        "immutable_object_storage_certified": False,
        "database_connections": 0,
        "database_writes": 0,
    }
