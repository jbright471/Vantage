# Operations

This guide covers running Vantage locally with Docker Compose and deploying the lightweight remote agent to Linux worker nodes.

## Local Development

Requirements:

- Docker Desktop with WSL2 enabled on Windows
- Git
- Existing local Ollama endpoints if you want live model inventory

Create a local token file:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print('VANTAGE_AGENT_SHARED_TOKEN=' + secrets.token_urlsafe(48))" | Set-Content .env
```

Start the stack:

```powershell
docker compose up --build -d
```

Open:

- UI: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)

Watch logs:

```powershell
docker compose logs -f
```

Stop:

```powershell
docker compose down
```

## Production Direction

The current `docker-compose.yml` is development-oriented. It mounts local source directories into containers so FastAPI reload and Vite HMR stay fast.

For a production deployment through Portainer or another Compose host:

- remove source-code bind mounts
- use built images instead of live-mounted code
- persist `vantage.sqlite3` to a named volume or host path
- provide `VANTAGE_AGENT_SHARED_TOKEN` as a secret or environment variable
- expose the frontend only to trusted LAN users
- keep the backend reachable only from the frontend and trusted operator machines

## Portainer Deployment Sketch

1. Push the Vantage repository or built images to a location your Portainer host can reach.
2. Create a Portainer stack from a production Compose file.
3. Set `VANTAGE_AGENT_SHARED_TOKEN` in Portainer environment variables or secrets.
4. Mount persistent storage for SQLite.
5. Start the stack and confirm:

```powershell
Invoke-RestMethod http://<host>:8000/api/health
```

6. Open the UI at:

```text
http://<host>:5173
```

## Remote Linux Agent

The remote agent is a FastAPI service managed by systemd.

Current service file:

```text
deploy/bastet/vantage-agent.service
```

Default port:

```text
9110
```

### Install On A Worker Node

On the worker node:

```bash
sudo mkdir -p /opt/vantage
sudo chown "$USER":"$USER" /opt/vantage
python3 -m venv /opt/vantage/.venv
/opt/vantage/.venv/bin/python -m pip install -r /opt/vantage/deploy/bastet/requirements-agent.txt
```

Copy the `agent/` package and deployment files into `/opt/vantage`.

Create the agent env file:

```bash
cat >/opt/vantage/vantage-agent.env <<'EOF'
VANTAGE_AGENT_SHARED_TOKEN=<same-token-as-control-plane>
EOF
chmod 600 /opt/vantage/vantage-agent.env
```

Install the service:

```bash
sudo cp /opt/vantage/deploy/bastet/vantage-agent.service /etc/systemd/system/vantage-agent.service
sudo systemctl daemon-reload
sudo systemctl enable --now vantage-agent
```

Check status:

```bash
systemctl status vantage-agent --no-pager
```

## Agent Verification

Unauthenticated requests should fail:

```powershell
Invoke-WebRequest http://192.168.50.209:9110/health -SkipHttpErrorCheck
```

Authenticated requests should pass:

```powershell
$token = (Get-Content .env | Where-Object { $_ -like 'VANTAGE_AGENT_SHARED_TOKEN=*' }).Split('=',2)[1]
Invoke-RestMethod http://192.168.50.209:9110/health -Headers @{ Authorization = "Bearer $token" }
```

The control plane should show the node as healthy:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/nodes
```

## Database Protection

Snapshot pruning is automatic during the backend polling loop.

Current defaults:

- keep snapshots for `24` hours
- keep at most `5000` snapshots per node
- keep at least `1` snapshot per node

Tune these in [config/vantage.bootstrap.toml](./config/vantage.bootstrap.toml).
