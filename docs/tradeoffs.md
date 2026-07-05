# Tradeoffs

This project is intentionally small. The goal is to demonstrate the platform layer around LLM workflows without turning the starter into an unfinished enterprise system.

The MVP favors local repeatability, inspectable code, and concrete operational signals over breadth. The tradeoffs below are design decisions, not missing pieces.

## What The MVP Optimizes For

### Deterministic local path

The default provider is a deterministic mock provider. This keeps the quickstart, tests, evals, and CI runnable without API keys, network access, or model availability.

What this buys:

- stable tests and examples
- public-safe demos
- no surprise provider spend
- easy review from a fresh clone

What it does not prove:

- live provider quality
- real model latency
- real token pricing
- vendor-specific failure behavior

Live provider smoke tests are intentionally deferred to configured environments with explicit secrets.

### Small provider gateway

The provider interface normalizes prompts, model names, token counts, provider names, and metadata. It is enough to support mock, OpenAI, and user-owned providers without requiring a full plugin marketplace.

What this buys:

- one workflow path for mock and live providers
- a clear custom-provider extension point
- predictable request and response objects

What is deferred:

- provider discovery
- provider capability negotiation
- model-specific schema constraints
- streaming responses
- multi-provider failover

Those are production concerns once there are multiple real providers to manage.

### JSON prompt registry

Prompts are stored as JSON files in the repository. This makes prompt versions reviewable in normal code review and keeps the starter independent of external prompt-management services.

What this buys:

- transparent prompt metadata
- versioned templates alongside code
- easy prompt inspection through CLI commands
- deterministic evals against known prompt versions

What is deferred:

- prompt approval workflows
- audit signatures
- remote prompt deployment
- environment-specific prompt promotion

The repo shows the shape of prompt governance without pretending to be a full governance system.

### Pydantic validation and simple guardrails

The MVP validates structured JSON with Pydantic and routes outputs into `accepted`, `needs_review`, or `rejected`. Basic PII checks are included to demonstrate review routing.

What this buys:

- typed workflow outputs
- clear failure categories
- a visible boundary between automation and review
- traceable guardrail outcomes

What is deferred:

- full PII redaction
- policy-specific safety rules
- domain-specific risk scoring
- reviewer assignment and queue integrations

The point is to make guardrails operationally visible, not to claim comprehensive safety coverage.

### SQLite for traces, eval metrics, and idempotency

SQLite keeps the platform inspectable and runnable locally while still preserving real operational concepts: request IDs, session IDs, latency, token counts, estimated cost, validation outcomes, eval runs, and idempotency records.

What this buys:

- local observability without infrastructure
- durable cross-process idempotency for the demo workflow
- simple joins between eval cases and traces
- a useful migration target for production storage

What is deferred:

- managed databases
- distributed locking
- data retention policy
- warehouse export
- OpenTelemetry pipelines

SQLite is the smallest storage choice that still demonstrates responsible traceability.

### Reliability primitives before orchestration

The project includes retry, timeout, rate-limit, and idempotency behavior. It avoids introducing a background queue or workflow engine.

What this buys:

- visible failure behavior in normal tests
- lower implementation complexity
- direct CLI/API smoke testing
- a clear path to later orchestration

What is deferred:

- async job queues
- distributed rate limiting
- circuit breakers
- backoff policy tuning
- dead-letter queues

The MVP keeps reliability close to the provider call so reviewers can see the behavior without learning an orchestration framework.

## Deferred Production Features

These are intentionally out of scope for the starter:

- multi-tenant auth and RBAC
- prompt approval and promotion workflows
- distributed tracing backend
- provider plugin marketplace or discovery mechanism
- advanced circuit breakers, backoff policies, and async orchestration
- distributed rate limiting across multiple API processes
- external idempotency store for multi-host deployments
- required local LLM runtime for CI
- full PII redaction pipeline
- RAG retrieval service
- Kubernetes deployment manifests
- advanced eval rubrics and human review UI
- operational cost and ownership guide for regular live runs

Each item has a natural production path, but adding all of them would bury the core platform pattern. The MVP is intentionally a scaffold: enough to show how the pieces connect, small enough to audit quickly.

## Production Extension Path

The next production version would likely replace local defaults with managed services while keeping the same boundaries:

- replace SQLite traces with a database, warehouse table, or OpenTelemetry exporter
- replace in-memory rate limiting with Redis or gateway-level quotas
- replace local prompt JSON with a governed prompt registry if team process requires it
- route `needs_review` outputs to a task queue or review tool
- add live provider smoke tests behind secrets and explicit flags
- use trace metrics to monitor cost, latency, failure rate, validation rate, and review volume

The implementation is deliberately shaped so those extensions are additive rather than a rewrite.
