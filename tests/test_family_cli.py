import json

import pytest

from claw_gauntlet.cli import main


def test_family_json_lists_the_complete_planned_catalog(capsys):
    assert main(["family", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    by_name = {item["name"]: item for item in payload["claws"]}

    assert len(payload["claws"]) == 29
    assert set(by_name) == {
        "StarClaw",
        "GHClaw",
        "HNClaw",
        "RSSClaw",
        "ProjectClaw",
        "TrustClaw",
        "RRSClaw",
        "DigestClaw",
        "ReleaseClaw",
        "DocsClaw",
        "BlogClaw",
        "TwitterClaw",
        "BlogAgent",
        "EvidenceStore",
        "TaskLedgerAdapter",
        "AgentMailTransport",
        "SandboxRunner",
        "ForkClaw",
        "BirdClaw",
        "PaperClaw",
        "AppClaw",
        "PeopleClaw",
        "SkillClaw",
        "CassMemoryAdapter",
        "MCPServer",
        "CredentialArbiter",
        "Scheduler",
        "Dashboard",
        "SponsorClaw",
    }
    assert {item["status"] for item in payload["claws"]} == {
        "experimental",
        "planned",
    }
    assert by_name["BlogAgent"]["kind"] == "agent"
    assert by_name["Dashboard"]["kind"] == "interface"
    assert by_name["ReleaseClaw"]["kind"] == "delivery"
    assert by_name["EvidenceStore"]["kind"] == "infrastructure"
    assert by_name["SponsorClaw"]["kind"] == "intelligence"


def test_manifest_json_is_case_insensitive_and_sorted(capsys):
    assert main(["manifest", "rrsclaw", "--json"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)

    assert output == json.dumps(payload, sort_keys=True) + "\n"
    assert payload["name"] == "RRSClaw"
    assert payload["capabilities"] == ["run.score", "run.regression"]
    assert payload["status"] == "experimental"


def test_manifest_rejects_an_unknown_name(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["manifest", "MissingClaw", "--json"])

    assert exc_info.value.code == 2
    assert "unknown manifest: MissingClaw" in capsys.readouterr().err
