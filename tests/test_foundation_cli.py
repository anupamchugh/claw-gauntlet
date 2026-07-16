import json
from hashlib import sha256
from pathlib import Path

import claw_gauntlet.cli as cli_module
from claw_gauntlet.cli import main
from claw_gauntlet.sponsorship import SponsorResearchReport


def _invoke(arguments, capsys):
    assert main(arguments) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = captured.out.splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def test_sponsor_inbox_uses_installed_state_directory_by_default():
    arguments = cli_module._parser().parse_args(["sponsor", "inbox"])

    assert arguments.state_dir == (
        Path.home() / "Library" / "Application Support" / "ClawGauntlet" / "state"
    )


def test_local_foundation_workflow_persists_evidence_runs_and_handoffs(
    tmp_path,
    capsys,
):
    state_dir = tmp_path / "state"
    evidence_input = tmp_path / "evidence.json"
    evidence_input.write_text(
        json.dumps({"items": [1, 2], "source": "public"}),
        encoding="utf-8",
    )

    evidence = _invoke(
        [
            "evidence",
            "put",
            "--state-dir",
            str(state_dir),
            "--input",
            str(evidence_input),
        ],
        capsys,
    )
    assert evidence["status"] == "stored"
    assert evidence["artifact_ref"].startswith("evidence://sha256/")

    run_input = tmp_path / "run.json"
    run_input.write_text(
        json.dumps(
            {
                "claw_name": "GHClaw",
                "claw_version": "0.1.0",
                "input_hash": f"sha256:{sha256(b'public-input').hexdigest()}",
                "artifact_refs": [evidence["artifact_ref"]],
                "outcome": "failure",
                "duration_ms": 20,
                "retries": 4,
                "approvals_required": 1,
                "approvals_granted": 0,
                "permission_violations": 0,
                "human_corrections": 0,
            }
        ),
        encoding="utf-8",
    )
    recorded = _invoke(
        [
            "run",
            "record",
            "--state-dir",
            str(state_dir),
            "--input",
            str(run_input),
        ],
        capsys,
    )
    run_id = recorded["run"]["run_id"]

    scored = _invoke(
        ["run", "score", "--state-dir", str(state_dir), run_id],
        capsys,
    )
    assert scored["score"]["overall"] < 85

    shown = _invoke(
        ["run", "show", "--state-dir", str(state_dir), run_id],
        capsys,
    )
    assert shown["run"]["run_id"] == run_id
    assert shown["score"] == scored["score"]

    considered = _invoke(
        [
            "improvement",
            "consider",
            "--state-dir",
            str(state_dir),
            run_id,
        ],
        capsys,
    )
    assert considered["status"] == "proposed"
    assert considered["proposal"]["source_run_id"] == run_id
    assert considered["task"]["proposal_id"] == considered["proposal"]["proposal_id"]

    assert (state_dir / "evidence").is_dir()
    assert (state_dir / "runs.duckdb").is_file()
    outbox = state_dir / "mail" / "outbox.jsonl"
    assert outbox.is_file()
    handoffs = [json.loads(line) for line in outbox.read_text().splitlines()]
    assert len(handoffs) == 1
    assert handoffs[0]["artifact_refs"] == [evidence["artifact_ref"]]
    assert "public-input" not in outbox.read_text()


def test_foundation_command_returns_a_structured_error(tmp_path, capsys):
    result = main(
        [
            "run",
            "show",
            "--state-dir",
            str(tmp_path / "state"),
            "missing-run",
        ]
    )

    assert result == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error == {
        "error": "run not found: missing-run",
        "status": "error",
    }


def test_github_to_project_cli_slice_uses_immutable_evidence(
    tmp_path,
    capsys,
    monkeypatch,
):
    repository_evidence = {
        "schema": "claw.evidence.github-repository.v1",
        "source_url": "https://api.github.com/repos/example/tool",
        "observed_at": "2026-07-16T00:00:00Z",
        "full_name": "example/tool",
        "html_url": "https://github.com/example/tool",
        "description": "Reliable agent workflow tooling",
        "topics": ["agents", "workflow"],
        "license_spdx": "MIT",
        "language": "Python",
        "archived": False,
        "fork": False,
        "stargazers_count": 42,
        "forks_count": 3,
        "open_issues_count": 2,
        "pushed_at": "2026-07-15T12:00:00Z",
        "default_branch": "main",
    }

    class FakeCollector:
        def repository(self, repository):
            assert repository == "example/tool"
            return repository_evidence

    monkeypatch.setattr(cli_module, "GitHubPublicCollector", FakeCollector)
    state_dir = tmp_path / "state"
    collected = _invoke(
        [
            "github",
            "repo",
            "--state-dir",
            str(state_dir),
            "example/tool",
        ],
        capsys,
    )
    assert collected["status"] == "collected"
    assert collected["run"]["claw_name"] == "GHClaw"

    project = tmp_path / "project.json"
    project.write_text(
        json.dumps(
            {
                "project_name": "Public Agent Workspace",
                "keywords": ["agents", "swift"],
            }
        ),
        encoding="utf-8",
    )
    evaluated = _invoke(
        [
            "project",
            "evaluate",
            "--state-dir",
            str(state_dir),
            "--artifact-ref",
            collected["artifact_ref"],
            "--input",
            str(project),
        ],
        capsys,
    )

    assert evaluated["status"] == "evaluated"
    assert evaluated["evaluation"]["decision"] == "candidate"
    assert evaluated["evaluation"]["artifact_refs"] == [collected["artifact_ref"]]
    assert evaluated["run"]["claw_name"] == "ProjectClaw"


def test_publication_bundle_cli_creates_an_approval_gated_publisher_request(
    tmp_path,
    capsys,
):
    state_dir = tmp_path / "state"
    source = tmp_path / "source.json"
    source.write_text(json.dumps({"claim": "Public evidence"}), encoding="utf-8")
    stored = _invoke(
        [
            "evidence",
            "put",
            "--state-dir",
            str(state_dir),
            "--input",
            str(source),
        ],
        capsys,
    )
    publication_input = tmp_path / "publication.json"
    publication_input.write_text(
        json.dumps(
            {
                "title": "Claw Gauntlet release",
                "content": ["Evidence first. Publishing only after approval."],
                "artifact_refs": [stored["artifact_ref"]],
                "source_urls": ["https://github.com/example/tool"],
            }
        ),
        encoding="utf-8",
    )

    bundled = _invoke(
        [
            "publication",
            "bundle",
            "--channel",
            "twitter",
            "--state-dir",
            str(state_dir),
            "--input",
            str(publication_input),
        ],
        capsys,
    )
    assert bundled["run"]["claw_name"] == "TwitterClaw"
    assert bundled["bundle"]["approval_required"] is True

    requested = _invoke(
        [
            "publication",
            "request",
            "--state-dir",
            str(state_dir),
            bundled["artifact_ref"],
        ],
        capsys,
    )
    assert requested["status"] == "approval-requested"
    outbox = state_dir / "mail" / "publisher-requests.jsonl"
    handoff = json.loads(outbox.read_text().strip())
    assert handoff["approval_required"] is True
    assert handoff["artifact_refs"] == [bundled["artifact_ref"]]
    assert "Evidence first" not in outbox.read_text()


def _sponsor_campaign_file(tmp_path):
    path = tmp_path / "campaign.json"
    path.write_text(
        json.dumps(
            {
                "project_name": "Claw Gauntlet",
                "repository_url": "https://github.com/anupamchugh/claw-gauntlet",
                "description": "Evidence-backed capability intelligence.",
                "community_ask": "Support fixtures, CI, and documentation.",
                "company_pilot": "A bounded two-week evidence workflow pilot.",
                "price_range": "$500-$1,500",
                "learning_repositories": ["obra/superpowers"],
                "target_categories": ["AI developer tools"],
                "max_drafts": 2,
            }
        ),
        encoding="utf-8",
    )
    return path


def _sponsor_report_payload():
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
                "body": "Would you review one bounded public workflow?",
                "confidence": 75,
            }
        ],
    }


def test_sponsor_ingest_and_inbox_cli_are_approval_only(tmp_path, capsys):
    state_dir = tmp_path / "state"
    campaign = _sponsor_campaign_file(tmp_path)
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_sponsor_report_payload()), encoding="utf-8")

    ingested = _invoke(
        [
            "sponsor",
            "ingest",
            "--state-dir",
            str(state_dir),
            "--config",
            str(campaign),
            "--input",
            str(report),
        ],
        capsys,
    )
    inbox = _invoke(
        ["sponsor", "inbox", "--state-dir", str(state_dir)],
        capsys,
    )

    assert ingested["status"] == "awaiting-review"
    assert len(ingested["reviews"]) == 1
    assert inbox["status"] == "found"
    assert inbox["count"] == 1
    assert inbox["items"][0]["requested_action"] == "review-sponsor-outreach"
    assert "body" not in inbox["items"][0]


def test_sponsor_research_cli_runs_researcher_then_ingests(
    tmp_path,
    capsys,
    monkeypatch,
):
    campaign = _sponsor_campaign_file(tmp_path)
    state_dir = tmp_path / "state"

    class FakeResearcher:
        def __init__(self, state_root, *, working_directory):
            assert state_root == state_dir
            assert working_directory == tmp_path

        def research(self, parsed_campaign):
            assert parsed_campaign.project_name == "Claw Gauntlet"
            return SponsorResearchReport.from_dict(_sponsor_report_payload())

    monkeypatch.setattr(cli_module, "CodexSponsorResearcher", FakeResearcher)

    result = _invoke(
        [
            "sponsor",
            "research",
            "--state-dir",
            str(state_dir),
            "--config",
            str(campaign),
            "--workspace",
            str(tmp_path),
        ],
        capsys,
    )

    assert result["status"] == "awaiting-review"
    assert result["research_summary"] == "One public feedback prospect."


def test_sponsor_ingest_notifies_only_when_new_reviews_exist(
    tmp_path,
    capsys,
    monkeypatch,
):
    state_dir = tmp_path / "state"
    campaign = _sponsor_campaign_file(tmp_path)
    report = tmp_path / "report.json"
    report.write_text(json.dumps(_sponsor_report_payload()), encoding="utf-8")
    notifications = []
    monkeypatch.setattr(cli_module, "notify_owner", notifications.append)
    command = [
        "sponsor",
        "ingest",
        "--state-dir",
        str(state_dir),
        "--config",
        str(campaign),
        "--input",
        str(report),
        "--notify",
    ]

    _invoke(command, capsys)
    _invoke(command, capsys)

    assert notifications == [1]


def test_sponsor_schedule_cli_installs_and_reports_status(
    tmp_path,
    capsys,
    monkeypatch,
):
    calls = []

    class FakeManager:
        def install(self, schedule):
            calls.append(schedule)
            return tmp_path / "SponsorAgent.plist"

        def status(self):
            return True

        def uninstall(self):
            calls.append("uninstalled")

    monkeypatch.setattr(cli_module, "LaunchAgentManager", FakeManager)
    campaign = _sponsor_campaign_file(tmp_path)
    common = [
        "--state-dir",
        str(tmp_path / "state"),
    ]
    installed = _invoke(
        [
            "sponsor",
            "schedule",
            "install",
            *common,
            "--config",
            str(campaign),
            "--workspace",
            str(tmp_path),
            "--task-dir",
            str(tmp_path),
            "--executable",
            str(tmp_path / "clawgauntlet"),
        ],
        capsys,
    )
    status = _invoke(
        ["sponsor", "schedule", "status", *common],
        capsys,
    )
    removed = _invoke(
        ["sponsor", "schedule", "uninstall", *common],
        capsys,
    )

    assert installed["status"] == "installed"
    assert installed["plist"] == str(tmp_path / "SponsorAgent.plist")
    assert calls[0].campaign_config == campaign
    assert status == {"loaded": True, "status": "running"}
    assert removed["status"] == "uninstalled"
