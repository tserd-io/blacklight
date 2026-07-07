# Architecture

The project models a compact internal LLM platform layer. Application workflows call a stable platform interface instead of calling model providers directly.

## Components

- Provider gateway normalizes requests and responses across model providers.
- Prompt registry loads versioned templates and renders validated inputs.
- Guardrails validate structured outputs, flag basic PII risk, and route outcomes as accepted, needs review, or rejected.
- Observability stores request metadata, latency, token counts, estimated cost, validation status, guardrail outcome, and error category.
- Eval runner executes synthetic fixtures against the same platform path used by the API.

## Integration Boundary

Blacklight should own governance, traceability, evals, guardrails, provider policy, and review decisions.

LangGraph and LangChain can be useful future adapters:

- LangGraph can execute validated workflow graphs with state, branching, retries, and human-review interrupts.
- LangChain can adapt retrievers, document loaders, model wrappers, and tools behind Blacklight-owned registries and policies.

They should not replace Blacklight's platform layer. See [LangGraph And LangChain Integration Strategy](langgraph-langchain.md).

## Request Flow

1. A workflow submits a synthetic support ticket.
2. The prompt registry renders the active prompt version.
3. The provider gateway calls the configured model provider.
4. Guardrails parse and validate the JSON response, assigning an `accepted`, `needs_review`, or `rejected` outcome.
5. The trace store writes operational metadata and the guardrail outcome to SQLite.
6. The API returns a typed response object.

## Why SQLite

SQLite keeps the MVP runnable without managed infrastructure while still making traces queryable. In a production platform, this could be replaced by a warehouse table, OpenTelemetry collector, or observability backend.
