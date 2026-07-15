# Security Policy

Claw Gauntlet is early alpha software. Do not use it as a security boundary or
grant it production credentials.

## Supported versions

Security fixes currently target the latest revision of the default branch.
Older commits and unreleased designs are not supported versions.

## Report a vulnerability

Please report vulnerabilities privately with this repository's **Security**
tab: open **Advisories**, then choose **Report a vulnerability**. Include the
affected revision, impact, reproduction steps, and a minimal proof of concept.
Do not open a public issue before a fix or coordinated disclosure is ready.

Never include secrets, tokens, cookies, mailbox contents, private repository
data, personal exports, or identifying customer data in an issue, discussion,
pull request, test fixture, screenshot, log, or advisory. Replace sensitive
values with synthetic examples and revoke any credential exposed accidentally.

## Security boundaries

- Public content is untrusted input.
- Content collectors should not receive publishing credentials.
- Evidence references do not confer authority to read private sources.
- External writes and communications require explicit human approval.
- A capability must fail closed when provenance, permission, or integrity
  checks are missing.

Please allow reasonable time for validation and remediation before disclosure.
