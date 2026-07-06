# App Shell Packaging Plan

This plan defines the app shell packaging direction for Blacklight Studio. The enterprise default should be a browser web app served from managed infrastructure. The desktop shell should be an optional local/private packaging layer that starts the same Blacklight service and opens the same console experience.

This gives enterprise teams a serviceable default while still preserving a polished local install path for demos, private model use, or environments that need local/offline operation.

In both modes, the user experience should still be clickable. A user should be able to click a Blacklight Studio application icon or launcher shortcut and land in the app, even when the target is a managed browser web app rather than a bundled desktop UI.

## Serviceability Direction

The most serviceable enterprise deployment is a browser web app:

- one centrally managed deployment instead of per-machine app updates
- cleaner SSO, IAM, network, audit, and policy integration
- centralized logs, traces, metrics, and operational support
- fewer OS-specific support paths across Windows, Linux, and future macOS users
- private provider keys and model access controlled by managed infrastructure

The desktop shell remains useful when the app must run locally, launch a local model runtime, work with private machine resources, or provide a polished installed demo. It should package the web console, not fork the product into a separate desktop-only UI.

Enterprise deployments can still provide clickable app behavior by installing a managed shortcut, start-menu entry, desktop file, or browser-installed app that opens the approved Blacklight web URL.

## Target Platforms

The managed browser web app should be platform-neutral. The optional desktop shell should treat Windows and Linux as first-class packaging targets.

- Browser web app: enterprise default for managed deployments.
- Windows desktop shell: first local packaged target for business-user testing.
- Linux desktop shell: supported for technical and operations users who want a local app shell around the same API and console.
- macOS: future target after Windows and Linux packaging decisions are proven.

## Shell Shape

The browser web app and desktop shell should share the same console routes. The desktop shell should be a thin wrapper around the local Blacklight service and console UI:

1. Launch the local API/workflow service if it is not already running.
2. Open the local console in an app window or controlled browser view.
3. Show provider and model readiness before workflows are run.
4. Keep settings and status visible without requiring a terminal.
5. Reuse the existing console routes, especially `/console`, `/console/providers`, `/console/local-model`, and `/console/settings`.

This keeps the desktop app small and avoids duplicating business logic in a separate frontend runtime.

## Clickable App Behavior

The packaging layer should provide a clickable entry point regardless of deployment mode:

- Managed web app: a branded shortcut, pinned browser app, start-menu entry, or Linux desktop entry opens the approved Blacklight URL.
- Local desktop shell: the app icon starts the local service if needed and opens `/console` in the packaged shell or controlled browser view.
- Demo mode: the app icon opens the local console with seeded/mock-mode readiness available.

This keeps the business-user mental model simple: click Blacklight Studio, review readiness, run the workflow. The deployment model can differ behind that entry point.

## App And Installer Icons

Required icon assets:

- App icon: `packaging/assets/blacklight-studio-icon-clean-square-hires.png`
- Installer icon: `packaging/assets/blacklight-studio-icon-flashlight-ring-clean-square-hires.png`

The app icon should represent the launched Blacklight Studio application. The installer icon should represent setup, discovery, and first-run readiness. These source PNG assets are expected to be converted into platform-specific formats during packaging, such as `.ico` for Windows and distribution-specific icon sizes for Linux.

## Installer Experience

The installer must clearly tell the user why administrator permissions may be required.

Required message:

> Blacklight Studio can install and configure a local model runtime for private/offline use. This may require administrator permissions and can download model files to this computer.

The installer must also offer a bypass path:

- Continue with local model setup if the user wants private/local inference.
- Skip local model setup if the user already has a hosted provider key or a configured provider endpoint.
- Start in mock/demo mode if the user wants to explore without a live provider.

This avoids forcing a local model install on users who already have an approved hosted provider key.

## First-Run Modes

The first-run screen should present three plain-language choices:

- Local model: best for privacy and offline control; may require admin permissions, disk space, and model downloads.
- Hosted provider: best when the user already has an approved provider key; may create usage costs.
- Demo mode: best for trying the app safely with synthetic examples and no live model.

Each mode should lead to a readiness check before any workflow is run.

## Runtime Status

The app shell should expose whether Blacklight Studio is:

- running locally with mock/demo mode
- using a hosted provider
- using a configured custom provider
- using a local model
- able to use a local model fallback

The existing local model status and provider settings endpoints are the source of truth for this status.

## Packaging Approach

Initial packaging should avoid bundling large model weights into the app installer. A first-run download is easier to explain, update, and support than a very large default installer.

Windows packaging should plan for:

- app shortcut with the app icon
- optional shortcut target for the managed Blacklight web URL
- installer using the installer icon
- local service startup behind the app
- user-writable data directory for SQLite traces and settings
- clear admin-permission prompt before local model runtime setup
- code signing before broad distribution

Linux packaging should plan for:

- app desktop entry with the app icon
- optional desktop entry target for the managed Blacklight web URL
- package-managed install path where possible
- user-writable data directory for traces and settings
- optional local model runtime setup that respects distribution-specific permissions
- no assumption that Docker, GPU drivers, or Ollama are already installed

macOS packaging is deferred. The likely future work is app bundle packaging, notarization, code signing, and a macOS-specific local model runtime decision.

## Tradeoffs

Package size:
Keeping model weights out of the base installer keeps downloads smaller. The tradeoff is that first-run setup must explain download size, licensing, and hardware requirements.

Updates:
The app shell, Python package, model runtime, and model weights may need different update cadences. The installer should avoid coupling all of them into one opaque update.

Signing:
Windows and macOS distribution should use code signing before a broad user release. Linux packaging should provide checksums and package metadata appropriate to the selected distribution path.

Support:
Local model setup creates support obligations around permissions, disk space, hardware compatibility, runtime startup, and model quality. Hosted-provider mode shifts support toward key management, provider access, and cost controls.

Deployment assumptions:
The first desktop release should assume single-user local operation. Multi-user shared machines, managed enterprise desktop deployment, fleet-managed desktop installs, and locked-down endpoint policies should be documented as later hardening work.
