from dataclasses import replace

import pytest

from claw_gauntlet.run_ledger import RunLedger, RunScore
from claw_gauntlet.run_record import RunRecord


INPUT_HASH = "sha256:c96c6d5be8d08a12e7b5cdc1b207fa6b2430974c86803d8891675e76fd992c20"
ARTIFACT_REF = "evidence://sha256/c7c5c1d70c5dec4416ab6158afd0b223ef40c29b1dc1f97ed9428b94d4cadb1c"


def _record() -> RunRecord:
    return RunRecord.create(
        claw_name="GHClaw",
        claw_version="0.1.0",
        input_hash=INPUT_HASH,
        artifact_refs=(ARTIFACT_REF,),
        outcome="success",
        duration_ms=20,
        retries=0,
        approvals_required=0,
        approvals_granted=0,
        permission_violations=0,
        human_corrections=0,
    )


def test_run_score_and_baseline_survive_reopen(tmp_path):
    path = tmp_path / "runs.duckdb"
    record = _record()
    score = RunScore(record.run_id, 100, 100, 100, 100)

    with RunLedger(path) as ledger:
        ledger.record_run(record)
        ledger.record_score(score)
        ledger.set_baseline("GHClaw", record.run_id)

    with RunLedger(path) as ledger:
        assert ledger.get_run(record.run_id) == record
        assert ledger.get_score(record.run_id) == score
        assert ledger.get_baseline("GHClaw") == record.run_id


def test_duplicate_run_is_idempotent_but_conflicting_payload_is_rejected(tmp_path):
    record = _record()

    with RunLedger(tmp_path / "runs.duckdb") as ledger:
        ledger.record_run(record)
        ledger.record_run(record)

        with pytest.raises(ValueError, match="conflicting run"):
            ledger.record_run(replace(record, outcome="failure"))

        assert ledger.get_run(record.run_id) == record


def test_missing_run_score_and_baseline_return_none(tmp_path):
    record = _record()

    with RunLedger(tmp_path / "runs.duckdb") as ledger:
        assert ledger.get_run(record.run_id) is None
        assert ledger.get_score(record.run_id) is None
        assert ledger.get_baseline("GHClaw") is None


@pytest.mark.parametrize("dimension", [-1, 101, True, 1.5])
def test_run_score_rejects_out_of_range_or_non_integer_dimensions(dimension):
    values = {
        "run_id": _record().run_id,
        "reliability": 100,
        "resilience": 100,
        "safety": 100,
        "overall": 100,
    }
    values["safety"] = dimension

    with pytest.raises(ValueError, match="safety"):
        RunScore(**values)
