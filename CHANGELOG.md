# Changelog

All notable Vantage changes are tracked here.

This project follows a pragmatic Keep a Changelog style and uses semantic versioning once public releases begin.

## [Unreleased]

No unreleased changes yet.

## [0.1.0] - 2026-05-13

### Added

- Visibility-first local AI command center with Nodes, Runs, Models, Routing, and Evals surfaces.
- FastAPI backend, SQLite persistence, React/Vite frontend, Docker Compose development environment, and production Compose deployment path.
- Remote Linux node agent contract with shared-token authentication.
- SSE full-state streaming, bounded snapshot pruning, run CSV/JSON exports, and operator guide drawer.
- Eval Lab, Eval Intelligence, routing policy control, guided remediation, production packaging, Portainer guide, setup checker, release bundle script, and GitHub release workflow.
- Demo mode behind `VANTAGE_DEMO_MODE=1` with safe synthetic nodes, models, runs, warnings, eval data, and routing policies.
- Dismissible in-app onboarding checklist for first-run operator setup.
- First-run setup wizard that generates token, node registry, local Ollama, and verification snippets without mutating local files.
- Static product microsite under `docs/product/`.
- Product-ready install walkthrough script and shot list under `docs/walkthrough/`.
- Open-source repository assets: MIT license, support guide, code of conduct, issue templates, pull request template, screenshot guide, and release announcement template.
- Public-safe tracked bootstrap defaults with the example remote worker disabled until operators configure their own agent URL.
- Configurable remote-agent identity through `VANTAGE_AGENT_NODE_ID`.

### Changed

- README, Roadmap, Operator Guide, Security, and Release documentation now describe the public/open-source operating model.
- First-run quickstart now starts in demo mode to avoid polling real or placeholder infrastructure.

### Removed

- Machine-specific legacy `deploy/remote-worker` assets from the tracked release surface.
