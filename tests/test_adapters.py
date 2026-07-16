import json
import os
from types import SimpleNamespace

import pytest

from claw_gauntlet.adapters import (
    BeadsTaskLedger,
    JsonlMailTransport,
    SponsorTaskLedger,
    TaskLedgerError,
)
from claw_gauntlet.handoff import HandoffEnvelope, artifact_refs_checksum
from claw_gauntlet.improvement import ImprovementProposal
from claw_gauntlet.sponsorship import SponsorReview


ARTIFACT_REF = "evidence://sha256/c7c5c1d70c5dec4416ab6158afd0b223ef40c29b1dc1f97ed9428b94d4cadb1c"


def _proposal() -> ImprovementProposal:
    return ImprovementProposal(
        proposal_id="a" * 64,
        title="Improve GHClaw run reliability",
        description="Reproduce the failed run and correct its deterministic cause.",
        acceptance_criteria="The replay passes and its RRS score is at least 85.",
        source_run_id="123e4567e89b42d3a456426614174000",
        artifact_refs=(ARTIFACT_REF,),
        priority="1",
    )


def _handoff(summary="Review one evidence-backed improvement.") -> HandoffEnvelope:
    return HandoffEnvelope.create(
        source="RRSClaw",
        destination="GHClaw",
        artifact_refs=(ARTIFACT_REF,),
        requested_action="review-improvement",
        summary=summary,
        checksum=artifact_refs_checksum((ARTIFACT_REF,)),
        approval_required=True,
    )


def test_beads_adapter_uses_argument_array_and_reference_only_metadata(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="br-123\n", stderr="")

    adapter = BeadsTaskLedger(tmp_path, runner=runner)
    adapter.create_improvement(_proposal())

    command, kwargs = calls[0]
    assert isinstance(command, list)
    assert command[:3] == ["bd", "create", "Improve GHClaw run reliability"]
    assert kwargs.get("shell") is not True
    assert kwargs["cwd"] == tmp_path
    metadata = json.loads(command[command.index("--metadata") + 1])
    assert metadata["artifact_refs"] == [ARTIFACT_REF]
    assert "evidence contents" not in " ".join(command)


def test_beads_adapter_redacts_command_stderr(tmp_path):
    def runner(command, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="API_KEY=must-not-escape",
        )

    with pytest.raises(TaskLedgerError) as error:
        BeadsTaskLedger(tmp_path, runner=runner).create_improvement(_proposal())

    assert "must-not-escape" not in str(error.value)


def test_jsonl_mail_appends_canonical_handoff_reference(tmp_path):
    outbox = tmp_path / "mail" / "outbox.jsonl"
    transport = JsonlMailTransport(outbox)
    handoff = _handoff()

    transport.send(handoff)

    lines = outbox.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == handoff.to_dict()
    assert lines[0] == json.dumps(
        handoff.to_dict(),
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert os.stat(outbox).st_mode & 0o777 == 0o600


def test_jsonl_mail_rejects_token_like_content_without_writing(tmp_path):
    outbox = tmp_path / "outbox.jsonl"

    with pytest.raises(ValueError, match="sensitive"):
        JsonlMailTransport(outbox).send(_handoff("api_key=must-not-be-mailed"))

    assert not outbox.exists()


def test_sponsor_task_adapter_creates_reference_only_approval_task(tmp_path):
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="claw-123\n", stderr="")

    review = SponsorReview(
        draft_id="b" * 64,
        draft_ref=ARTIFACT_REF,
        prospect_name="Example Developer Tools",
        public_url="https://github.com/example",
        lane="company-pilot",
        confidence=82,
    )
    SponsorTaskLedger(tmp_path, runner=runner).create_review(review)

    command, kwargs = calls[0]
    assert command[:3] == ["bd", "create", "Review sponsor draft: Example Developer Tools"]
    assert command[command.index("--external-ref") + 1] == f"sponsor-draft:{review.draft_id}"
    assert command[command.index("--labels") + 1] == "approval-required,sponsorship"
    metadata = json.loads(command[command.index("--metadata") + 1])
    assert metadata == {
        "draft_id": review.draft_id,
        "draft_ref": ARTIFACT_REF,
        "lane": "company-pilot",
        "public_url": "https://github.com/example",
    }
    assert kwargs["cwd"] == tmp_path
    assert kwargs.get("shell") is not True


def test_sponsor_task_adapter_exports_only_when_tracker_exists(tmp_path):
    tracker = tmp_path / ".beads" / "issues.jsonl"
    tracker.parent.mkdir()
    tracker.write_text("", encoding="utf-8")
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="claw-123\n", stderr="")

    review = SponsorReview(
        draft_id="b" * 64,
        draft_ref=ARTIFACT_REF,
        prospect_name="Example",
        public_url="https://github.com/example",
        lane="feedback",
        confidence=70,
    )
    SponsorTaskLedger(tmp_path, runner=runner).create_review(review)

    assert calls[1] == ["bd", "export", "-o", str(tracker)]
