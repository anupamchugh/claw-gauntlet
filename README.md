# Claw Gauntlet

Claw Gauntlet is an early, local-first foundation for building evidence-backed
agent capabilities. A **Claw** is a small, versioned capability with an explicit
input, output, permission boundary, and failure contract. The gauntlet records
what happened so a person or another agent can inspect the evidence instead of
trusting a confident summary.

> **Alpha status:** this repository is a foundation under active development.
> The catalog describes the intended family, but catalog registration does not
> mean a connector is available.

## What works today

- A semantically versioned catalog of immutable capability manifests.
- Versioned, validated handoff envelopes and run records.
- A POSIX-only local content-addressed evidence store with canonical JSON,
  SHA-256 references, integrity verification, and path-hardening tests.
- A DuckDB run ledger, deterministic Reliability/Resilience/Safety scoring,
  bounded improvement proposals, and reference-only Agent Mail outboxes.
- Anonymous, read-only GHClaw and StarClaw collection plus deterministic,
  cited ProjectClaw screening of public repository evidence.
- Immutable BlogClaw and TwitterClaw draft bundles with reference-only,
  approval-required Publisher requests.
- Read-only SponsorClaw research with strict reports, deduplicated draft
  evidence, optional Beads review tasks, and a local approval inbox.
- JSON CLI commands for inspecting the catalog and exercising the local
  evidence-to-improvement workflow.

Working components report `experimental`; unimplemented catalog entries remain
`planned`. Outbound publishing is not implemented.

## Quick start

Claw Gauntlet requires Python 3.12 and
[`uv`](https://docs.astral.sh/uv/getting-started/installation/). The catalog CLI
is portable across supported Python platforms. `EvidenceStore` and its tests
currently require POSIX descriptor-relative, no-follow I/O, so use Linux or
macOS for the full suite.

```bash
git clone https://github.com/anupamchugh/claw-gauntlet.git
cd claw-gauntlet
uv sync --locked
uv run pytest -q
uv run clawgauntlet family --json
uv run clawgauntlet manifest rrsclaw --json
```

The commands print structured JSON. The stateful commands require an
explicit `--state-dir`; see the [local foundation workflow](docs/foundation.md).
GitHub commands collect only public metadata through anonymous read-only API
requests. No command contacts a publishing platform or uses credentials.

## RSSClaw and RRSClaw

The similar names have different jobs:

- **RSSClaw** is the planned collection boundary for public RSS, Atom, JSON
  Feed, newsletter, and YouTube-upload transports. It will normalize their
  metadata into a common entry format.
- **RRSClaw** means Reliability, Resilience, and Safety Claw. It is the planned
  evaluator for run completion, reproducibility, provenance, recovery,
  permissions, corrections, cost, and latency.

A newsletter is a transport, not a separate knowledge type. The planned order
is advertised RSS/Atom first, publisher feeds next, an approved mailbox for
email-only sources, and a public archive as a final fallback. Planned YouTube
support uses public channel upload feeds for discovery. Neither newsletter nor
YouTube collection is implemented yet.

## Architecture

```text
public GitHub source
    -> bounded anonymous collector (working)
    -> normalized repository evidence reference (working)
    -> content-addressed EvidenceStore (working)
    -> RunRecord and handoff (working)
    -> RRS evaluation (working)
    -> human-approved delivery (planned)
```

The important boundary is between untrusted source material and authority.
Collectors should not hold publishing credentials. Evidence is passed by
immutable reference, permissions stay least-privileged, and external actions
require explicit human approval.

## Planned source packs

The design includes curated, public-only packs for engineering blogs, AI labs,
builder essays, feeds and newsletters, and public video-upload metadata. A
source pack is a reviewed set of canonical seeds and discovery rules—not a copy
of third-party articles and not proof that a connector ships today.

The roadmap also covers GitHub stars and repositories, Hacker News research,
papers, digests, documentation, releases, approved social bundles, and
provider-neutral visual assets. These remain planned until their manifest
status and capability documentation say otherwise.

## Project documents

- [V1/V2 design and safety model](docs/superpowers/specs/2026-07-16-claw-family-v1-v2-design.md)
- [Incremental foundation plan](docs/superpowers/plans/2026-07-16-claw-foundation-v1.md)
- [Local foundation workflow](docs/foundation.md)
- [Working capability index](docs/capabilities.md)
- [GitHub public collection and project screening](docs/github.md)
- [BlogClaw and TwitterClaw publishing workflow](docs/publishing.md)
- [SponsorClaw funding and autonomous review loop](docs/sponsorship.md)
- [Curated agentic startup operating stack](docs/startup-operating-stack.md)
- [Reviewed Gas Town execution](docs/gastown.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Support and sponsorship](SUPPORT.md)

## License

[MIT](LICENSE). Source content collected by future adapters will retain its own
copyright and license; this project license does not grant rights to republish
third-party material.
