# Vantage Release Announcement Template

Use this template for GitHub releases, community posts, or changelog summaries.

## Title

Vantage v0.1.0: Local AI Command Center

## Summary

Vantage is a local-first AI command center for operators running private models across local and remote machines. The first public release focuses on visibility, honest state, auditable actions, local evals, and a Docker-first path for homelab deployment.

## Highlights

- Nodes, Runs, Models, Routing, and Eval Lab surfaces for serious local AI setups.
- Public-safe demo mode, first-run setup wizard, in-app Operator Guide, and release-ready documentation.
- Remote agent contract with bearer/HMAC auth options, signed audit exports, and production Compose packaging.

## Upgrade Notes

- This is the first public release.
- Start with demo mode before connecting real worker nodes.
- Keep Vantage on a trusted LAN or VPN unless you add your own network access controls.
- Back up SQLite before upgrading future production deployments.

## Verification

```powershell
python -m pytest tests -q
cd frontend
npm run test -- --run
npm run build
```

## Links

- README: `./README.md`
- Operator Guide: `./OPERATOR_GUIDE.md`
- Release Packaging: `./RELEASE.md`
- Security: `./SECURITY.md`
