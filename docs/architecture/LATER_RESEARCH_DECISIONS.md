# Later Research Decisions

This document converts the original Later Research list into explicit product and architecture decisions. The goal is to keep Vantage honest: finish the research where a decision is enough, and only promote implementation work when the safety model is clear.

## Decision Summary

| Topic | Current decision | Status |
| --- | --- | --- |
| Rust remote agent | Keep the HTTP agent contract stable; defer Rust until distribution friction justifies a compiled binary. | Decided, not started |
| Multi-user UI authentication and roles | Do not build app-native users until there is a real multi-operator deployment. Use reverse-proxy auth for early shared installs. | Decided, deferred |
| Multi-control-plane deployments | Not supported with SQLite. Requires Postgres, leader election or ownership leases, and agent-side control-plane identity. | Decided, deferred |
| Postgres support | Support non-SQLite SQLAlchemy URLs at the engine layer; keep SQLite as the default. | Foundation shipped |
| Cross-node model synchronization | Treat as a planning surface first. Do not copy, pull, or delete models until the agent action contract is allowlisted and auditable. | Planned |
| Host service remediation | Use a privileged local node agent, never a privileged backend container. Every action must be allowlisted, confirmed, idempotent, and recorded as a Run. | Boundary defined |

## Rust Remote Agent

The Python FastAPI agent remains the right implementation while Vantage is changing quickly. It shares Pydantic models with the control plane, is easy to debug on a homelab node, and keeps the current iteration loop fast.

Rust becomes attractive when distribution is the problem:

- operators want a single binary with no Python runtime
- agents need to run on small or locked-down worker nodes
- packaging and upgrade ergonomics matter more than iteration speed
- the HTTP contract has stabilized enough that rewrite churn is low

Do not plan a broad rewrite. Instead, preserve the agent boundary so a Rust implementation can satisfy the same endpoints later:

- `GET /health`
- `GET /gpu`
- `GET /models`
- `GET /runs`
- future `POST /actions/*` endpoints only after allowlists and audit semantics are final

## Multi-User UI Authentication And Roles

Vantage remains single-operator by default. For early shared installs, put Vantage behind a trusted reverse proxy or VPN that handles authentication. App-native user accounts are intentionally deferred because they change the product from local-first control plane to multi-tenant operations software.

Before app-native users are implemented, Vantage needs:

- a user table and migration path
- session or token storage strategy
- role definitions for read-only, operator, and admin actions
- audit metadata that records actor identity on every configuration-impacting Run
- UI affordances for disabled actions when a user can observe but not mutate state

Default role model when promoted:

| Role | Intended permissions |
| --- | --- |
| Viewer | Read dashboards, inspect runs, export non-sensitive reports. |
| Operator | Trigger capability checks, evals, warning acknowledgement, and safe refresh actions. |
| Admin | Edit nodes, routing policies, auth settings, remediation allowlists, and release/security settings. |

## Multi-Control-Plane Deployments

Multiple active Vantage control planes should not point at the same SQLite file or independently mutate the same agents. That creates split-brain risk: duplicate polling, conflicting routing changes, duplicate eval execution, and ambiguous action ownership.

Multi-control-plane support requires:

- Postgres or another shared database with real concurrent writer semantics
- ownership leases for pollers, scheduled evals, scheduled reports, and remediation workers
- explicit `control_plane_id` on action Runs and agent requests
- agent-side trust rules that accept commands only from allowed control-plane identities
- UI indicators for which control plane owns a worker loop

Until those exist, the supported production shape is one active control plane plus many observed worker nodes.

## Postgres Support

SQLite remains the default because it is local-first, zero-ops, and appropriate for a single operator. Vantage now supports non-SQLite SQLAlchemy URLs at the engine-configuration layer so operators can experiment with Postgres without tripping over SQLite-specific connection arguments.

Use Postgres when:

- run history or node snapshots outgrow SQLite comfort
- multiple backend processes need safe concurrent writes
- a deployment needs external database backup, restore, and monitoring workflows
- future multi-control-plane work becomes real

Required environment shape:

```bash
VANTAGE_DATABASE_URL=postgresql+psycopg://vantage:<password>@<postgres-host>:5432/vantage
```

Install the optional driver package when running outside the provided image:

```bash
pip install "vantage[postgres]"
```

Postgres support is a database backend option, not a multi-control-plane guarantee by itself.

## Cross-Node Model Synchronization

Model synchronization should start as planning and visibility. The first useful UI is not "sync now"; it is "these nodes disagree and here is the safest plan."

Minimum product shape:

- compare model name, digest, size, and placement across nodes
- mark a source node and one or more target nodes
- show a dry-run plan before any transfer
- record the plan as a Run before execution
- execute only through an authenticated agent action
- record per-target success, failure, duration, and final digest

Do not implement direct filesystem copies from the control-plane backend. A sync action may eventually use Ollama pull/copy semantics or an agent-managed transfer, but the control plane should remain the observer and coordinator.

## Host Service Remediation

Host remediation is allowed only through a local or remote node agent that is explicitly installed for that purpose. The Dockerized backend must not be made privileged to restart services, read host sockets, or mutate host state.

Every remediation action must define:

- action type
- target resource
- required role
- idempotency-key structure
- allowed node roles
- timeout
- verification check
- success and failure Run metadata

Initial safe candidates:

| Action | Scope | Verification |
| --- | --- | --- |
| `ollama_restart` | Restart Ollama service on one node. | `/health` and `/models` recover after restart. |
| `agent_restart_self` | Ask agent supervisor to restart the agent process. | Agent returns healthy after supervisor restart. |
| `clear_model_cache` | Remove only explicitly allowlisted cache paths. | Disk and model inventory refresh. |

Unsafe by default:

- arbitrary shell commands
- arbitrary path deletion
- Docker socket mounting into the backend
- privileged backend containers
- remediation that bypasses Run audit records

## Promotion Criteria

A Later Research item can move into a numbered phase only when it has:

- a bounded operator problem
- an explicit non-goal list
- a data model or contract
- a failure-mode story
- tests that cover the safety boundary
- documentation for operators
