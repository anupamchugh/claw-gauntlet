# Blog and X publishing workflow

BlogClaw and TwitterClaw are experimental publication-bundle builders. They do
not log into a blog, X, LinkedIn, or any other account. `TweetClaw` is a friendly
alias for TwitterClaw, not a separate connector.

## 1. Build a cited bundle

Prepare JSON with approved source references and public source URLs:

```json
{
  "title": "Claws become a system",
  "content": ["A draft post or the first post in a thread."],
  "artifact_refs": ["evidence://sha256/REPLACE_WITH_64_HEX_DIGEST"],
  "source_urls": ["https://github.com/example/tool"]
}
```

For a blog draft:

```bash
uv run clawgauntlet publication bundle \
  --channel blog \
  --state-dir .claw-state \
  --input publication.json
```

For an X draft or thread:

```bash
uv run clawgauntlet publication bundle \
  --channel twitter \
  --state-dir .claw-state \
  --input publication.json
```

A blog bundle contains one body. A TwitterClaw bundle contains up to twenty
items, each conservatively limited to 280 characters. The result records a
content hash and an immutable bundle evidence reference.

## 2. Ask the managed Publisher for review

```bash
uv run clawgauntlet publication request \
  --state-dir .claw-state \
  evidence://sha256/BUNDLE_DIGEST
```

This appends a reference-only, approval-required handoff to
`.claw-state/mail/publisher-requests.jsonl`. The request does not contain the
post body and does not grant permission to publish.

## 3. Review and post

The current experimental release stops at the approval request. A human should
open the immutable bundle, check claims, citations, privacy, disclosure, image
rights, links, and destination, then post it manually.

An outbound adapter is intentionally not included yet. A future adapter must:

1. accept a single-use approval receipt bound to the exact bundle hash,
2. hold credentials outside prompts, evidence, logs, and Agent Mail,
3. publish once to one explicitly named destination,
4. record the resulting public URL or platform receipt, and
5. reject changed, repeated, expired, or unapproved content.

This separation is why a managed agent is useful: it can keep collecting,
scoring, drafting, and notifying across terminal sessions while the narrow
Publisher remains unable to act until a person approves the exact artifact.
