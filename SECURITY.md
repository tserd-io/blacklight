# Security Policy

Blacklight is an early-stage AI platform starter kit for building inspectable LLM workflows, providers, prompts, guardrails, traces, evals, and review paths. Security reports are welcome and should be handled privately until a fix or mitigation is available.

## Supported Versions

Blacklight is currently pre-1.0. Security fixes are prioritized for the active development line and the most recent published release, when releases exist.

| Version | Supported |
| --- | --- |
| `main` | Yes |
| Latest release | Yes |
| Older releases | Best effort |
| Forks or private modifications | Not officially supported |

## Reporting A Vulnerability

Please do not open a public GitHub issue for a suspected vulnerability.

Preferred reporting path:

1. Use GitHub's private vulnerability reporting or a private security advisory for this repository, if available.
2. Include a clear description of the issue, affected files or components, and practical reproduction steps.
3. Include any relevant CLI commands, API requests, trace IDs, logs, or screenshots after removing secrets and private data.
4. If the report involves provider credentials, prompts, traces, eval data, or review queues, redact tokens, customer data, private prompts, and proprietary workflow details.

If private vulnerability reporting is unavailable, contact the repository maintainers privately through the owner's GitHub profile or organization contact path before disclosing details publicly.

## What To Include

Helpful reports usually include:

- The affected component, such as CLI, API, provider adapter, workflow runner, validation, guardrails, tracing, evals, review queue, docs, or CI.
- The impact and realistic attack scenario.
- Steps to reproduce using mock-provider or public-safe sample data when possible.
- Expected behavior versus actual behavior.
- Whether the issue exposes secrets, private prompts, model inputs, provider responses, traces, eval results, or approval decisions.
- Suggested mitigation, if known.

## Response Expectations

Maintainers will aim to:

- Acknowledge the report within 5 business days.
- Triage severity and affected versions.
- Keep the reporter updated when a fix, mitigation, or advisory is prepared.
- Credit the reporter when appropriate and requested.

Response times may vary while the project is pre-1.0 and maintained by a small team.

## Security Scope

In scope:

- Secret leakage through logs, traces, eval outputs, docs, screenshots, or CLI/API responses.
- Unsafe handling of provider credentials or environment variables.
- Prompt, tool, retrieval, or workflow behavior that can bypass guardrails or human-review requirements.
- Traceability gaps where domain inputs cannot be audited against range outputs for security-relevant decisions.
- CI/release automation risks that could publish unsafe artifacts or expose credentials.

Out of scope:

- Vulnerabilities that require modifying private forks or unsupported deployments.
- Reports based only on missing optional hardening in local development setups.
- Social engineering, spam, denial-of-service against third-party providers, or physical attacks.
- Public disclosure before maintainers have had a reasonable chance to investigate and respond.

## Public-Safe Examples

When sharing reproduction material, use mock-provider flows or synthetic data whenever possible. Do not include API keys, access tokens, private prompts, customer content, proprietary plans, or real trace data unless a maintainer explicitly requests it through a private channel.
