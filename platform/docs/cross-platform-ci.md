# Cross-Platform CI Runner Evaluation

## Recommendation

Keep default pull-request CI Linux-only for now.

Do not add Windows and macOS runners to every PR yet. The current Linux jobs already protect the most important fresh-clone promises: install the package, run lint and tests, smoke the README commands, validate package metadata, and build the Docker image in mock mode.

Add scoped Windows and macOS smoke checks later, preferably on a scheduled workflow, release workflow, or explicit manual workflow dispatch. That gives the project a cross-platform signal without making every normal PR slower or noisier.

## Decision

Blacklight should defer always-on Windows and macOS PR runners until the CLI/package install path becomes a release-blocking foundation for the future app shell or GUI, or until one of these becomes true:

- The app-shell or installer work depends on platform-specific behavior.
- A bug appears that Linux CI cannot catch, such as path handling, shell quoting, filesystem permissions, or wheel install behavior.
- Release approval needs a stronger cross-platform install signal.

Until then, cross-platform checks should stay lightweight, mock-provider-first, and no-secret.

## Options Compared

### Keep Linux-only CI

Best fit for the current default PR path.

What it protects:

- fast feedback on normal changes
- Python version compatibility through the core test matrix
- quickstart behavior in mock mode
- package build and metadata validation
- Docker API smoke behavior

Tradeoff:

- does not catch Windows PowerShell quoting, Windows path behavior, macOS shell/path differences, or platform-specific package install issues

### Add Windows smoke checks to every PR

Useful once Windows packaging or app-shell behavior becomes release-critical.

What it would catch:

- backslash path assumptions
- PowerShell command quoting issues
- console-script install behavior on Windows
- SQLite file path and permission differences

Tradeoff:

- adds queue time and maintenance surface to every PR
- can fail for runner-specific environment differences that are not product defects

### Add macOS smoke checks to every PR

Useful later, but not urgent.

What it would catch:

- POSIX shell differences from Ubuntu
- package install behavior on macOS runners
- future app-shell assumptions for macOS distribution

Tradeoff:

- macOS runners are usually scarcer and more expensive than Linux runners
- macOS is currently a future target, not a first-class packaging target

### Add cross-platform checks only for scheduled, manual, or release workflows

Best next step when cross-platform confidence becomes useful.

What it protects:

- release confidence without slowing every PR
- periodic detection of platform drift
- manual verification before a release candidate

Tradeoff:

- regressions may be detected later than the PR that introduced them

## Proposed Future Smoke Scope

A future cross-platform smoke workflow should stay small:

- runners: `windows-latest`, `macos-latest`, and optionally `ubuntu-latest` for parity
- Python: one supported version, probably `3.11` or the release baseline
- install: `pip install -e ".[dev,api]"`
- commands:
  - `blacklight health`
  - `blacklight demo --trace-db-path .tmp/cross-platform-smoke.sqlite3 --session-id cross-platform-smoke`
  - `blacklight eval run --trace-db-path .tmp/cross-platform-smoke.sqlite3 --session-id cross-platform-eval`
- environment:
  - `LLM_PROVIDER=mock`
  - `OLLAMA_BASE_URL=https://example.com`
- trigger:
  - `workflow_dispatch`
  - `schedule`
  - optionally `push` tags matching `v*`

Do not include Docker, Ollama model downloads, browser UI checks, or live provider calls in this workflow. Those are heavier and should remain separate opt-in checks.

## Follow-Up Issue Candidate

Title: Add scheduled cross-platform CLI smoke workflow

Scope:

- Add a GitHub Actions workflow for Windows and macOS CLI smoke checks.
- Trigger it manually and on a weekly schedule.
- Keep it mock-provider-first and no-secret.
- Run only install, `blacklight health`, `blacklight demo`, and `blacklight eval run`.
- Do not add it to every pull request until cross-platform packaging becomes release-critical.

Acceptance criteria:

- Windows and macOS smoke checks pass without provider keys.
- The workflow can be run manually before release approval.
- Normal PR CI remains Linux-only and fast.
- Failures clearly identify the OS runner.
