# Tradeoffs

## Included

- Deterministic mock provider for local development and CI
- Optional OpenAI provider behind an extra dependency
- Custom provider import path for user-owned provider adapters
- Basic provider retry and timeout wrapper
- In-memory per-session provider rate limiting
- Stable idempotency key propagation across provider retry attempts
- SQLite-backed idempotency cache for completed ticket-classification requests
- JSON prompt registry to avoid requiring external services
- Pydantic validation for structured outputs
- SQLite trace store for transparent local observability

## Deferred

- Multi-tenant auth and RBAC
- Prompt approval workflow
- Distributed tracing backend
- Full provider plugin marketplace or discovery mechanism
- Advanced circuit breakers, backoff policies, and async orchestration
- Distributed rate limiting across multiple API processes
- External idempotency store for multi-host deployments
- Required local LLM runtime for CI
- Full PII redaction pipeline
- RAG retrieval service
- Kubernetes deployment manifests
- Advanced eval rubrics and human review UI

The goal is to show platform thinking without turning the repo into an unfinished enterprise system.
