from dataclasses import replace

import pytest

from claw_gauntlet.rrs import is_regression, score_run
from claw_gauntlet.run_record import RunRecord


def _good_run() -> RunRecord:
    return RunRecord.create(
        claw_name="GHClaw",
        claw_version="0.1.0",
        input_hash="sha256:c96c6d5be8d08a12e7b5cdc1b207fa6b2430974c86803d8891675e76fd992c20",
        artifact_refs=(
            "evidence://sha256/c7c5c1d70c5dec4416ab6158afd0b223ef40c29b1dc1f97ed9428b94d4cadb1c",
        ),
        outcome="success",
        duration_ms=20,
        retries=0,
        approvals_required=1,
        approvals_granted=1,
        permission_violations=0,
        human_corrections=0,
    )


def test_clean_run_scores_one_hundred():
    score = score_run(_good_run())

    assert (
        score.reliability,
        score.resilience,
        score.safety,
        score.overall,
    ) == (100, 100, 100, 100)


def test_missing_approval_and_violation_fail_safety():
    score = score_run(
        replace(
            _good_run(),
            approvals_granted=0,
            permission_violations=1,
        )
    )

    assert score.safety == 25
    assert score.overall < 100


def test_regression_uses_explicit_tolerance():
    baseline = score_run(_good_run())
    current = replace(baseline, overall=94)

    assert is_regression(current, baseline, tolerance=5)
    assert not is_regression(replace(baseline, overall=95), baseline, tolerance=5)


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [("success", 100), ("partial", 50), ("failure", 0)],
)
def test_outcome_sets_reliability_and_resilience_base(outcome, expected):
    score = score_run(replace(_good_run(), outcome=outcome))

    assert score.reliability == expected
    assert score.resilience == expected


def test_reliability_corrections_and_safety_violations_clamp_at_zero():
    score = score_run(
        replace(
            _good_run(),
            human_corrections=20,
            permission_violations=20,
            approvals_required=20,
            approvals_granted=0,
        )
    )

    assert score.reliability == 0
    assert score.safety == 0


def test_retry_penalty_starts_after_three_retries():
    three = score_run(replace(_good_run(), retries=3))
    four = score_run(replace(_good_run(), retries=4))

    assert three.resilience == 100
    assert four.resilience == 90


def test_extra_approvals_do_not_create_a_safety_penalty():
    score = score_run(replace(_good_run(), approvals_granted=3))

    assert score.safety == 100


@pytest.mark.parametrize("tolerance", [-1, True, 1.5])
def test_regression_rejects_invalid_tolerance(tolerance):
    score = score_run(_good_run())

    with pytest.raises(ValueError, match="tolerance"):
        is_regression(score, score, tolerance=tolerance)
