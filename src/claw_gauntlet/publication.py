from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any
from urllib.parse import urlparse

from claw_gauntlet.handoff import HandoffEnvelope, artifact_refs_checksum


_CHANNELS = {"blog", "twitter"}
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_EVIDENCE_REF = re.compile(r"^evidence://sha256/[0-9a-f]{64}$")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("publication time must be a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_timestamp(value: Any) -> str:
    if type(value) is not str or not value.endswith("Z"):
        raise ValueError("created_at must be a UTC ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("created_at must be a UTC ISO-8601 timestamp") from error
    if parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("created_at must be a UTC ISO-8601 timestamp")
    return value


def _nonempty(value: Any, field: str, *, maximum: int) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{field} exceeds the {maximum} character limit")
    return value


def _canonical_hash(value: Any, *, prefix: bool) -> str:
    canonical = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = sha256(canonical).hexdigest()
    return f"sha256:{digest}" if prefix else digest


def _source_urls(value: Any) -> tuple[str, ...]:
    if type(value) not in (list, tuple) or not value or len(value) > 50:
        raise ValueError("source_urls must contain 1 to 50 HTTPS URLs")
    urls = tuple(value)
    for url in urls:
        if type(url) is not str:
            raise ValueError("source_urls must contain only HTTPS URLs")
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("source_urls must contain only HTTPS URLs without credentials")
    return urls


def _artifact_refs(value: Any) -> tuple[str, ...]:
    if type(value) not in (list, tuple) or not value or len(value) > 50:
        raise ValueError("artifact_refs must contain 1 to 50 evidence references")
    refs = tuple(value)
    if any(type(ref) is not str or _EVIDENCE_REF.fullmatch(ref) is None for ref in refs):
        raise ValueError("artifact_refs must contain only evidence SHA-256 references")
    return refs


def _content(channel: str, value: Any) -> tuple[str, ...]:
    if type(value) not in (list, tuple) or not value:
        raise ValueError("content must be a non-empty list")
    items = tuple(_nonempty(item, "content item", maximum=100_000) for item in value)
    if channel == "blog" and len(items) != 1:
        raise ValueError("blog bundles require exactly one content item")
    if channel == "twitter":
        if len(items) > 20:
            raise ValueError("twitter bundles support at most 20 posts")
        if any(len(item) > 280 for item in items):
            raise ValueError("twitter content items must not exceed 280 characters")
    return items


@dataclass(frozen=True)
class PublicationBundle:
    bundle_id: str
    created_at: str
    protocol_version: str
    channel: str
    title: str
    content: tuple[str, ...]
    content_hash: str
    artifact_refs: tuple[str, ...]
    source_urls: tuple[str, ...]
    approval_required: bool

    def __post_init__(self) -> None:
        if type(self.channel) is not str or self.channel not in _CHANNELS:
            raise ValueError("channel must be blog or twitter")
        created_at = _validate_timestamp(self.created_at)
        title = _nonempty(self.title, "title", maximum=200)
        content = _content(self.channel, self.content)
        refs = _artifact_refs(self.artifact_refs)
        urls = _source_urls(self.source_urls)
        if self.protocol_version != "1.0.0":
            raise ValueError("unsupported publication protocol version")
        if type(self.approval_required) is not bool or not self.approval_required:
            raise ValueError("publication bundles must require approval")
        expected_content_hash = _canonical_hash(list(content), prefix=True)
        if self.content_hash != expected_content_hash or _SHA256.fullmatch(self.content_hash) is None:
            raise ValueError("content_hash does not match publication content")
        identity = {
            "approval_required": True,
            "artifact_refs": list(refs),
            "channel": self.channel,
            "content_hash": self.content_hash,
            "created_at": created_at,
            "protocol_version": self.protocol_version,
            "source_urls": list(urls),
            "title": title,
        }
        expected_bundle_id = _canonical_hash(identity, prefix=False)
        if self.bundle_id != expected_bundle_id or _DIGEST.fullmatch(self.bundle_id) is None:
            raise ValueError("bundle_id does not match publication metadata")
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "artifact_refs", refs)
        object.__setattr__(self, "source_urls", urls)

    @classmethod
    def create(
        cls,
        *,
        channel: str,
        title: str,
        content: list[str] | tuple[str, ...],
        artifact_refs: list[str] | tuple[str, ...],
        source_urls: list[str] | tuple[str, ...],
        now: Callable[[], datetime] = _utc_now,
    ) -> "PublicationBundle":
        if channel not in _CHANNELS:
            raise ValueError("channel must be blog or twitter")
        created_at = _timestamp(now())
        title = _nonempty(title, "title", maximum=200)
        normalized_content = _content(channel, content)
        normalized_refs = _artifact_refs(artifact_refs)
        normalized_urls = _source_urls(source_urls)
        content_hash = _canonical_hash(list(normalized_content), prefix=True)
        identity = {
            "approval_required": True,
            "artifact_refs": list(normalized_refs),
            "channel": channel,
            "content_hash": content_hash,
            "created_at": created_at,
            "protocol_version": "1.0.0",
            "source_urls": list(normalized_urls),
            "title": title,
        }
        return cls(
            bundle_id=_canonical_hash(identity, prefix=False),
            created_at=created_at,
            protocol_version="1.0.0",
            channel=channel,
            title=title,
            content=normalized_content,
            content_hash=content_hash,
            artifact_refs=normalized_refs,
            source_urls=normalized_urls,
            approval_required=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "protocol_version": self.protocol_version,
            "channel": self.channel,
            "title": self.title,
            "content": list(self.content),
            "content_hash": self.content_hash,
            "artifact_refs": list(self.artifact_refs),
            "source_urls": list(self.source_urls),
            "approval_required": self.approval_required,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PublicationBundle":
        if type(payload) is not dict:
            raise ValueError("publication bundle must be an object")
        return cls(
            bundle_id=payload["bundle_id"],
            created_at=payload["created_at"],
            protocol_version=payload["protocol_version"],
            channel=payload["channel"],
            title=payload["title"],
            content=payload["content"],
            content_hash=payload["content_hash"],
            artifact_refs=payload["artifact_refs"],
            source_urls=payload["source_urls"],
            approval_required=payload["approval_required"],
        )


def publisher_request(
    bundle: PublicationBundle,
    *,
    bundle_ref: str,
) -> HandoffEnvelope:
    if not isinstance(bundle, PublicationBundle):
        raise TypeError("bundle must be a PublicationBundle")
    refs = _artifact_refs([bundle_ref])
    source = "BlogClaw" if bundle.channel == "blog" else "TwitterClaw"
    return HandoffEnvelope.create(
        source=source,
        destination="Publisher",
        artifact_refs=refs,
        requested_action="review-publication",
        summary=f"Review {bundle.channel} bundle: {bundle.title}",
        provenance=bundle.source_urls,
        checksum=artifact_refs_checksum(refs),
        approval_required=True,
    )
