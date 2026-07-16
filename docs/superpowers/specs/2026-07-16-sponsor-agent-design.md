# Sponsor Agent Design

## Purpose

Sponsor Agent turns public project evidence into a small, ethical funding
pipeline for Claw Gauntlet. It may research, rank, draft, persist, schedule, and
notify without supervision. It may never send an external message, create a
financial commitment, alter payment settings, or claim a relationship without
explicit owner approval.

The first release supports two separate funding lanes:

1. GitHub Sponsors for voluntary community support of the open-source work.
2. A bounded company pilot for setup, evidence-workflow design, or an audit,
   paid separately through an invoice or Stripe Payment Link.

GitHub Sponsors already uses Stripe Connect for payouts. A direct Stripe link is
therefore a commercial payment surface, not another repository sponsor button.

## Success criteria

- A headless weekly cycle can research public sources and prepare at most five
  cited prospects.
- Every draft is stored as immutable evidence and deduplicated across cycles.
- Every proposed external contact creates an approval-required local handoff.
- An optional Beads task records the human decision that is needed.
- A macOS notification tells the owner that drafts are waiting.
- No runtime path can send email, post to social media, modify GitHub, or charge
  money.
- Missing Codex, malformed research, unavailable Beads, or failed notification
  produces a structured failure without broadening authority.

## Roles and boundaries

There is one scheduled agent, not a swarm:

```text
Scheduler
  -> read-only Codex researcher with web search
  -> strict SponsorResearchReport validation
  -> immutable EvidenceStore
  -> deduplicated approval inbox
  -> optional Beads review task
  -> local macOS notification
  -> human approve, edit, decline, or mark no-contact
```

The researcher runs with a read-only sandbox, an ephemeral session, a strict
JSON output schema, and no user MCP configuration. Its output is untrusted until
the local validator accepts it.

Agent Mail remains an agent-to-agent transport. The first release writes a
reference-only `sponsor-approvals.jsonl` outbox compatible with the existing
handoff boundary. When the local Agent Mail service is healthy, a later adapter
may relay those references. Agent Mail is not treated as a human notification
channel and its absence does not stop the local approval inbox.

## Campaign input

The campaign is a small JSON file containing:

- project name and public repository URL;
- a truthful one-sentence project description;
- the community sponsorship ask;
- the bounded company pilot offer and price range;
- public learning repositories;
- target categories, not scraped personal contact lists;
- a maximum of one to five drafts per cycle.

Secrets, cookies, email addresses, private repository paths, and private source
content are rejected. Research uses only public HTTPS evidence.

## Research report

The strict report contains a summary and zero to five prospects. Each prospect
has:

- a public name and canonical public URL;
- one lane: `community-sponsor`, `company-pilot`, or `feedback`;
- a concise fit reason;
- one to five public HTTPS evidence URLs;
- a subject and draft body;
- a confidence value from 0 to 100.

The draft must not say that a person or company uses, endorses, or depends on
Claw Gauntlet unless the cited public evidence says so. Repository stars and
follows are discovery signals, not permission to contact someone.

## Persistence and idempotency

The complete validated report and each accepted prospect are written to the
content-addressed evidence store. A deterministic draft ID is computed from the
lane, public URL, evidence URLs, subject, and body. Previously seen IDs are not
re-enqueued.

The approval inbox contains only handoff metadata and evidence references, not
the pitch body. Human-readable draft content is recovered from the local
evidence store. State lives outside the public checkout with owner-only
permissions.

## Approval states

The autonomous cycle only creates `awaiting-review`. The human or a future
approval command may transition it to:

- `approved-for-manual-send`;
- `edit-requested`;
- `declined`;
- `no-contact`.

There is deliberately no `sent` transition in V1. Sending is manual until a
separate delivery design is approved and audited.

## Scheduling and notification

On macOS, an installer creates a user LaunchAgent that runs once when installed
and then every Monday at 10:00 local time. It invokes the installed
`clawgauntlet sponsor research` command with explicit config, state, and task
directories. Standard output and error are written under the private state
directory.

When new drafts exist, the command uses `/usr/bin/osascript` to display a local
notification. The notification contains a count and the safe inbox command; it
does not contain prospect details or draft text.

## Sponsor offers

The proposed GitHub Sponsors tiers are intentionally inexpensive to fulfill:

- $5/month — Builder Backer: public sponsor badge and thanks.
- $15/month — Signal Supporter: Builder Backer plus a monthly Claw Field Note.
- $50/month — Claw Patron: Signal Supporter plus optional organization credit
  on a neutral supporters page.

Sponsorship never buys roadmap control, endorsements, private data, priority
support, or guaranteed delivery.

The separate company pilot is a two-week, fixed-scope engagement covering one
public or customer-approved repository, one evidence workflow, documented
permission boundaries, and a handoff report. The initial quoted range is
$500-$1,500, finalized by the owner before any offer is sent.

## Non-goals

- Mass outbound email, LinkedIn automation, or X automation.
- Harvesting starrers, private emails, or personal data.
- Autonomous negotiation, contracts, invoicing, refunds, or taxes.
- Stripe Connect marketplace functionality.
- Automatically changing the GitHub Sponsors profile.
- Promising sponsor benefits that the project cannot reliably fulfill.
