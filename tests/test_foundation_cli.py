import json
from hashlib import sha256

from claw_gauntlet.cli import main


def _invoke(arguments, capsys):
    assert main(arguments) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = captured.out.splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


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
