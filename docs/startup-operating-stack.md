# Agentic startup operating stack

This is a learning collection, not a dependency bundle and not a prospect list.
SponsorClaw may study these public repositories for workflow patterns. Inclusion
does not imply endorsement, compatibility, permission to contact maintainers, or
that Claw Gauntlet should install the project.

Choose one strong tool per job. A startup does not become more agentic by
installing every framework.

## Solo developer loop

| Repository | Learn or use it for | Claw Gauntlet relationship |
| --- | --- | --- |
| [`openai/codex`](https://github.com/openai/codex) | Terminal coding agent and bounded non-interactive execution | A possible read-only researcher runtime |
| [`anthropics/claude-code`](https://github.com/anthropics/claude-code) | Repository-aware terminal agent workflows | Another compatible operator, not a required dependency |
| [`obra/superpowers`](https://github.com/obra/superpowers) | Test-first skills, planning, and explicit review gates | Methodology and sponsor-positioning learning source |
| [`Aider-AI/aider`](https://github.com/Aider-AI/aider) | Small, direct pair-programming loop | Useful alternative when a full orchestration layer is excessive |
| [`cline/cline`](https://github.com/cline/cline) | IDE, CLI, and SDK agent surfaces | Study product packaging across several agent interfaces |
| [`OpenHands/OpenHands`](https://github.com/OpenHands/OpenHands) | Broader software-development agent platform | Study sandboxing and delegated development workflows |

## Multi-agent coordination and memory

| Repository | Learn or use it for | Claw Gauntlet relationship |
| --- | --- | --- |
| [`gastownhall/gastown`](https://github.com/gastownhall/gastown) | Multiple coding agents working from durable tasks | Optional heavy orchestration after the work can be decomposed safely |
| [`gastownhall/beads`](https://github.com/gastownhall/beads) | Git-friendly durable issue and dependency memory | Local task source of truth for approval and implementation work |
| [`Dicklesworthstone/mcp_agent_mail`](https://github.com/Dicklesworthstone/mcp_agent_mail) | Agent identities, inboxes, threads, and advisory file leases | Agent-to-agent transport; not a human notification service |
| [`Dicklesworthstone/cass_memory_system`](https://github.com/Dicklesworthstone/cass_memory_system) | Procedural memory across coding sessions | Recover lessons, then verify them against the live checkout |
| [`langchain-ai/langgraph`](https://github.com/langchain-ai/langgraph) | Durable stateful agent graphs | Useful when the product needs explicit resumable graph execution |
| [`microsoft/autogen`](https://github.com/microsoft/autogen) | Agent conversation and orchestration patterns | Research source; avoid adding a second orchestrator without a concrete need |

The lean default for a small team is Codex or Claude Code + Beads + repository
tests. Add Agent Mail when agents genuinely overlap. Add Gas Town only when
there are enough independent tasks to justify multi-agent operations.

## Product, web, marketing, and customer workflows

| Repository | Learn or use it for | Primary job |
| --- | --- | --- |
| [`triggerdotdev/trigger.dev`](https://github.com/triggerdotdev/trigger.dev) | Durable background and AI workflows | Jobs and automation |
| [`supabase/supabase`](https://github.com/supabase/supabase) | Postgres-backed web, mobile, and AI applications | Product backend |
| [`coollabsio/coolify`](https://github.com/coollabsio/coolify) | Self-hosted application deployment | Deployment |
| [`twentyhq/twenty`](https://github.com/twentyhq/twenty) | Open CRM and AI-oriented customer records | Sales pipeline |
| [`PostHog/posthog`](https://github.com/PostHog/posthog) | Product analytics, flags, replay, surveys, and experiments | Product learning |
| [`dubinc/dub`](https://github.com/dubinc/dub) | Link attribution and campaign measurement | Marketing attribution |
| [`formbricks/formbricks`](https://github.com/formbricks/formbricks) | User research and surveys | Customer feedback |
| [`calcom/cal.diy`](https://github.com/calcom/cal.diy) | Open scheduling infrastructure | Demos and customer calls |
| [`plausible/analytics`](https://github.com/plausible/analytics) | Privacy-oriented web analytics | Website measurement |
| [`opencollective/opencollective`](https://github.com/opencollective/opencollective) | Public governance, RFCs, and collective operations | Fiscal-host learning |

Licenses and self-hosting terms vary. Inspect the current license and commercial
terms before embedding any of these products.

## iOS delivery

| Repository | Learn or use it for | Primary job |
| --- | --- | --- |
| [`pointfreeco/swift-composable-architecture`](https://github.com/pointfreeco/swift-composable-architecture) | Explicit state, effects, dependencies, and testability | Application architecture |
| [`tuist/tuist`](https://github.com/tuist/tuist) | Scalable Xcode project and build workflows | Project automation |
| [`fastlane/fastlane`](https://github.com/fastlane/fastlane) | Repeatable signing, beta, screenshot, and store delivery | Release automation |

For a solo Apple developer, native SwiftUI plus focused tests and Fastlane or
ASC CLI is usually enough. Add TCA or Tuist when the application's state or
project graph actually warrants the extra layer.

## Funding and sponsorship lesson

The strongest sponsor pages studied for this project do three things:

1. Feature current work, not an old identity.
2. Quantify useful public output without inflating claims.
3. Offer inexpensive, sustainable benefits rather than roadmap control.

The agent may learn from public sponsor pages and funding metadata. It must not
treat stars, followers, contributors, or maintainers as a cold-contact list.
