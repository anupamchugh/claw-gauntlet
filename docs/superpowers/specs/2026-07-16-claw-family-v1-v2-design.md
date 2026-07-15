# Claw Family V1 and V2 Design

**Date:** 2026-07-16
**Status:** Proposed for implementation
**Repository:** Claw Gauntlet

## Purpose

Claw Gauntlet turns public signals into evidence, decisions, releases, and useful writing. Each Claw has one job. The family shares a versioned handoff protocol, a durable task ledger, and explicit approval gates.

The system must remain useful from a terminal, an agent harness, or an MCP client. It must also remain safe to publish. Private repositories, private paths, browser cookies, access tokens, and unpublished customer data stay outside public artifacts.

## Product Boundary

The first two versions cover the complete public Claw family. They do not promise autonomous social behavior.

- Claws collect, transform, evaluate, document, or publish.
- Beads records durable work, dependencies, decisions, and ownership.
- Agent Mail carries messages and handoff notifications between active agents.
- The evidence store holds the actual artifacts referenced by those messages.
- MCP exposes stable commands to compatible agent clients.
- Humans approve external publication, credential use, and irreversible actions.

## Family Expansion Model

The family grows through contracts, not names alone.

- A **Claw** owns a durable capability or public data source.
- An **Agent** owns a role, identity, or repository, such as the personal BlogAgent.
- An **Adapter** connects durable infrastructure such as Beads or memory.
- A **Transport** moves messages or talks to one external service.

New work becomes a mode of an existing Claw when it shares the same input, policy, and output contract. It becomes a new Claw only when it needs a distinct capability manifest, permission boundary, evidence schema, and test suite.

For example, engineering writing is a BlogClaw profile rather than EngineeringBlogClaw. BirdClaw owns X transport and saved-post collection; TwitterClaw owns the research and publication workflow. Agent Mail remains a transport. It is not a Claw.

### Complete V1 and V2 Catalog

| Family | Component | Release | Responsibility |
| --- | --- | --- | --- |
| Discovery | StarClaw | V1 | Watch public GitHub stars and deltas |
| Discovery | GHClaw | V1 | Collect public repository evidence |
| Discovery | HNClaw | V1 | Research HN, check launch fit, and monitor threads |
| Discovery | RSSClaw | V1 | Normalize RSS, Atom, and JSON Feed |
| Intelligence | ProjectClaw | V1 | Evaluate evidence against an authorized project |
| Intelligence | TrustClaw | V1 | Check provenance, maintenance, security, and publication risk |
| Intelligence | RRSClaw | V1 | Measure reliability, resilience, and safety of Claw runs |
| Intelligence | DigestClaw | V1 | Produce cited watchlist and release digests |
| Delivery | ReleaseClaw | V1 | Gate and package releases |
| Delivery | DocsClaw | V1 | Build and verify reference documentation |
| Delivery | BlogClaw | V1 | Build voice-aware blog drafts |
| Delivery | TwitterClaw | V1 | Build approval-gated X publication bundles |
| Agent | BlogAgent | V1 | Own the personal blog's conventions and drafts |
| Infrastructure | EvidenceStore | V1 | Store immutable artifacts and provenance |
| Infrastructure | TaskLedgerAdapter | V1 | Map durable work and decisions to Beads |
| Infrastructure | AgentMailTransport | V1 | Notify and coordinate active agents |
| Infrastructure | SandboxRunner | V1 | Execute untrusted checks without publisher credentials |
| Discovery | ForkClaw | V2 | Map meaningful fork divergence and reusable patches |
| Discovery | BirdClaw | V2 | Own X search, saved posts, and transport-neutral records |
| Discovery | PaperClaw | V2 | Collect papers, versions, citations, and code links |
| Discovery | AppClaw | V2 | Collect public app listings, releases, and product signals |
| Intelligence | PeopleClaw | V2 | Track public creator and maintainer activity across sources |
| Intelligence | SkillClaw | V2 | Inventory, compare, validate, and deduplicate agent skills |
| Infrastructure | CassMemoryAdapter | V2 | Recover relevant prior reasoning without becoming source-of-truth storage |
| Infrastructure | MCPServer | V2 | Expose negotiated Claw capabilities to agent clients |
| Infrastructure | CredentialArbiter | V2 | Approve narrow credential use without exposing secrets |
| Infrastructure | Scheduler | V2 | Create bounded wake-ups and freshness checks |
| Interface | Dashboard | V2 | Show versions, handoffs, evidence freshness, and approvals |

This catalog absorbs the current registry and the approved publishing additions. Public status must show whether each entry is planned, experimental, stable, or deprecated.

### Extension Contract

A community Claw joins the family only when it supplies:

1. a capability manifest and semantic version,
2. typed input and evidence output schemas,
3. the smallest permissions it needs,
4. deterministic public fixtures,
5. policy and failure tests,
6. provenance and retention rules,
7. user documentation and runnable examples,
8. a maintainer and deprecation path.

The extension kit generates this skeleton and runs the same contract suite used by built-in Claws. Third-party Claws run in SandboxRunner until TrustClaw and a human reviewer approve broader permissions.

### What the Family Can Do

The combined family supports seven complete workflows:

1. **Maker radar:** watch public creators, stars, repositories, forks, apps, papers, feeds, and skills.
2. **Evidence-based adoption:** compare candidates, test them safely, explain relevance, and record adopt, reject, watch, or build decisions.
3. **Repository improvement:** turn public evidence into cited issues, Beads, documentation changes, and reviewable pull requests.
4. **Release operations:** verify versions, compatibility, tests, changelogs, provenance, documentation, and release notes.
5. **Personal publishing:** convert approved evidence into blog drafts, X publication bundles, and an HN launch brief without autonomous engagement.
6. **Agent coordination:** pass durable work through Beads, notify agents through Agent Mail, and expose capabilities through MCP.
7. **Community maintenance:** accept third-party Claws, test compatibility, publish status, document migrations, and retire unsafe or abandoned integrations.

Sponsorship remains repository metadata and transparent community support. DocsClaw maintains funding documentation, and ReleaseClaw verifies it. No Claw receives payment credentials or autonomously changes financial accounts.

## Version Model

Three version layers prevent unrelated changes from moving in lockstep.

1. **Release train:** `V1` and `V2` describe product milestones.
2. **Claw Protocol:** semantic versions describe the handoff envelope and capability manifest. A major change breaks compatibility, a minor change adds optional fields or capabilities, and a patch fixes behavior without changing the contract.
3. **Claw implementation:** each Claw has its own semantic version, such as `starclaw 1.2.0`.

Each Claw moves through `planned`, `experimental`, `stable`, and `deprecated`. Public status output must distinguish registered scaffolds from working connectors.

### Capability Manifest

Every Claw publishes a machine-readable manifest with these fields:

```json
{
  "name": "rssclaw",
  "version": "1.0.0",
  "protocol_version": "1.0.0",
  "status": "stable",
  "capabilities": ["feed.fetch", "feed.normalize", "feed.diff"],
  "inputs": ["rss", "atom", "jsonfeed"],
  "outputs": ["claw.evidence.feed-item.v1"],
  "permissions": ["network:read"],
  "approval_required": []
}
```

ReleaseClaw rejects incompatible manifests before release. DocsClaw publishes a compatibility matrix for every stable release.

## Handoff Protocol

Claws pass references, not secrets or large payloads. The V1 envelope contains:

```json
{
  "handoff_id": "01J...",
  "created_at": "2026-07-16T12:00:00Z",
  "protocol_version": "1.0.0",
  "from": "ghclaw",
  "to": "docsclaw",
  "artifact_refs": ["evidence://sha256/..."],
  "requested_action": "update-release-docs",
  "summary": "Three user-facing changes need documentation.",
  "provenance": ["https://github.com/example/project/releases/tag/v1.0.0"],
  "checksum": "sha256:...",
  "approval_required": false
}
```

The evidence store verifies the checksum when a receiving Claw opens an artifact. Unsupported major protocol versions fail closed. Missing artifacts, invalid checksums, or insufficient permissions create a blocked Bead and a clear Agent Mail response.

## Coordination

Beads and Agent Mail solve different problems.

- A Bead survives sessions. It records state, owner, dependencies, acceptance criteria, and the final decision.
- An Agent Mail message wakes or informs an agent. It contains the handoff ID and artifact references, not the full evidence set.
- A Claw may create or update a Bead, then notify the next agent through Agent Mail.
- Reprocessing the same handoff ID is idempotent.
- Every external action links back to the Bead, handoff, evidence, and approval that authorized it.

## V1: Evidence to Release

V1 ships a working, tested local-first pipeline.

### StarClaw

Snapshots public GitHub stars for configured accounts, detects additions and removals, and records provenance. It never treats a star as an endorsement.

### GHClaw

Collects public repository metadata, releases, issues, pull requests, contributors, and activity deltas through authenticated or anonymous GitHub access. It respects API limits and repository visibility.

### ProjectClaw

Evaluates a public or explicitly authorized local project against collected evidence. It produces recommendations with citations, confidence, and rejected alternatives.

### TrustClaw

Checks provenance, maintenance signals, licenses, security advisories, suspicious instructions, and publication risk. It reports evidence, not a universal trust score.

### RRSClaw

RRSClaw means Reliability, Resilience, and Safety Claw. It evaluates every Claw run against deterministic acceptance criteria before using model-based diagnosis. The score covers completion, reproducibility, provenance, retry and recovery behavior, permission compliance, cost, latency, and human corrections.

Each run emits a versioned `RunRecord` with the Claw and protocol versions, input hash, artifact references, outcome, duration, retries, approvals, violations, and corrections. RRSClaw stores measurements in the run ledger, opens an improvement Bead when a regression is reproducible, and links the Bead to the evidence.

The self-improvement loop is bounded:

1. Observe a run without changing it.
2. Score the run against a stable evaluation contract.
3. Diagnose a reproducible failure.
4. Create an improvement Bead with acceptance criteria.
5. Build a candidate change in SandboxRunner.
6. Replay fixed fixtures and prior failures.
7. Obtain independent review.
8. Release to a canary workload.
9. Promote or roll back through ReleaseClaw.
10. Record the new baseline and migration notes.

RRSClaw cannot change goals, constitutions, permissions, credential policy, evaluation criteria, approval requirements, or historical evidence. Those are governance settings.

### ReleaseClaw

Enforces semantic versions, protocol compatibility, changelog entries, tests, package checks, provenance, and release notes. It cannot publish until the release approval gate passes.

### DocsClaw

Generates and validates reference documentation, quick starts, capability manifests, compatibility tables, and migration notes. It fails when examples cannot run or when documented status exceeds implementation status.

### BlogAgent and BlogClaw

The personal blog at `anupamchugh.github.io` gets a dedicated BlogAgent. BlogClaw supplies the reusable writing and validation capabilities. BlogAgent owns the site's repository conventions and the author's voice profile.

The workflow is:

1. DigestClaw selects a release or evidence bundle.
2. BlogAgent creates a draft in the blog repository.
3. The voice checker reports cadence drift without changing the author's ideas.
4. DocsClaw verifies code samples and links.
5. TrustClaw checks private data, unsupported claims, copied text, and accidental endorsements.
6. The author reviews the rendered draft.
7. A separate PublishAgent commits and pushes only after explicit approval.

BlogAgent cannot access social credentials. PublishAgent cannot read unrelated private data. The published post includes an AI-assistance disclosure when an agent materially writes or edits it.

### TwitterClaw

TwitterClaw researches public X posts, saves source URLs, drafts post variants, and creates a publication bundle. An isolated XPublishAgent handles the outbound action after approval.

V1 supports research, saved-post watchlists, draft generation, link validation, duplicate detection, and manual or approval-gated publication. Browser cookies and tokens never enter prompts, logs, evidence files, or Agent Mail. The implementation may use a local browser-cookie transport for research, but the public interface remains transport-neutral.

### HNClaw

HNClaw checks Show HN eligibility, finds related submissions, prepares an evidence and FAQ bundle, monitors the resulting thread, and routes factual questions to other Claws. The human author submits and writes all HN comments.

HNClaw never votes, solicits votes, manufactures engagement, or posts generated comments. A runnable project may qualify for Show HN. A blog post, newsletter, sign-up page, or fundraiser uses a normal submission instead.

### RSSClaw

RSSClaw ingests RSS, Atom, and JSON Feed. It normalizes items, preserves canonical URLs and source timestamps, detects changes, and emits evidence bundles for DigestClaw.

The initial public fixtures include the Atom feed at `https://blog.fsck.com/feed/feed.xml`. RSSClaw records the linked article as a source. It does not copy full copyrighted posts into the repository.

### DigestClaw

Combines evidence into daily, weekly, release, and watchlist digests. Every claim links to its source artifact. DigestClaw can open Beads or send Agent Mail, but it cannot publish externally.

## V2: Ecosystem and Remote Operation

V2 expands sources and makes the V1 contracts available across machines.

### ForkClaw

Maps repository forks, meaningful divergence, active maintainers, and reusable patches. It distinguishes mechanical forks from independent projects.

### BirdClaw

BirdClaw owns X transport and saved-post collection. TwitterClaw remains the higher-level research and publishing workflow. This split allows the transport to change without breaking publication policy.

### PaperClaw

PaperClaw tracks public papers, revisions, citations, implementation repositories, and reproducibility evidence. It stores abstracts and metadata by default, not copyrighted full text.

### AppClaw

AppClaw tracks public app listings, release notes, pricing changes, platform support, and linked repositories. Storefront metadata remains a signal rather than proof of product quality.

### PeopleClaw

PeopleClaw joins public identities across approved sources and records activity deltas. It preserves source-specific identities, allows corrections, and avoids speculative identity matching.

### SkillClaw

SkillClaw inventories agent skills, validates instructions and dependencies, detects duplicates, and records compatibility. TrustClaw supplies the security and provenance checks.

### Feed Expansion

RSSClaw adds WebSub where available, conditional requests, backoff, feed discovery, retention policies, and cross-feed deduplication.

### MCP Server

The MCP server exposes manifests, collection, evaluation, handoff, digest, and status tools. It never exposes raw credentials. Clients negotiate the Claw Protocol version before work begins.

### Cross-Machine Agent Mail

Remote agents exchange handoff notifications through authenticated project channels. Artifact references use a shared or synchronized evidence store. Contact approval, project isolation, delivery receipts, and replay protection are mandatory.

### Memory Adapter

CassMemoryAdapter retrieves relevant prior decisions and reasoning for an agent. EvidenceStore and Beads remain the deterministic records. Memory can suggest context, but it cannot silently override live evidence.

### Credential Arbiter

CredentialArbiter evaluates a narrow request containing the actor, host, action, scope, and approval record. It returns a short-lived capability or denial. The calling agent never receives the underlying credential.

### Scheduling and Heartbeats

Schedulers create bounded wake-ups with a reason, deadline, budget, and Bead. Heartbeats report health and freshness. A heartbeat cannot grant new permissions or turn a draft into a publication.

### Dashboard

A read-only dashboard shows Claw versions, compatibility, recent handoffs, blocked Beads, evidence freshness, and pending approvals. Mutations continue through the same commands used by agents.

## Agentic User-in-the-Loop Pattern

The design adopts four ideas from Jesse Vincent's “Some new agentic patterns”:

1. The main reasoning agent cannot communicate externally.
2. Ephemeral outbound agents receive narrow capabilities.
3. Credentials remain outside agent transcripts and are injected only for an approved host and action.
4. The agents that use a tool test it, report friction, and review proposed improvements.

This pattern improves BlogAgent, XPublishAgent, HNClaw, RSSClaw, and ReleaseClaw. RSSClaw contributes untrusted content, so it must never share a process with credentials or publishing authority. An arbiter approves credential use and records the decision without revealing the credential.

Source: `https://blog.fsck.com/2026/07/05/new-patterns/`

## Security and Publication Policy

- Public-only collection is the default.
- Local project access requires an explicit allowlist.
- Collection agents cannot publish.
- Publishing agents cannot browse arbitrary sources.
- Credentials belong to the publisher identity, not the main agent.
- Tokens, cookies, and passwords never appear in prompts, messages, logs, Beads, or evidence.
- Outbound requests are restricted to approved hosts and actions.
- External publication requires a human approval record in V1 and V2.
- Each public artifact receives a private-data scan, provenance check, and claim audit.
- HN comments always remain human-authored.

## Failure Handling

- Rate limits produce resumable handoffs with retry timestamps.
- Authentication failures stop the relevant connector without blocking unrelated Claws.
- Invalid feeds retain the last valid snapshot and record a parse failure.
- Deleted or changed sources remain in an append-only provenance record.
- Duplicate handoffs return the prior result.
- Protocol-major mismatches fail before side effects.
- Publish failures leave the draft intact and record no success until the remote URL is verified.
- Partial release failures prevent the version tag from advancing.

## Testing and Release Gates

Every stable Claw needs:

- unit tests for parsing and policy,
- contract tests for manifests and handoffs,
- deterministic public fixtures,
- failure tests for rate limits, missing artifacts, incompatible versions, and denied approvals,
- integration tests that use test identities or dry-run transports,
- privacy and secret scans,
- documentation examples that execute,
- an independent review before release.

Publishing smoke tests stop before the irreversible action unless a human explicitly authorizes a test post. The release report lists working capabilities, experimental capabilities, and known limits.

## Delivery Sequence

The implementation proceeds in reviewable slices:

1. Correct the family registry statuses and define manifests.
2. Implement the handoff protocol, `RunRecord`, evidence store, and run ledger.
3. Ship RRSClaw, replay, canary, and rollback foundations.
4. Integrate Beads and Agent Mail adapters.
5. Ship StarClaw and GHClaw.
6. Ship ProjectClaw and TrustClaw.
7. Ship ReleaseClaw and DocsClaw.
8. Ship RSSClaw and DigestClaw.
9. Ship BlogClaw, BlogAgent, and approval-gated PublishAgent.
10. Ship TwitterClaw and HNClaw without autonomous social engagement.
11. Release V1 after complete verification.
12. Add ForkClaw, BirdClaw, PaperClaw, and AppClaw.
13. Add PeopleClaw and SkillClaw.
14. Add CassMemoryAdapter, CredentialArbiter, and the extension kit.
15. Add MCP, cross-machine handoffs, scheduling, heartbeats, and dashboard.
16. Release V2 after compatibility, security, and migration verification.

Each slice stays below the workspace review-size alarm. Generated fixtures and mechanical metadata remain separate from implementation diffs.

## V1 and V2 Exit Criteria

V1 is complete when every V1 Claw is stable, the local pipeline runs end to end from collection to an approved draft or release, RRSClaw can reproduce regressions and verify a canary rollback, documentation examples pass, and no public artifact exposes private data or credentials.

V2 is complete when every V2 component negotiates protocol versions, cross-machine handoffs survive retries and replays, outbound agents remain isolated, and V1 clients continue to work or receive tested migration guidance.
