# Capability index

This index describes executable behavior, not roadmap intent. Catalog entries
remain `planned` until their source or delivery connector ships with contract
tests.

| Command or API | Input | Output | Permission | Failure behavior | Owner |
| --- | --- | --- | --- | --- | --- |
| `clawgauntlet family --json` | none | sorted catalog JSON | none | argument error, exit 2 | `family.py`, `cli.py` |
| `clawgauntlet manifest NAME --json` | catalog name | one manifest | none | unknown name, exit 2 | `family.py`, `manifest.py` |
| `clawgauntlet evidence put` | JSON file, state directory | immutable evidence reference | local read/write | structured JSON error, exit 1 | `evidence.py`, `cli.py` |
| `clawgauntlet run record` | validated run JSON | persisted run record | local read/write | reject malformed or conflicting record | `run_record.py`, `run_ledger.py` |
| `clawgauntlet run score` | state directory, run ID | persisted RRS dimensions | local read/write | missing run or invalid state, exit 1 | `rrs.py`, `run_ledger.py` |
| `clawgauntlet run show` | state directory, run ID | run and optional score | local read | missing run, exit 1 | `run_ledger.py`, `cli.py` |
| `clawgauntlet improvement consider` | scored run, threshold | proposal plus reference-only handoff | local read/write | no proposal above threshold; structured error otherwise | `improvement.py`, `adapters.py` |
| `clawgauntlet github repo` | public `OWNER/REPOSITORY` | allowlisted repository evidence and scored run | anonymous network read, local write | reject private/malformed/oversized responses | `github_claws.py`, `cli.py` |
| `clawgauntlet github stars` | public username, 1–10 pages | bounded public-star snapshot and scored run | anonymous network read, local write | conservative incomplete marker at page bound | `github_claws.py`, `cli.py` |
| `clawgauntlet project evaluate` | GHClaw reference, public project brief | cited deterministic screening | local read/write | reject wrong schemas, missing evidence, malformed brief | `project_claw.py`, `cli.py` |
| `clawgauntlet publication bundle` | blog body or X thread plus evidence | immutable cited publication bundle and scored run | local read/write | reject unsafe URLs, missing evidence refs, or invalid bounds | `publication.py`, `cli.py` |
| `clawgauntlet publication request` | publication bundle reference | approval-required Publisher handoff | owner-only local write | reject missing or tampered bundles | `publication.py`, `adapters.py` |
| `EvidenceStore` | bytes or JSON | `evidence://sha256/...` | hardened POSIX local I/O | fail closed on integrity or containment changes | `evidence.py` |
| `RunLedger` | run and score objects | DuckDB persistence | local database I/O | reject conflicting or orphaned records | `run_ledger.py` |
| `BeadsTaskLedger` | improvement proposal | one `bd create` invocation | approved subprocess in selected checkout | redacted adapter error | `adapters.py` |
| `JsonlMailTransport` | handoff envelope | fsynced JSONL outbox entry | owner-only local write | reject token-like content | `adapters.py` |

The GitHub surface has anonymous read-only network permission. The remaining
working surface has no network permission, and no component has publishing,
credential, browser, merge, deployment, or outbound-publication permission.
HNClaw, RSSClaw, TrustClaw, DigestClaw, ReleaseClaw, DocsClaw, BlogAgent, and all
V2 connectors remain registered plans, not executable connectors. BlogClaw and
TwitterClaw currently build and request review of bundles; they cannot post.

`TweetClaw` is a conversational alias for the planned TwitterClaw workflow. It
is not a second component or a way around publisher approval.
