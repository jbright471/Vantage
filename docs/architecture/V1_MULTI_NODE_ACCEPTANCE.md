# V1 Multi-Node Acceptance

## Supported topology

Vantage v1 supports one desktop-local control plane and one or more explicitly registered Linux model hosts on a trusted LAN or VPN.

- The browser UI stays on `127.0.0.1` by default.
- Each worker runs the systemd-managed Vantage agent on TCP `9110`.
- The operator installs each agent and adds its stable node ID and URL to `config/vantage.bootstrap.toml`.
- Vantage does not scan the LAN or silently enroll machines.
- New installations use HMAC-signed requests with timestamp and replay checks.

## V1 remote capabilities

- health, CPU, memory, GPU, Ollama, model, and recent-run observation
- deterministic capability checks
- prompt-suite eval execution, including scheduled evals
- model-placement visibility and capability-aware routing policy
- node quarantine and re-enable inside Vantage

Quarantine changes Vantage's configured use of the node. It does not stop a host, container, Ollama service, or agent.

## V1 non-goals

- LAN scanning or automatic enrollment
- Windows or macOS agent support
- arbitrary shell commands
- host/service restart or privileged remediation
- model pull, load, unload, copy, or delete actions
- public-internet agent exposure
- multiple active control planes

## Release acceptance checklist

- [x] A clean Linux install prompts for the shared secret without placing it in shell history.
- [x] The generated agent env defaults to HMAC and the v1 action allowlist.
- [x] The systemd service runs as a dedicated user with a read-only system boundary and no capabilities.
- [x] The setup wizard generates matching node identity, agent, firewall, and TOML registration guidance.
- [x] `scripts/check-setup.ps1` verifies an HMAC-protected `/health` endpoint.
- [x] Polling and every interactive/scheduled remote model path use the same HMAC-aware transport.
- [x] Automated tests exercise an actual FastAPI agent contract through signed GET and POST requests.
- [ ] Complete one clean install on a separate Linux host and retain redacted evidence of health, model inventory, one capability check, and the starter eval suite.
- [ ] Verify the worker firewall permits TCP `9110` from the control-plane address and denies an unrelated LAN address.
- [x] Verify agent restart and control-plane restart both recover without re-registration.

## Bastet upgrade acceptance (2026-07-25)

An explicitly authorized existing Pop!_OS worker was upgraded from the legacy Vantage agent rather than treated as a clean-install substitute.

- the previous unit, environment, requirements, and agent source were retained in a root-only rollback backup
- the service now runs as the dedicated `vantage-agent` identity with a mode `600` environment, no capabilities, no new privileges, and a read-only system boundary
- HMAC health passed from the control plane after rotating the legacy mismatched credential through an SSH stdin-only token file
- systemd IP filtering is effective and restricts the service to loopback plus the configured control-plane address
- Vantage reported the node as `healthy` and `live`, observed two GPUs and two Ollama models, and completed a deterministic Gemma capability check
- explicit agent and control-plane restarts both recovered without re-registration

The clean external-user installation, starter eval suite, and denial test from a genuinely unrelated LAN host remain release gates.

HMAC authenticates request contents but does not encrypt HTTP payloads. Use a trusted LAN with source-scoped firewall rules, or a trusted VPN/TLS tunnel, when prompts and responses require transport confidentiality.
