import json

from claw_gauntlet.cli import main


def test_family_json_lists_available_and_planned_claws(capsys):
    assert main(["family", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    by_name = {item["name"]: item for item in payload["claws"]}

    assert by_name["StarClaw"]["status"] == "available"
    assert by_name["GHClaw"]["status"] == "available"
    assert by_name["ReleaseClaw"]["status"] == "planned"
    assert by_name["ProjectClaw"]["status"] == "available"
    assert by_name["DigestClaw"]["status"] == "available"
    assert by_name["BirdClaw"]["status"] == "planned"
    assert by_name["AgentMailTransport"]["kind"] == "infrastructure"
