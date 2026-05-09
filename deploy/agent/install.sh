#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${VANTAGE_INSTALL_DIR:-/opt/vantage}"
AGENT_USER="${VANTAGE_AGENT_USER:-vantage-agent}"
AGENT_PORT="${VANTAGE_AGENT_PORT:-9110}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this installer as root or with sudo." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required before installing the Vantage agent." >&2
  exit 1
fi

if ! id "${AGENT_USER}" >/dev/null 2>&1; then
  NOLOGIN_SHELL="$(command -v nologin || echo /usr/sbin/nologin)"
  useradd --system --home "${INSTALL_DIR}" --shell "${NOLOGIN_SHELL}" "${AGENT_USER}"
fi

mkdir -p "${INSTALL_DIR}"
rm -rf "${INSTALL_DIR}/agent"
cp -R "${REPO_ROOT}/agent" "${INSTALL_DIR}/agent"
cp "${SCRIPT_DIR}/requirements-agent.txt" "${INSTALL_DIR}/requirements-agent.txt"

python3 -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${INSTALL_DIR}/.venv/bin/python" -m pip install -r "${INSTALL_DIR}/requirements-agent.txt"

if [[ ! -f "${INSTALL_DIR}/vantage-agent.env" ]]; then
  {
    echo "VANTAGE_AGENT_PORT=${AGENT_PORT}"
    echo "VANTAGE_AGENT_SHARED_TOKEN=${VANTAGE_AGENT_SHARED_TOKEN:-}"
    echo "VANTAGE_AGENT_OLLAMA_BASE_URLS=${VANTAGE_AGENT_OLLAMA_BASE_URLS:-http://127.0.0.1:11434}"
  } >"${INSTALL_DIR}/vantage-agent.env"
  chmod 600 "${INSTALL_DIR}/vantage-agent.env"
fi

chown -R "${AGENT_USER}:${AGENT_USER}" "${INSTALL_DIR}"
cp "${SCRIPT_DIR}/vantage-agent.service" /etc/systemd/system/vantage-agent.service
systemctl daemon-reload
systemctl enable --now vantage-agent

echo "Vantage agent installed."
echo "Check status with: systemctl status vantage-agent --no-pager"
echo "Verify health with: curl -H 'Authorization: Bearer <token>' http://127.0.0.1:${AGENT_PORT}/health"
