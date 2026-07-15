from datetime import datetime, timezone

import pytest

from claw_gauntlet.publication import PublicationBundle, publisher_request


_REF = "evidence://sha256/" + "a" * 64


def test_blog_bundle_round_trips_with_a_content_hash_and_sources():
    bundle = PublicationBundle.create(
        channel="blog",
        title="Claws become a system",
        content=["A cited draft with an explicit human approval boundary."],
        artifact_refs=[_REF],
        source_urls=["https://github.com/example/tool"],
        now=lambda: datetime(2026, 7, 16, tzinfo=timezone.utc),
    )

    assert bundle.channel == "blog"
    assert bundle.approval_required is True
    assert bundle.content_hash.startswith("sha256:")
    assert PublicationBundle.from_dict(bundle.to_dict()) == bundle
    malformed = {**bundle.to_dict(), "created_at": "not-a-timestamp"}
    with pytest.raises(ValueError, match="created_at"):
        PublicationBundle.from_dict(malformed)


def test_twitter_bundle_supports_a_thread_but_rejects_oversized_posts():
    bundle = PublicationBundle.create(
        channel="twitter",
        title="Release thread",
        content=["First cited post.", "Second cited post."],
        artifact_refs=[_REF],
        source_urls=["https://github.com/example/tool"],
        now=lambda: datetime(2026, 7, 16, tzinfo=timezone.utc),
    )

    assert bundle.content == ("First cited post.", "Second cited post.")
    with pytest.raises(ValueError, match="280"):
        PublicationBundle.create(
            channel="twitter",
            title="Too long",
            content=["x" * 281],
            artifact_refs=[_REF],
            source_urls=["https://example.com/source"],
        )


@pytest.mark.parametrize(
    "source_url",
    [
        "http://example.com/source",
        "https://user:secret@example.com/source",
        "file:///private/source",
    ],
)
def test_publication_bundle_rejects_unsafe_source_urls(source_url):
    with pytest.raises(ValueError, match="HTTPS"):
        PublicationBundle.create(
            channel="blog",
            title="Draft",
            content=["Body"],
            artifact_refs=[_REF],
            source_urls=[source_url],
        )


def test_publisher_request_is_reference_only_and_requires_approval():
    bundle = PublicationBundle.create(
        channel="twitter",
        title="Release thread",
        content=["Cited post."],
        artifact_refs=[_REF],
        source_urls=["https://github.com/example/tool"],
        now=lambda: datetime(2026, 7, 16, tzinfo=timezone.utc),
    )
    bundle_ref = "evidence://sha256/" + "b" * 64

    request = publisher_request(bundle, bundle_ref=bundle_ref)

    assert request.source == "TwitterClaw"
    assert request.destination == "Publisher"
    assert request.artifact_refs == (bundle_ref,)
    assert request.approval_required is True
    assert "Cited post" not in str(request.to_dict())
