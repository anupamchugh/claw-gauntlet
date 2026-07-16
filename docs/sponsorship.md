# Sponsorship and SponsorClaw

Claw Gauntlet uses two separate funding lanes.

## Community sponsorship

GitHub Sponsors is the community-support surface. GitHub handles the sponsor
experience and uses Stripe for payout processing; Claw Gauntlet does not need a
second payment integration for this lane.

Proposed sustainable tiers:

- **$5/month — Builder Backer:** public sponsor badge and thanks.
- **$15/month — Signal Supporter:** Builder Backer plus a monthly Claw Field
  Note covering verified progress and lessons.
- **$50/month — Claw Patron:** Signal Supporter plus optional organization
  credit on a neutral supporters page.

Sponsorship never buys roadmap control, endorsements, private data, priority
support, or guaranteed delivery. These tier descriptions are copy for the
maintainer's GitHub Sponsors settings; repository code cannot change financial
or identity settings.

Suggested sponsor-profile introduction:

> I build Claw Gauntlet, a local-first evidence and handoff layer for agents.
> It helps coding agents turn public signals into cited, inspectable drafts
> while keeping publishing, credentials, and financial decisions behind human
> approval. Sponsorship funds public fixtures, connector health checks, CI,
> documentation, and maintenance.

## Company pilot

The company lane is a fixed-scope service, not an OSS donation. The initial
offer is a two-week setup or audit for one approved repository and one evidence
workflow, including documented permission boundaries and a handoff report. The
initial range is **$500-$1,500**, finalized by the owner before the offer is
sent. It can later be paid through an invoice or a Stripe Payment Link.

## Run one bounded cycle

Copy and edit the public example. Do not add emails, secrets, private repository
paths, or customer data.

```bash
mkdir -p "$PWD/.local-sponsor-state"
chmod 700 "$PWD/.local-sponsor-state"

uv run clawgauntlet sponsor research \
  --state-dir "$PWD/.local-sponsor-state" \
  --config examples/sponsor-campaign.json \
  --workspace "$PWD" \
  --task-dir "$PWD" \
  --notify
```

The researcher starts Codex with an ephemeral session, web search, ignored user
MCP configuration, a read-only sandbox, and a strict output schema. It can read
public sources and the checkout. It cannot modify the checkout or contact a
prospect.

Inspect the safe inbox metadata:

```bash
uv run clawgauntlet sponsor inbox \
  --state-dir "$PWD/.local-sponsor-state"
```

The pitch body is stored in the private content-addressed evidence store. The
inbox and Beads task carry only an evidence reference and review summary.

## Install the weekly macOS loop

Use an installed, stable executable path rather than a disposable worktree:

```bash
clawgauntlet sponsor schedule install \
  --state-dir "/absolute/private/state" \
  --config "/absolute/path/to/sponsor-campaign.json" \
  --workspace "/absolute/path/to/claw-gauntlet" \
  --task-dir "/absolute/path/to/claw-gauntlet" \
  --executable "/absolute/path/to/clawgauntlet"
```

The user LaunchAgent runs immediately and then every Monday at 10:00 local time.
New drafts cause a local macOS notification. Logs live under the private state
directory.

```bash
clawgauntlet sponsor schedule status --state-dir "/absolute/private/state"
clawgauntlet sponsor schedule uninstall --state-dir "/absolute/private/state"
```

## Agent Mail boundary

Agent Mail coordinates agents; it does not proactively notify the human owner.
SponsorClaw therefore writes a reference-only local approval outbox and uses a
macOS notification. A future Agent Mail adapter may relay those references when
the local service is healthy. The outbox remains the source of truth if Agent
Mail is unavailable.

There is no `send` command in SponsorClaw V1. Approval means the owner may copy,
edit, and send the draft manually through a chosen account.
