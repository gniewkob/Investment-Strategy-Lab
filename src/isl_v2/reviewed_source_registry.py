"""Reviewed-source registry and local artifact integrity checks for ISL research.

A trusted publisher pin must be curated separately from caller-provided data.
There are currently NO authenticated PLN total-return sources. The committed
registry deliberately contains no real approved entries. Even if local artifact
bytes match a test pin, this module never authorizes model use, historical PIT,
a trading signal, or any financial operation.

No HTTP calls, DB writes, runtime secrets, auto-discovery, or dynamic imports.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from types import MappingProxyType
from urllib.parse import urlsplit
import re

from .provenance import utc
from .total_return_evidence_preflight import EXPECTED_INSTRUMENTS

_SHA = re.compile(r"^[a-f0-9]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{2,100}$")
MAX_ARTIFACT_BYTES = 1_000_000

# Only pins reviewed and committed under separately controlled source
# governance may go here. No live publisher pins have been reviewed yet.
REVIEWED_SOURCE_PINS = MappingProxyType({})


class SourceRegistryBlocked(ValueError):
    """Fail-closed official-series, content, or availability evidence check."""


@dataclass(frozen=True)
class ReviewedSourcePin:
    """Immutable publisher/source binding; not an investment authorization."""

    instrument_code: str
    source_code: str
    official_series_id: str
    canonical_url: str
    license_url: str
    source_version: str
    source_sha256: str
    first_public_at: str
    currency: str = "PLN"
    value_concept: str = "TOTAL_RETURN_INDEX"
    return_basis: str = "GROSS_TOTAL_RETURN"
    interval_code: str = "1mo"


def registry_inventory() -> dict:
    """List independently unprovisioned research assets, not a trust claim."""
    return {
        "registry_version": "research_source_pins_v01",
        "assets": [
            {
                "instrument_code": instrument,
                "source_state": "PIN_REVIEW_REQUIRED" if instrument not in REVIEWED_SOURCE_PINS
                else "PIN_PRESENT_NOT_MODEL_ADMITTED",
            }
            for instrument in EXPECTED_INSTRUMENTS
        ],
        "reviewed_source_pin_count": len(REVIEWED_SOURCE_PINS),
        "historic_publication_evidence_verified": False,
        "model_admission_granted": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def _strict_https(url: object) -> bool:
    if not isinstance(url, str) or len(url) > 512:
        return False
    try:
        p = urlsplit(url)
        port = p.port
    except ValueError:
        return False
    if (p.scheme != "https" or p.hostname is None or p.username is not None
            or p.password is not None or port not in (None, 443)
            or p.query or p.fragment or not p.path.startswith("/")):
        return False
    expected_authority = p.hostname if port is None else p.hostname + ":443"
    return p.netloc == expected_authority


def _iso_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise SourceRegistryBlocked("TIMESTAMP_INVALID")
    try:
        return utc(value)
    except ValueError as exc:
        raise SourceRegistryBlocked("TIMESTAMP_INVALID") from exc


def _verify_with_reviewed_pin(
    pin: ReviewedSourcePin, claimed: dict, artifact_bytes: bytes,
    *, captured_at: str, decision_asof: str,
) -> dict:
    """Internal, synthetic-testable integrity gate. NOT publisher authentication.

    A supplied byte blob can match the exact checksum of a separately curated
    pin. Only a separately trusted downloader can attest the origin/capture
    time; this pure function cannot establish either.
    """
    if not isinstance(pin, ReviewedSourcePin) or not isinstance(claimed, dict):
        raise SourceRegistryBlocked("PIN_OR_CLAIM_INVALID")
    if pin.instrument_code not in EXPECTED_INSTRUMENTS:
        raise SourceRegistryBlocked("PIN_UNKNOWN_INSTRUMENT")
    for name in ("source_code", "official_series_id", "source_version"):
        value = getattr(pin, name)
        if not isinstance(value, str) or not _TOKEN.fullmatch(value):
            raise SourceRegistryBlocked("PIN_IDENTIFIER_INVALID")
    if not _strict_https(pin.canonical_url) or not _strict_https(pin.license_url):
        raise SourceRegistryBlocked("PIN_URL_INVALID")
    if not isinstance(pin.source_sha256, str) or not _SHA.fullmatch(pin.source_sha256):
        raise SourceRegistryBlocked("PIN_DIGEST_INVALID")
    if (pin.currency != "PLN" or pin.value_concept != "TOTAL_RETURN_INDEX"
            or pin.return_basis not in ("GROSS_TOTAL_RETURN", "NET_TOTAL_RETURN")
            or pin.interval_code != "1mo"):
        raise SourceRegistryBlocked("PIN_PRICE_BASIS_INVALID")

    for field in (
        "instrument_code", "source_code", "official_series_id",
        "source_version", "canonical_url", "license_url", "source_sha256",
        "currency", "value_concept", "return_basis", "interval_code",
        "first_public_at",
    ):
        if field not in claimed or claimed[field] != getattr(pin, field):
            raise SourceRegistryBlocked("SOURCE_BINDING_MISMATCH")

    if not isinstance(artifact_bytes, bytes) or not 0 < len(artifact_bytes) <= MAX_ARTIFACT_BYTES:
        raise SourceRegistryBlocked("ARTIFACT_BYTES_INVALID")
    content_digest = sha256(artifact_bytes).hexdigest()
    if content_digest != pin.source_sha256:
        raise SourceRegistryBlocked("ARTIFACT_DIGEST_MISMATCH")

    publication = _iso_utc(pin.first_public_at)
    capture = _iso_utc(captured_at)
    cutoff = _iso_utc(decision_asof)
    if publication > cutoff:
        raise SourceRegistryBlocked("PUBLICATION_AFTER_DECISION")
    if capture < publication:
        raise SourceRegistryBlocked("CAPTURE_BEFORE_PUBLICATION")
    if capture > cutoff:
        raise SourceRegistryBlocked("RETROSPECTIVE_CAPTURE_AFTER_DECISION")

    return {
        "instrument_code": pin.instrument_code,
        "source_code": pin.source_code,
        "official_series_id": pin.official_series_id,
        "artifact_sha256_matches_reviewed_pin": True,
        "source_metadata_matches_reviewed_pin": True,
        "artifact_bytes_count": len(artifact_bytes),
        "source_network_origin_attested": False,
        "capture_clock_independently_attested": False,
        "historical_pit_certified": False,
        "model_admission_granted": False,
        "qualified_model_series": [],
        "model_state": "HOLD_CASH",
        "financial_operations": 0,
    }


def verify_registry_candidate(
    claimed: dict, artifact_bytes: bytes, *, captured_at: str, decision_asof: str
) -> dict:
    """Public entrypoint: fail closed while official reviewed pin list is empty."""
    if not isinstance(claimed, dict) or claimed.get("instrument_code") not in EXPECTED_INSTRUMENTS:
        raise SourceRegistryBlocked("UNKNOWN_INSTRUMENT")
    pin = REVIEWED_SOURCE_PINS.get(claimed["instrument_code"])
    if pin is None:
        raise SourceRegistryBlocked("NO_REVIEWED_SOURCE_PIN")
    return _verify_with_reviewed_pin(
        pin, claimed, artifact_bytes, captured_at=captured_at, decision_asof=decision_asof
    )
