# Milestone 5 Issue Tickets: Business-User App Productization

Milestone 5 turns the CLI-ready package into a product direction for non-technical users. The goal is that a business user can install an application, click an icon, run workflows, and review status/history without touching the command line.

This milestone is intentionally separate from Milestone 4. Milestone 4 proves engineering operability through the CLI package; Milestone 5 explores the user-facing app shell and installer experience.

## Candidate. Package Desktop App Shell

Purpose:
Provide a polished entry point for business users who expect an installable app rather than a Python package or CLI.

Tasks:

- Define a desktop app packaging approach for Windows first, with macOS noted as a future target.
- Include app icon, installer, launch shortcut, and first-run experience.
- Start the local API/workflow service behind the app when needed.
- Show provider/model readiness before a user runs a workflow.
- Document package size, update cadence, signing, and support tradeoffs.

Acceptance criteria:

- A business user can install and launch the app without using a terminal.
- The app exposes whether it is running locally, using a hosted provider, or in fallback mode.
- Packaging notes explain support risks and deployment assumptions.

Suggested labels:

- `enhancement`
- `usability`
- `release`

## Candidate. Add First-Run Provider Setup

Purpose:
Hide provider configuration complexity behind a guided setup flow.

Tasks:

- Add first-run choices for local model, hosted provider, or mock/demo mode.
- Explain privacy mode, cost mode, and quality mode in business-friendly language.
- Validate provider readiness before saving configuration.
- Provide clear recovery steps when the provider is unavailable.

Acceptance criteria:

- A new user can complete setup without editing environment variables.
- Provider readiness is visible.
- Failure states are actionable and do not expose implementation jargon.

Suggested labels:

- `usability`
- `provider-gateway`
- `release`

## Candidate. Add Local Model Management

Purpose:
Make local inference shippable for business users by managing model availability inside the application experience.

Tasks:

- Decide whether the app bundles a small default model or downloads one during first run.
- Add model health checks and clear status messages.
- Document hardware requirements and expected performance ranges.
- Explain model licensing, update strategy, and disk usage.
- Support local-model fallback when the hosted provider is unavailable, privacy mode is selected, or the user chooses a local model.

Acceptance criteria:

- The user can see whether the local model is installed, loading, ready, or unavailable.
- The app can identify a ready local model fallback when one is installed and configured.
- Local model tradeoffs are documented clearly: privacy/control versus package size, hardware compatibility, quality, and support burden.

Implemented scope:

- Add `blacklight local-model status` for local runtime readiness inspection.
- Add `/console/local-model` and `/api/console/local-model` for app-visible local model status.
- Report Ollama status as `unavailable`, `loading`, or `ready` based on configuration, endpoint reachability, and installed model list.
- Surface start/install commands, installed model choices, local fallback status, private hosted-provider status, and tradeoff notes without requiring model downloads in CI or quickstart.
- Keep provider keys out of app-editable `user.env`; private keys belong in `.env`, shell environment variables, or deployment secrets.
- Keep model weights out of the repo; a future installer can choose first-run download with explicit disk, license, hardware, quality, and support disclosures.

Suggested labels:

- `enhancement`
- `provider-gateway`
- `usability`
- `release`

## Candidate. Add Session History UI

Purpose:
Expose operational history to business users without requiring CLI trace commands.

Tasks:

- Show a timeline of workflow runs for a session.
- Include provider, model, status, cost estimate, review outcome, and failure reason.
- Add filters for accepted, needs-review, rejected, and failed requests.
- Link reviewable outputs to a simple review surface.

Acceptance criteria:

- A user can inspect what happened in a session from the app.
- Cost and review status are visible without reading raw trace JSON.
- The UI maps to the same trace/session model used by the CLI.

Suggested labels:

- `observability`
- `usability`
- `enhancement`

## Candidate. Add Business Review Queue UI

Purpose:
Turn `needs_review` from an internal status into a usable business workflow.

Tasks:

- List items that need review.
- Show why the item was routed to review.
- Allow approve/reject/needs-more-info outcomes.
- Persist review decisions for audit and future evals.

Acceptance criteria:

- Reviewable outputs are not buried in logs.
- Review decisions are visible and auditable.
- The UI keeps rejected outputs out of automated downstream workflows.

Suggested labels:

- `guardrails`
- `usability`
- `enhancement`
