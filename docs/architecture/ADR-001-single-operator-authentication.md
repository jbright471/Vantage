# ADR-001: Single-operator control-plane authentication

- Status: accepted
- Date: 2026-07-25

## Context

Vantage is a local-first, single-operator control plane. Its browser and non-integration `/api/*` routes can read operational data and trigger node, routing, eval, and LLM actions. Loopback binding is a useful network control, but it is not an application identity boundary.

## Decision

Vantage uses one high-entropy operator token to establish a short-lived signed browser session:

- `VANTAGE_CONTROL_PLANE_TOKEN` authenticates interactive login and may be used as a Bearer token by trusted operator scripts.
- `VANTAGE_SESSION_SIGNING_KEY` signs browser sessions and must be independently generated.
- The session cookie is `HttpOnly`, `SameSite=Strict`, path-scoped to `/`, and time-limited (eight hours by default).
- Cookie-authenticated unsafe requests require a double-submit CSRF token. Bearer-authenticated scripts do not.
- Login attempts are rate-limited. Costly LLM/eval paths have separate rate and concurrency limits.
- Health and authentication-status routes remain public so orchestration and the login screen can function.
- Integration automation continues to use its separate `VANTAGE_EXTERNAL_API_TOKEN`.

The browser never stores the operator token in local or session storage. Production Compose fails before startup when either required control-plane secret is missing.

## Consequences

This is intentionally smaller than a multi-user identity system and fits the current ownership model. It does not provide accounts, roles, external revocation, federation, or per-user audit attribution. A future multi-user or internet-facing edition should replace this design with mature OIDC and server-side authorization rather than extending the shared operator token into an account system.

Changing the session signing key invalidates all sessions. Logout clears browser cookies, but a copied stateless session remains valid until expiry; use a short maximum age and rotate the signing key after suspected theft.
