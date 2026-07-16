import argparse
from hashlib import sha256
import json
from collections.abc import Sequence
from pathlib import Path
import sys
from time import monotonic_ns
from typing import Any

from claw_gauntlet.adapters import (
    JsonlMailTransport,
    SponsorTaskLedger,
    TaskLedgerError,
)
from claw_gauntlet.evidence import EvidenceRef, EvidenceStore
from claw_gauntlet.family import family_payload, manifest_for
from claw_gauntlet.github_claws import GitHubAPIError, GitHubPublicCollector
from claw_gauntlet.handoff import HandoffEnvelope
from claw_gauntlet.improvement import ImprovementCoordinator, ImprovementProposal
from claw_gauntlet.project_claw import evaluate_repository
from claw_gauntlet.publication import PublicationBundle, publisher_request
from claw_gauntlet.research_agent import CodexSponsorResearcher, ResearchAgentError
from claw_gauntlet.rrs import score_run
from claw_gauntlet.run_ledger import RunLedger, RunScore
from claw_gauntlet.run_record import RunRecord
from claw_gauntlet.sponsor_scheduler import (
    LaunchAgentError,
    LaunchAgentManager,
    SponsorSchedule,
    notify_owner,
)
from claw_gauntlet.sponsorship import (
    SponsorCampaign,
    SponsorCycle,
    SponsorResearchReport,
)


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

    github = subparsers.add_parser("github")
    github_commands = github.add_subparsers(dest="github_command", required=True)
    github_repo = github_commands.add_parser("repo")
    _add_state_dir(github_repo)
    github_repo.add_argument("repository")
    github_stars = github_commands.add_parser("stars")
    _add_state_dir(github_stars)
    github_stars.add_argument("username")
    github_stars.add_argument("--max-pages", type=int, default=1)

    sponsor = subparsers.add_parser("sponsor")
    sponsor_commands = sponsor.add_subparsers(dest="sponsor_command", required=True)
    sponsor_research = sponsor_commands.add_parser("research")
    _add_state_dir(sponsor_research)
    sponsor_research.add_argument("--config", type=Path, required=True)
    sponsor_research.add_argument("--workspace", type=Path, required=True)
    sponsor_research.add_argument("--task-dir", type=Path)
    sponsor_research.add_argument("--notify", action="store_true")
    sponsor_ingest = sponsor_commands.add_parser("ingest")
    _add_state_dir(sponsor_ingest)
    sponsor_ingest.add_argument("--config", type=Path, required=True)
    sponsor_ingest.add_argument("--input", type=Path, required=True)
    sponsor_ingest.add_argument("--task-dir", type=Path)
    sponsor_ingest.add_argument("--notify", action="store_true")
    sponsor_inbox = sponsor_commands.add_parser("inbox")
    _add_state_dir(sponsor_inbox)
    sponsor_schedule = sponsor_commands.add_parser("schedule")
    schedule_commands = sponsor_schedule.add_subparsers(
        dest="schedule_command",
        required=True,
    )
    schedule_install = schedule_commands.add_parser("install")
    _add_state_dir(schedule_install)
    schedule_install.add_argument("--config", type=Path, required=True)
    schedule_install.add_argument("--workspace", type=Path, required=True)
    schedule_install.add_argument("--task-dir", type=Path, required=True)
    schedule_install.add_argument("--executable", type=Path, required=True)
    for name in ("status", "uninstall"):
        schedule_command = schedule_commands.add_parser(name)
        _add_state_dir(schedule_command)

    project = subparsers.add_parser("project")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    project_evaluate = project_commands.add_parser("evaluate")
    _add_state_dir(project_evaluate)
    project_evaluate.add_argument("--artifact-ref", required=True)
    project_evaluate.add_argument("--input", type=Path, required=True)

    publication = subparsers.add_parser("publication")
    publication_commands = publication.add_subparsers(
        dest="publication_command",
        required=True,
    )
    publication_bundle = publication_commands.add_parser("bundle")
    _add_state_dir(publication_bundle)
    publication_bundle.add_argument("--channel", choices=("blog", "twitter"), required=True)
    publication_bundle.add_argument("--input", type=Path, required=True)
    publication_request = publication_commands.add_parser("request")
    _add_state_dir(publication_request)
    publication_request.add_argument("bundle_ref")
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


def _canonical_hash(payload: Any) -> str:
    canonical = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256(canonical).hexdigest()}"


def _record_success(
    ledger: RunLedger,
    *,
    claw_name: str,
    input_payload: Any,
    artifact_refs: list[str],
    duration_ms: int,
) -> RunRecord:
    record = RunRecord.create(
        claw_name=claw_name,
        claw_version="0.1.0",
        input_hash=_canonical_hash(input_payload),
        artifact_refs=artifact_refs,
        outcome="success",
        duration_ms=duration_ms,
        retries=0,
        approvals_required=0,
        approvals_granted=0,
        permission_violations=0,
        human_corrections=0,
    )
    ledger.record_run(record)
    score = score_run(record)
    ledger.record_score(score)
    return record


def _evidence_ref(uri: str) -> EvidenceRef:
    prefix = "evidence://sha256/"
    if type(uri) is not str or not uri.startswith(prefix):
        raise ValueError("artifact_ref must be an evidence SHA-256 reference")
    return EvidenceRef(algorithm="sha256", digest=uri.removeprefix(prefix))


def _foundation_command(args: argparse.Namespace) -> dict[str, Any]:
    state_root = _state_root(args.state_dir)
    if args.command == "sponsor" and args.sponsor_command == "schedule":
        manager = LaunchAgentManager()
        if args.schedule_command == "install":
            schedule = SponsorSchedule(
                executable=args.executable,
                state_dir=state_root,
                campaign_config=args.config,
                workspace=args.workspace,
                task_dir=args.task_dir,
            )
            path = manager.install(schedule)
            return {"plist": str(path), "status": "installed"}
        if args.schedule_command == "status":
            loaded = manager.status()
            return {"loaded": loaded, "status": "running" if loaded else "stopped"}
        manager.uninstall()
        return {"status": "uninstalled"}
    if args.command == "sponsor" and args.sponsor_command == "inbox":
        return _sponsor_inbox(state_root)
    if args.command == "sponsor":
        campaign = SponsorCampaign.from_dict(_read_json_object(args.config))
        if args.sponsor_command == "research":
            report = CodexSponsorResearcher(
                state_root,
                working_directory=args.workspace,
            ).research(campaign)
        else:
            report = SponsorResearchReport.from_dict(_read_json_object(args.input))
        task_ledger = (
            SponsorTaskLedger(args.task_dir) if args.task_dir is not None else None
        )
        result = SponsorCycle(state_root, task_ledger=task_ledger).ingest(
            campaign,
            report,
        )
        if args.notify and result.new_reviews:
            notify_owner(len(result.new_reviews))
        return {
            "report_ref": result.report_ref,
            "research_summary": report.summary,
            "reviews": [review.to_dict() for review in result.new_reviews],
            "status": result.status,
        }
    if args.command == "evidence" and args.evidence_command == "put":
        reference = EvidenceStore(state_root / "evidence").put_json(
            _read_json_object(args.input)
        )
        return {"artifact_ref": reference.uri, "status": "stored"}

    evidence_store = EvidenceStore(state_root / "evidence")
    if args.command == "github":
        started_at = monotonic_ns()
        collector = GitHubPublicCollector()
        if args.github_command == "repo":
            input_payload = {"repository": args.repository}
            evidence = collector.repository(args.repository)
            claw_name = "GHClaw"
            summary = {"repository": evidence["full_name"]}
        else:
            input_payload = {
                "max_pages": args.max_pages,
                "username": args.username,
            }
            evidence = collector.starred(args.username, max_pages=args.max_pages)
            claw_name = "StarClaw"
            summary = {
                "complete": evidence["complete"],
                "repository_count": len(evidence["repositories"]),
                "username": evidence["username"],
            }
        reference = evidence_store.put_json(evidence)
        duration_ms = max(0, round((monotonic_ns() - started_at) / 1_000_000))
        with RunLedger(state_root / "runs.duckdb") as ledger:
            record = _record_success(
                ledger,
                claw_name=claw_name,
                input_payload=input_payload,
                artifact_refs=[reference.uri],
                duration_ms=duration_ms,
            )
        return {
            "artifact_ref": reference.uri,
            "run": record.to_dict(),
            "status": "collected",
            "summary": summary,
        }

    if args.command == "project" and args.project_command == "evaluate":
        started_at = monotonic_ns()
        project_input = _read_json_object(args.input)
        source_reference = _evidence_ref(args.artifact_ref)
        source_evidence = evidence_store.get_json(source_reference)
        evaluation = evaluate_repository(
            source_evidence,
            project_name=project_input["project_name"],
            keywords=project_input["keywords"],
            artifact_ref=source_reference.uri,
        )
        evaluation_reference = evidence_store.put_json(evaluation)
        duration_ms = max(0, round((monotonic_ns() - started_at) / 1_000_000))
        with RunLedger(state_root / "runs.duckdb") as ledger:
            record = _record_success(
                ledger,
                claw_name="ProjectClaw",
                input_payload={
                    "project": project_input,
                    "source_artifact_ref": source_reference.uri,
                },
                artifact_refs=[evaluation_reference.uri],
                duration_ms=duration_ms,
            )
        return {
            "artifact_ref": evaluation_reference.uri,
            "evaluation": evaluation,
            "run": record.to_dict(),
            "status": "evaluated",
        }

    if args.command == "publication" and args.publication_command == "bundle":
        started_at = monotonic_ns()
        publication_input = _read_json_object(args.input)
        bundle = PublicationBundle.create(
            channel=args.channel,
            title=publication_input["title"],
            content=publication_input["content"],
            artifact_refs=publication_input["artifact_refs"],
            source_urls=publication_input["source_urls"],
        )
        bundle_reference = evidence_store.put_json(bundle.to_dict())
        duration_ms = max(0, round((monotonic_ns() - started_at) / 1_000_000))
        with RunLedger(state_root / "runs.duckdb") as ledger:
            record = _record_success(
                ledger,
                claw_name="BlogClaw" if bundle.channel == "blog" else "TwitterClaw",
                input_payload={
                    "artifact_refs": list(bundle.artifact_refs),
                    "channel": bundle.channel,
                    "content_hash": bundle.content_hash,
                    "source_urls": list(bundle.source_urls),
                    "title": bundle.title,
                },
                artifact_refs=[bundle_reference.uri],
                duration_ms=duration_ms,
            )
        return {
            "artifact_ref": bundle_reference.uri,
            "bundle": bundle.to_dict(),
            "run": record.to_dict(),
            "status": "bundled",
        }

    if args.command == "publication" and args.publication_command == "request":
        bundle_reference = _evidence_ref(args.bundle_ref)
        bundle = PublicationBundle.from_dict(evidence_store.get_json(bundle_reference))
        request = publisher_request(bundle, bundle_ref=bundle_reference.uri)
        JsonlMailTransport(
            state_root / "mail" / "publisher-requests.jsonl"
        ).send(request)
        return {
            "handoff": request.to_dict(),
            "status": "approval-requested",
        }

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


def _sponsor_inbox(state_root: Path) -> dict[str, Any]:
    outbox = state_root / "mail" / "sponsor-approvals.jsonl"
    if not outbox.exists():
        return {"count": 0, "items": [], "status": "empty"}
    items = []
    for line in outbox.read_text(encoding="utf-8").splitlines():
        handoff = HandoffEnvelope.from_dict(json.loads(line))
        if handoff.source != "SponsorClaw":
            raise ValueError("sponsor inbox contains a non-SponsorClaw handoff")
        items.append(
            {
                "artifact_refs": list(handoff.artifact_refs),
                "created_at": handoff.created_at,
                "handoff_id": handoff.handoff_id,
                "requested_action": handoff.requested_action,
                "summary": handoff.summary,
            }
        )
    return {
        "count": len(items),
        "items": items,
        "status": "found" if items else "empty",
    }


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
    except (
        GitHubAPIError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        ResearchAgentError,
        TaskLedgerError,
        LaunchAgentError,
        _FoundationCommandError,
    ) as error:
        print(
            json.dumps({"error": str(error), "status": "error"}, sort_keys=True),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


def entrypoint() -> None:
    raise SystemExit(main())
