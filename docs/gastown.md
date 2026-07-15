# Reviewed Gas Town execution

Gas Town is an optional multi-agent execution layer, not a prerequisite for
using Claw Gauntlet. Beads remains durable work state, Agent Mail carries
reference-only notifications, and Claw Gauntlet supplies evidence and run
quality contracts.

## Intake gate

Do not run `gt init` until the foundation has at least fifty passing tests, a
clean privacy scan, compatible protocol contracts, and no Critical or Important
review finding. Initialization never grants publishing or credential access.

## Operating policy

- Use no more than two implementation polecats concurrently at first.
- Give each polecat one ready, atomic Bead and an isolated checkout.
- Configure `--merge=mr`; never use `--merge=direct`.
- Assign a separate `--review-only` worker after every implementation Bead.
- Have a Verifier rerun acceptance commands after review and before merge.
- Stop Mayor dispatch when the full suite, privacy scan, protocol contract, or
  evidence-integrity check fails.
- Keep external publication outside automatic convoys.

The normal path is:

```text
Bead ready -> Mayor assignment -> Implementer evidence -> read-only review
  -> clean-checkout verification -> human merge decision
```

For public delivery, the path ends separately:

```text
approved evidence -> BlogClaw/TwitterClaw bundle -> human approval receipt
  -> isolated Publisher -> public receipt
```

Gas Town helps the project continue without repeated chat prompts because work,
ownership, dependencies, and wake-ups become durable. It does not decide the
goal, invent authority, or replace human review.
