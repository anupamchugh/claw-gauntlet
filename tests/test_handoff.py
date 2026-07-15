from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import UUID

import pytest

from claw_gauntlet.handoff import HandoffEnvelope, new_handoff_id


def _handoff_payload():
    return {
        "handoff_id": "123e4567e89b42d3a456426614174000",
        "created_at": "2026-07-16T12:00:00Z",
        "protocol_version": "1.0.0",
        "from": "GHClaw",
        "to": "DocsClaw",
        "artifact_refs": ["evidence://sha256/abc"],
        "requested_action": "update-release-docs",
        "summary": "Document one verified change.",
        "provenance": ["https://github.com/example/project/releases/tag/v1.0.0"],
        "checksum": "sha256:abc",
        "approval_required": False,
    }


def test_handoff_round_trip_and_major_version_guard():
    handoff = HandoffEnvelope.create(
        source="GHClaw",
        destination="DocsClaw",
        artifact_refs=("evidence://sha256/abc",),
        requested_action="update-release-docs",
        summary="Document one verified change.",
        provenance=("https://github.com/example/project/releases/tag/v1.0.0",),
        checksum="sha256:abc",
        approval_required=False,
    )

    assert HandoffEnvelope.from_dict(handoff.to_dict()) == handoff
    assert handoff.to_dict()["from"] == "GHClaw"
    assert handoff.to_dict()["to"] == "DocsClaw"
    handoff.require_protocol_major(1)


def test_handoff_create_uses_uuid4_utc_timestamp_and_compatibility_defaults():
    handoff = HandoffEnvelope.create(
        source="GHClaw",
        destination="DocsClaw",
        artifact_refs=("evidence://sha256/abc",),
        requested_action="update-release-docs",
        summary="Document one verified change.",
        checksum="sha256:abc",
        approval_required=False,
    )

    assert UUID(handoff.handoff_id).version == 4
    assert len(new_handoff_id()) == 32
    assert handoff.created_at.endswith("Z")
    assert datetime.fromisoformat(handoff.created_at.replace("Z", "+00:00")).utcoffset().total_seconds() == 0
    assert handoff.protocol_version == "1.0.0"
    assert handoff.provenance == ()


def test_handoff_is_immutable_and_copies_caller_owned_sequences():
    artifact_refs = ["evidence://sha256/abc"]
    provenance = ["https://github.com/example/project/releases/tag/v1.0.0"]
    handoff = HandoffEnvelope.create(
        source="GHClaw",
        destination="DocsClaw",
        artifact_refs=artifact_refs,
        requested_action="update-release-docs",
        summary="Document one verified change.",
        provenance=provenance,
        checksum="sha256:abc",
        approval_required=False,
    )

    artifact_refs.clear()
    provenance.clear()

    assert handoff.artifact_refs == ("evidence://sha256/abc",)
    assert handoff.provenance == ("https://github.com/example/project/releases/tag/v1.0.0",)
    with pytest.raises(FrozenInstanceError):
        handoff.summary = "changed"


def test_handoff_rejects_missing_artifacts_and_protocol_major_mismatch():
    with pytest.raises(ValueError, match="artifact_refs"):
        HandoffEnvelope.create(
            source="GHClaw",
            destination="DocsClaw",
            artifact_refs=(),
            requested_action="update-release-docs",
            summary="Document one verified change.",
            checksum="sha256:abc",
            approval_required=False,
        )

    handoff = HandoffEnvelope.from_dict(_handoff_payload())
    with pytest.raises(ValueError, match="protocol major"):
        handoff.require_protocol_major(2)


@pytest.mark.parametrize("checksum", ["abc", "sha256:"])
def test_handoff_rejects_invalid_checksums(checksum):
    payload = _handoff_payload()
    payload["checksum"] = checksum

    with pytest.raises(ValueError, match="checksum"):
        HandoffEnvelope.from_dict(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("handoff_id", None),
        ("created_at", 7),
        ("protocol_version", "v1.0.0"),
        ("from", ""),
        ("to", None),
        ("artifact_refs", ("evidence://sha256/abc",)),
        ("artifact_refs", []),
        ("artifact_refs", [7]),
        ("requested_action", ""),
        ("summary", None),
        ("provenance", ("https://example.com",)),
        ("provenance", None),
        ("provenance", [7]),
        ("provenance", ["release-tag-v1.0.0"]),
        ("checksum", ""),
        ("approval_required", 0),
    ],
)
def test_handoff_from_dict_rejects_malformed_fields(field, value):
    payload = _handoff_payload()
    payload[field] = value

    error_field = {"from": "source", "to": "destination"}.get(field, field)
    with pytest.raises(ValueError, match=error_field):
        HandoffEnvelope.from_dict(payload)
