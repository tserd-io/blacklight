# Issue Ticket Packages

These markdown packages group the planned public GitHub issues by milestone. Each package contains issue-ready titles, purpose statements, task lists, acceptance criteria, and suggested labels.

- [Milestone 1: Runnable MVP](milestone-1.md)
- [Milestone 2: Observability And Guardrails](milestone-2.md)
- [Milestone 3: Portfolio-Grade Documentation](milestone-3.md)
- [Milestone 4: CLI-Ready Package And Release](milestone-4.md)
- [Milestone 5: Business-User App Productization](milestone-5.md)
- Milestone 6: Desktop App Productization and approval history is captured in [Milestone 5: Business-User App Productization](milestone-5.md)
- Milestone 7: Managed Agents is documented in [Managed agents](../managed-agents.md) and tracked in the published issues below
- Milestone 8: Agent Runs And Traceability is documented in [Managed agents](../managed-agents.md) and tracked in the published issues below
- [Milestone 9: Formal Blacklight SDK](milestone-9.md)

Each milestone ends with a final QA and approval ticket. That gate is meant to keep the project incremental: finish, verify, and approve one slice before expanding the next.

## Published GitHub Issues

### Milestone 1: Runnable MVP

- [#1 Add CLI Entry Points For Platform Workflows](https://github.com/tserd-io/blacklight/issues/1)
- [#2 Add Provider Factory](https://github.com/tserd-io/blacklight/issues/2)
- [#3 Add Retry And Timeout Wrapper](https://github.com/tserd-io/blacklight/issues/3)
- [#4 Improve Eval Report](https://github.com/tserd-io/blacklight/issues/4)
- [#5 Milestone 1 Final QA And Approval](https://github.com/tserd-io/blacklight/issues/5)

### Milestone 2: Observability And Guardrails

- [#6 Expand Trace Store Queries](https://github.com/tserd-io/blacklight/issues/6)
- [#7 Improve Guardrail Outcomes](https://github.com/tserd-io/blacklight/issues/7)
- [#8 Add Public-Safe Synthetic Data Review](https://github.com/tserd-io/blacklight/issues/8)
- [#9 Milestone 2 Final QA And Approval](https://github.com/tserd-io/blacklight/issues/9)

### Milestone 3: Portfolio-Grade Documentation

- [#10 Rewrite README As Portfolio Artifact](https://github.com/tserd-io/blacklight/issues/10)
- [#11 Strengthen Architecture Docs](https://github.com/tserd-io/blacklight/issues/11)
- [#12 Add Tradeoffs And Failure Modes](https://github.com/tserd-io/blacklight/issues/12)
- [#13 Milestone 3 Final QA And Approval](https://github.com/tserd-io/blacklight/issues/13)

### Milestone 4: CLI-Ready Package And Release

- [#14 Add Dockerfile](https://github.com/tserd-io/blacklight/issues/14)
- [#15 Final CI Cleanup](https://github.com/tserd-io/blacklight/issues/15)
- [#16 Prepare v0.1 Release](https://github.com/tserd-io/blacklight/issues/16)
- [#17 Milestone 4 Final QA And Release Approval](https://github.com/tserd-io/blacklight/issues/17)
- [#19 Add Provider Configuration Smoke Tests](https://github.com/tserd-io/blacklight/issues/19)
- [#39 Add Operational Cost And Ownership Guide](https://github.com/tserd-io/blacklight/issues/39)
- [#41 Add Session History Trace View](https://github.com/tserd-io/blacklight/issues/41)
- [#62 Add Ollama Local Runtime Configuration](https://github.com/tserd-io/blacklight/issues/62)

### Milestone 5: Business-User App Productization

- [#43 Package Desktop App Shell](https://github.com/tserd-io/blacklight/issues/43)
- [#44 Add Session History UI](https://github.com/tserd-io/blacklight/issues/44)
- [#45 Add First-Run Provider Setup](https://github.com/tserd-io/blacklight/issues/45)
- [#46 Add Local Model Management](https://github.com/tserd-io/blacklight/issues/46)
- [#47 Add Business Review Queue UI](https://github.com/tserd-io/blacklight/issues/47)

### Milestone 6: Desktop App Productization

- [#54 Milestone 6 Final QA And Productization Approval](https://github.com/tserd-io/blacklight/issues/54)

Milestone 6 completed the business-user productization approval pass around web-first app shell packaging, optional desktop shell guidance, first-run provider setup, local model status, and final QA.

### Milestone 7: Managed Agents

- [#77 Add AgentDefinition schema and registry](https://github.com/tserd-io/blacklight/issues/77)
- [#78 Add agents CLI list and show commands](https://github.com/tserd-io/blacklight/issues/78)
- [#79 Add agents API and read-only profile payload](https://github.com/tserd-io/blacklight/issues/79)
- [#80 Add read-only agent profile to console](https://github.com/tserd-io/blacklight/issues/80)
- [#81 Document managed agents, domain/range, and graph-readiness](https://github.com/tserd-io/blacklight/issues/81)
- [#82 Milestone 7 final QA and approval](https://github.com/tserd-io/blacklight/issues/82)

Milestone 7 completed the managed-agent foundation pass: `ticket_classifier_agent`, read-only CLI/API/console inspection, explicit domain/range contracts, and managed-agent documentation.

### Milestone 8: Agent Runs And Traceability

- [#91 Add managed-agent run CLI](https://github.com/tserd-io/blacklight/issues/91)
- [#92 Persist agent run trace envelope](https://github.com/tserd-io/blacklight/issues/92)
- [#93 Add ergonomic trace show for agent runs](https://github.com/tserd-io/blacklight/issues/93)
- [#94 Add managed-agent run API](https://github.com/tserd-io/blacklight/issues/94)
- [#95 Add one-click console agent run journey](https://github.com/tserd-io/blacklight/issues/95)
- [#96 Attach guardrail and review outcomes to agent runs](https://github.com/tserd-io/blacklight/issues/96)
- [#97 Link agent runs to eval evidence](https://github.com/tserd-io/blacklight/issues/97)
- [#98 Milestone 8 final QA and approval](https://github.com/tserd-io/blacklight/issues/98)

Milestone 8 completed runnable managed-agent paths with durable run IDs, domain-to-range trace envelopes, review-routed outcomes, eval evidence links, and CLI/API/console parity.

### Milestone 9: Formal Blacklight SDK

- [#124 Add Formal SDK Facade](https://github.com/tserd-io/blacklight/issues/124)
- [#125 Add SDK Workflow Runner](https://github.com/tserd-io/blacklight/issues/125)
- [#126 Add SDK Trace, Eval, And Provider Clients](https://github.com/tserd-io/blacklight/issues/126)
- [#127 Add SDK Managed-Agent Surfaces](https://github.com/tserd-io/blacklight/issues/127)
- [#128 Add SDK Documentation And Examples](https://github.com/tserd-io/blacklight/issues/128)
- [#130 Add SDK Contract Tests](https://github.com/tserd-io/blacklight/issues/130)
- [#129 Milestone 9 Final QA And Approval](https://github.com/tserd-io/blacklight/issues/129)

Milestone 9 creates the stable `blacklight.sdk` Python embedding surface for workflows, traces, evals, providers, and managed agents.
