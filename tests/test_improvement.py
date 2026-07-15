from dataclasses import replace

import pytest

from claw_gauntlet.improvement import ImprovementCoordinator
from claw_gauntlet.rrs import score_run
from claw_gauntlet.run_record import RunRecord


def _run_record() -> RunRecord:
    return RunRecord.create(
        claw_name="GHClaw",
        claw_version="0.1.0",
        input_hash="sha256:c96c6d5be8d08a12e7b5cdc1b207fa6b2430974c86803d8891675e76fd992c20",
        artifact_refs=(
            "evidence://sha256/c7c5c1d70c5dec4416ab6158afd0b223ef40c29b1dc1f97ed9428b94d4cadb1c",
        ),
        outcome="failure",
        duration_ms=20,
        retries=4,
        approvals_required=1,
        approvals_granted=0,
        permission_violations=0,
        human_corrections=0,
    )


class FakeLedger:
    def __init__(self):
        self.created = []

    def create_improvement(self, proposal):
        self.created.append(proposal)


class FakeMail:
    def __init__(self):
        self.sent = []

    def send(self, handoff):
        self.sent.append(handoff)


def test_low_score_creates_one_idempotent_improvement():
    record = _run_record()
    score = score_run(record)
    ledger = FakeLedger()
    mail = FakeMail()
    coordinator = ImprovementCoordinator(ledger, mail, threshold=85)

    first = coordinator.consider(record, score)
    second = coordinator.consider(record, score)

    assert first == second
    assert len(ledger.created) == 1
    assert len(mail.sent) == 1
    assert mail.sent[0].artifact_refs == record.artifact_refs
    assert mail.sent[0].approval_required is True


def test_passing_score_creates_nothing():
    record = _run_record()
    score = replace(score_run(record), overall=85)
    ledger = FakeLedger()
    mail = FakeMail()

    result = ImprovementCoordinator(ledger, mail, threshold=85).consider(
        record,
        score,
    )

    assert result is None
    assert ledger.created == []
    assert mail.sent == []


def test_mail_failure_does_not_mark_proposal_delivered():
    record = _run_record()
    score = score_run(record)
    ledger = FakeLedger()

    class FailOnceMail(FakeMail):
        def __init__(self):
            super().__init__()
            self.failed = False

        def send(self, handoff):
            if not self.failed:
                self.failed = True
                raise OSError("mail unavailable")
            super().send(handoff)

    mail = FailOnceMail()
    coordinator = ImprovementCoordinator(ledger, mail, threshold=85)

    with pytest.raises(OSError, match="mail unavailable"):
        coordinator.consider(record, score)

    delivered = coordinator.consider(record, score)

    assert delivered is not None
    assert len(mail.sent) == 1


def test_score_must_belong_to_the_considered_run():
    record = _run_record()
    score = replace(score_run(record), run_id=_run_record().run_id)

    with pytest.raises(ValueError, match="run_id"):
        ImprovementCoordinator(FakeLedger(), FakeMail()).consider(record, score)
