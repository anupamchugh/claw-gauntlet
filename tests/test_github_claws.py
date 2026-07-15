from datetime import datetime, timezone

import pytest

from claw_gauntlet.github_claws import (
    GitHubPublicCollector,
    diff_star_snapshots,
)


def _repo(name="example/tool", **overrides):
    payload = {
        "full_name": name,
        "private": False,
        "visibility": "public",
        "html_url": f"https://github.com/{name}",
        "description": "A reliable agent workflow tool",
        "topics": ["agents", "workflow"],
        "license": {"spdx_id": "MIT"},
        "language": "Python",
        "archived": False,
        "fork": False,
        "stargazers_count": 42,
        "forks_count": 3,
        "open_issues_count": 2,
        "pushed_at": "2026-07-15T12:00:00Z",
        "default_branch": "main",
    }
    payload.update(overrides)
    return payload


def test_collect_public_repository_normalizes_a_bounded_allowlist():
    requested = []

    def fetch(url):
        requested.append(url)
        return _repo(untrusted_field="must not leak")

    collector = GitHubPublicCollector(
        fetch_json=fetch,
        now=lambda: datetime(2026, 7, 16, tzinfo=timezone.utc),
    )

    evidence = collector.repository("example/tool")

    assert requested == ["https://api.github.com/repos/example/tool"]
    assert evidence == {
        "archived": False,
        "default_branch": "main",
        "description": "A reliable agent workflow tool",
        "fork": False,
        "forks_count": 3,
        "full_name": "example/tool",
        "html_url": "https://github.com/example/tool",
        "language": "Python",
        "license_spdx": "MIT",
        "observed_at": "2026-07-16T00:00:00Z",
        "open_issues_count": 2,
        "pushed_at": "2026-07-15T12:00:00Z",
        "schema": "claw.evidence.github-repository.v1",
        "source_url": "https://api.github.com/repos/example/tool",
        "stargazers_count": 42,
        "topics": ["agents", "workflow"],
    }
    assert "untrusted_field" not in evidence


def test_collect_stars_is_bounded_and_diffable():
    pages = {
        "https://api.github.com/users/obra/starred?direction=desc&page=1&per_page=100&sort=created": [
            _repo("one/alpha"),
            _repo("two/beta"),
        ],
        "https://api.github.com/users/obra/starred?direction=desc&page=2&per_page=100&sort=created": [],
    }
    collector = GitHubPublicCollector(
        fetch_json=pages.__getitem__,
        now=lambda: datetime(2026, 7, 16, tzinfo=timezone.utc),
    )

    current = collector.starred("obra", max_pages=2)
    previous = {
        **current,
        "repositories": [_repo("one/alpha"), _repo("old/gone")],
    }
    delta = diff_star_snapshots(previous, current)

    assert [repo["full_name"] for repo in current["repositories"]] == [
        "one/alpha",
        "two/beta",
    ]
    assert current["complete"] is True
    assert delta == {"added": ["two/beta"], "removed": ["old/gone"]}


@pytest.mark.parametrize("value", ["", "../secret", "owner", "https://github.com/o/r"])
def test_repository_slug_rejects_noncanonical_input(value):
    collector = GitHubPublicCollector(fetch_json=lambda _: {})
    with pytest.raises(ValueError, match="owner/repository"):
        collector.repository(value)


def test_private_repository_payload_fails_closed():
    collector = GitHubPublicCollector(fetch_json=lambda _: _repo(private=True))
    with pytest.raises(ValueError, match="public repository"):
        collector.repository("example/tool")
