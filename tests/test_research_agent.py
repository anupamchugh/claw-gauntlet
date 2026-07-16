import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from claw_gauntlet.research_agent import (
    CodexSponsorResearcher,
    ResearchAgentError,
    _report_schema,
)
from claw_gauntlet.sponsorship import SponsorCampaign


def _campaign():
    return SponsorCampaign.from_dict(
        {
            "project_name": "Claw Gauntlet",
            "repository_url": "https://github.com/anupamchugh/claw-gauntlet",
            "description": "Evidence-backed capability intelligence for agentic projects.",
            "community_ask": "Support public fixtures, CI, and documentation.",
            "company_pilot": "A two-week evidence workflow setup for one repository.",
            "price_range": "$500-$1,500",
            "learning_repositories": ["obra/superpowers", "simonw/datasette"],
            "target_categories": ["AI developer tools"],
            "max_drafts": 2,
        }
    )


def _report():
    return {
        "summary": "One public feedback prospect.",
        "prospects": [
            {
                "name": "Example",
                "public_url": "https://github.com/example",
                "lane": "feedback",
                "fit_reason": "The public repository documents agent workflows.",
                "evidence_urls": ["https://github.com/example/tool"],
                "subject": "Claw Gauntlet feedback request",
                "body": "Would you be open to reviewing one bounded public workflow?",
                "confidence": 75,
            }
        ],
    }


def test_researcher_runs_codex_ephemerally_in_read_only_mode(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(json.dumps(_report()), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="events", stderr="warnings")

    researcher = CodexSponsorResearcher(
        tmp_path / "state",
        working_directory=tmp_path,
        executable="/opt/codex",
        runner=runner,
        timeout_seconds=123,
    )

    report = researcher.research(_campaign())

    command, kwargs = calls[0]
    assert command[:3] == ["/opt/codex", "--search", "exec"]
    assert "--ephemeral" in command
    assert command.count("--search") == 1
    assert "--ignore-user-config" in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert command[command.index("--cd") + 1] == str(tmp_path)
    assert command[-1] == "-"
    assert kwargs["timeout"] == 123
    assert kwargs["check"] is False
    assert kwargs.get("shell") is not True
    assert "Never send" in kwargs["input"]
    assert "obra/superpowers" in kwargs["input"]
    schema_path = Path(command[command.index("--output-schema") + 1])
    assert not schema_path.exists()
    assert report.prospects[0].lane == "feedback"


def test_researcher_redacts_codex_failure_output(tmp_path):
    def runner(command, **kwargs):
        return SimpleNamespace(
            returncode=7,
            stdout="",
            stderr="AUTH_TOKEN=must-not-escape",
        )

    with pytest.raises(ResearchAgentError) as error:
        CodexSponsorResearcher(
            tmp_path / "state",
            working_directory=tmp_path,
            runner=runner,
        ).research(_campaign())

    assert "exit 7" in str(error.value)
    assert "must-not-escape" not in str(error.value)


def test_researcher_rejects_malformed_output_and_cleans_temporary_files(tmp_path):
    def runner(command, **kwargs):
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"summary":"bad","prospects":"not-a-list"}')
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    state_root = tmp_path / "state"
    with pytest.raises(ValueError, match="prospects"):
        CodexSponsorResearcher(
            state_root,
            working_directory=tmp_path,
            runner=runner,
        ).research(_campaign())

    assert list((state_root / "research-tmp").iterdir()) == []


def test_output_schema_uses_only_supported_structured_output_keywords():
    def walk(value):
        if isinstance(value, dict):
            assert "format" not in value
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(_report_schema())
