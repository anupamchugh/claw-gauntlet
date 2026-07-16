from collections.abc import Callable
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Protocol, TYPE_CHECKING

from claw_gauntlet.handoff import HandoffEnvelope


if TYPE_CHECKING:
    from claw_gauntlet.improvement import ImprovementProposal
    from claw_gauntlet.sponsorship import SponsorReview


_SENSITIVE_CONTENT = re.compile(
    r"(?i)(api[_-]?key|auth[_-]?token|access[_-]?token|password|cookie|ct0)"
)
_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)


class TaskLedgerError(RuntimeError):
    """Raised when the durable task adapter rejects an improvement."""


class TaskLedgerPort(Protocol):
    def create_improvement(self, proposal: "ImprovementProposal") -> Any: ...


class MailTransportPort(Protocol):
    def send(self, handoff: HandoffEnvelope) -> Any: ...


class BeadsTaskLedger:
    def __init__(
        self,
        working_directory: str | Path,
        *,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self.working_directory = Path(working_directory)
        self._runner = runner

    def create_improvement(self, proposal: "ImprovementProposal") -> None:
        metadata = json.dumps(
            {
                "artifact_refs": list(proposal.artifact_refs),
                "proposal_id": proposal.proposal_id,
                "source_run_id": proposal.source_run_id,
            },
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        command = [
            "bd",
            "create",
            proposal.title,
            "--type",
            "task",
            "--priority",
            proposal.priority,
            "--description",
            proposal.description,
            "--acceptance",
            proposal.acceptance_criteria,
            "--external-ref",
            f"claw-run:{proposal.source_run_id}",
            "--metadata",
            metadata,
            "--silent",
        ]
        result = self._runner(
            command,
            cwd=self.working_directory,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise TaskLedgerError(
                f"Beads rejected improvement proposal (exit {result.returncode}); "
                "stderr redacted"
            )


class SponsorTaskLedger:
    def __init__(
        self,
        working_directory: str | Path,
        *,
        runner: Callable[..., Any] = subprocess.run,
    ) -> None:
        self.working_directory = Path(working_directory)
        self._runner = runner

    def create_review(self, review: "SponsorReview") -> None:
        from claw_gauntlet.sponsorship import SponsorReview

        if not isinstance(review, SponsorReview):
            raise TypeError("review must be a SponsorReview")
        metadata = json.dumps(
            {
                "draft_id": review.draft_id,
                "draft_ref": review.draft_ref,
                "lane": review.lane,
                "public_url": review.public_url,
            },
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        command = [
            "bd",
            "create",
            f"Review sponsor draft: {review.prospect_name}",
            "--type",
            "task",
            "--priority",
            "1",
            "--description",
            (
                f"Review the evidence-backed {review.lane} draft for "
                f"{review.public_url}. Approve, edit, decline, or mark no-contact."
            ),
            "--acceptance",
            (
                "The owner records an explicit decision. No external message is sent "
                "by this task or by SponsorClaw."
            ),
            "--external-ref",
            f"sponsor-draft:{review.draft_id}",
            "--labels",
            "approval-required,sponsorship",
            "--metadata",
            metadata,
            "--silent",
        ]
        self._run(command, "create sponsor review")
        tracker = self.working_directory / ".beads" / "issues.jsonl"
        if tracker.is_file():
            self._run(["bd", "export", "-o", str(tracker)], "export sponsor review")

    def _run(self, command: list[str], action: str) -> None:
        result = self._runner(
            command,
            cwd=self.working_directory,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise TaskLedgerError(
                f"Beads failed to {action} (exit {result.returncode}); stderr redacted"
            )


class JsonlMailTransport:
    def __init__(self, outbox_path: str | Path) -> None:
        self.outbox_path = Path(outbox_path)

    def send(self, handoff: HandoffEnvelope) -> None:
        if not isinstance(handoff, HandoffEnvelope):
            raise TypeError("handoff must be a HandoffEnvelope")
        canonical = json.dumps(
            handoff.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if _SENSITIVE_CONTENT.search(canonical) is not None:
            raise ValueError("handoff contains sensitive token-like content")

        self.outbox_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(
            self.outbox_path,
            os.O_WRONLY | os.O_APPEND | os.O_CREAT | _O_CLOEXEC,
            mode=0o600,
        )
        try:
            os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            with os.fdopen(
                descriptor,
                "a",
                encoding="utf-8",
                closefd=False,
            ) as outbox:
                outbox.write(canonical + "\n")
                outbox.flush()
                os.fsync(outbox.fileno())
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
