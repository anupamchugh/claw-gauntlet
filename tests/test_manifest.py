from dataclasses import FrozenInstanceError

import pytest

from claw_gauntlet.family import family_manifests, manifest_for
from claw_gauntlet.manifest import CapabilityManifest, parse_semver


def _manifest_payload():
    return {
        "name": "RRSClaw",
        "version": "0.1.0",
        "protocol_version": "1.0.0",
        "status": "planned",
        "kind": "intelligence",
        "capabilities": ["run.score"],
        "permissions": ["evidence:read"],
    }


def test_semver_and_manifest_round_trip():
    assert parse_semver("1.2.3") == (1, 2, 3)
    manifest = CapabilityManifest(
        name="RRSClaw",
        version="0.1.0",
        protocol_version="1.0.0",
        status="experimental",
        kind="intelligence",
        capabilities=("run.score",),
        permissions=("evidence:read",),
    )
    assert CapabilityManifest.from_dict(manifest.to_dict()) == manifest


@pytest.mark.parametrize("value", ["1", "1.2", "v1.2.3", "01.2.3", "1.02.3", "1.2.03", "1.2.3.4"])
def test_parse_semver_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="invalid semantic version"):
        parse_semver(value)


def test_manifest_is_immutable_and_rejects_invalid_status():
    manifest = CapabilityManifest(
        name="RRSClaw",
        version="0.1.0",
        protocol_version="1.0.0",
        status="planned",
        kind="intelligence",
        capabilities=("run.score",),
        permissions=("evidence:read",),
    )
    with pytest.raises(FrozenInstanceError):
        manifest.status = "stable"
    with pytest.raises(ValueError, match="invalid status"):
        CapabilityManifest(
            name="RRSClaw",
            version="0.1.0",
            protocol_version="1.0.0",
            status="available",
            kind="intelligence",
            capabilities=("run.score",),
            permissions=("evidence:read",),
        )


def test_manifest_copies_caller_owned_mutable_sequences():
    capabilities = ["run.score"]
    permissions = ["evidence:read"]
    manifest = CapabilityManifest(
        name="RRSClaw",
        version="0.1.0",
        protocol_version="1.0.0",
        status="planned",
        kind="intelligence",
        capabilities=capabilities,
        permissions=permissions,
    )

    capabilities.append("run.regression")
    permissions.clear()

    assert manifest.capabilities == ("run.score",)
    assert manifest.permissions == ("evidence:read",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", None),
        ("name", 7),
        ("name", ""),
        ("version", None),
        ("version", 7),
        ("version", ""),
        ("protocol_version", None),
        ("protocol_version", 7),
        ("protocol_version", ""),
        ("status", None),
        ("status", 7),
        ("status", ""),
        ("kind", None),
        ("kind", 7),
        ("kind", ""),
        ("capabilities", None),
        ("capabilities", 7),
        ("capabilities", ("run.score",)),
        ("capabilities", [None]),
        ("capabilities", [7]),
        ("capabilities", [""]),
        ("permissions", None),
        ("permissions", 7),
        ("permissions", ("evidence:read",)),
        ("permissions", [None]),
        ("permissions", [7]),
        ("permissions", [""]),
    ],
)
def test_manifest_from_dict_rejects_malformed_fields(field, value):
    payload = _manifest_payload()
    payload[field] = value

    with pytest.raises(ValueError, match=field):
        CapabilityManifest.from_dict(payload)


def test_family_contains_each_component_once_and_reports_real_status():
    manifests = family_manifests()
    names = [item.name for item in manifests]
    assert len(names) == len(set(names))
    assert {"RRSClaw", "DocsClaw", "BlogClaw", "TwitterClaw", "ForkClaw"} <= set(names)
    assert {item.status for item in manifests} == {"planned", "experimental"}
    assert {
        "StarClaw",
        "GHClaw",
        "ProjectClaw",
        "RRSClaw",
        "BlogClaw",
        "TwitterClaw",
        "EvidenceStore",
        "TaskLedgerAdapter",
        "AgentMailTransport",
    } == {item.name for item in manifests if item.status == "experimental"}
    assert {item.version for item in manifests} == {"0.1.0"}
    assert {item.protocol_version for item in manifests} == {"1.0.0"}
    assert manifest_for("RRSClaw").capabilities == ("run.score", "run.regression")
    assert manifest_for("rrsclaw") == manifest_for("RRSClaw")


def test_family_component_kinds_match_the_complete_catalog():
    assert {item.name: item.kind for item in family_manifests()} == {
        "StarClaw": "discovery",
        "GHClaw": "discovery",
        "HNClaw": "discovery",
        "RSSClaw": "discovery",
        "ProjectClaw": "intelligence",
        "TrustClaw": "intelligence",
        "RRSClaw": "intelligence",
        "DigestClaw": "intelligence",
        "ReleaseClaw": "delivery",
        "DocsClaw": "delivery",
        "BlogClaw": "delivery",
        "TwitterClaw": "delivery",
        "BlogAgent": "agent",
        "EvidenceStore": "infrastructure",
        "TaskLedgerAdapter": "infrastructure",
        "AgentMailTransport": "infrastructure",
        "SandboxRunner": "infrastructure",
        "ForkClaw": "discovery",
        "BirdClaw": "discovery",
        "PaperClaw": "discovery",
        "AppClaw": "discovery",
        "PeopleClaw": "intelligence",
        "SkillClaw": "intelligence",
        "CassMemoryAdapter": "infrastructure",
        "MCPServer": "infrastructure",
        "CredentialArbiter": "infrastructure",
        "Scheduler": "infrastructure",
        "Dashboard": "interface",
    }


def test_manifest_for_fails_closed_on_unknown_names():
    with pytest.raises(KeyError, match="unknown manifest: MissingClaw"):
        manifest_for("MissingClaw")
