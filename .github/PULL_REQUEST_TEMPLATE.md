# Pull Request

## Summary

Describe what changed and why.

## Related Issue

Closes #

## Type Of Change

- [ ] Feature or product improvement
- [ ] Bug fix
- [ ] Documentation
- [ ] CI/release automation
- [ ] Managed agent or architecture
- [ ] Refactor or maintenance
- [ ] Final QA / milestone approval

## User-Facing Impact

What can a user do now that they could not do before? If there is no user-facing change, say so.

## CLI/API/Console Parity

If this changes a workflow, explain how it appears across the product surfaces.

- CLI:
- API:
- Console/UI:

## Domain, Range, And Traceability

For agent, workflow, provider, validation, guardrail, trace, or eval changes:

- Domain changed or inspected:
- Range changed or produced:
- Trace path from domain to range:
- Guardrail or review behavior:

## Demo Or Mock-Provider Path

How can this be tried without private data, API keys, or paid provider access?

## Screenshots Or Output

Add screenshots, terminal captures, API responses, or trace/eval IDs when useful.

```text

```

## Verification

- [ ] `cd platform`
- [ ] `ruff check .`
- [ ] `pytest`
- [ ] Relevant CLI command tested
- [ ] Relevant API or console behavior tested
- [ ] Documentation/examples updated where needed

## Public-Safe Review

- [ ] No API keys, secrets, private prompts, customer data, or private planning details are included
- [ ] Demo data and screenshots are safe to publish
- [ ] Files under `plans/` are not included

## Reviewer Notes

Call out anything reviewers should pay special attention to.
