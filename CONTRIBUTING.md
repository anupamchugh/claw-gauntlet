# Contributing

Claw Gauntlet is building a small, inspectable foundation before adding broad
automation. Contributions are welcome when they preserve that boundary.

## Before opening a change

Open an issue for a new Claw, provider, permission, protocol field, or external
side effect. Describe the capability boundary, expected evidence, failure
behavior, and why an existing Claw or adapter cannot own it.

Keep changes reviewable. Prefer one coherent model, adapter, test group, or
documentation slice per pull request. Split a feature before its implementation
diff approaches roughly 1,500 changed lines; generated artifacts are the main
exception.

## Development

Use Python 3.12 and `uv`:

```bash
uv sync --locked
uv run pytest -q
uv run python -m compileall -q src tests
git diff --check "$(git merge-base origin/main HEAD)"...HEAD
```

Add tests before or with behavior changes. Public interfaces need success,
validation, failure, and privacy-boundary coverage.

## Evidence and fixtures

- Use public, minimal, license-compatible fixtures. Do not commit scraped
  articles, private repository data, personal exports, access tokens, cookies,
  mailbox contents, or proprietary datasets.
- Record source provenance and observation time when a test depends on an
  external format. Prefer a small synthetic fixture derived from a documented
  schema over a mutable live request.
- Preserve canonical URLs, content hashes, and explicit source attribution.
  Never remove provenance to make deduplication easier.
- Treat all collected content as untrusted input. A parser or collector must not
  share credentials or publishing authority.

## Permissions and external actions

Declare the smallest permission set a capability needs. Network access,
credentials, repository writes, messages, posts, votes, purchases, and other
external effects require explicit boundaries and human approval. Claw Gauntlet
must not autonomously manufacture engagement, contact people, or publish on a
contributor's behalf.

## Pull requests

Explain the scope and non-goals, link the issue, show test evidence, and call
out new permissions or data retention. Update the manifest, capability docs,
and protocol version when the public contract changes. A catalog entry stays
`planned` until its working implementation, tests, permissions, and failure
behavior are documented.

By contributing, you agree that your contribution is licensed under the MIT
License in this repository.
