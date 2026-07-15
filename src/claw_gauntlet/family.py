from typing import Any

from claw_gauntlet.manifest import CapabilityManifest


_VERSION = "0.1.0"
_PROTOCOL_VERSION = "1.0.0"
_STATUS = "planned"


def _manifest(
    name: str,
    kind: str,
    capabilities: tuple[str, ...],
    permissions: tuple[str, ...] = ("public:evidence:read",),
    *,
    status: str = _STATUS,
) -> CapabilityManifest:
    return CapabilityManifest(
        name=name,
        version=_VERSION,
        protocol_version=_PROTOCOL_VERSION,
        status=status,
        kind=kind,
        capabilities=capabilities,
        permissions=permissions,
    )


_MANIFESTS = (
    _manifest("StarClaw", "discovery", ("github.stars.watch",), status="experimental"),
    _manifest("GHClaw", "discovery", ("github.repo.collect",), status="experimental"),
    _manifest("HNClaw", "discovery", ("hn.research",)),
    _manifest("RSSClaw", "discovery", ("feed.collect",)),
    _manifest("ProjectClaw", "intelligence", ("evidence.evaluate",), status="experimental"),
    _manifest("TrustClaw", "intelligence", ("provenance.verify",)),
    _manifest(
        "RRSClaw",
        "intelligence",
        ("run.score", "run.regression"),
        status="experimental",
    ),
    _manifest("DigestClaw", "intelligence", ("digest.build",)),
    _manifest("ReleaseClaw", "delivery", ("release.verify",)),
    _manifest("DocsClaw", "delivery", ("docs.verify",)),
    _manifest("BlogClaw", "delivery", ("blog.draft",)),
    _manifest("TwitterClaw", "delivery", ("publication.bundle",)),
    _manifest("BlogAgent", "agent", ("blog.conventions.apply",)),
    _manifest(
        "EvidenceStore",
        "infrastructure",
        ("evidence.store",),
        ("evidence:read", "evidence:write"),
        status="experimental",
    ),
    _manifest(
        "TaskLedgerAdapter",
        "infrastructure",
        ("task.map",),
        ("task:read", "task:write"),
        status="experimental",
    ),
    _manifest(
        "AgentMailTransport",
        "infrastructure",
        ("handoff.notify",),
        ("handoff:send",),
        status="experimental",
    ),
    _manifest("SandboxRunner", "infrastructure", ("check.run",), ("sandbox:execute",)),
    _manifest("ForkClaw", "discovery", ("github.forks.map",)),
    _manifest("BirdClaw", "discovery", ("public.posts.collect",)),
    _manifest("PaperClaw", "discovery", ("paper.collect",)),
    _manifest("AppClaw", "discovery", ("app.collect",)),
    _manifest("PeopleClaw", "intelligence", ("people.activity.collect",)),
    _manifest("SkillClaw", "intelligence", ("skill.inventory",)),
    _manifest("CassMemoryAdapter", "infrastructure", ("memory.recover",), ("memory:read",)),
    _manifest("MCPServer", "infrastructure", ("manifest.expose",), ("manifest:read",)),
    _manifest(
        "CredentialArbiter",
        "infrastructure",
        ("credential.approve",),
        ("credential:approve",),
    ),
    _manifest("Scheduler", "infrastructure", ("freshness.schedule",), ("schedule:write",)),
    _manifest("Dashboard", "interface", ("status.view",)),
)


def family_manifests() -> tuple[CapabilityManifest, ...]:
    return _MANIFESTS


def manifest_for(name: str) -> CapabilityManifest:
    normalized_name = name.casefold()
    for manifest in _MANIFESTS:
        if manifest.name.casefold() == normalized_name:
            return manifest
    raise KeyError(f"unknown manifest: {name}")


def family_payload() -> dict[str, list[dict[str, Any]]]:
    return {"claws": [manifest.to_dict() for manifest in family_manifests()]}
