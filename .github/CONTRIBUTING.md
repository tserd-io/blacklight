<p align="center">
  <img src="platform/docs/assets/blacklight-studio-readme-logo.png" alt="Blacklight Studio logo" width="420">
</p>

# Contributing To Blacklight Studio

Thanks for helping improve Blacklight Studio.

Blacklight is a compact AI workflow platform starter for governed provider routing, prompt versioning, evals, guardrails, traces, review flows, and local-first AI workflow demos. Contributions should preserve the same product promise:

> Build agents and workflows that feel personal to the work, but behave like production software.

## Contribution Principles

Good contributions make Blacklight easier to run, inspect, explain, or safely extend.

Prioritize changes that improve:

- fresh-clone usability
- deterministic mock-mode behavior
- clear CLI/API/console parity
- traceability and observability
- guardrail and review outcomes
- public-safe synthetic examples
- readable architecture and tradeoff documentation

Avoid changes that make the starter feel like a sprawling framework before the underlying product model is clear.

## Public-Safe Data Rule

Use synthetic examples only.

Do not add:

- real customer data
- private business workflows
- secrets or API keys
- production traces
- sensitive government/legal/tax/medical records
- realistic personal identifiers

High-risk document, form, legal, tax, medical, benefits, or government-adjacent examples must be framed as preparation and review workflows, not professional advice or final submission automation.

## Getting Started

Clone the repo and install the platform package:

```bash
cd platform
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,api]"
```

Run the local checks:

```bash
ruff check .
pytest
blacklight demo --verbose
```

The default development path uses the mock provider. No API key is required.

## Branching

Create one branch per issue.

Recommended format:

```text
codex/<issue-number>-short-description
```

Examples:

```text
codex/77-agent-definition-registry
codex/84-readme-quickstart-smoke-tests
```

Keep each branch scoped to the issue it addresses. If you notice unrelated improvements, open or update an issue rather than folding them into the current pull request.

## Issue Workflow

Before starting work:

1. Pick an open issue.
2. Check its milestone and priority label.
3. Confirm the acceptance criteria are clear.
4. Create a focused branch.

If an issue is too broad, split it before implementing.

Priority labels mean:

| Label | Meaning |
| --- | --- |
| `priority:p0` | Do first; protects core usability or unlocks the next product layer |
| `priority:p1` | High priority; should follow P0 work |
| `priority:p2` | Useful after the core path is stable |
| `priority:p3` | Later polish or exploratory work |

## Pull Request Expectations

A good PR should include:

- a short summary of what changed
- the issue number it addresses
- tests or a clear explanation when tests are not needed
- updated docs if user-facing behavior changed
- local verification notes

Use this checklist:

```text
- [ ] Scoped to one issue
- [ ] Uses mock mode by default
- [ ] No secrets or private data
- [ ] Tests added/updated where appropriate
- [ ] Docs updated for user-facing changes
- [ ] `ruff check .` passes
- [ ] `pytest` passes
```

## Architecture Guardrails

Blacklight owns:

- provider policy
- prompt and asset registries
- guardrail outcomes
- trace schema
- eval reporting
- review decisions
- domain/range contracts

External frameworks such as LangGraph or LangChain may be useful adapters, but they should not replace Blacklight's governance layer. Integrations must preserve Blacklight-native traces, guardrail outcomes, and domain-to-range evidence.

## Managed Agent Model

Future agent work should use the Blacklight domain/range framing:

```text
agent(domain) -> governed range
```

Domain describes what the agent can receive, retrieve, inspect, call, and reason over.

Range describes what the agent can produce, touch, export, route, or submit.

Every important run should eventually trace how the permitted domain became the actual range output:

```text
domain boundary
-> run inputs
-> context bundle
-> prompt/provider call
-> validation
-> guardrail decisions
-> range output
-> review/export/touch decision
-> eval evidence
```

## Documentation Style

Keep docs practical and direct.

Prefer:

- concrete commands
- expected outputs
- clear diagrams
- public-safe examples
- tradeoffs and non-goals

Avoid:

- vague AI claims
- enterprise buzzwords without implementation
- examples that imply professional advice
- hiding the CLI behind the UI

## Release Readiness

Before release-oriented changes, verify:

```bash
cd platform
ruff check .
pytest
blacklight health
blacklight demo --verbose
blacklight eval run
```

Release changes should keep the fresh-clone path deterministic, mock-provider-first, and credential-free.

## Questions

If a change might expand the product scope, prefer opening an issue first. Blacklight should grow deliberately: small enough to understand, complete enough to run, structured enough to govern.
