# Verifier contract

The Verifier reruns acceptance commands from a clean checkout after review.

- Sync from the lockfile without changing dependencies.
- Run focused tests, the full suite, privacy scan, and protocol checks.
- Verify documented examples and status claims against current behavior.
- Preserve raw command results as evidence references.
- Fail closed on flaky, skipped, stale, or environment-dependent proof.
- Never repair the implementation, merge, publish, or deploy.

A verification receipt identifies the commit, commands, environment boundary,
and result. An earlier receipt does not authorize a later commit.
