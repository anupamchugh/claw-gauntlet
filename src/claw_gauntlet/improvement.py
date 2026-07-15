from dataclasses import dataclass
from hashlib import sha256
import json
import re

from claw_gauntlet.adapters import MailTransportPort, TaskLedgerPort
from claw_gauntlet.handoff import HandoffEnvelope, artifact_refs_checksum
from claw_gauntlet.run_ledger import RunScore
from claw_gauntlet.run_record import RunRecord


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ImprovementProposal:
    proposal_id: str
    title: str
    description: str
    acceptance_criteria: str
    source_run_id: str
    artifact_refs: tuple[str, ...]
    priority: str

    def __post_init__(self) -> None:
        if _DIGEST.fullmatch(self.proposal_id) is None:
            raise ValueError("proposal_id must be a lowercase SHA-256 digest")
        for field in (
            "title",
            "description",
            "acceptance_criteria",
            "source_run_id",
            "priority",
        ):
            value = getattr(self, field)
            if type(value) is not str or not value:
                raise ValueError(f"{field} must be a non-empty string")
        if type(self.artifact_refs) not in (list, tuple):
            raise ValueError("artifact_refs must be a list or tuple")
        object.__setattr__(self, "artifact_refs", tuple(self.artifact_refs))


class ImprovementCoordinator:
    def __init__(
        self,
        task_ledger: TaskLedgerPort,
        mail_transport: MailTransportPort,
        *,
        threshold: int = 85,
    ) -> None:
        if type(threshold) is not int or not 0 <= threshold <= 100:
            raise ValueError("threshold must be an integer from 0 to 100")
        self._task_ledger = task_ledger
        self._mail_transport = mail_transport
        self.threshold = threshold
        self._delivered: dict[str, ImprovementProposal] = {}

    def consider(
        self,
        record: RunRecord,
        score: RunScore,
    ) -> ImprovementProposal | None:
        if not isinstance(record, RunRecord):
            raise TypeError("record must be a RunRecord")
        if not isinstance(score, RunScore):
            raise TypeError("score must be a RunScore")
        if score.run_id != record.run_id:
            raise ValueError("score run_id must match the considered run")
        if score.overall >= self.threshold:
            return None

        proposal = self._proposal_for(record, score)
        delivered = self._delivered.get(proposal.proposal_id)
        if delivered is not None:
            return delivered

        handoff = HandoffEnvelope.create(
            source="RRSClaw",
            destination=record.claw_name,
            artifact_refs=record.artifact_refs,
            requested_action="review-improvement",
            summary=proposal.title,
            checksum=artifact_refs_checksum(record.artifact_refs),
            approval_required=True,
        )
        self._task_ledger.create_improvement(proposal)
        self._mail_transport.send(handoff)
        self._delivered[proposal.proposal_id] = proposal
        return proposal

    @staticmethod
    def _proposal_for(record: RunRecord, score: RunScore) -> ImprovementProposal:
        identity = json.dumps(
            {
                "overall": score.overall,
                "reliability": score.reliability,
                "resilience": score.resilience,
                "run_id": record.run_id,
                "safety": score.safety,
            },
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        proposal_id = sha256(identity).hexdigest()
        return ImprovementProposal(
            proposal_id=proposal_id,
            title=f"Improve {record.claw_name} run reliability",
            description=(
                f"Reproduce run {record.run_id} and correct the deterministic "
                f"cause of its RRS score {score.overall}."
            ),
            acceptance_criteria=(
                "The failed behavior has a regression test, the replay passes, "
                "and the resulting RRS score meets the configured threshold."
            ),
            source_run_id=record.run_id,
            artifact_refs=record.artifact_refs,
            priority="1",
        )
