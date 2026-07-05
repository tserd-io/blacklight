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

## Backend Choices

Backend decisions fall into two categories: where model inference runs, and where operational data is stored or exported. The MVP uses the simplest local choices, but the boundaries are meant to make production backends replaceable.

### Model backends

#### Mock provider

Use the mock provider for development, CI, demos, and public-safe examples.

Why an organization would use it:

- prove workflow behavior before paying for live calls
- keep tests deterministic
- avoid sending data outside the local environment
- make onboarding work without credentials

Tradeoff:

- it does not prove real model quality, provider latency, pricing, rate-limit behavior, or vendor reliability

#### Hosted API provider

Hosted APIs include providers such as OpenAI, Azure OpenAI, Anthropic, Google, or similar managed model services.

Why an organization would use it:

- fastest path to strong model quality
- no GPU procurement or inference operations
- easier burst scaling
- clear per-token pricing model

Tradeoff:

- vendor dependency, data-governance review, per-token spend, provider rate limits, and exposure to pricing or API changes

Hosted APIs are usually the right first production choice when the organization values speed, model quality, and lower infrastructure burden.

#### Local or on-prem provider

Local providers include Ollama, LM Studio, llama.cpp, vLLM, or a private localhost HTTP endpoint.

Why an organization would use it:

- stronger data control
- offline or private-network operation
- no external per-token API bill
- reuse of existing hardware
- ability to standardize on an open model

Tradeoff:

- hardware cost, electricity, model downloads, runtime tuning, security patching, uptime, capacity planning, and potentially lower model quality

Local inference is most defensible when privacy or control matters, hardware already exists, or the same model serves enough workflows to keep utilization high. For a low-volume workload, dedicated hardware can be more expensive per run than a hosted API.

For a CLI-ready package, local inference is more shippable as an optional fallback than as the required primary path. A fallback can be used when a hosted provider is unavailable, a cost ceiling is reached, data cannot leave the environment, or a degraded private/offline response is acceptable. That fallback should be visible in traces through provider metadata and a fallback reason rather than silently changing behavior.

For a business-user desktop app, the tradeoff changes. If the app provides an installer, app icon, first-run setup, model readiness checks, and managed model download or bundled model support, local inference can be a polished product feature instead of a developer setup burden. That belongs in a later app-productization milestone, separate from the CLI-ready package.

#### Self-hosted cloud model

Self-hosted cloud inference runs open or private models on cloud GPUs through tools such as vLLM, TGI, or a Kubernetes deployment.

Why an organization would use it:

- more control than hosted APIs
- cloud elasticity without buying hardware
- ability to tune model/runtime choices
- clearer network and data boundaries than public APIs in some organizations

Tradeoff:

- GPU costs, deployment complexity, autoscaling, monitoring, incident response, and capacity management

This is a better fit for teams that already operate cloud infrastructure and need control beyond what a hosted API offers.

### Storage and observability backends

#### SQLite

SQLite is the MVP trace, eval, and idempotency backend.

Why an organization would use it:

- local development
- demos
- single-process tools
- lightweight proof of traceability

Tradeoff:

- not a multi-service production observability backend and not ideal for long retention, dashboards, or concurrent distributed writers

#### Postgres or managed relational database

A relational database is the natural first production step for trace and eval history.

Why an organization would use it:

- durable records
- joins across sessions, eval runs, cases, and traces
- backups and access control
- familiar operational model

Tradeoff:

- schema migrations, database hosting, credentials, retention policy, and query performance work

#### Warehouse or analytics backend

Warehouses such as BigQuery, Snowflake, or Databricks are better for reporting than request-time debugging.

Why an organization would use it:

- cost reports
- usage trends
- model/provider comparisons
- automation ROI analysis

Tradeoff:

- not usually the first place an operator debugs a live request

#### OpenTelemetry or monitoring backend

OpenTelemetry exporters send traces and metrics to tools such as Datadog, Honeycomb, Grafana, Jaeger, New Relic, or an OpenTelemetry Collector.

Why an organization would use it:

- production dashboards
- alerting
- distributed trace timelines
- latency and failure-rate monitoring

Tradeoff:

- instrumentation discipline, backend cost, and operational setup

This is the right direction when the workflow becomes business-critical enough that failures, latency, and cost regressions need active monitoring.

### Rule of thumb

- Use `mock` to build safely.
- Use hosted APIs to move fast.
- Use local/on-prem inference when control or privacy outweighs operating complexity.
- Use self-hosted cloud inference when customization matters and the team can operate infrastructure.
- Use SQLite for the local MVP.
- Use Postgres for production history.
- Use OpenTelemetry or monitoring tools for live operations.
- Use a warehouse for cost, usage, and ROI reporting.

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
