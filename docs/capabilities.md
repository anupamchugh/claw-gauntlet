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
| `clawgauntlet sponsor research` | bounded public campaign, state and workspace paths | strict report, draft evidence, approval handoffs | read-only Codex web/repo research, local write | redact subprocess output; reject malformed or unsafe reports | `research_agent.py`, `sponsorship.py`, `cli.py` |
| `clawgauntlet sponsor ingest` | approved agent report and campaign | deduplicated review requests | owner-only local write | reject secrets, email addresses, unsafe URLs, and excess prospects | `sponsorship.py`, `cli.py` |
| `clawgauntlet sponsor inbox` | private state directory | reference-only pending review metadata | owner-only local read | reject malformed or foreign handoffs | `cli.py` |
| `clawgauntlet sponsor schedule` | absolute executable, campaign, state, workspace and task paths | macOS user LaunchAgent | user launchd write | redacted launchctl failure; unsupported off macOS | `sponsor_scheduler.py`, `cli.py` |
| `EvidenceStore` | bytes or JSON | `evidence://sha256/...` | hardened POSIX local I/O | fail closed on integrity or containment changes | `evidence.py` |
| `RunLedger` | run and score objects | DuckDB persistence | local database I/O | reject conflicting or orphaned records | `run_ledger.py` |
| `BeadsTaskLedger` | improvement proposal | one `bd create` invocation | approved subprocess in selected checkout | redacted adapter error | `adapters.py` |
| `JsonlMailTransport` | handoff envelope | fsynced JSONL outbox entry | owner-only local write | reject token-like content | `adapters.py` |
| `SponsorTaskLedger` | sponsor review reference | one approval-required Beads task | approved subprocess in selected checkout | fixed argv and redacted adapter failure | `adapters.py` |

The GitHub and SponsorClaw research surfaces have public read-only network
permission. The remaining working surface has no network permission, and no component has publishing,
credential, browser, merge, deployment, or outbound-publication permission.
HNClaw, RSSClaw, TrustClaw, DigestClaw, ReleaseClaw, DocsClaw, BlogAgent, and all
V2 connectors remain registered plans, not executable connectors. BlogClaw and
TwitterClaw currently build and request review of bundles; they cannot post.

`TweetClaw` is a conversational alias for the planned TwitterClaw workflow. It
is not a second component or a way around publisher approval.
