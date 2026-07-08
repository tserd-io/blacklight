# Managed Agents

Blacklight treats a managed agent as a governed product surface around a workflow.

The current implementation starts with one packaged agent:

```text
ticket_classifier_agent
-> ticket_classifier workflow
-> TicketClassification output
```

The goal is not to create an autonomous agent builder yet. The goal is to make a workflow inspectable as an agent before it becomes editable, runnable as a graph node, or connected to broader tools and retrieval.

## Workflow, Agent, And Future Graph Node

A workflow is executable business logic. In Blacklight today, `ticket_classifier` accepts a support-ticket style input, renders a prompt, calls the configured provider, validates the output, applies guardrails, and writes trace evidence.

A managed agent is the governed profile around that workflow. It answers:

- what the workflow is allowed to receive
- what context it can use
- what provider and prompt policy applies
- what output it is allowed to produce
- what it may touch or route onward
- what review and guardrail requirements apply
- what trace evidence must prove the behavior

A future graph node is a managed agent used inside a larger workflow graph. A graph node should not be just a function call. It should carry its domain, governed range, trace contract, and review policy with it so graph validation can decide whether it is safe to connect to another node.

## Domain

An agent domain is the permitted input and context boundary.

For `ticket_classifier_agent`, the domain includes:

- ticket subject and body
- session id and idempotency key when supplied
- approved static sample support-ticket context
- public-safe synthetic eval fixtures
- provider policy routed through the shared provider factory
- prompt ids and allowed prompt versions
- limits such as no external retrieval and no source-record mutation

The domain is intentionally explicit because it prevents vague agent behavior. A reviewer should be able to ask, "What was this agent allowed to know or use?" and find the answer in the agent profile.

## Governed Range

An agent governed range is the permitted output and touch surface.

For `ticket_classifier_agent`, the governed range includes:

- `TicketClassification` structured output
- read-only classification metadata
- trace rows written through the shared trace store
- eval metrics written during deterministic evals
- review routing for `needs_review=true` outputs
- guardrail enforcement through schema validation and sensitive-text checks

The governed range is not just the return type. It also states what the agent can affect after producing output. This matters because future agents may propose actions, fill forms, route records, or trigger review handoffs.

## Domain-To-Range Trace

Blacklight's core rule is:

```text
agent(domain) -> governed range
```

Every important run should eventually prove how the permitted domain became the actual governed range outcome.

The trace path should include:

```text
domain boundary
-> run inputs
-> context bundle
-> prompt/provider call
-> validation
-> guardrail decision
-> range output
-> review/export/touch decision
-> eval evidence
```

This is why managed agents should be inspectable before they are editable. If a user can edit an agent before the domain, governed range, and trace contract are visible, the system becomes hard to audit. Inspectability creates the contract first; editing can come later with validation.

## Graph Readiness

Future graph validation should compare one node's governed range against the next node's domain.

Example:

```text
Node A governed range
-> classification.category, severity, needs_review

Node B domain
-> accepts classification.category and severity
-> rejects unreviewed needs_review outputs
```

That connection is valid only if Node A produces the fields Node B requires and if Node B's domain allows the review state coming from Node A.

This is the range-to-domain compatibility check:

```text
previous_node.governed_range must satisfy next_node.domain
```

Graph execution frameworks such as LangGraph can be useful later, but they should execute graphs after Blacklight validates compatibility. They should not become the source of truth for whether a graph is safe.

## Inspectable Before Editable

The first milestone keeps managed agents read-only on purpose.

Read-only profiles let users inspect:

- domain boundaries
- governed range
- prompt ids and versions
- related workflow
- trace requirements
- review policy
- eval evidence
- CLI/API/console paths

This gives business users and technical reviewers a shared description of what an agent is allowed to do. Later edit/create flows can validate changes against the same model instead of inventing a separate configuration surface.

## Current Surfaces

CLI:

```bash
blacklight agents list
blacklight agents show ticket_classifier_agent
blacklight agents show ticket_classifier_agent --json
```

API:

```text
GET /api/agents
GET /api/agents/ticket_classifier_agent
```

Console:

```text
/console/agents
/console/agents/ticket_classifier_agent
```

These surfaces are read-only and require no private provider credentials.

## Non-Goals

Milestone 7 does not include:

- arbitrary user-created agents
- agent editing or promotion workflows
- autonomous tool selection
- unrestricted retrieval
- graph execution
- LangGraph as a required runtime
- side-effecting actions from agent output
- document or form automation beyond the existing sample workflow

## Safety Constraints

Managed agents should preserve Blacklight's governance layer:

- provider calls must go through the provider gateway
- prompt versions must be declared and inspectable
- output must validate against a typed schema
- guardrail outcomes must be recorded
- review-required outputs must stay blocked from downstream automation
- traces must connect the run to session, prompt, provider, model, validation, guardrail, cost, and error evidence
- future tools and retrieval must be declared in the domain before use
- future graph edges must pass range-to-domain compatibility checks before execution

The product story is simple: Blacklight agents are not magic workers. They are governed workflow surfaces with explicit boundaries, traceable behavior, and reviewable outputs.
