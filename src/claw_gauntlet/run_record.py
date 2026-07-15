from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from claw_gauntlet.manifest import (
    _nonempty_string,
    _payload_string_list,
    _string_tuple,
    parse_semver,
)


_DEFAULT_PROTOCOL_VERSION = "1.0.0"
_OUTCOMES = {"success", "partial", "failure"}


def new_run_id() -> str:
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


def _nonnegative_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    created_at: str
    protocol_version: str
    claw_name: str
    claw_version: str
    input_hash: str
    artifact_refs: tuple[str, ...]
    outcome: str
    duration_ms: int
    retries: int
    approvals_required: int
    approvals_granted: int
    permission_violations: int
    human_corrections: int

    def __post_init__(self) -> None:
        _uuid4_hex(self.run_id, "run_id")
        _utc_timestamp(self.created_at, "created_at")
        _semantic_version(self.protocol_version, "protocol_version")
        _nonempty_string(self.claw_name, "claw_name")
        _semantic_version(self.claw_version, "claw_version")
        _nonempty_string(self.input_hash, "input_hash")
        object.__setattr__(
            self,
            "artifact_refs",
            _string_tuple(self.artifact_refs, "artifact_refs"),
        )
        _nonempty_string(self.outcome, "outcome")
        if self.outcome not in _OUTCOMES:
            raise ValueError(f"invalid outcome: {self.outcome}")
        for field in (
            "duration_ms",
            "retries",
            "approvals_required",
            "approvals_granted",
            "permission_violations",
            "human_corrections",
        ):
            _nonnegative_int(getattr(self, field), field)

    @classmethod
    def create(
        cls,
        *,
        claw_name: str,
        claw_version: str,
        input_hash: str,
        artifact_refs: tuple[str, ...] | list[str],
        outcome: str,
        duration_ms: int,
        retries: int,
        approvals_required: int,
        approvals_granted: int,
        permission_violations: int,
        human_corrections: int,
        protocol_version: str = _DEFAULT_PROTOCOL_VERSION,
    ) -> "RunRecord":
        return cls(
            run_id=new_run_id(),
            created_at=_utc_now(),
            protocol_version=protocol_version,
            claw_name=claw_name,
            claw_version=claw_version,
            input_hash=input_hash,
            artifact_refs=artifact_refs,
            outcome=outcome,
            duration_ms=duration_ms,
            retries=retries,
            approvals_required=approvals_required,
            approvals_granted=approvals_granted,
            permission_violations=permission_violations,
            human_corrections=human_corrections,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "protocol_version": self.protocol_version,
            "claw_name": self.claw_name,
            "claw_version": self.claw_version,
            "input_hash": self.input_hash,
            "artifact_refs": list(self.artifact_refs),
            "outcome": self.outcome,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
            "approvals_required": self.approvals_required,
            "approvals_granted": self.approvals_granted,
            "permission_violations": self.permission_violations,
            "human_corrections": self.human_corrections,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RunRecord":
        if type(payload) is not dict:
            raise ValueError("run record payload must be a dictionary")
        return cls(
            run_id=_uuid4_hex(payload["run_id"], "run_id"),
            created_at=_utc_timestamp(payload["created_at"], "created_at"),
            protocol_version=_semantic_version(payload["protocol_version"], "protocol_version"),
            claw_name=_nonempty_string(payload["claw_name"], "claw_name"),
            claw_version=_semantic_version(payload["claw_version"], "claw_version"),
            input_hash=_nonempty_string(payload["input_hash"], "input_hash"),
            artifact_refs=_payload_string_list(payload["artifact_refs"], "artifact_refs"),
            outcome=_nonempty_string(payload["outcome"], "outcome"),
            duration_ms=_nonnegative_int(payload["duration_ms"], "duration_ms"),
            retries=_nonnegative_int(payload["retries"], "retries"),
            approvals_required=_nonnegative_int(
                payload["approvals_required"], "approvals_required"
            ),
            approvals_granted=_nonnegative_int(
                payload["approvals_granted"], "approvals_granted"
            ),
            permission_violations=_nonnegative_int(
                payload["permission_violations"], "permission_violations"
            ),
            human_corrections=_nonnegative_int(
                payload["human_corrections"], "human_corrections"
            ),
        )
