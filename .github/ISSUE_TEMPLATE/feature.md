---
name: Feature template
about: Propose a focused Blacklight feature or product improvement.
title: "[Feature]: "
labels: enhancement
assignees: ""
---

## Outcome

What should a user be able to do when this is complete?

## Current Gap

What is missing, confusing, slow, or incomplete today?

## Proposed Scope

- 
- 
- 

## Area

Choose the main area:

- [ ] CLI
- [ ] API
- [ ] Console/UI
- [ ] Workflows
- [ ] Runs
- [ ] Traces
- [ ] Evals
- [ ] Prompts
- [ ] Providers
- [ ] Review Queue
- [ ] Documentation

## CLI/API/Console Parity

If this changes a user workflow, describe how the same action should be exposed across CLI, API, and console.

Example CLI command:

```bash
blacklight workflows run ticket_classifier --verbose
```

## Mock-Provider Path

How should this work without API keys or paid provider access?

## Acceptance Criteria

- [ ] User outcome is implemented
- [ ] Mock-provider path works where applicable
- [ ] CLI output is clear in verbose mode
- [ ] API or console behavior is documented where applicable
- [ ] Tests or examples cover the behavior

## Suggested Milestone

Milestone:

## Priority

- [ ] priority:p0 - blocks release or core workflow
- [ ] priority:p1 - unlocks near-term usability
- [ ] priority:p2 - valuable but not blocking
- [ ] priority:p3 - polish or later
