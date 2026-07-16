import json
import os

import pytest

from claw_gauntlet.evidence import EvidenceRef, EvidenceStore
from claw_gauntlet.sponsorship import (
    SponsorCampaign,
    SponsorCycle,
    SponsorProspect,
    SponsorResearchReport,
)


def _campaign_payload():
    return {
        "project_name": "Claw Gauntlet",
        "repository_url": "https://github.com/anupamchugh/claw-gauntlet",
        "description": "Evidence-backed capability intelligence for agentic projects.",
        "community_ask": "Support public fixtures, CI, and documentation.",
        "company_pilot": "A two-week evidence workflow setup for one repository.",
        "price_range": "$500-$1,500",
        "learning_repositories": [
            "obra/superpowers",
            "simonw/datasette",
            "sindresorhus/awesome",
        ],
        "target_categories": ["AI developer tools", "open-source programs"],
        "max_drafts": 3,
    }


def _prospect_payload(**overrides):
    payload = {
        "name": "Example Developer Tools",
        "public_url": "https://github.com/example",
        "lane": "company-pilot",
        "fit_reason": "The public repository documents agent workflow tooling.",
        "evidence_urls": [
            "https://github.com/example/tool",
            "https://example.com/open-source",
        ],
        "subject": "A bounded evidence-workflow pilot",
        "body": (
            "Hello Example team, I am building Claw Gauntlet, a local-first "
            "evidence layer for agent workflows. Your public tool repository "
            "suggests a relevant workflow problem. Would a short, bounded "
            "pilot be useful to evaluate? No external write access is needed."
        ),
        "confidence": 82,
    }
    payload.update(overrides)
    return payload


def _report_payload(prospects=None):
    return {
        "summary": "One evidence-backed company pilot candidate.",
        "prospects": prospects or [_prospect_payload()],
    }


def test_campaign_and_report_are_immutable_and_round_trip():
    campaign_payload = _campaign_payload()
    campaign = SponsorCampaign.from_dict(campaign_payload)
    report = SponsorResearchReport.from_dict(_report_payload())

    campaign_payload["learning_repositories"].append("example/late-mutation")

    assert campaign.learning_repositories == (
        "obra/superpowers",
        "simonw/datasette",
        "sindresorhus/awesome",
    )
    assert campaign.to_dict()["max_drafts"] == 3
    assert isinstance(report.prospects, tuple)
    assert SponsorResearchReport.from_dict(report.to_dict()) == report


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("repository_url", "http://github.com/example/tool", "repository_url"),
        ("repository_url", "https://gitlab.com/example/tool", "repository_url"),
        ("learning_repositories", ["https://github.com/example/tool"], "repository"),
        ("target_categories", [], "target_categories"),
        ("max_drafts", 0, "max_drafts"),
        ("max_drafts", 6, "max_drafts"),
        ("community_ask", "API_KEY=do-not-store", "sensitive"),
        ("company_pilot", "Contact me at owner@example.com", "email"),
    ],
)
def test_campaign_rejects_unsafe_or_unbounded_fields(field, value, message):
    payload = _campaign_payload()
    payload[field] = value

    with pytest.raises(ValueError, match=message):
        SponsorCampaign.from_dict(payload)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("public_url", "http://github.com/example", "public_url"),
        ("public_url", "https://user:pass@example.com", "public_url"),
        ("lane", "advertising", "lane"),
        ("evidence_urls", [], "evidence_urls"),
        ("evidence_urls", ["https://example.com"] * 6, "evidence_urls"),
        ("body", "Send using access_token=not-allowed", "sensitive"),
        ("body", "Contact private-person@example.com", "email"),
        ("confidence", -1, "confidence"),
        ("confidence", 101, "confidence"),
    ],
)
def test_prospect_rejects_unsafe_or_unbounded_fields(field, value, message):
    payload = _prospect_payload(**{field: value})

    with pytest.raises(ValueError, match=message):
        SponsorProspect.from_dict(payload)


def test_report_rejects_more_than_five_prospects():
    with pytest.raises(ValueError, match="at most 5"):
        SponsorResearchReport.from_dict(
            _report_payload([_prospect_payload(name=f"Prospect {index}") for index in range(6)])
        )


class _CapturedTasks:
    def __init__(self):
        self.reviews = []

    def create_review(self, review):
        self.reviews.append(review)


def test_cycle_stores_reference_only_approvals_and_deduplicates(tmp_path):
    state_root = tmp_path / "state"
    tasks = _CapturedTasks()
    campaign = SponsorCampaign.from_dict(_campaign_payload())
    report = SponsorResearchReport.from_dict(_report_payload())
    cycle = SponsorCycle(state_root, task_ledger=tasks)

    first = cycle.ingest(campaign, report)
    second = cycle.ingest(campaign, report)

    assert first.status == "awaiting-review"
    assert len(first.new_reviews) == 1
    assert second.status == "no-new-drafts"
    assert second.new_reviews == ()
    assert first.report_ref.startswith("evidence://sha256/")
    review = first.new_reviews[0]
    assert review.draft_ref.startswith("evidence://sha256/")
    assert review.lane == "company-pilot"
    assert tasks.reviews == [review]

    outbox = state_root / "mail" / "sponsor-approvals.jsonl"
    handoffs = [json.loads(line) for line in outbox.read_text().splitlines()]
    assert len(handoffs) == 1
    assert handoffs[0]["approval_required"] is True
    assert handoffs[0]["requested_action"] == "review-sponsor-outreach"
    assert handoffs[0]["artifact_refs"] == [review.draft_ref]
    assert report.prospects[0].body not in outbox.read_text()
    assert os.stat(outbox).st_mode & 0o777 == 0o600

    store = EvidenceStore(state_root / "evidence")
    reference = EvidenceRef("sha256", review.draft_ref.rsplit("/", 1)[-1])
    stored = store.get_json(reference)
    assert stored["draft_id"] == review.draft_id
    assert stored["prospect"] == report.prospects[0].to_dict()


def test_cycle_honors_campaign_limit_in_confidence_order(tmp_path):
    campaign_payload = _campaign_payload()
    campaign_payload["max_drafts"] = 1
    campaign = SponsorCampaign.from_dict(campaign_payload)
    report = SponsorResearchReport.from_dict(
        _report_payload(
            [
                _prospect_payload(name="Lower confidence", confidence=40),
                _prospect_payload(
                    name="Higher confidence",
                    public_url="https://github.com/higher",
                    confidence=90,
                ),
            ]
        )
    )

    result = SponsorCycle(tmp_path / "state").ingest(campaign, report)

    assert len(result.new_reviews) == 1
    assert result.new_reviews[0].prospect_name == "Higher confidence"
