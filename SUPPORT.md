# Support

Vantage is designed as a local-first homelab tool. Community support should preserve that posture.

## Before Filing An Issue

- Confirm you are on the latest released tag or current `master`.
- Run `docker compose ps` and confirm both containers are healthy.
- Open `/api/health/ready` and capture the readiness response.
- Export relevant runs as JSON if the issue involves actions, evals, routing, or node refresh.
- Remove private IPs, real hostnames, prompts, secrets, and local paths before sharing logs.

## Useful Diagnostics

```powershell
docker compose logs backend --tail 200
docker compose logs frontend --tail 100
Invoke-RestMethod http://127.0.0.1:8000/api/health/ready
```

For production deployments, also check your supervisor:

```bash
journalctl -u vantage-agent --no-pager -n 200
```

## Security Issues

Do not open public issues for vulnerabilities or exposed secrets. Follow [SECURITY.md](./SECURITY.md).
