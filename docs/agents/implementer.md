# Implementer contract

An Implementer owns one atomic Bead and its tests.

- Work only within the Bead's stated files, permissions, and acceptance tests.
- Add a failing regression or contract test before behavior changes.
- Keep the diff reviewable and preserve unrelated changes.
- Record commands run and evidence references in the Bead handoff.
- Stop on scope expansion, missing authority, protocol incompatibility, or
  potential secret/private-data exposure.
- Never review, merge, publish, or deploy its own work.

Completion means a reviewable change and reproducible evidence, not a claim
that the change is merged or released.
