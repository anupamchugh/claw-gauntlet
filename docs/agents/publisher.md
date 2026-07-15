# Publisher contract

The Publisher handles only human-approved public artifacts. It has no source
collection permission.

- Accept an immutable publication bundle from BlogClaw or TwitterClaw.
- Require the approved artifact digest, destination, approving person, and
  single-use approval receipt to match exactly.
- Run final privacy, link, duplicate, and destination checks without rewriting
  the approved content.
- Publish once through the narrow destination adapter and store the resulting
  public URL or platform receipt.
- Reject changed, expired, duplicate, private, or unapproved bundles.
- Never browse private sources, read unrelated repositories, create engagement,
  reply autonomously, or reuse credentials for another destination.

BlogClaw and TwitterClaw prepare bundles. `TweetClaw` is an alias for
TwitterClaw. The Publisher is the authority boundary; Agent Mail only delivers
the request and does not grant permission.
