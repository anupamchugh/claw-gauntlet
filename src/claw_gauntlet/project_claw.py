import re
from typing import Any


_EVIDENCE_REF = re.compile(r"^evidence://sha256/[0-9a-f]{64}$")


def _nonempty(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def evaluate_repository(
    evidence: dict[str, Any],
    *,
    project_name: str,
    keywords: list[str],
    artifact_ref: str,
) -> dict[str, Any]:
    """Create a deterministic, cited screening result, not an adoption verdict."""

    if type(evidence) is not dict or evidence.get("schema") != "claw.evidence.github-repository.v1":
        raise ValueError("evidence must use the github-repository v1 schema")
    project_name = _nonempty(project_name, "project_name")
    if type(keywords) is not list or not keywords:
        raise ValueError("keywords must be a non-empty list")
    normalized_keywords = []
    for keyword in keywords:
        normalized = _nonempty(keyword, "keyword").casefold()
        if normalized not in normalized_keywords:
            normalized_keywords.append(normalized)
    if type(artifact_ref) is not str or _EVIDENCE_REF.fullmatch(artifact_ref) is None:
        raise ValueError("artifact_ref must be an evidence SHA-256 reference")

    corpus = " ".join(
        str(value or "")
        for value in (
            evidence.get("full_name"),
            evidence.get("description"),
            evidence.get("language"),
            " ".join(evidence.get("topics", [])),
        )
    ).casefold()
    matched = [keyword for keyword in normalized_keywords if keyword in corpus]
    unmatched = [keyword for keyword in normalized_keywords if keyword not in corpus]
    risks = []
    if evidence.get("archived") is True:
        risks.append("archived")
    if not evidence.get("license_spdx") or evidence.get("license_spdx") == "NOASSERTION":
        risks.append("license-not-declared")

    if "archived" in risks:
        decision = "reject"
    elif risks:
        decision = "review"
    elif matched:
        decision = "candidate"
    else:
        decision = "unmatched"

    return {
        "schema": "claw.evaluation.project-repository.v1",
        "project_name": project_name,
        "repository": evidence.get("full_name"),
        "decision": decision,
        "matched_keywords": matched,
        "unmatched_keywords": unmatched,
        "risks": risks,
        "confidence": "deterministic-keyword-match",
        "artifact_refs": [artifact_ref],
        "source_urls": [evidence.get("html_url")],
    }
