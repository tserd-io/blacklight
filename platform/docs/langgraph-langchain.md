# LangGraph And LangChain Integration Strategy

Blacklight should use LangGraph and LangChain as optional adapters, not as the core product architecture.

The guiding split:

```text
Blacklight owns governance.
LangGraph can execute graphs.
LangChain can adapt providers, tools, and retrieval.
```

This preserves Blacklight's platform value: domain/range contracts, traces, evals, guardrails, review, provider policy, and production evidence.

## LangGraph Fit

LangGraph is the stronger fit for Blacklight's long-term workflow direction.

It maps naturally to:

- typed workflow nodes
- guarded transitions
- durable run state
- retries
- human-review interrupts
- resumable execution
- branching workflows
- step-level traces

Future Blacklight workflow graphs could compile into LangGraph graphs:

```text
Blacklight workflow graph
-> validate domain/range compatibility
-> compile to LangGraph
-> execute
-> emit Blacklight traces, guardrail outcomes, reviews, and eval evidence
```

Blacklight should still own graph validation. LangGraph should not decide whether a workflow is safe to run.

## LangChain Fit

LangChain is useful as an adapter layer.

Good uses:

- retriever adapters for future context registry sources
- document loaders for controlled ingestion flows
- tool wrappers behind Blacklight's own `ToolDefinition`
- optional model wrapper behind the provider gateway

Blacklight should not become a thin LangChain wrapper. That would weaken the platform signal and hide the governance layer that makes the project valuable.

## Domain And Range Boundary

LangGraph/LangChain integrations must respect Blacklight's managed-agent model:

```text
agent(domain) -> governed range
```

Domain:

- input schema
- retrieval surface
- allowed context sources
- blocked context sources
- allowed tools
- provider/model policy
- cost and latency limits

Range:

- output schema
- touch surface
- allowed output channels
- review requirements
- guardrail enforcement
- failure and fallback behavior

The trace from domain to range must remain complete, even if LangGraph executes the graph or LangChain adapts a retriever/tool/model.

## Trace Requirements

Every LangGraph or LangChain-backed run should still produce Blacklight-native trace evidence:

- agent ID and version
- workflow ID and version
- domain snapshot
- input snapshot
- context bundle ID
- sources considered, used, blocked, stale, or missing
- tools allowed, requested, used, blocked, or skipped
- prompt ID and version
- provider/model
- validation result
- guardrail decisions
- range contract
- output snapshot
- touch attempts allowed or blocked
- review decision
- final status
- latency and estimated cost

The trace proves that the workflow stayed inside its permitted domain and only produced or touched what its range allowed.

## Human Review

LangGraph interrupts are a good future fit for Blacklight's review queue.

Example:

```text
agent output
-> guardrail/policy node
-> interrupt for human review
-> approve/edit/reject
-> resume workflow
```

Blacklight should remain the source of truth for:

- review requirement policy
- reviewer decision
- reviewer notes
- resumed workflow state
- audit trail

## Recommended Future Milestone

Create this only after managed agents and workflow runs are stable:

```text
Milestone: LangGraph Runtime Adapter
```

Candidate issues:

- Compile a simple Blacklight workflow graph into LangGraph.
- Run `ticket_classifier_agent` as a one-node LangGraph graph.
- Preserve Blacklight trace schema during LangGraph execution.
- Add human-review interrupt proof of concept.
- Prove output parity with the current workflow runner.
- Document when to use the native runner vs LangGraph adapter.

Acceptance criteria:

- Mock-mode execution requires no live provider credentials.
- The LangGraph path emits the same guardrail and trace evidence as the native path.
- Tests prove parity for the ticket-classifier workflow.
- LangGraph remains optional.

## Non-Goals

- Replacing the provider gateway with LangChain.
- Letting LangChain tools bypass Blacklight permissions.
- Letting agents choose unrestricted retrieval sources.
- Making LangGraph required for simple local workflows.
- Hiding Blacklight traces behind framework-native traces only.

## Positioning

The right portfolio story is:

> Blacklight can integrate with LangGraph and LangChain, but it keeps governance, traceability, evals, and policy enforcement in its own platform layer.

