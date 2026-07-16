from collections.abc import Callable
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
from typing import Any, Protocol
from urllib.parse import urlparse

from claw_gauntlet.adapters import JsonlMailTransport
from claw_gauntlet.evidence import EvidenceStore
from claw_gauntlet.handoff import HandoffEnvelope, artifact_refs_checksum


_LANES = {"community-sponsor", "company-pilot", "feedback"}
_REPOSITORY = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}$"
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE = re.compile(
    r"(?i)(api[_-]?key|auth[_-]?token|access[_-]?token|password|cookie|ct0)\s*[:=]"
)
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)


def _text(value: Any, field: str, *, maximum: int) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValueError(f"{field} exceeds the {maximum} character limit")
    if _SENSITIVE.search(normalized):
        raise ValueError(f"{field} contains sensitive token-like content")
    if _EMAIL.search(normalized):
        raise ValueError(f"{field} must not contain an email address")
    return normalized


def _https_url(value: Any, field: str, *, github_repository: bool = False) -> str:
    if type(value) is not str or len(value) > 2_048:
        raise ValueError(f"{field} must be a bounded HTTPS URL")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"{field} must be an HTTPS URL without credentials")
    if github_repository:
        repository = parsed.path.strip("/")
        if (
            parsed.netloc.casefold() != "github.com"
            or _REPOSITORY.fullmatch(repository) is None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(f"{field} must be a canonical public GitHub repository URL")
        return f"https://github.com/{repository}"
    return value


def _repository(value: Any) -> str:
    if type(value) is not str or _REPOSITORY.fullmatch(value) is None:
        raise ValueError("learning repository must use owner/repository format")
    return value


def _text_list(
    value: Any,
    field: str,
    *,
    minimum: int,
    maximum: int,
    item_limit: int,
) -> tuple[str, ...]:
    if type(value) is not list or not minimum <= len(value) <= maximum:
        raise ValueError(f"{field} must contain {minimum} to {maximum} items")
    return tuple(_text(item, f"{field} item", maximum=item_limit) for item in value)


def _url_list(value: Any, field: str) -> tuple[str, ...]:
    if type(value) is not list or not 1 <= len(value) <= 5:
        raise ValueError(f"{field} must contain 1 to 5 HTTPS URLs")
    return tuple(_https_url(item, field) for item in value)


@dataclass(frozen=True)
class SponsorCampaign:
    project_name: str
    repository_url: str
    description: str
    community_ask: str
    company_pilot: str
    price_range: str
    learning_repositories: tuple[str, ...]
    target_categories: tuple[str, ...]
    max_drafts: int

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SponsorCampaign":
        if type(payload) is not dict:
            raise ValueError("campaign must be an object")
        repositories = payload.get("learning_repositories")
        if type(repositories) is not list or not 1 <= len(repositories) <= 20:
            raise ValueError("learning_repositories must contain 1 to 20 repositories")
        max_drafts = payload.get("max_drafts")
        if type(max_drafts) is not int or not 1 <= max_drafts <= 5:
            raise ValueError("max_drafts must be an integer from 1 to 5")
        return cls(
            project_name=_text(payload.get("project_name"), "project_name", maximum=100),
            repository_url=_https_url(
                payload.get("repository_url"),
                "repository_url",
                github_repository=True,
            ),
            description=_text(payload.get("description"), "description", maximum=500),
            community_ask=_text(
                payload.get("community_ask"), "community_ask", maximum=500
            ),
            company_pilot=_text(
                payload.get("company_pilot"), "company_pilot", maximum=500
            ),
            price_range=_text(payload.get("price_range"), "price_range", maximum=80),
            learning_repositories=tuple(_repository(item) for item in repositories),
            target_categories=_text_list(
                payload.get("target_categories"),
                "target_categories",
                minimum=1,
                maximum=10,
                item_limit=100,
            ),
            max_drafts=max_drafts,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_name": self.project_name,
            "repository_url": self.repository_url,
            "description": self.description,
            "community_ask": self.community_ask,
            "company_pilot": self.company_pilot,
            "price_range": self.price_range,
            "learning_repositories": list(self.learning_repositories),
            "target_categories": list(self.target_categories),
            "max_drafts": self.max_drafts,
        }


@dataclass(frozen=True)
class SponsorProspect:
    name: str
    public_url: str
    lane: str
    fit_reason: str
    evidence_urls: tuple[str, ...]
    subject: str
    body: str
    confidence: int

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SponsorProspect":
        if type(payload) is not dict:
            raise ValueError("prospect must be an object")
        lane = payload.get("lane")
        if type(lane) is not str or lane not in _LANES:
            raise ValueError(f"lane must be one of {sorted(_LANES)}")
        confidence = payload.get("confidence")
        if type(confidence) is not int or not 0 <= confidence <= 100:
            raise ValueError("confidence must be an integer from 0 to 100")
        return cls(
            name=_text(payload.get("name"), "name", maximum=100),
            public_url=_https_url(payload.get("public_url"), "public_url"),
            lane=lane,
            fit_reason=_text(payload.get("fit_reason"), "fit_reason", maximum=500),
            evidence_urls=_url_list(payload.get("evidence_urls"), "evidence_urls"),
            subject=_text(payload.get("subject"), "subject", maximum=160),
            body=_text(payload.get("body"), "body", maximum=2_000),
            confidence=confidence,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "public_url": self.public_url,
            "lane": self.lane,
            "fit_reason": self.fit_reason,
            "evidence_urls": list(self.evidence_urls),
            "subject": self.subject,
            "body": self.body,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class SponsorResearchReport:
    summary: str
    prospects: tuple[SponsorProspect, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SponsorResearchReport":
        if type(payload) is not dict:
            raise ValueError("research report must be an object")
        prospects = payload.get("prospects")
        if type(prospects) is not list or len(prospects) > 5:
            raise ValueError("prospects must be a list containing at most 5 items")
        return cls(
            summary=_text(payload.get("summary"), "summary", maximum=1_000),
            prospects=tuple(SponsorProspect.from_dict(item) for item in prospects),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "prospects": [prospect.to_dict() for prospect in self.prospects],
        }


@dataclass(frozen=True)
class SponsorReview:
    draft_id: str
    draft_ref: str
    prospect_name: str
    public_url: str
    lane: str
    confidence: int

    def __post_init__(self) -> None:
        if type(self.draft_id) is not str or _DIGEST.fullmatch(self.draft_id) is None:
            raise ValueError("draft_id must be a lowercase SHA-256 digest")
        if not self.draft_ref.startswith("evidence://sha256/"):
            raise ValueError("draft_ref must be an evidence SHA-256 reference")
        _text(self.prospect_name, "prospect_name", maximum=100)
        _https_url(self.public_url, "public_url")
        if self.lane not in _LANES:
            raise ValueError("lane is unsupported")
        if type(self.confidence) is not int or not 0 <= self.confidence <= 100:
            raise ValueError("confidence must be an integer from 0 to 100")


class SponsorTaskPort(Protocol):
    def create_review(self, review: SponsorReview) -> Any: ...


@dataclass(frozen=True)
class SponsorCycleResult:
    status: str
    report_ref: str
    new_reviews: tuple[SponsorReview, ...]


class _SeenDrafts:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "seen.json"
        self.lock_path = root / ".seen.lock"

    def run_once(self, draft_id: str, action: Callable[[], None]) -> bool:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root.chmod(0o700)
        descriptor = os.open(
            self.lock_path,
            os.O_RDWR | os.O_CREAT | _O_CLOEXEC,
            mode=0o600,
        )
        try:
            os.fchmod(descriptor, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            seen = self._read()
            if draft_id in seen:
                return False
            action()
            seen.add(draft_id)
            self._write(seen)
            return True
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read(self) -> set[str]:
        if not self.path.exists():
            return set()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if type(payload) is not list or any(
            type(item) is not str or _DIGEST.fullmatch(item) is None for item in payload
        ):
            raise ValueError("sponsor seen state is malformed")
        return set(payload)

    def _write(self, seen: set[str]) -> None:
        temporary = self.root / f".seen.{secrets.token_hex(8)}.tmp"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_CLOEXEC,
            mode=0o600,
        )
        try:
            content = json.dumps(sorted(seen), separators=(",", ":")).encode("utf-8")
            with os.fdopen(descriptor, "wb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise


class SponsorCycle:
    def __init__(
        self,
        state_root: str | Path,
        *,
        task_ledger: SponsorTaskPort | None = None,
    ) -> None:
        self.state_root = Path(state_root)
        self.evidence_store = EvidenceStore(self.state_root / "evidence")
        self.mail = JsonlMailTransport(
            self.state_root / "mail" / "sponsor-approvals.jsonl"
        )
        self.seen = _SeenDrafts(self.state_root / "sponsorship")
        self.task_ledger = task_ledger

    def ingest(
        self,
        campaign: SponsorCampaign,
        report: SponsorResearchReport,
    ) -> SponsorCycleResult:
        if not isinstance(campaign, SponsorCampaign):
            raise TypeError("campaign must be a SponsorCampaign")
        if not isinstance(report, SponsorResearchReport):
            raise TypeError("report must be a SponsorResearchReport")
        report_reference = self.evidence_store.put_json(report.to_dict())
        candidates = sorted(
            report.prospects,
            key=lambda item: (-item.confidence, item.name.casefold(), item.public_url),
        )[: campaign.max_drafts]
        reviews: list[SponsorReview] = []
        for prospect in candidates:
            draft_id = _draft_id(prospect)
            draft_payload = {
                "schema": "claw.sponsor-draft.v1",
                "draft_id": draft_id,
                "campaign": {
                    "project_name": campaign.project_name,
                    "repository_url": campaign.repository_url,
                },
                "prospect": prospect.to_dict(),
                "research_report_ref": report_reference.uri,
                "status": "awaiting-review",
            }
            draft_reference = self.evidence_store.put_json(draft_payload)
            review = SponsorReview(
                draft_id=draft_id,
                draft_ref=draft_reference.uri,
                prospect_name=prospect.name,
                public_url=prospect.public_url,
                lane=prospect.lane,
                confidence=prospect.confidence,
            )

            def enqueue() -> None:
                handoff = HandoffEnvelope.create(
                    source="SponsorClaw",
                    destination="Owner",
                    artifact_refs=(review.draft_ref,),
                    requested_action="review-sponsor-outreach",
                    summary=(
                        f"Review {review.lane} draft for {review.prospect_name} "
                        f"(confidence {review.confidence})"
                    ),
                    provenance=prospect.evidence_urls,
                    checksum=artifact_refs_checksum((review.draft_ref,)),
                    approval_required=True,
                )
                if self.task_ledger is not None:
                    self.task_ledger.create_review(review)
                self.mail.send(handoff)

            if self.seen.run_once(draft_id, enqueue):
                reviews.append(review)
        return SponsorCycleResult(
            status="awaiting-review" if reviews else "no-new-drafts",
            report_ref=report_reference.uri,
            new_reviews=tuple(reviews),
        )


def _draft_id(prospect: SponsorProspect) -> str:
    identity = {
        "body": prospect.body,
        "evidence_urls": list(prospect.evidence_urls),
        "lane": prospect.lane,
        "public_url": prospect.public_url,
        "subject": prospect.subject,
    }
    canonical = json.dumps(
        identity,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(canonical).hexdigest()
