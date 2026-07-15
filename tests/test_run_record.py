from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import UUID

import pytest

from claw_gauntlet.run_record import RunRecord, new_run_id


def _run_payload():
    return {
        "run_id": "123e4567e89b42d3a456426614174000",
        "created_at": "2026-07-16T12:00:00Z",
        "protocol_version": "1.0.0",
        "claw_name": "GHClaw",
        "claw_version": "0.1.0",
        "input_hash": "sha256:input",
        "artifact_refs": ["evidence://sha256/abc"],
        "outcome": "success",
        "duration_ms": 25,
        "retries": 0,
        "approvals_required": 0,
        "approvals_granted": 0,
        "permission_violations": 0,
        "human_corrections": 0,
    }


def test_run_record_round_trip():
    record = RunRecord.create(
        claw_name="GHClaw",
        claw_version="0.1.0",
        input_hash="sha256:input",
        artifact_refs=("evidence://sha256/abc",),
        outcome="success",
        duration_ms=25,
        retries=0,
        approvals_required=0,
        approvals_granted=0,
        permission_violations=0,
        human_corrections=0,
    )

    assert RunRecord.from_dict(record.to_dict()) == record


def test_run_record_create_uses_uuid4_utc_timestamp_and_protocol_default():
    record = RunRecord.create(
        claw_name="GHClaw",
        claw_version="0.1.0",
        input_hash="sha256:input",
        artifact_refs=(),
        outcome="partial",
        duration_ms=0,
        retries=0,
        approvals_required=1,
        approvals_granted=0,
        permission_violations=0,
        human_corrections=0,
    )

    assert UUID(record.run_id).version == 4
    assert len(new_run_id()) == 32
    assert record.created_at.endswith("Z")
    assert datetime.fromisoformat(record.created_at.replace("Z", "+00:00")).utcoffset().total_seconds() == 0
    assert record.protocol_version == "1.0.0"


@pytest.mark.parametrize("outcome", ["success", "partial", "failure"])
def test_run_record_accepts_documented_outcomes(outcome):
    payload = _run_payload()
    payload["outcome"] = outcome
    assert RunRecord.from_dict(payload).outcome == outcome


def test_run_record_is_immutable_and_copies_caller_owned_artifacts():
    artifact_refs = ["evidence://sha256/abc"]
    record = RunRecord.create(
        claw_name="GHClaw",
        claw_version="0.1.0",
        input_hash="sha256:input",
        artifact_refs=artifact_refs,
        outcome="success",
        duration_ms=25,
        retries=0,
        approvals_required=0,
        approvals_granted=0,
        permission_violations=0,
        human_corrections=0,
    )
    artifact_refs.clear()

    assert record.artifact_refs == ("evidence://sha256/abc",)
    with pytest.raises(FrozenInstanceError):
        record.outcome = "failure"


@pytest.mark.parametrize("claw_version", ["1", "v1.2.3", "01.2.3"])
def test_run_record_rejects_invalid_semantic_versions(claw_version):
    payload = _run_payload()
    payload["claw_version"] = claw_version

    with pytest.raises(ValueError, match="invalid semantic version"):
        RunRecord.from_dict(payload)


@pytest.mark.parametrize(
    "field",
    [
        "duration_ms",
        "retries",
        "approvals_required",
        "approvals_granted",
        "permission_violations",
        "human_corrections",
    ],
)
def test_run_record_rejects_negative_measurements(field):
    payload = _run_payload()
    payload[field] = -1

    with pytest.raises(ValueError, match=field):
        RunRecord.from_dict(payload)


def test_run_record_rejects_invalid_outcome():
    payload = _run_payload()
    payload["outcome"] = "cancelled"

    with pytest.raises(ValueError, match="outcome"):
        RunRecord.from_dict(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_id", None),
        ("created_at", 7),
        ("protocol_version", "v1.0.0"),
        ("claw_name", ""),
        ("claw_version", 7),
        ("input_hash", None),
        ("artifact_refs", ("evidence://sha256/abc",)),
        ("artifact_refs", [7]),
        ("outcome", None),
        ("duration_ms", True),
        ("retries", 1.5),
        ("approvals_required", "0"),
        ("approvals_granted", None),
        ("permission_violations", False),
        ("human_corrections", 1.5),
    ],
)
def test_run_record_from_dict_rejects_malformed_fields(field, value):
    payload = _run_payload()
    payload[field] = value

    with pytest.raises(ValueError, match=field):
        RunRecord.from_dict(payload)
