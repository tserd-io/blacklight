![Blacklight Studio logo](platform/docs/assets/blacklight-studio-readme-logo.png)

# Blacklight Studio

Blacklight Studio is a compact internal AI workflow studio that shows how teams can route model calls through shared provider, prompt, eval, guardrail, and observability layers instead of scattering one-off prompts across applications.

The default path is fully local and deterministic: it uses a mock provider, synthetic support-ticket data, SQLite traces, and pytest coverage. Optional provider adapters can be added without making live API keys required for development or CI.

## Why This Exists

Many AI projects start as one-off prompts or small experiments. That can work for a demo, but it becomes hard to manage when a team needs to understand what the system is doing, why it made a decision, how much it costs, and whether it is still performing well over time.

This project shows a more accountable way to package AI workflows:

- model providers can be swapped or tested without rewriting the workflow
- prompts are organized so changes can be reviewed instead of hidden in code
- safety checks can route uncertain outputs to review before they reach a user
- evaluations help catch quality drops when prompts or models change
- traces show what ran, how long it took, whether it failed, and what it may have cost
- CLI and API entry points make the workflow easier to test, demo, and operate

Blacklight Studio keeps those ideas small enough to understand quickly while still runnable end to end.

## Repository Layout

The public repo root is intentionally minimal. The implementation, docs, tests, Docker assets, and package configuration live under [`platform/`](platform/).

Start here for the full project:

- [Platform README](platform/README.md)
- [Architecture](platform/docs/architecture.md)
- [Provider configuration](platform/docs/provider-configuration.md)
- [Release notes](platform/docs/release-notes.md)

## Quickstart

```bash
cd platform
pip install -e ".[dev,api]"
blacklight demo --verbose
```
