from collections.abc import Callable
from datetime import datetime, timezone
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


_API_ROOT = "https://api.github.com"
_API_VERSION = "2026-03-10"
_OWNER = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


class GitHubAPIError(RuntimeError):
    """A bounded, non-secret GitHub API failure."""


def _default_fetch_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "claw-gauntlet/0.1.0",
            "X-GitHub-Api-Version": _API_VERSION,
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            content = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        raise GitHubAPIError(
            f"GitHub API request failed with HTTP {error.code}"
        ) from error
    except URLError as error:
        raise GitHubAPIError("GitHub API request failed") from error
    if len(content) > _MAX_RESPONSE_BYTES:
        raise GitHubAPIError("GitHub API response exceeded the 4 MiB limit")
    try:
        return json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise GitHubAPIError("GitHub API returned invalid JSON") from error


def _utc_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime):
        raise TypeError("now must return a datetime")
    if value.tzinfo is None:
        raise ValueError("now must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _slug(value: str) -> tuple[str, str]:
    if type(value) is not str:
        raise ValueError("repository must use owner/repository format")
    parts = value.split("/")
    if (
        len(parts) != 2
        or _OWNER.fullmatch(parts[0]) is None
        or _REPOSITORY.fullmatch(parts[1]) is None
    ):
        raise ValueError("repository must use owner/repository format")
    return parts[0], parts[1]


def _username(value: str) -> str:
    if type(value) is not str or _OWNER.fullmatch(value) is None:
        raise ValueError("username must be a canonical GitHub account name")
    return value


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is not None and type(value) is not str:
        raise ValueError(f"GitHub field {key} must be a string or null")
    return value


def _integer(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if type(value) is not int or value < 0:
        raise ValueError(f"GitHub field {key} must be a nonnegative integer")
    return value


def _normalize_repository(
    payload: Any,
    *,
    observed_at: str,
    source_url: str | None = None,
) -> dict[str, Any]:
    if type(payload) is not dict:
        raise ValueError("GitHub repository response must be an object")
    if payload.get("private") is not False or payload.get("visibility") not in (
        None,
        "public",
    ):
        raise ValueError("GHClaw accepts only a public repository payload")
    full_name = payload.get("full_name")
    owner, repository = _slug(full_name)
    canonical_name = f"{owner}/{repository}"
    html_url = payload.get("html_url")
    if html_url != f"https://github.com/{canonical_name}":
        raise ValueError("GitHub html_url must match the public repository")
    topics = payload.get("topics", [])
    if type(topics) is not list or any(type(item) is not str for item in topics):
        raise ValueError("GitHub topics must be a list of strings")
    license_payload = payload.get("license")
    if license_payload is None:
        license_spdx = None
    elif type(license_payload) is dict:
        license_spdx = _optional_string(license_payload, "spdx_id")
    else:
        raise ValueError("GitHub license must be an object or null")
    return {
        "schema": "claw.evidence.github-repository.v1",
        "source_url": source_url or f"{_API_ROOT}/repos/{canonical_name}",
        "observed_at": observed_at,
        "full_name": canonical_name,
        "html_url": html_url,
        "description": _optional_string(payload, "description"),
        "topics": sorted(set(topics), key=str.casefold),
        "license_spdx": license_spdx,
        "language": _optional_string(payload, "language"),
        "archived": payload.get("archived") is True,
        "fork": payload.get("fork") is True,
        "stargazers_count": _integer(payload, "stargazers_count"),
        "forks_count": _integer(payload, "forks_count"),
        "open_issues_count": _integer(payload, "open_issues_count"),
        "pushed_at": _optional_string(payload, "pushed_at"),
        "default_branch": _optional_string(payload, "default_branch"),
    }


class GitHubPublicCollector:
    """Anonymous, read-only collection of public GitHub evidence."""

    def __init__(
        self,
        *,
        fetch_json: Callable[[str], Any] = _default_fetch_json,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._fetch_json = fetch_json
        self._now = now

    def repository(self, repository: str) -> dict[str, Any]:
        owner, name = _slug(repository)
        source_url = f"{_API_ROOT}/repos/{owner}/{name}"
        payload = self._fetch_json(source_url)
        return _normalize_repository(
            payload,
            observed_at=_utc_timestamp(self._now()),
            source_url=source_url,
        )

    def starred(self, username: str, *, max_pages: int = 1) -> dict[str, Any]:
        username = _username(username)
        if type(max_pages) is not int or not 1 <= max_pages <= 10:
            raise ValueError("max_pages must be an integer from 1 to 10")
        observed_at = _utc_timestamp(self._now())
        repositories: list[dict[str, Any]] = []
        complete = False
        for page in range(1, max_pages + 1):
            query = urlencode(
                {
                    "direction": "desc",
                    "page": page,
                    "per_page": 100,
                    "sort": "created",
                }
            )
            source_url = f"{_API_ROOT}/users/{username}/starred?{query}"
            payload = self._fetch_json(source_url)
            if type(payload) is not list:
                raise ValueError("GitHub starred response must be a list")
            repositories.extend(
                _normalize_repository(item, observed_at=observed_at)
                for item in payload
            )
            if len(payload) < 100:
                complete = True
                break
        return {
            "schema": "claw.evidence.github-stars.v1",
            "source_url": f"https://github.com/{username}?tab=stars",
            "observed_at": observed_at,
            "username": username,
            "complete": complete,
            "repositories": repositories,
        }


def diff_star_snapshots(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, list[str]]:
    for name, snapshot in (("previous", previous), ("current", current)):
        if type(snapshot) is not dict or snapshot.get("schema") != "claw.evidence.github-stars.v1":
            raise ValueError(f"{name} must be a GitHub stars snapshot")
        if type(snapshot.get("repositories")) is not list:
            raise ValueError(f"{name} repositories must be a list")
    previous_names = {item["full_name"] for item in previous["repositories"]}
    current_names = {item["full_name"] for item in current["repositories"]}
    return {
        "added": sorted(current_names - previous_names, key=str.casefold),
        "removed": sorted(previous_names - current_names, key=str.casefold),
    }
