from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ClawRegistration:
    name: str
    kind: str
    status: str
    permission: str


_AVAILABLE = {
    "StarClaw",
    "GHClaw",
    "ProjectClaw",
    "TrustClaw",
    "DigestClaw",
}

_DISCOVERY = (
    "StarClaw",
    "GHClaw",
    "ReleaseClaw",
    "HNClaw",
    "BirdClaw",
    "RSSClaw",
    "PaperClaw",
    "AppClaw",
)

_INTELLIGENCE = (
    "PeopleClaw",
    "SkillClaw",
    "TrustClaw",
    "ProjectClaw",
    "DigestClaw",
)

_INFRASTRUCTURE = (
    "CassMemoryAdapter",
    "AgentMailTransport",
    "TaskLedgerAdapter",
    "MCPServer",
    "SandboxRunner",
)


def family_payload() -> dict[str, list[dict[str, str]]]:
    registrations: list[ClawRegistration] = []
    for kind, names in (
        ("discovery", _DISCOVERY),
        ("intelligence", _INTELLIGENCE),
        ("infrastructure", _INFRASTRUCTURE),
    ):
        for name in names:
            registrations.append(
                ClawRegistration(
                    name=name,
                    kind=kind,
                    status="available" if name in _AVAILABLE else "planned",
                    permission="read-only" if kind != "infrastructure" else "disabled",
                )
            )
    return {"claws": [asdict(item) for item in registrations]}
