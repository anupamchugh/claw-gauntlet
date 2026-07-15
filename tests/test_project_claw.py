import pytest

from claw_gauntlet.project_claw import evaluate_repository


def _evidence(**overrides):
    payload = {
        "schema": "claw.evidence.github-repository.v1",
        "full_name": "example/tool",
        "html_url": "https://github.com/example/tool",
        "description": "A reliable workflow for coordinating agents",
        "topics": ["agents", "workflow"],
        "language": "Python",
        "license_spdx": "MIT",
        "archived": False,
    }
    payload.update(overrides)
    return payload


def test_project_evaluation_is_cited_and_explainable():
    result = evaluate_repository(
        _evidence(),
        project_name="Public Agent Workspace",
        keywords=["agents", "swift", "workflow"],
        artifact_ref="evidence://sha256/" + "a" * 64,
    )

    assert result["decision"] == "candidate"
    assert result["matched_keywords"] == ["agents", "workflow"]
    assert result["unmatched_keywords"] == ["swift"]
    assert result["artifact_refs"] == ["evidence://sha256/" + "a" * 64]
    assert result["confidence"] == "deterministic-keyword-match"


def test_project_evaluation_routes_archived_or_unlicensed_repositories_to_review():
    archived = evaluate_repository(
        _evidence(archived=True),
        project_name="Public Project",
        keywords=["agents"],
        artifact_ref="evidence://sha256/" + "b" * 64,
    )
    unlicensed = evaluate_repository(
        _evidence(license_spdx=None),
        project_name="Public Project",
        keywords=["agents"],
        artifact_ref="evidence://sha256/" + "c" * 64,
    )

    assert archived["decision"] == "reject"
    assert "archived" in archived["risks"]
    assert unlicensed["decision"] == "review"
    assert "license-not-declared" in unlicensed["risks"]


def test_project_evaluation_rejects_the_wrong_evidence_schema():
    with pytest.raises(ValueError, match="github-repository"):
        evaluate_repository(
            {"schema": "other"},
            project_name="Public Project",
            keywords=["agents"],
            artifact_ref="evidence://sha256/" + "d" * 64,
        )
