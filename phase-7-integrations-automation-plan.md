# Phase 7: Integrations And Automation

## Goal
Expose Vantage's warnings, failed runs, eval signals, and reports to external automation tools without making the core control plane dependent on those tools.

## Tasks
- [x] Add optional external API token guard for integration endpoints → Verify: unauthorized integration calls return `401` when token is configured.
- [x] Build integration event export for warnings, failed runs, and eval regressions → Verify: API test returns normalized event records.
- [x] Add webhook dispatch adapters for generic, Slack, and Discord targets → Verify: service tests check outgoing payload shapes.
- [x] Add router-log import endpoint that creates durable `Run` records → Verify: import test persists router runs without duplicating IDs.
- [x] Add Markdown report export for incident notes and Obsidian → Verify: report API includes nodes, warnings, failed runs, and eval context.
- [x] Add collector registry seam for future model runtimes → Verify: unit test registers and resolves collector descriptors.
- [x] Update docs and env examples for n8n, webhooks, API tokens, reports, and collector plugins → Verify: roadmap and operator docs describe the new surfaces.
- [x] Run backend/frontend verification → Verify: pytest, frontend tests, and build complete.

## Done When
- [x] External tools can pull events, import router logs, and export Markdown reports.
- [x] Webhook dispatch is opt-in and token-protected.
- [x] Vantage has a clear plugin-style collector extension seam.
- [x] Documentation is current for open-source operators.
