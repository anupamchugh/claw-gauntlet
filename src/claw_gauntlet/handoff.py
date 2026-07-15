from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from claw_gauntlet.manifest import (
    _nonempty_string,
    _payload_string_list,
    _string_tuple,
    parse_semver,
)


_DEFAULT_PROTOCOL_VERSION = "1.0.0"
_SUPPORTED_PROTOCOL_MAJOR = 1
_SHA256 = re.compile(r"^sha256:([0-9a-fA-F]{64})$")
_EVIDENCE_REF = re.compile(r"^evidence://sha256/([0-9a-fA-F]{64})$")


def new_handoff_id() -> str:
    return uuid4().hex


def _uuid4_hex(value: Any, field: str) -> str:
    value = _nonempty_string(value, field)
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError(f"{field} must be a UUID4 hex identifier") from error
    if parsed.version != 4 or value != parsed.hex:
        raise ValueError(f"{field} must be a UUID4 hex identifier")
    return value


def _utc_timestamp(value: Any, field: str) -> str:
    value = _nonempty_string(value, field)
    if not value.endswith("Z"):
        raise ValueError(f"{field} must be a UTC ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{field} must be a UTC ISO-8601 timestamp") from error
    if parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError(f"{field} must be a UTC ISO-8601 timestamp")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _semantic_version(value: Any, field: str) -> str:
    value = _nonempty_string(value, field)
    try:
        parse_semver(value)
    except ValueError as error:
        raise ValueError(f"{field} has invalid semantic version: {value}") from error
    return value


def _protocol_version(value: Any) -> str:
    value = _semantic_version(value, "protocol_version")
    major = parse_semver(value)[0]
    if major != _SUPPORTED_PROTOCOL_MAJOR:
        raise ValueError(
            f"unsupported protocol major: expected {_SUPPORTED_PROTOCOL_MAJOR}, got {major}"
        )
    return value


def _sha256_value(value: Any, field: str) -> str:
    value = _nonempty_string(value, field)
    match = _SHA256.fullmatch(value)
    if match is None:
        raise ValueError(f"{field} must use sha256:<64-hex-digest> format")
    return f"sha256:{match.group(1).lower()}"


def _artifact_refs(
    value: Any,
    *,
    payload: bool = False,
    required: bool = True,
) -> tuple[str, ...]:
    if payload:
        items = _payload_string_list(value, "artifact_refs", required=required)
    else:
        items = _string_tuple(value, "artifact_refs", required=required)
    normalized = []
    for item in items:
        match = _EVIDENCE_REF.fullmatch(item)
        if match is None:
            raise ValueError(
                "artifact_refs must contain only evidence://sha256/<64-hex-digest> references"
            )
        normalized.append(f"evidence://sha256/{match.group(1).lower()}")
    return tuple(normalized)


def artifact_refs_checksum(artifact_refs: tuple[str, ...] | list[str]) -> str:
    """Hash the canonical compact JSON bytes of ordered evidence references."""
    normalized = _artifact_refs(artifact_refs)
    canonical = json.dumps(
        list(normalized),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(canonical).hexdigest()}"


def _provenance_urls(value: Any, *, payload: bool = False) -> tuple[str, ...]:
    if payload:
        items = _payload_string_list(value, "provenance")
    else:
        items = _string_tuple(value, "provenance")
    for item in items:
        parsed = urlparse(item)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("provenance must contain only HTTP(S) URLs")
    return items


@dataclass(frozen=True)
class HandoffEnvelope:
    handoff_id: str
    created_at: str
    protocol_version: str
    source: str
    destination: str
    artifact_refs: tuple[str, ...]
    requested_action: str
    summary: str
    provenance: tuple[str, ...]
    checksum: str
    approval_required: bool

    def __post_init__(self) -> None:
        _uuid4_hex(self.handoff_id, "handoff_id")
        _utc_timestamp(self.created_at, "created_at")
        _protocol_version(self.protocol_version)
        _nonempty_string(self.source, "source")
        _nonempty_string(self.destination, "destination")
        object.__setattr__(
            self,
            "artifact_refs",
            _artifact_refs(self.artifact_refs),
        )
        _nonempty_string(self.requested_action, "requested_action")
        _nonempty_string(self.summary, "summary")
        object.__setattr__(self, "provenance", _provenance_urls(self.provenance))
        normalized_checksum = _sha256_value(self.checksum, "checksum")
        expected_checksum = artifact_refs_checksum(self.artifact_refs)
        if normalized_checksum != expected_checksum:
            raise ValueError("checksum does not match canonical ordered artifact_refs JSON")
        object.__setattr__(self, "checksum", normalized_checksum)
        if type(self.approval_required) is not bool:
            raise ValueError("approval_required must be a boolean")

    @classmethod
    def create(
        cls,
        *,
        source: str,
        destination: str,
        artifact_refs: tuple[str, ...] | list[str],
        requested_action: str,
        summary: str,
        checksum: str,
        approval_required: bool,
        provenance: tuple[str, ...] | list[str] = (),
        protocol_version: str = _DEFAULT_PROTOCOL_VERSION,
    ) -> "HandoffEnvelope":
        return cls(
            handoff_id=new_handoff_id(),
            created_at=_utc_now(),
            protocol_version=protocol_version,
            source=source,
            destination=destination,
            artifact_refs=artifact_refs,
            requested_action=requested_action,
            summary=summary,
            provenance=provenance,
            checksum=checksum,
            approval_required=approval_required,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "created_at": self.created_at,
            "protocol_version": self.protocol_version,
            "from": self.source,
            "to": self.destination,
            "artifact_refs": list(self.artifact_refs),
            "requested_action": self.requested_action,
            "summary": self.summary,
            "provenance": list(self.provenance),
            "checksum": self.checksum,
            "approval_required": self.approval_required,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "HandoffEnvelope":
        if type(payload) is not dict:
            raise ValueError("handoff payload must be a dictionary")
        return cls(
            handoff_id=_uuid4_hex(payload["handoff_id"], "handoff_id"),
            created_at=_utc_timestamp(payload["created_at"], "created_at"),
            protocol_version=_protocol_version(payload["protocol_version"]),
            source=_nonempty_string(payload["from"], "source"),
            destination=_nonempty_string(payload["to"], "destination"),
            artifact_refs=_artifact_refs(payload["artifact_refs"], payload=True),
            requested_action=_nonempty_string(payload["requested_action"], "requested_action"),
            summary=_nonempty_string(payload["summary"], "summary"),
            provenance=_provenance_urls(payload["provenance"], payload=True),
            checksum=_sha256_value(payload["checksum"], "checksum"),
            approval_required=_payload_bool(payload["approval_required"], "approval_required"),
        )

    def require_protocol_major(self, expected: int) -> None:
        if type(expected) is not int or expected < 0:
            raise ValueError("expected protocol major must be a nonnegative integer")
        actual = parse_semver(self.protocol_version)[0]
        if actual != expected:
            raise ValueError(f"protocol major mismatch: expected {expected}, got {actual}")


def _payload_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field} must be a boolean")
    return value
