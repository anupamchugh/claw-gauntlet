from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from uuid import UUID

import pytest

from claw_gauntlet import handoff as handoff_module
from claw_gauntlet.handoff import HandoffEnvelope, new_handoff_id


ARTIFACT_DIGEST = "c7c5c1d70c5dec4416ab6158afd0b223ef40c29b1dc1f97ed9428b94d4cadb1c"
ARTIFACT_REF = f"evidence://sha256/{ARTIFACT_DIGEST}"
ARTIFACT_REFS_CHECKSUM = "b8699645b752c44ac547cd72d0d326f0dae7d49088793a39baf1e54897e1fa7c"
CHECKSUM = f"sha256:{ARTIFACT_REFS_CHECKSUM}"


def _handoff_payload():
    return {
        "handoff_id": "123e4567e89b42d3a456426614174000",
        "created_at": "2026-07-16T12:00:00Z",
        "protocol_version": "1.0.0",
        "from": "GHClaw",
        "to": "DocsClaw",
        "artifact_refs": [ARTIFACT_REF],
        "requested_action": "update-release-docs",
        "summary": "Document one verified change.",
        "provenance": ["https://github.com/example/project/releases/tag/v1.0.0"],
        "checksum": CHECKSUM,
        "approval_required": False,
    }


def test_handoff_round_trip_and_major_version_guard():
    handoff = HandoffEnvelope.create(
        source="GHClaw",
        destination="DocsClaw",
        artifact_refs=(ARTIFACT_REF,),
        requested_action="update-release-docs",
        summary="Document one verified change.",
        provenance=("https://github.com/example/project/releases/tag/v1.0.0",),
        checksum=CHECKSUM,
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
        artifact_refs=(ARTIFACT_REF,),
        requested_action="update-release-docs",
        summary="Document one verified change.",
        checksum=CHECKSUM,
        approval_required=False,
    )

    assert UUID(handoff.handoff_id).version == 4
    assert len(new_handoff_id()) == 32
    assert handoff.created_at.endswith("Z")
    assert datetime.fromisoformat(handoff.created_at.replace("Z", "+00:00")).utcoffset().total_seconds() == 0
    assert handoff.protocol_version == "1.0.0"
    assert handoff.provenance == ()


def test_handoff_is_immutable_and_copies_caller_owned_sequences():
    artifact_refs = [ARTIFACT_REF]
    provenance = ["https://github.com/example/project/releases/tag/v1.0.0"]
    handoff = HandoffEnvelope.create(
        source="GHClaw",
        destination="DocsClaw",
        artifact_refs=artifact_refs,
        requested_action="update-release-docs",
        summary="Document one verified change.",
        provenance=provenance,
        checksum=CHECKSUM,
        approval_required=False,
    )

    artifact_refs.clear()
    provenance.clear()

    assert handoff.artifact_refs == (ARTIFACT_REF,)
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
            checksum=CHECKSUM,
            approval_required=False,
        )

    handoff = HandoffEnvelope.from_dict(_handoff_payload())
    with pytest.raises(ValueError, match="protocol major"):
        handoff.require_protocol_major(2)


@pytest.mark.parametrize("checksum", ["abc", "sha256:", "sha256:" + "0" * 63])
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
        ("artifact_refs", (ARTIFACT_REF,)),
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


def test_handoff_checksum_is_sha256_of_canonical_ordered_artifact_refs_json():
    assert handoff_module.artifact_refs_checksum((ARTIFACT_REF,)) == CHECKSUM


def test_handoff_rejects_unsupported_protocol_major_on_construction_and_parsing():
    handoff = HandoffEnvelope.from_dict(_handoff_payload())
    with pytest.raises(ValueError, match="unsupported protocol major"):
        replace(handoff, protocol_version="2.0.0")

    payload = _handoff_payload()
    payload["protocol_version"] = "2.0.0"
    with pytest.raises(ValueError, match="unsupported protocol major"):
        HandoffEnvelope.from_dict(payload)


@pytest.mark.parametrize(
    "artifact_ref",
    [
        "evidence://sha256/" + "0" * 63,
        "evidence://sha1/" + ARTIFACT_DIGEST,
        "https://example.com/artifact",
    ],
)
def test_handoff_rejects_malformed_evidence_artifact_refs(artifact_ref):
    payload = _handoff_payload()
    payload["artifact_refs"] = [artifact_ref]

    with pytest.raises(ValueError, match="artifact_refs"):
        HandoffEnvelope.from_dict(payload)


def test_handoff_rejects_checksum_that_does_not_match_artifact_refs():
    payload = _handoff_payload()
    payload["checksum"] = "sha256:" + "0" * 64

    with pytest.raises(ValueError, match="checksum"):
        HandoffEnvelope.from_dict(payload)


def test_handoff_normalizes_case_insensitive_sha256_hex_to_lowercase():
    payload = _handoff_payload()
    payload["artifact_refs"] = [ARTIFACT_REF.upper().replace("EVIDENCE://SHA256/", "evidence://sha256/")]
    payload["checksum"] = CHECKSUM.upper().replace("SHA256:", "sha256:")

    handoff = HandoffEnvelope.from_dict(payload)

    assert handoff.artifact_refs == (ARTIFACT_REF,)
    assert handoff.checksum == CHECKSUM


@pytest.mark.parametrize(
    "provenance",
    [
        "https://user@example.com/release",
        "https://user:secret@example.com/release",
    ],
)
def test_handoff_rejects_provenance_urls_with_userinfo_on_construction_and_parsing(provenance):
    with pytest.raises(ValueError, match="provenance"):
        HandoffEnvelope.create(
            source="GHClaw",
            destination="DocsClaw",
            artifact_refs=(ARTIFACT_REF,),
            requested_action="update-release-docs",
            summary="Document one verified change.",
            provenance=(provenance,),
            checksum=CHECKSUM,
            approval_required=False,
        )

    payload = _handoff_payload()
    payload["provenance"] = [provenance]
    with pytest.raises(ValueError, match="provenance"):
        HandoffEnvelope.from_dict(payload)
