# GitHub public collection

GHClaw and StarClaw are experimental, anonymous, read-only GitHub connectors.
They use GitHub's versioned public REST API and retain a strict allowlist of
repository metadata. They do not clone repositories, read private resources,
list a repository's stargazers, or accept credentials.

## Collect a repository

```bash
uv run clawgauntlet github repo \
  --state-dir .claw-state \
  OWNER/REPOSITORY
```

The result includes an immutable evidence reference, a GHClaw run record, and a
short summary. The evidence contains public repository identity, description,
topics, declared SPDX license, language, archival/fork state, bounded activity
counts, and public timestamps.

## Snapshot a person's public stars

```bash
uv run clawgauntlet github stars \
  --state-dir .claw-state \
  steipete \
  --max-pages 2
```

Each page contains at most 100 repositories. `--max-pages` is restricted to
1–10. The response reports `complete: false` whenever the configured bound may
have truncated the list. A snapshot is a public bookmark watchlist, not an
endorsement by the account owner.

The library function `diff_star_snapshots(previous, current)` returns sorted
`added` and `removed` repository names. A scheduler can call the bounded
snapshot command later; scheduling is not part of the connector itself.

GitHub documents the public starred-repositories endpoint and its pagination at
<https://docs.github.com/en/rest/activity/starring>. The connector sends the
recommended GitHub JSON media type and a versioned API header. Anonymous rate
limits and GitHub policy still apply.

## Screen repository evidence for a public project

Create a public project brief:

```json
{
  "project_name": "Public Agent Workspace",
  "keywords": ["agents", "workflow", "swift"]
}
```

Then evaluate one GHClaw artifact:

```bash
uv run clawgauntlet project evaluate \
  --state-dir .claw-state \
  --artifact-ref evidence://sha256/REPLACE_WITH_64_HEX_DIGEST \
  --input project.json
```

ProjectClaw performs an explainable keyword screen and reports matched terms,
unmatched terms, license/archive risks, the source URL, and the exact evidence
reference. `candidate` means “inspect further,” not “install” or “adopt.” It
never edits the evaluated project.

Do not use this public workflow for a confidential project name or private
requirements unless its state directory and retention policy are explicitly
authorized for that data.
