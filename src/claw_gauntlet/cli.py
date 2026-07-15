import argparse
import json
from collections.abc import Sequence
from pathlib import Path
import sys
from typing import Any

from claw_gauntlet.adapters import JsonlMailTransport
from claw_gauntlet.evidence import EvidenceStore
from claw_gauntlet.family import family_payload, manifest_for
from claw_gauntlet.improvement import ImprovementCoordinator, ImprovementProposal
from claw_gauntlet.rrs import score_run
from claw_gauntlet.run_ledger import RunLedger, RunScore
from claw_gauntlet.run_record import RunRecord


class _FoundationCommandError(RuntimeError):
    pass


class _CapturedTaskLedger:
    """Local CLI task sink; production deployments can bind BeadsTaskLedger."""

    def __init__(self) -> None:
        self.proposal: ImprovementProposal | None = None

    def create_improvement(self, proposal: ImprovementProposal) -> None:
        self.proposal = proposal


def _add_state_dir(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state-dir", type=Path, required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clawgauntlet")
    subparsers = parser.add_subparsers(dest="command", required=True)

    family = subparsers.add_parser("family")
    family.add_argument("--json", action="store_true", dest="as_json")

    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("name")
    manifest.add_argument("--json", action="store_true", dest="as_json")

    evidence = subparsers.add_parser("evidence")
    evidence_commands = evidence.add_subparsers(dest="evidence_command", required=True)
    evidence_put = evidence_commands.add_parser("put")
    _add_state_dir(evidence_put)
    evidence_put.add_argument("--input", type=Path, required=True)

    run = subparsers.add_parser("run")
    run_commands = run.add_subparsers(dest="run_command", required=True)
    run_record = run_commands.add_parser("record")
    _add_state_dir(run_record)
    run_record.add_argument("--input", type=Path, required=True)
    for name in ("score", "show"):
        command = run_commands.add_parser(name)
        _add_state_dir(command)
        command.add_argument("run_id")

    improvement = subparsers.add_parser("improvement")
    improvement_commands = improvement.add_subparsers(
        dest="improvement_command",
        required=True,
    )
    consider = improvement_commands.add_parser("consider")
    _add_state_dir(consider)
    consider.add_argument("run_id")
    consider.add_argument("--threshold", type=int, default=85)
    return parser


def _state_root(path: Path) -> Path:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if type(payload) is not dict:
        raise ValueError("input JSON must be an object")
    return payload


def _score_payload(score: RunScore | None) -> dict[str, Any] | None:
    if score is None:
        return None
    return {
        "run_id": score.run_id,
        "reliability": score.reliability,
        "resilience": score.resilience,
        "safety": score.safety,
        "overall": score.overall,
    }


def _proposal_payload(proposal: ImprovementProposal) -> dict[str, Any]:
    return {
        "proposal_id": proposal.proposal_id,
        "title": proposal.title,
        "description": proposal.description,
        "acceptance_criteria": proposal.acceptance_criteria,
        "source_run_id": proposal.source_run_id,
        "artifact_refs": list(proposal.artifact_refs),
        "priority": proposal.priority,
    }


def _required_run(ledger: RunLedger, run_id: str) -> RunRecord:
    record = ledger.get_run(run_id)
    if record is None:
        raise _FoundationCommandError(f"run not found: {run_id}")
    return record


def _foundation_command(args: argparse.Namespace) -> dict[str, Any]:
    state_root = _state_root(args.state_dir)
    if args.command == "evidence" and args.evidence_command == "put":
        reference = EvidenceStore(state_root / "evidence").put_json(
            _read_json_object(args.input)
        )
        return {"artifact_ref": reference.uri, "status": "stored"}

    ledger_path = state_root / "runs.duckdb"
    with RunLedger(ledger_path) as ledger:
        if args.command == "run" and args.run_command == "record":
            record = RunRecord.create(**_read_json_object(args.input))
            ledger.record_run(record)
            return {"run": record.to_dict(), "status": "recorded"}

        record = _required_run(ledger, args.run_id)
        if args.command == "run" and args.run_command == "score":
            score = score_run(record)
            ledger.record_score(score)
            return {"score": _score_payload(score), "status": "scored"}
        if args.command == "run" and args.run_command == "show":
            return {
                "run": record.to_dict(),
                "score": _score_payload(ledger.get_score(record.run_id)),
                "status": "found",
            }
        if args.command == "improvement" and args.improvement_command == "consider":
            score = ledger.get_score(record.run_id)
            if score is None:
                score = score_run(record)
                ledger.record_score(score)
            tasks = _CapturedTaskLedger()
            coordinator = ImprovementCoordinator(
                tasks,
                JsonlMailTransport(state_root / "mail" / "outbox.jsonl"),
                threshold=args.threshold,
            )
            proposal = coordinator.consider(record, score)
            if proposal is None:
                return {"proposal": None, "status": "accepted"}
            proposal_payload = _proposal_payload(proposal)
            return {
                "proposal": proposal_payload,
                "status": "proposed",
                "task": proposal_payload,
            }
    raise _FoundationCommandError("unsupported foundation command")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "family":
        payload = family_payload()
        print(json.dumps(payload, sort_keys=True))
        return 0
    if args.command == "manifest":
        try:
            payload = manifest_for(args.name).to_dict()
        except KeyError as error:
            parser.error(error.args[0])
        print(json.dumps(payload, sort_keys=True))
        return 0
    try:
        payload = _foundation_command(args)
    except (OSError, ValueError, KeyError, TypeError, _FoundationCommandError) as error:
        print(
            json.dumps({"error": str(error), "status": "error"}, sort_keys=True),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


def entrypoint() -> None:
    raise SystemExit(main())
