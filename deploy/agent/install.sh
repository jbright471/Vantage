#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${VANTAGE_INSTALL_DIR:-/opt/vantage}"
AGENT_USER="${VANTAGE_AGENT_USER:-vantage-agent}"
AGENT_PORT="${VANTAGE_AGENT_PORT:-9110}"
AGENT_NODE_ID="${VANTAGE_AGENT_NODE_ID:-remote-agent}"
AGENT_AUTH_MODE="${VANTAGE_AGENT_AUTH_MODE:-hmac}"
AGENT_KEY_ID="${VANTAGE_AGENT_KEY_ID:-vantage-lan-v1}"
AGENT_ALLOWED_ACTIONS="${VANTAGE_AGENT_ALLOWED_ACTIONS:-read,capability_check,eval_attempt}"
AGENT_TOKEN_FILE="${VANTAGE_AGENT_SHARED_TOKEN_FILE:-}"
CONTROL_PLANE_CIDRS="${VANTAGE_AGENT_CONTROL_PLANE_CIDRS:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${INSTALL_DIR}/vantage-agent.env"

read_env_value() {
  local key="$1"
  awk -F= -v key="${key}" '$1 == key { value = substr($0, index($0, "=") + 1) } END { print value }' "${ENV_FILE}"
}

upsert_env_value() {
  local key="$1"
  local value="$2"
  local env_stage
  env_stage="$(mktemp "${INSTALL_DIR}/.vantage-env.XXXXXX")"
  if [[ -f "${ENV_FILE}" ]]; then
    awk -F= -v key="${key}" '$1 != key { print }' "${ENV_FILE}" >"${env_stage}"
  fi
  printf '%s=%s\n' "${key}" "${value}" >>"${env_stage}"
  chmod 600 "${env_stage}"
  mv "${env_stage}" "${ENV_FILE}"
}

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this installer as root or with sudo." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required before installing the Vantage agent." >&2
  exit 1
fi

if [[ ! "${INSTALL_DIR}" =~ ^/[A-Za-z0-9._/-]+$ ]] || [[ "${INSTALL_DIR}" =~ ^/(|opt|usr|var|etc|home|root)$ ]]; then
  echo "VANTAGE_INSTALL_DIR must be a narrow absolute path such as /opt/vantage." >&2
  exit 1
fi
if [[ ! "${AGENT_USER}" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
  echo "VANTAGE_AGENT_USER is not a valid Linux service account name." >&2
  exit 1
fi
if [[ ! "${AGENT_PORT}" =~ ^[0-9]+$ ]] || (( AGENT_PORT < 1 || AGENT_PORT > 65535 )); then
  echo "VANTAGE_AGENT_PORT must be an integer between 1 and 65535." >&2
  exit 1
fi
if [[ ! "${AGENT_NODE_ID}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "VANTAGE_AGENT_NODE_ID must contain only letters, numbers, dots, underscores, and hyphens." >&2
  exit 1
fi
if [[ "${AGENT_AUTH_MODE}" != "hmac" && "${AGENT_AUTH_MODE}" != "bearer" && "${AGENT_AUTH_MODE}" != "bearer_or_hmac" ]]; then
  echo "VANTAGE_AGENT_AUTH_MODE must be hmac, bearer, or bearer_or_hmac." >&2
  exit 1
fi
if [[ -n "${AGENT_KEY_ID}" && ! "${AGENT_KEY_ID}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "VANTAGE_AGENT_KEY_ID must contain only letters, numbers, dots, underscores, and hyphens." >&2
  exit 1
fi
IFS=',' read -r -a configured_actions <<<"${AGENT_ALLOWED_ACTIONS}"
for action in "${configured_actions[@]}"; do
  case "${action}" in
    read|capability_check|eval_attempt) ;;
    *)
      echo "Unsupported VANTAGE_AGENT_ALLOWED_ACTIONS entry: ${action}" >&2
      exit 1
      ;;
  esac
done

configured_control_plane_cidrs=()
if [[ -n "${CONTROL_PLANE_CIDRS}" ]]; then
  IFS=',' read -r -a configured_control_plane_cidrs <<<"${CONTROL_PLANE_CIDRS}"
  for cidr in "${configured_control_plane_cidrs[@]}"; do
    cidr="${cidr//[[:space:]]/}"
    if ! python3 -c 'import ipaddress, sys; ipaddress.ip_network(sys.argv[1], strict=False)' "${cidr}"; then
      echo "Invalid VANTAGE_AGENT_CONTROL_PLANE_CIDRS entry: ${cidr}" >&2
      exit 1
    fi
  done
fi

mkdir -p "${INSTALL_DIR}"

if [[ -n "${AGENT_TOKEN_FILE}" ]]; then
  if [[ ! "${AGENT_TOKEN_FILE}" =~ ^/[A-Za-z0-9._/-]+$ ]] || [[ ! -f "${AGENT_TOKEN_FILE}" ]]; then
    echo "VANTAGE_AGENT_SHARED_TOKEN_FILE must name an existing absolute file." >&2
    exit 1
  fi
  if ! IFS= read -r VANTAGE_AGENT_SHARED_TOKEN <"${AGENT_TOKEN_FILE}"; then
    if [[ -z "${VANTAGE_AGENT_SHARED_TOKEN}" ]]; then
      echo "VANTAGE_AGENT_SHARED_TOKEN_FILE is empty." >&2
      exit 1
    fi
  fi
elif [[ -f "${ENV_FILE}" ]]; then
  VANTAGE_AGENT_SHARED_TOKEN="$(read_env_value "VANTAGE_AGENT_SHARED_TOKEN")"
else
  if [[ -z "${VANTAGE_AGENT_SHARED_TOKEN:-}" ]]; then
    if [[ ! -t 0 ]]; then
      echo "Set VANTAGE_AGENT_SHARED_TOKEN or run interactively so the installer can prompt securely." >&2
      exit 1
    fi
    read -r -s -p "Agent shared secret: " VANTAGE_AGENT_SHARED_TOKEN
    echo
  fi
fi
if [[ "${#VANTAGE_AGENT_SHARED_TOKEN}" -lt 32 || ! "${VANTAGE_AGENT_SHARED_TOKEN}" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "VANTAGE_AGENT_SHARED_TOKEN must be at least 32 URL-safe characters." >&2
  exit 1
fi

if ! id "${AGENT_USER}" >/dev/null 2>&1; then
  NOLOGIN_SHELL="$(command -v nologin || echo /usr/sbin/nologin)"
  useradd --system --user-group --home "${INSTALL_DIR}" --shell "${NOLOGIN_SHELL}" "${AGENT_USER}"
fi

AGENT_STAGE="$(mktemp -d "${INSTALL_DIR}/.agent-stage.XXXXXX")"
trap 'rm -rf -- "${AGENT_STAGE}"' EXIT
cp -R "${REPO_ROOT}/agent" "${AGENT_STAGE}/agent"
if [[ -d "${INSTALL_DIR}/agent" ]]; then
  mv "${INSTALL_DIR}/agent" "${INSTALL_DIR}/agent.backup.$(date -u +%Y%m%d%H%M%S)"
fi
mv "${AGENT_STAGE}/agent" "${INSTALL_DIR}/agent"
cp "${SCRIPT_DIR}/requirements-agent.txt" "${INSTALL_DIR}/requirements-agent.txt"

python3 -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${INSTALL_DIR}/.venv/bin/python" -m pip install -r "${INSTALL_DIR}/requirements-agent.txt"

upsert_env_value "VANTAGE_AGENT_PORT" "${AGENT_PORT}"
upsert_env_value "VANTAGE_AGENT_SHARED_TOKEN" "${VANTAGE_AGENT_SHARED_TOKEN}"
upsert_env_value "VANTAGE_AGENT_AUTH_MODE" "${AGENT_AUTH_MODE}"
upsert_env_value "VANTAGE_AGENT_KEY_ID" "${AGENT_KEY_ID}"
upsert_env_value "VANTAGE_AGENT_ALLOWED_ACTIONS" "${AGENT_ALLOWED_ACTIONS}"
upsert_env_value "VANTAGE_AGENT_LLM_REQUESTS_PER_MINUTE" "${VANTAGE_AGENT_LLM_REQUESTS_PER_MINUTE:-30}"
upsert_env_value "VANTAGE_AGENT_LLM_MAX_CONCURRENCY" "${VANTAGE_AGENT_LLM_MAX_CONCURRENCY:-1}"
upsert_env_value "VANTAGE_EVAL_NUM_PREDICT" "${VANTAGE_EVAL_NUM_PREDICT:-512}"
upsert_env_value "VANTAGE_LLM_MAX_RESPONSE_CHARS" "${VANTAGE_LLM_MAX_RESPONSE_CHARS:-65536}"
upsert_env_value "VANTAGE_AGENT_OLLAMA_BASE_URLS" "${VANTAGE_AGENT_OLLAMA_BASE_URLS:-http://127.0.0.1:11434}"
upsert_env_value "VANTAGE_AGENT_NODE_ID" "${AGENT_NODE_ID}"
chmod 600 "${INSTALL_DIR}/vantage-agent.env"

chown -R "${AGENT_USER}:${AGENT_USER}" "${INSTALL_DIR}"
sed \
  -e "s|@@INSTALL_DIR@@|${INSTALL_DIR}|g" \
  -e "s|@@AGENT_USER@@|${AGENT_USER}|g" \
  "${SCRIPT_DIR}/vantage-agent.service" >/etc/systemd/system/vantage-agent.service
if [[ ${#configured_control_plane_cidrs[@]} -gt 0 ]]; then
  NETWORK_POLICY_FILE="/etc/systemd/system/vantage-agent.service.d/network-policy.conf"
  install -d -m 755 "$(dirname "${NETWORK_POLICY_FILE}")"
  {
    echo "[Service]"
    echo "IPAddressDeny=any"
    echo "IPAddressAllow=127.0.0.0/8"
    echo "IPAddressAllow=::1/128"
    for cidr in "${configured_control_plane_cidrs[@]}"; do
      echo "IPAddressAllow=${cidr//[[:space:]]/}"
    done
  } >"${NETWORK_POLICY_FILE}"
  chmod 644 "${NETWORK_POLICY_FILE}"
fi
systemctl daemon-reload
systemctl enable vantage-agent
systemctl restart vantage-agent

echo "Vantage agent installed."
echo "Check status with: systemctl status vantage-agent --no-pager"
echo "From the control-plane host, allow TCP ${AGENT_PORT} only from the Vantage control plane and verify with scripts/check-setup.ps1."
if [[ ${#configured_control_plane_cidrs[@]} -gt 0 ]]; then
  echo "The systemd network policy restricts the agent to loopback and: ${CONTROL_PLANE_CIDRS}."
fi
echo "Register this node as '${AGENT_NODE_ID}' with base URL http://<this-host-lan-ip>:${AGENT_PORT}."
