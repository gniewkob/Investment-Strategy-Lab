"""One-shot official DataverseNL Swinkels dataset version chronology.

Probes *publisher metadata* and SHA-pinned ODS, but never assumes that a
dataset version release is proof that each underlying yield was available at
an observation-time decision. Archives neither source file nor market values.

Only official DataverseNL endpoints are requested. Strict HTTPS/redirect,
download caps and SHA checks come from existing read-only source client.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from urllib.parse import quote

from scripts.research_swinkels_original_source_probe_v01 import (
    PUBLISHER, DOI, OFFICIAL_METADATA, MAX_METADATA_BYTES, SourceUnavailable,
    fetch, parse_api,
)
from scripts.swinkels_formula_topology_probe_v01 import (
    SOURCE_ID, SOURCE_BYTES, SOURCE_SHA,
)

VERSIONS_API = (
    PUBLISHER + "/api/datasets/:persistentId/versions?persistentId="
    + quote("doi:" + DOI, safe="")
)
TARGET_ID = SOURCE_ID
EXPECTED_MONTH_COUNT = 36
EARLIEST_MONTH = "2020-01"
LATEST_MONTH = "2022-12"
DATASET_RELEASE_STATE = "RELEASED"
MAX_VERSIONS = 80


def _release_date(value):
    """Read UTC release date; never fall back to lastUpdateTime as releaseTime."""
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return None
    return stamp.astimezone(timezone.utc).date().isoformat()


def _linked_file_ids(version):
    """File IDs in version inventory, not byte-level historical snapshots."""
    files = version.get("files")
    if not isinstance(files, list):
        return None
    ids = set()
    for item in files:
        if not isinstance(item, dict):
            continue
        data = item.get("dataFile", item)
        if isinstance(data, dict) and type(data.get("id")) is int:
            ids.add(data["id"])
    return ids


def audit_release_timeline(versions, publisher_file_sha_verified: bool):
    if type(publisher_file_sha_verified) is not bool:
        raise SourceUnavailable("source proof has invalid type")
    if not publisher_file_sha_verified:
        raise SourceUnavailable("publisher original ODS digest unverified")
    if not isinstance(versions, list) or not 1 <= len(versions) <= MAX_VERSIONS:
        raise SourceUnavailable("dataset version inventory missing or excessive")

    inventory = []
    for v in versions:
        if not isinstance(v, dict):
            raise SourceUnavailable("unstructured dataset version")
        state = v.get("versionState")
        if state != DATASET_RELEASE_STATE:
            # Draft releaseTime is not evidence of public publication.
            continue
        dataset_pid = v.get("datasetPersistentId")
        if isinstance(dataset_pid, str) and dataset_pid.lower() != "doi:" + DOI.lower():
            raise SourceUnavailable("version persistent identifier mismatch")
        number = v.get("versionNumber")
        minor = v.get("versionMinorNumber", 0)
        if type(number) is not int or type(minor) is not int:
            raise SourceUnavailable("invalid dataset version identifier")
        file_ids = _linked_file_ids(v)
        inventory.append({
            "version": f"{number}.{minor}",
            "release_date_utc": _release_date(v.get("releaseTime")),
            "file_id_membership": (
                "MEMBER" if TARGET_ID in file_ids else "NOT_MEMBER"
            ) if file_ids is not None else "NOT_EXPOSED",
        })
    if not inventory:
        raise SourceUnavailable("no published dataset versions exposed")
    if len({item["version"] for item in inventory}) != len(inventory):
        raise SourceUnavailable("duplicate publisher version identifier")

    dated = sorted(
        item["release_date_utc"]
        for item in inventory
        if item["file_id_membership"] == "MEMBER" and item["release_date_utc"]
    )
    earliest = dated[0] if dated else None
    period_end = "2022-12-31"
    if earliest is not None and earliest <= period_end:
        # A catalog timestamp alone does not prove no revisions or market yield
        # availability on any historical observation date.
        metadata_conclusion = "PRE_2023_VERSION_EXISTS_NOT_PIT_CERTIFICATION"
    elif earliest:
        metadata_conclusion = "LISTED_FILE_ID_FIRST_RELEASE_AFTER_2022_WINDOW"
    else:
        metadata_conclusion = "EXACT_FILE_RELEASE_DATE_UNRESOLVED"

    return {
        "dataset_doi": DOI,
        "original_file_id": TARGET_ID,
        "original_file_sha256": SOURCE_SHA,
        "original_bytes_verified": True,
        "version_inventory": sorted(inventory, key=lambda x: x["version"]),
        "earliest_exposed_release_of_file_id": earliest,
        "source_release_chronology": metadata_conclusion,
        "inspection_window": EARLIEST_MONTH + ".." + LATEST_MONTH,
        "observation_months_per_variant": EXPECTED_MONTH_COUNT,
        "at_observation_vintage_values_verified": False,
        "underlying_yield_vintage_linked": False,
        "dataset_version_to_other_erasmus_doi_mapped": False,
        "point_in_time_decision_eligible": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def main():
    raw = fetch(PUBLISHER + "/api/access/datafile/" + str(SOURCE_ID), 5_000_000)
    source_verified = len(raw) == SOURCE_BYTES and hashlib.sha256(raw).hexdigest() == SOURCE_SHA
    if not source_verified:
        raise SourceUnavailable("original official ODS size/SHA does not match pinned receipt")
    metadata = parse_api(fetch(OFFICIAL_METADATA, MAX_METADATA_BYTES))
    if not isinstance(metadata, dict):
        raise SourceUnavailable("publisher dataset metadata unexpectedly structured")
    if metadata.get("protocol") not in (None, "doi"):
        raise SourceUnavailable("publisher dataset protocol unexpected")
    versions = parse_api(fetch(VERSIONS_API, MAX_METADATA_BYTES))
    result = audit_release_timeline(versions, publisher_file_sha_verified=True)
    print("SWINKELS_PUBLISHER_VERSION_PIT_AUDIT=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except SourceUnavailable as exc:
        print("SWINKELS_PUBLISHER_VERSION_PIT_AUDIT=BLOCKED: " + str(exc))
        sys.exit(2)
