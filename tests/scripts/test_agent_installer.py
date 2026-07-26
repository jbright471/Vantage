from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_linux_agent_installer_uses_secure_interactive_onboarding() -> None:
    installer = (ROOT / "deploy" / "agent" / "install.sh").read_text(encoding="utf-8")

    assert 'read -r -s -p "Agent shared secret: "' in installer
    assert 'VANTAGE_AGENT_AUTH_MODE:-hmac' in installer
    assert 'rm -rf "${INSTALL_DIR}/agent"' not in installer
    assert "allow TCP ${AGENT_PORT} only from the Vantage control plane" in installer


def test_linux_agent_installer_hardens_and_migrates_an_existing_environment() -> None:
    installer = (ROOT / "deploy" / "agent" / "install.sh").read_text(encoding="utf-8")

    assert 'read_env_value "VANTAGE_AGENT_SHARED_TOKEN"' in installer
    assert 'upsert_env_value "VANTAGE_AGENT_AUTH_MODE"' in installer
    assert 'upsert_env_value "VANTAGE_AGENT_NODE_ID"' in installer
    assert 'chmod 600 "${INSTALL_DIR}/vantage-agent.env"' in installer
    assert 'VANTAGE_AGENT_SHARED_TOKEN_FILE' in installer
    assert 'IFS= read -r VANTAGE_AGENT_SHARED_TOKEN <"${AGENT_TOKEN_FILE}"' in installer
    assert "systemctl restart vantage-agent" in installer
    assert "VANTAGE_AGENT_CONTROL_PLANE_CIDRS" in installer
    assert "vantage-agent.service.d/network-policy.conf" in installer
    assert 'echo "IPAddressDeny=any"' in installer


def test_linux_agent_service_has_a_read_only_system_boundary() -> None:
    service = (ROOT / "deploy" / "agent" / "vantage-agent.service").read_text(encoding="utf-8")

    assert "ProtectSystem=strict" in service
    assert "PrivateDevices=false" in service
    assert "CapabilityBoundingSet=" in service
    assert "RestrictSUIDSGID=true" in service


def test_setup_checker_can_verify_hmac_agents() -> None:
    checker = (ROOT / "scripts" / "check-setup.ps1").read_text(encoding="utf-8")

    assert "HMACSHA256" in checker
    assert 'X-Vantage-Signature' in checker
    assert "HMAC mode configured; verify" not in checker
