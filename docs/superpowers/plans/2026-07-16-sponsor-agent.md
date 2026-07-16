# Sponsor Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and install a bounded weekly agent that researches public funding prospects, creates cited drafts, and asks the owner for approval without sending anything externally.

**Architecture:** A read-only ephemeral Codex subprocess produces strict JSON research. Local domain validation stores reports and drafts in the existing content-addressed evidence store, deduplicates approval requests, optionally creates Beads review tasks, and raises a local macOS notification. A LaunchAgent invokes the command weekly.

**Tech Stack:** Python 3.12, standard library subprocess/plistlib/urllib parsing, existing EvidenceStore and HandoffEnvelope, Beads CLI adapter, pytest, launchd.

## Global Constraints

- Public HTTPS evidence only; never ingest secrets, private repositories, cookies, contact lists, or credentials.
- Maximum five prospects per cycle.
- No email, social, GitHub mutation, payment, contract, or financial-setting authority.
- Every proposed external message remains approval-required and manual-send only.
- Codex research runs ephemeral with web search, ignored user config, and a read-only sandbox.
- State and logs live outside the public checkout with owner-only permissions.

---

### Task 1: Validate and persist sponsor research

**Files:**
- Create: `src/claw_gauntlet/sponsorship.py`
- Create: `tests/test_sponsorship.py`
- Modify: `src/claw_gauntlet/adapters.py`
- Test: `tests/test_adapters.py`

**Interfaces:**
- Consumes: `EvidenceStore.put_json`, `HandoffEnvelope.create`, `JsonlMailTransport.send`.
- Produces: `SponsorCampaign.from_dict`, `SponsorResearchReport.from_dict`, `SponsorCycle.ingest`, and `SponsorTaskLedger.create_review`.

- [ ] **Step 1: Write failing campaign and report validation tests**

  Cover campaign bounds, HTTPS-only URLs, allowed lanes, five-prospect maximum,
  secret-like text rejection, canonical repository URLs, and immutable tuple
  conversion.

- [ ] **Step 2: Run the focused tests and confirm RED**

  Run: `uv run pytest tests/test_sponsorship.py -q`

  Expected: collection error because `claw_gauntlet.sponsorship` does not exist.

- [ ] **Step 3: Implement immutable campaign, prospect, and report models**

  Use frozen dataclasses, explicit length limits, `urllib.parse.urlparse`, and
  the existing token-like content policy. Reject unknown lanes and malformed
  nested structures with `ValueError`.

- [ ] **Step 4: Run validation tests and confirm GREEN**

  Run: `uv run pytest tests/test_sponsorship.py -q`

- [ ] **Step 5: Write failing ingestion and deduplication tests**

  Assert that the first ingest stores report and draft evidence, appends one
  reference-only approval handoff, and returns one new draft. Assert that the
  same report ingested again creates no additional handoff.

- [ ] **Step 6: Implement SponsorCycle with owner-only seen-ID state**

  Compute a deterministic SHA-256 ID, use atomic owner-only state writes, and
  pass only draft evidence references through the handoff outbox.

- [ ] **Step 7: Add and test SponsorTaskLedger**

  Invoke `bd create` with a fixed argument vector, reference-only metadata,
  `sponsorship` and `approval-required` labels, and redacted failure text. Run
  `bd export -o .beads/issues.jsonl` only when that tracker file already exists.

- [ ] **Step 8: Run focused adapter and sponsorship tests**

  Run: `uv run pytest tests/test_sponsorship.py tests/test_adapters.py -q`

- [ ] **Step 9: Commit the domain slice**

  ```bash
  git add src/claw_gauntlet/sponsorship.py src/claw_gauntlet/adapters.py tests/test_sponsorship.py tests/test_adapters.py
  git commit -m "feat: add approval-gated sponsor research"
  ```

### Task 2: Add the headless researcher and CLI

**Files:**
- Create: `src/claw_gauntlet/research_agent.py`
- Create: `tests/test_research_agent.py`
- Modify: `src/claw_gauntlet/cli.py`
- Modify: `tests/test_foundation_cli.py`
- Modify: `src/claw_gauntlet/family.py`
- Modify: `tests/test_family_cli.py`
- Modify: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `SponsorCampaign`, `SponsorResearchReport`, `SponsorCycle`, `BeadsTaskLedger` patterns.
- Produces: `CodexSponsorResearcher.research` and CLI commands `sponsor research`, `sponsor ingest`, and `sponsor inbox`.

- [ ] **Step 1: Write failing command-construction tests**

  Assert an argument array containing `codex exec`, `--ephemeral`, `--search`,
  `--ignore-user-config`, `--sandbox read-only`, strict schema/output paths,
  and no shell execution. Assert timeout and stderr redaction on failure.

- [ ] **Step 2: Run researcher tests and confirm RED**

  Run: `uv run pytest tests/test_research_agent.py -q`

- [ ] **Step 3: Implement CodexSponsorResearcher**

  Write the schema and output into an owner-only temporary directory under the
  state root, pass the bounded campaign prompt on standard input, validate the
  final JSON with `SponsorResearchReport.from_dict`, then remove temporary files.

- [ ] **Step 4: Run researcher tests and confirm GREEN**

  Run: `uv run pytest tests/test_research_agent.py -q`

- [ ] **Step 5: Write failing CLI workflow tests**

  Cover offline `sponsor ingest`, live-research injection, inbox summary, Beads
  opt-in, notification opt-in, and structured failures.

- [ ] **Step 6: Implement sponsor CLI commands**

  `research` runs the headless researcher and ingests its report. `ingest`
  accepts a report produced by any approved agent. `inbox` lists evidence
  references awaiting human review. None exposes a send command.

- [ ] **Step 7: Register SponsorClaw truthfully**

  Add experimental `SponsorClaw` with `sponsor.research` and `sponsor.draft`
  capabilities and permissions limited to public evidence read plus local
  evidence/handoff write.

- [ ] **Step 8: Run focused CLI and manifest tests**

  Run: `uv run pytest tests/test_research_agent.py tests/test_foundation_cli.py tests/test_family_cli.py tests/test_manifest.py -q`

- [ ] **Step 9: Commit the executable slice**

  ```bash
  git add src/claw_gauntlet/research_agent.py src/claw_gauntlet/cli.py src/claw_gauntlet/family.py tests
  git commit -m "feat: run bounded sponsor research agent"
  ```

### Task 3: Install the weekly loop and document the offers

**Files:**
- Create: `src/claw_gauntlet/sponsor_scheduler.py`
- Create: `tests/test_sponsor_scheduler.py`
- Create: `docs/sponsorship.md`
- Create: `examples/sponsor-campaign.json`
- Modify: `src/claw_gauntlet/cli.py`
- Modify: `README.md`
- Modify: `SUPPORT.md`
- Modify: `docs/capabilities.md`

**Interfaces:**
- Consumes: installed `clawgauntlet sponsor research` command.
- Produces: `install_launch_agent`, `uninstall_launch_agent`, sponsor profile copy, campaign example, and operator commands.

- [ ] **Step 1: Write failing LaunchAgent tests**

  Assert a deterministic plist with explicit executable/config/state/task
  paths, `RunAtLoad`, Monday 10:00 calendar interval, and private log paths.
  Assert Linux fails with a clear unsupported-platform error.

- [ ] **Step 2: Run scheduler tests and confirm RED**

  Run: `uv run pytest tests/test_sponsor_scheduler.py -q`

- [ ] **Step 3: Implement install, status, and uninstall operations**

  Write plist atomically, chmod it `0600`, call `launchctl bootstrap` and
  `kickstart` using argument arrays, and redact command stderr on failure.

- [ ] **Step 4: Run scheduler tests and confirm GREEN**

  Run: `uv run pytest tests/test_sponsor_scheduler.py -q`

- [ ] **Step 5: Add schedule CLI commands and campaign example**

  Expose `sponsor schedule install|status|uninstall`. The example uses public
  learning repositories and target categories, never personal contact data.

- [ ] **Step 6: Document the two lanes and exact human gate**

  Publish the three sustainable GitHub tiers, the bounded company pilot, inbox
  commands, launchd operations, Agent Mail distinction, and explicit statement
  that the agent does not send messages.

- [ ] **Step 7: Run the full verification suite**

  Run: `uv run pytest -q && uv run python -m compileall -q src tests && git diff --check origin/main...HEAD`

- [ ] **Step 8: Commit the operator slice**

  ```bash
  git add src/claw_gauntlet/sponsor_scheduler.py src/claw_gauntlet/cli.py tests/test_sponsor_scheduler.py docs examples README.md SUPPORT.md
  git commit -m "feat: schedule sponsor agent reviews"
  ```

- [ ] **Step 9: Publish and activate**

  Push the branch, open a pull request, wait for CI, merge only when green,
  install the released CLI, install the LaunchAgent with explicit local paths,
  kickstart one cycle, and verify its state, logs, approval inbox, Beads task,
  and macOS service status.
