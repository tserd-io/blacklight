<p align="center">
  <img src="wiki/assets/blacklight-studio-wiki-header-console.png" alt="Blacklight Studio console wiki header: AI workflow platform starter" width="100%">
</p>

# Blacklight Studio Wiki

Blacklight Studio is a compact AI workflow platform starter for teams that want shared provider routing, versioned prompts, guardrails, evals, and observability without turning the first implementation into a platform rewrite.

The default path is local and deterministic: mock provider, synthetic support-ticket data, SQLite traces, and pytest coverage. You can explore the whole workflow before adding live model credentials.

---

## Start Here

| I want to... | Go here | What you get |
| --- | --- | --- |
| Understand the system shape | [Architecture](architecture.md) | Component boundaries, request flow, and how the platform pieces fit together |
| Configure model backends | [Provider Configuration](provider-configuration.md) | Mock, OpenAI, custom provider, and Ollama setup notes |
| Build my own workflow | [Create Your Own Workflow](create-your-own-workflow.md) | A practical path for adapting the starter to a new use case |
| Review release scope | [Release Notes](release-notes.md) | Current version notes and user-facing capabilities |

## Quick Start

```bash
cd platform
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,api]"
pytest
blacklight demo --verbose
```

The demo runs the mock ticket-classification workflow, applies validation and guardrails, writes a trace, and prints follow-up commands for inspecting what happened.

## What This Gives You

| Layer | Why it matters |
| --- | --- |
| Provider routing | Swap mock, OpenAI, local, or custom providers without rewriting workflow code |
| Prompt registry | Keep prompt versions inspectable and reviewable instead of buried in application logic |
| Guardrails | Route uncertain, rejected, or sensitive outputs before they reach downstream users |
| Evals | Catch prompt or provider regressions with deterministic fixtures |
| Traces | Connect latency, token use, estimated cost, validation, failures, and review outcomes |
| CLI and API | Smoke test locally, demo quickly, and expose the workflow through FastAPI |

## Recommended Reading Path

1. [Architecture](architecture.md) - see the core request flow.
2. [Provider Configuration](provider-configuration.md) - choose mock, OpenAI, custom provider, or Ollama.
3. [Create Your Own Workflow](create-your-own-workflow.md) - adapt the starter to a real team workflow.
4. [Eval Methodology](eval-methodology.md) - understand how quality checks are structured.
5. [Operational Cost and Ownership](operational-cost-and-ownership.md) - plan cost visibility and ownership.

## Operator Notes

| Topic | Page |
| --- | --- |
| Failure handling | [Failure Modes](failure-modes.md) |
| Design tradeoffs | [Tradeoffs](tradeoffs.md) |
| Packaging direction | [Desktop Packaging](desktop-packaging.md) |
| Cross-platform CI | [Cross-Platform CI](cross-platform-ci.md) |
| Roadmap | [Roadmap](roadmap.md) |

## Local Signals To Check

```bash
blacklight health
blacklight prompts list
blacklight eval run
blacklight traces list --trace-db-path traces.sqlite3
```

Expected fresh-clone behavior: no API key is required, the mock provider is active, and the demo can run end to end locally.

---

<p align="center">
  <strong>Blacklight Studio:</strong> small enough to read, complete enough to run, structured enough to grow.
</p>
