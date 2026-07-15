# Local foundation workflow

Claw Gauntlet keeps three local stores beneath an explicit `--state-dir`:

```text
state/
├── evidence/          immutable content-addressed JSON
├── runs.duckdb        run records, RRS scores, and baselines
└── mail/outbox.jsonl  reference-only handoff envelopes
```

The state directory is created with owner-only permissions. Store it outside a
public checkout. Never place credentials, cookies, private source content, or
access tokens in a run record or handoff. Handoffs contain evidence references,
not the evidence itself.

## Record and score a run

First store a JSON result as evidence:

```bash
uv run clawgauntlet evidence put \
  --state-dir .claw-state \
  --input result.json
```

The response contains an `evidence://sha256/...` reference. Add that reference
to a run input such as:

```json
{
  "claw_name": "GHClaw",
  "claw_version": "0.1.0",
  "input_hash": "sha256:c96c6d5be8d08a12e7b5cdc1b207fa6b2430974c86803d8891675e76fd992c20",
  "artifact_refs": ["evidence://sha256/REPLACE_WITH_64_HEX_DIGEST"],
  "outcome": "success",
  "duration_ms": 25,
  "retries": 0,
  "approvals_required": 0,
  "approvals_granted": 0,
  "permission_violations": 0,
  "human_corrections": 0
}
```

Then record, score, and inspect it:

```bash
uv run clawgauntlet run record --state-dir .claw-state --input run.json
uv run clawgauntlet run score --state-dir .claw-state RUN_ID
uv run clawgauntlet run show --state-dir .claw-state RUN_ID
```

Every command emits one deterministic JSON object. Operational failures emit a
structured JSON error to standard error and return a non-zero exit code.

## RRS scoring

RRS means Reliability, Resilience, and Safety. The current deterministic policy
starts from the run outcome, penalizes human corrections and retries above
three, and applies safety penalties for permission violations and missing
approvals. The overall score is the rounded mean of the three dimensions.

This policy is intentionally understandable and versionable. It is not a claim
that one number can replace inspection of the stored evidence.

## Improvement handoffs

To consider a scored run against the default threshold of 85:

```bash
uv run clawgauntlet improvement consider \
  --state-dir .claw-state \
  RUN_ID
```

A low score creates a deterministic proposal and appends an approval-required
handoff to `mail/outbox.jsonl`. The local command returns the proposed task as
JSON; it does not require Beads. A managed deployment may bind the same
coordinator to `BeadsTaskLedger`, which invokes `bd` with a fixed argument list
and reference-only metadata.

Agent Mail and Beads have different responsibilities:

- Agent Mail transports a bounded handoff between agents or queues.
- Beads persists work ownership, acceptance criteria, and completion state.
- Neither grants authority to publish, merge, deploy, or access credentials.

External effects remain approval-gated. A handoff with
`approval_required: true` is a request for review, not permission to act.
