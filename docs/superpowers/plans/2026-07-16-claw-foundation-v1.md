# Claw Foundation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the versioned Claw protocol, content-addressed evidence store, DuckDB run ledger, deterministic RRSClaw evaluator, and bounded improvement handoffs that every V1 and V2 Claw will use.

**Architecture:** Small Python modules define immutable typed records and ports. Evidence lives on disk by content hash; run metadata and scores live in DuckDB; Beads and Agent Mail receive references rather than payloads. RRSClaw measures runs deterministically, proposes improvements, and never edits governance settings or production state.

**Tech Stack:** Python 3.12, dataclasses, standard-library JSON and hashing, DuckDB 1.5.4, pytest 8, uv, Beads CLI.

## Global Constraints

- Public artifacts contain no private-project names, paths, data, integrations, or history.
- Collection and evaluation are local-first and read-only by default.
- Credentials never appear in prompts, logs, evidence, Beads, or Agent Mail.
- External publication and irreversible actions require explicit human approval.
- Claw Protocol and Claw implementations use semantic versions.
- Public status values are exactly `planned`, `experimental`, `stable`, or `deprecated`.
- Unsupported protocol-major versions, invalid checksums, and missing approvals fail closed.
- Each task ends with focused tests, the full test suite, and a reviewable commit.
- Generated caches and local evidence remain untracked.

---

## File Map

| File | Responsibility |
| --- | --- |
| `src/claw_gauntlet/manifest.py` | Capability manifests and semantic-version validation |
| `src/claw_gauntlet/family.py` | Honest family catalog and manifest lookup |
| `src/claw_gauntlet/handoff.py` | Versioned inter-Claw handoff envelope |
| `src/claw_gauntlet/run_record.py` | Immutable record of one Claw execution |
| `src/claw_gauntlet/evidence.py` | Content-addressed, atomic evidence storage |
| `src/claw_gauntlet/run_ledger.py` | DuckDB persistence for runs, scores, and baselines |
| `src/claw_gauntlet/rrs.py` | Reliability, resilience, and safety scoring |
| `src/claw_gauntlet/improvement.py` | Bounded improvement proposal workflow |
| `src/claw_gauntlet/adapters.py` | Beads and local Agent Mail transport ports |
| `src/claw_gauntlet/cli.py` | JSON CLI for catalog, recording, scoring, and proposing |
| `tests/` | Contract, storage, scoring, adapter, and CLI tests |

### Task 1: Make the family registry truthful and versioned

**Files:**
- Create: `src/claw_gauntlet/manifest.py`
- Modify: `src/claw_gauntlet/family.py`
- Modify: `src/claw_gauntlet/cli.py`
- Modify: `tests/test_family_cli.py`
- Create: `tests/test_manifest.py`

**Interfaces:**
- Produces: `CapabilityManifest`, `parse_semver(value: str)`, `family_manifests()`, and `manifest_for(name: str)`.
- Consumes: no earlier task interfaces.

- [ ] **Step 1: Write failing manifest and complete-registry tests**

```python
from claw_gauntlet.family import family_manifests, manifest_for
from claw_gauntlet.manifest import CapabilityManifest, parse_semver


def test_semver_and_manifest_round_trip():
    assert parse_semver("1.2.3") == (1, 2, 3)
    manifest = CapabilityManifest(
        name="RRSClaw",
        version="0.1.0",
        protocol_version="1.0.0",
        status="experimental",
        kind="intelligence",
        capabilities=("run.score",),
        permissions=("evidence:read",),
    )
    assert CapabilityManifest.from_dict(manifest.to_dict()) == manifest


def test_family_contains_each_component_once_and_none_are_available():
    manifests = family_manifests()
    names = [item.name for item in manifests]
    assert len(names) == len(set(names))
    assert {"RRSClaw", "DocsClaw", "BlogClaw", "TwitterClaw", "ForkClaw"} <= set(names)
    assert {item.status for item in manifests} == {"planned"}
    assert manifest_for("RRSClaw").capabilities == ("run.score", "run.regression")
```

- [ ] **Step 2: Run the tests and confirm the missing interfaces fail**

Run: `uv run pytest tests/test_manifest.py tests/test_family_cli.py -q`

Expected: FAIL because `manifest.py`, `family_manifests`, and `manifest_for` do not exist.

- [ ] **Step 3: Implement semantic-version validation and immutable manifests**

```python
# src/claw_gauntlet/manifest.py
from dataclasses import asdict, dataclass
import re
from typing import Any

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_STATUSES = {"planned", "experimental", "stable", "deprecated"}


def parse_semver(value: str) -> tuple[int, int, int]:
    match = _SEMVER.fullmatch(value)
    if match is None:
        raise ValueError(f"invalid semantic version: {value}")
    return tuple(int(part) for part in match.groups())


@dataclass(frozen=True)
class CapabilityManifest:
    name: str
    version: str
    protocol_version: str
    status: str
    kind: str
    capabilities: tuple[str, ...]
    permissions: tuple[str, ...]

    def __post_init__(self) -> None:
        parse_semver(self.version)
        parse_semver(self.protocol_version)
        if self.status not in _STATUSES:
            raise ValueError(f"invalid status: {self.status}")
        if not self.name or not self.capabilities:
            raise ValueError("name and capabilities are required")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        payload["permissions"] = list(self.permissions)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CapabilityManifest":
        return cls(
            name=str(payload["name"]),
            version=str(payload["version"]),
            protocol_version=str(payload["protocol_version"]),
            status=str(payload["status"]),
            kind=str(payload["kind"]),
            capabilities=tuple(str(item) for item in payload["capabilities"]),
            permissions=tuple(str(item) for item in payload["permissions"]),
        )
```

- [ ] **Step 4: Replace the old status set with complete manifest registrations**

Implement `family_manifests()` as a tuple of `CapabilityManifest` values for every catalog component. Set all components to `planned`; registration alone is not availability. Use protocol `1.0.0`, implementation `0.1.0`, exact kinds from the design catalog, and minimal capabilities such as `github.stars.watch`, `github.repo.collect`, `run.score`, `feed.collect`, `docs.verify`, and `handoff.notify`. Implement case-insensitive `manifest_for(name)` and make `family_payload()` serialize the manifests.

- [ ] **Step 5: Add `manifest NAME --json` and keep `family --json` stable**

The CLI prints one sorted JSON object per invocation. Missing names produce an argparse error and exit code `2`.

- [ ] **Step 6: Run focused and full tests**

Run: `uv run pytest tests/test_manifest.py tests/test_family_cli.py -q`

Expected: PASS.

Run: `uv run pytest -q`

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/claw_gauntlet/manifest.py src/claw_gauntlet/family.py src/claw_gauntlet/cli.py tests/test_manifest.py tests/test_family_cli.py
git commit -m "feat: version the Claw capability catalog"
```

### Task 2: Define handoffs and run records

**Files:**
- Create: `src/claw_gauntlet/handoff.py`
- Create: `src/claw_gauntlet/run_record.py`
- Create: `tests/test_handoff.py`
- Create: `tests/test_run_record.py`

**Interfaces:**
- Consumes: `parse_semver` from Task 1.
- Produces: `HandoffEnvelope`, `RunRecord`, `new_handoff_id()`, and `new_run_id()`.

- [ ] **Step 1: Write failing validation and round-trip tests**

```python
from claw_gauntlet.handoff import HandoffEnvelope
from claw_gauntlet.run_record import RunRecord


def test_handoff_round_trip_and_major_version_guard():
    handoff = HandoffEnvelope.create(
        source="GHClaw",
        destination="DocsClaw",
        artifact_refs=("evidence://sha256/c7c5c1d70c5dec4416ab6158afd0b223ef40c29b1dc1f97ed9428b94d4cadb1c",),
        requested_action="update-release-docs",
        summary="Document one verified change.",
        checksum="sha256:b8699645b752c44ac547cd72d0d326f0dae7d49088793a39baf1e54897e1fa7c",
        approval_required=False,
    )
    assert HandoffEnvelope.from_dict(handoff.to_dict()) == handoff
    handoff.require_protocol_major(1)


def test_run_record_round_trip():
    record = RunRecord.create(
        claw_name="GHClaw",
        claw_version="0.1.0",
        input_hash="sha256:c96c6d5be8d08a12e7b5cdc1b207fa6b2430974c86803d8891675e76fd992c20",
        artifact_refs=("evidence://sha256/c7c5c1d70c5dec4416ab6158afd0b223ef40c29b1dc1f97ed9428b94d4cadb1c",),
        outcome="success",
        duration_ms=25,
        retries=0,
        approvals_required=0,
        approvals_granted=0,
        permission_violations=0,
        human_corrections=0,
    )
    assert RunRecord.from_dict(record.to_dict()) == record
```

- [ ] **Step 2: Run tests and verify missing modules fail**

Run: `uv run pytest tests/test_handoff.py tests/test_run_record.py -q`

Expected: FAIL with module import errors.

- [ ] **Step 3: Implement immutable JSON records**

Use frozen dataclasses, UTC ISO-8601 timestamps, UUID4 hex identifiers, tuple artifact references, and `to_dict`/`from_dict`. Both records fail closed unless the protocol major is exactly `1`. SHA-256 values accept case-insensitive 64-hex input and normalize to lowercase. `RunRecord.input_hash` uses `sha256:<64-hex-digest>` and evidence references use `evidence://sha256/<64-hex-digest>`. `RunRecord` accepts outcomes `success`, `partial`, or `failure`; rejects negative counters and durations; validates semantic versions. `HandoffEnvelope` requires non-empty source, destination, action, summary, checksum, and at least one artifact reference. Its checksum is SHA-256 over the UTF-8 bytes of the normalized, ordered `artifact_refs` list encoded as compact JSON with separators `(",", ":")`. `require_protocol_major(expected)` raises `ValueError` on mismatch.

- [ ] **Step 4: Add negative tests**

Test invalid semantic versions, missing artifacts, negative retries, invalid outcomes, and a protocol-major mismatch.

- [ ] **Step 5: Run focused and full tests**

Run: `uv run pytest tests/test_handoff.py tests/test_run_record.py -q`

Expected: PASS.

Run: `uv run pytest -q`

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/claw_gauntlet/handoff.py src/claw_gauntlet/run_record.py tests/test_handoff.py tests/test_run_record.py
git commit -m "feat: define versioned Claw handoffs"
```

### Task 3: Store evidence atomically by content hash

**Files:**
- Create: `src/claw_gauntlet/evidence.py`
- Create: `tests/test_evidence.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `EvidenceRef`, `EvidenceStore.put_bytes`, `put_json`, `get_bytes`, `get_json`, and `verify`.
- Consumes: no mutable global state.

- [ ] **Step 1: Write failing content-addressing tests**

```python
from claw_gauntlet.evidence import EvidenceStore


def test_put_is_content_addressed_idempotent_and_verified(tmp_path):
    store = EvidenceStore(tmp_path / "evidence")
    first = store.put_json({"source": "public", "items": [1, 2]})
    second = store.put_json({"items": [1, 2], "source": "public"})
    assert first == second
    assert first.uri.startswith("evidence://sha256/")
    assert store.get_json(first) == {"items": [1, 2], "source": "public"}
    assert store.verify(first)
```

- [ ] **Step 2: Run the test and confirm the module is missing**

Run: `uv run pytest tests/test_evidence.py -q`

Expected: FAIL with a module import error.

- [ ] **Step 3: Implement canonical JSON and atomic writes**

`put_json` encodes JSON with `sort_keys=True`, separators `(",", ":")`, and UTF-8. `put_bytes` hashes bytes with SHA-256, writes to `<root>/sha256/<first-two>/<digest>` through a temporary file in the target directory, calls `os.replace`, and returns an immutable `EvidenceRef(algorithm="sha256", digest=...)`. Reads recompute the digest and raise `EvidenceIntegrityError` on mismatch. Reject unsupported algorithms and path traversal.

- [ ] **Step 4: Add corruption and missing-artifact tests**

Modify a stored file and assert `verify` returns `False` while `get_bytes` raises `EvidenceIntegrityError`. Assert a valid but missing reference raises `FileNotFoundError`.

- [ ] **Step 5: Ignore local runtime artifacts**

Add these exact lines to `.gitignore`:

```gitignore
.venv/
.pytest_cache/
__pycache__/
*.py[cod]
.claw/
```

- [ ] **Step 6: Run focused and full tests**

Run: `uv run pytest tests/test_evidence.py -q`

Expected: PASS.

Run: `uv run pytest -q`

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add .gitignore src/claw_gauntlet/evidence.py tests/test_evidence.py
git commit -m "feat: add content-addressed evidence storage"
```

### Task 4: Persist runs and scores in DuckDB

**Files:**
- Modify: `pyproject.toml`
- Add: `uv.lock`
- Create: `src/claw_gauntlet/run_ledger.py`
- Create: `tests/test_run_ledger.py`

**Interfaces:**
- Consumes: `RunRecord` from Task 2.
- Produces: `RunScore`, `RunLedger.record_run`, `get_run`, `record_score`, `get_score`, `set_baseline`, and `get_baseline`.

- [ ] **Step 1: Add the DuckDB runtime dependency**

Run: `uv add 'duckdb>=1.5.4,<2'`

Expected: `pyproject.toml` and `uv.lock` include DuckDB.

- [ ] **Step 2: Write failing persistence tests**

```python
from claw_gauntlet.run_ledger import RunLedger, RunScore
from claw_gauntlet.run_record import RunRecord


def test_run_score_and_baseline_survive_reopen(tmp_path):
    path = tmp_path / "runs.duckdb"
    record = RunRecord.create(
        claw_name="GHClaw", claw_version="0.1.0", input_hash="sha256:c96c6d5be8d08a12e7b5cdc1b207fa6b2430974c86803d8891675e76fd992c20",
        artifact_refs=("evidence://sha256/c7c5c1d70c5dec4416ab6158afd0b223ef40c29b1dc1f97ed9428b94d4cadb1c",), outcome="success",
        duration_ms=20, retries=0, approvals_required=0, approvals_granted=0,
        permission_violations=0, human_corrections=0,
    )
    with RunLedger(path) as ledger:
        ledger.record_run(record)
        ledger.record_score(RunScore(record.run_id, 100, 100, 100, 100))
        ledger.set_baseline("GHClaw", record.run_id)
    with RunLedger(path) as ledger:
        assert ledger.get_run(record.run_id) == record
        assert ledger.get_score(record.run_id).overall == 100
        assert ledger.get_baseline("GHClaw") == record.run_id
```

- [ ] **Step 3: Run the test and confirm missing interfaces fail**

Run: `uv run pytest tests/test_run_ledger.py -q`

Expected: FAIL with a module import error.

- [ ] **Step 4: Implement schema creation and typed persistence**

Create tables `runs`, `scores`, and `baselines` during `RunLedger` initialization. Store full canonical record JSON in `runs` with indexed scalar fields for Claw, version, outcome, and timestamp. Use parameterized SQL only. Reject duplicate run IDs unless the canonical JSON matches exactly. Make the context manager close the connection.

- [ ] **Step 5: Add duplicate and missing-record tests**

Assert idempotent duplicate inserts succeed, conflicting duplicates raise `ValueError`, and missing lookups return `None`.

- [ ] **Step 6: Run focused and full tests**

Run: `uv run pytest tests/test_run_ledger.py -q`

Expected: PASS.

Run: `uv run pytest -q`

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/claw_gauntlet/run_ledger.py tests/test_run_ledger.py
git commit -m "feat: persist Claw runs in DuckDB"
```

### Task 5: Score reliability, resilience, and safety

**Files:**
- Create: `src/claw_gauntlet/rrs.py`
- Create: `tests/test_rrs.py`

**Interfaces:**
- Consumes: `RunRecord`, `RunScore`, and optional baseline score.
- Produces: `score_run(record: RunRecord) -> RunScore` and `is_regression(current, baseline, tolerance=5) -> bool`.

- [ ] **Step 1: Write failing deterministic-score tests**

```python
from dataclasses import replace
from claw_gauntlet.rrs import is_regression, score_run
from claw_gauntlet.run_record import RunRecord


def good_run():
    return RunRecord.create(
        claw_name="GHClaw", claw_version="0.1.0", input_hash="sha256:c96c6d5be8d08a12e7b5cdc1b207fa6b2430974c86803d8891675e76fd992c20",
        artifact_refs=("evidence://sha256/c7c5c1d70c5dec4416ab6158afd0b223ef40c29b1dc1f97ed9428b94d4cadb1c",), outcome="success",
        duration_ms=20, retries=0, approvals_required=1, approvals_granted=1,
        permission_violations=0, human_corrections=0,
    )


def test_clean_run_scores_one_hundred():
    score = score_run(good_run())
    assert (score.reliability, score.resilience, score.safety, score.overall) == (100, 100, 100, 100)


def test_missing_approval_and_violation_fail_safety():
    score = score_run(replace(good_run(), approvals_granted=0, permission_violations=1))
    assert score.safety == 25
    assert score.overall < 100


def test_regression_uses_explicit_tolerance():
    baseline = score_run(good_run())
    current = replace(baseline, overall=94)
    assert is_regression(current, baseline, tolerance=5)
```

- [ ] **Step 2: Run tests and confirm the module is missing**

Run: `uv run pytest tests/test_rrs.py -q`

Expected: FAIL with a module import error.

- [ ] **Step 3: Implement the exact deterministic policy**

Reliability starts from `100` for success, `50` for partial, and `0` for failure, then loses `10` per human correction. Resilience starts from `100` for success, `50` for partial, and `0` for failure, then loses `10` for each retry above three. Safety starts at `100`, loses `50` per permission violation, and loses `25` per required approval not granted. Clamp dimensions to `0..100`. Overall is the rounded arithmetic mean. A regression is `current.overall < baseline.overall - tolerance`.

- [ ] **Step 4: Add boundary tests**

Test clamping, three retries without penalty, four retries with penalty, partial outcomes, failure outcomes, and extra approvals without penalty.

- [ ] **Step 5: Run focused and full tests**

Run: `uv run pytest tests/test_rrs.py -q`

Expected: PASS.

Run: `uv run pytest -q`

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/claw_gauntlet/rrs.py tests/test_rrs.py
git commit -m "feat: score Claw run quality"
```

### Task 6: Create bounded improvement proposals and handoffs

**Files:**
- Create: `src/claw_gauntlet/improvement.py`
- Create: `src/claw_gauntlet/adapters.py`
- Create: `tests/test_improvement.py`
- Create: `tests/test_adapters.py`

**Interfaces:**
- Consumes: `RunRecord`, `RunScore`, `HandoffEnvelope`, and evidence references.
- Produces: `ImprovementProposal`, `ImprovementCoordinator`, `TaskLedgerPort`, `BeadsTaskLedger`, `MailTransportPort`, and `JsonlMailTransport`.

- [ ] **Step 1: Write failing proposal-policy tests**

```python
from claw_gauntlet.improvement import ImprovementCoordinator


def test_low_score_creates_one_idempotent_improvement(run_record, low_score, fake_ledger, fake_mail):
    coordinator = ImprovementCoordinator(fake_ledger, fake_mail, threshold=85)
    first = coordinator.consider(run_record, low_score)
    second = coordinator.consider(run_record, low_score)
    assert first.proposal_id == second.proposal_id
    assert len(fake_ledger.created) == 1
    assert len(fake_mail.sent) == 1


def test_passing_score_creates_nothing(run_record, good_score, fake_ledger, fake_mail):
    coordinator = ImprovementCoordinator(fake_ledger, fake_mail, threshold=85)
    assert coordinator.consider(run_record, good_score) is None
```

- [ ] **Step 2: Run tests and confirm missing interfaces fail**

Run: `uv run pytest tests/test_improvement.py tests/test_adapters.py -q`

Expected: FAIL with module import errors.

- [ ] **Step 3: Implement proposals and ports**

`ImprovementProposal` contains a deterministic SHA-256 proposal ID derived from run ID and score, title, description, acceptance criteria, source run ID, evidence references, and priority. `ImprovementCoordinator.consider` returns `None` for scores at or above the threshold. For lower scores it calls `TaskLedgerPort.create_improvement` and sends one handoff notification through `MailTransportPort`. Repeated proposal IDs are idempotent.

- [ ] **Step 4: Implement the Beads adapter safely**

`BeadsTaskLedger` accepts a working directory and injectable command runner. It runs an argument array without a shell:

```python
[
    "bd", "create", proposal.title,
    "--type", "task",
    "--priority", proposal.priority,
    "--description", proposal.description,
    "--acceptance", proposal.acceptance_criteria,
    "--external-ref", f"claw-run:{proposal.source_run_id}",
    "--metadata", canonical_metadata_json,
    "--silent",
]
```

It never embeds evidence payloads or secrets. A non-zero result raises `TaskLedgerError` with redacted stderr.

- [ ] **Step 5: Implement a local Agent Mail-compatible outbox**

`JsonlMailTransport` appends canonical JSON handoff notifications to an outbox file under an exclusive file lock and calls `flush` plus `os.fsync`. It stores artifact references only. A later MCP adapter can consume the same envelope without changing the coordinator.

- [ ] **Step 6: Add adapter failure and injection tests**

Assert the Beads runner receives an argument list, never `shell=True`, and never receives evidence contents. Assert mail contains no token-like fields. Assert adapter failures do not mark a proposal delivered.

- [ ] **Step 7: Run focused and full tests**

Run: `uv run pytest tests/test_improvement.py tests/test_adapters.py -q`

Expected: PASS.

Run: `uv run pytest -q`

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/claw_gauntlet/improvement.py src/claw_gauntlet/adapters.py tests/test_improvement.py tests/test_adapters.py
git commit -m "feat: propose bounded Claw improvements"
```

### Task 7: Expose a complete local JSON workflow

**Files:**
- Modify: `src/claw_gauntlet/cli.py`
- Create: `tests/test_foundation_cli.py`
- Create: `docs/foundation.md`

**Interfaces:**
- Consumes: all Tasks 1 through 6.
- Produces commands `evidence put`, `run record`, `run score`, `run show`, and `improvement consider`.

- [ ] **Step 1: Write a failing end-to-end CLI test**

The test writes public fixture JSON, runs `evidence put`, records a run that references the returned URI, scores it, reads it back, and verifies a failing run produces exactly one local improvement notification. Invoke `main([...])` directly and parse every stdout line as JSON.

- [ ] **Step 2: Run the end-to-end test and confirm commands are missing**

Run: `uv run pytest tests/test_foundation_cli.py -q`

Expected: FAIL because the subcommands do not exist.

- [ ] **Step 3: Implement commands with explicit runtime paths**

Every stateful command requires `--state-dir PATH`; it creates `evidence/`, `runs.duckdb`, and `mail/outbox.jsonl` beneath that path. Commands print one JSON result with `status`, identifiers, and artifact references. Errors print structured JSON to stderr and return non-zero. No command reads arbitrary environment variables except standard locale and temporary-directory settings.

- [ ] **Step 4: Document exact local usage**

`docs/foundation.md` explains the three stores, shows commands against `.claw/`, defines the RRS policy, distinguishes Beads from Agent Mail, and states every approval boundary. Examples must run without network access.

- [ ] **Step 5: Run focused, full, and documentation smoke tests**

Run: `uv run pytest tests/test_foundation_cli.py -q`

Expected: PASS.

Run: `uv run pytest -q`

Expected: all tests PASS.

Run: `uv run clawgauntlet family --json | python -m json.tool >/dev/null`

Expected: exit code `0`.

- [ ] **Step 6: Scan public product files for forbidden private references**

Run: `rg -n -i 'private-project-name|/Users/[^/]+/Desktop|auth[_-]?token|ct0|password' README.md docs src tests pyproject.toml .github 2>/dev/null`

Expected: no private paths or credential values. Documentation may contain generic policy words such as `password` only in a prohibition; review each match manually.

- [ ] **Step 7: Commit**

```bash
git add src/claw_gauntlet/cli.py tests/test_foundation_cli.py docs/foundation.md
git commit -m "feat: expose the Claw foundation workflow"
```

### Task 8: Verify the foundation and prepare Gas Town intake

**Files:**
- Create: `docs/capabilities.md`
- Create: `docs/agents/mayor.md`
- Create: `docs/agents/implementer.md`
- Create: `docs/agents/reviewer.md`
- Create: `docs/agents/verifier.md`
- Create: `docs/agents/publisher.md`
- Create: `docs/gastown.md`

**Interfaces:**
- Consumes: the complete foundation CLI and tests.
- Produces: capability discovery and reviewed execution contracts needed before `gt init`.

- [ ] **Step 1: Write the capability index**

List each working command, input, output, permissions, failure behavior, and owning module. Planned Claws remain visibly planned.

- [ ] **Step 2: Write five role contracts**

Mayor assigns ready Beads and never edits product files. Implementer owns one atomic Bead and its tests. Reviewer is read-only and reports Critical, Important, and Minor findings. Verifier reruns acceptance commands from a clean checkout. Publisher handles only approved public artifacts and has no collection permissions.

- [ ] **Step 3: Document the Gas Town operating policy**

Use at most two implementation polecats concurrently until fifty foundation tests pass. Use `--merge=mr`, never `--merge=direct`. Assign a separate `--review-only` worker after each implementation Bead. The Mayor stops dispatch when the full suite, privacy scan, or protocol contract fails. External publishing remains outside automatic convoys.

- [ ] **Step 4: Run the final foundation verification**

Run: `uv sync --frozen`

Expected: exit code `0`.

Run: `uv run pytest -q`

Expected: all tests PASS.

Run: `git diff --check`

Expected: no output.

Run: `git status --short`

Expected: only intentionally staged documentation before commit.

- [ ] **Step 5: Commit**

```bash
git add docs/capabilities.md docs/agents docs/gastown.md
git commit -m "docs: define reviewed Gas Town execution"
```

- [ ] **Step 6: Perform an independent read-only review**

Review the complete foundation range against the design specification. Block Gas Town initialization on any Critical or Important finding. Record Minor findings as neutral Beads after the clean backlog exists.
