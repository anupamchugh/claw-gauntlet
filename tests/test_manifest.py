from dataclasses import FrozenInstanceError

import pytest

from claw_gauntlet.family import family_manifests, manifest_for
from claw_gauntlet.manifest import CapabilityManifest, parse_semver


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


def test_family_contains_each_component_once_and_none_are_available():
    manifests = family_manifests()
    names = [item.name for item in manifests]
    assert len(names) == len(set(names))
    assert {"RRSClaw", "DocsClaw", "BlogClaw", "TwitterClaw", "ForkClaw"} <= set(names)
    assert {item.status for item in manifests} == {"planned"}
    assert {item.version for item in manifests} == {"0.1.0"}
    assert {item.protocol_version for item in manifests} == {"1.0.0"}
    assert manifest_for("RRSClaw").capabilities == ("run.score", "run.regression")
    assert manifest_for("rrsclaw") == manifest_for("RRSClaw")


def test_manifest_for_fails_closed_on_unknown_names():
    with pytest.raises(KeyError, match="unknown manifest: MissingClaw"):
        manifest_for("MissingClaw")
