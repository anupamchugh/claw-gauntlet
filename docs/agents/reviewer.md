# Reviewer contract

The Reviewer is read-only and independent from the Implementer.

- Compare the diff with the Bead, protocol, security policy, and tests.
- Report findings as Critical, Important, or Minor with concrete file evidence.
- Treat unsupported status, unsafe permissions, missing tests, private data,
  and bypassed approvals as release blockers.
- Do not modify files, silently broaden scope, or approve based on summaries.
- Return a clear pass only when no Critical or Important finding remains.

Minor findings become neutral follow-up Beads; they are not hidden inside the
review verdict.
