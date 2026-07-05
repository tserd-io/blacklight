![Blacklight Studio logo](platform/docs/assets/blacklight-studio-readme-logo.png)

# LLM Platform Starter

A compact portfolio project for a local, self-explaining LLM workflow platform.

The public repo root is intentionally minimal. The implementation, docs, tests, Docker assets, and package configuration live under [`platform/`](platform/).

Start here:

- [Platform README](platform/README.md)
- [Architecture](platform/docs/architecture.md)
- [Provider configuration](platform/docs/provider-configuration.md)
- [Release notes](platform/docs/release-notes.md)

Quickstart:

```bash
cd platform
pip install -e ".[dev,api]"
llm-platform demo --verbose
```
