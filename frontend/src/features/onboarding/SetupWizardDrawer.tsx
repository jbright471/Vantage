import { useState } from "react";

import type { ModelRecord, NodeRecord, RoutingRuleRecord } from "../../api/client";
import { OverlayHeader, OverlaySurface } from "../../components/OverlaySurface";

type WizardStep = "token" | "nodes" | "ollama" | "verify";

export interface SetupWizardDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  nodes: NodeRecord[];
  models: ModelRecord[];
  routingRules: RoutingRuleRecord[];
  streamStatus: string;
}

const steps: { id: WizardStep; label: string }[] = [
  { id: "token", label: "Token" },
  { id: "nodes", label: "Nodes" },
  { id: "ollama", label: "Ollama" },
  { id: "verify", label: "Verify" },
];

function generateToken(): string {
  const bytes = new Uint8Array(36);
  window.crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes)).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function generateRequiredSecrets() {
  return {
    agentToken: generateToken(),
    controlPlaneToken: generateToken(),
    sessionSigningKey: generateToken(),
    auditSigningKey: generateToken(),
  };
}

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function buildNodeToml(nodeName: string, nodeUrl: string, nodeRole: string): string {
  const nodeId = slugify(nodeName) || "gpu-worker";
  return [
    "[[nodes]]",
    `node_id = "${nodeId}"`,
    `display_name = "${nodeName.trim() || "GPU Worker"}"`,
    `base_url = "${nodeUrl.trim() || "http://worker.example.invalid:9110"}"`,
    `role = "${nodeRole}"`,
    "enabled = true",
  ].join("\n");
}

function buildAgentNodeEnv(nodeName: string): string {
  return [
    `VANTAGE_AGENT_NODE_ID=${slugify(nodeName) || "gpu-worker"}`,
    "VANTAGE_AGENT_AUTH_MODE=hmac",
    "VANTAGE_AGENT_KEY_ID=vantage-lan-v1",
    "VANTAGE_AGENT_ALLOWED_ACTIONS=read,capability_check,eval_attempt",
    "VANTAGE_AGENT_OLLAMA_BASE_URLS=http://127.0.0.1:11434",
    "VANTAGE_AGENT_CONTROL_PLANE_CIDRS=<control-plane-ip>/32",
  ].join("\n");
}

function buildLinuxAgentInstall(nodeName: string): string {
  const nodeId = slugify(nodeName) || "gpu-worker";
  return [
    `sudo VANTAGE_AGENT_NODE_ID=${nodeId} \\`,
    "  VANTAGE_AGENT_AUTH_MODE=hmac \\",
    "  VANTAGE_AGENT_KEY_ID=vantage-lan-v1 \\",
    '  VANTAGE_AGENT_OLLAMA_BASE_URLS="http://127.0.0.1:11434" \\',
    '  VANTAGE_AGENT_CONTROL_PLANE_CIDRS="<control-plane-ip>/32" \\',
    "  bash deploy/agent/install.sh",
  ].join("\n");
}

function buildOllamaEnv(endpointList: string): string {
  const normalized = endpointList
    .split(",")
    .map((endpoint) => endpoint.trim())
    .filter(Boolean)
    .join(",");
  return `VANTAGE_LOCAL_OLLAMA_BASE_URLS=${normalized || "http://host.docker.internal:11400"}`;
}

function SetupCodeBlock({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
  }

  return (
    <div className="setup-code-block">
      <div>
        <strong>{label}</strong>
        <button type="button" className="text-action-button" onClick={() => void copy()}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre>
        <code>{value}</code>
      </pre>
    </div>
  );
}

export function SetupWizardDrawer({
  isOpen,
  onClose,
  nodes,
  models,
  routingRules,
  streamStatus,
}: SetupWizardDrawerProps) {
  const [activeStep, setActiveStep] = useState<WizardStep>("token");
  const [secrets, setSecrets] = useState(generateRequiredSecrets);
  const [nodeName, setNodeName] = useState("gpu-worker-a");
  const [nodeUrl, setNodeUrl] = useState("http://worker.example.invalid:9110");
  const [nodeRole, setNodeRole] = useState("remote");
  const [ollamaEndpoints, setOllamaEndpoints] = useState("http://host.docker.internal:11400");

  if (!isOpen) {
    return null;
  }

  const envSnippet = [
    `VANTAGE_AGENT_SHARED_TOKEN=${secrets.agentToken}`,
    "VANTAGE_AGENT_AUTH_MODE=hmac",
    "VANTAGE_AGENT_KEY_ID=vantage-lan-v1",
    "VANTAGE_AGENT_ALLOWED_ACTIONS=read,capability_check,eval_attempt",
    `VANTAGE_CONTROL_PLANE_TOKEN=${secrets.controlPlaneToken}`,
    `VANTAGE_SESSION_SIGNING_KEY=${secrets.sessionSigningKey}`,
    `VANTAGE_AUDIT_SIGNING_KEY=${secrets.auditSigningKey}`,
    "VANTAGE_AUDIT_KEY_ID=local-audit-key",
    "VANTAGE_EXTERNAL_API_TOKEN=",
    "VANTAGE_WEBHOOK_ALLOWED_HOSTS=",
  ].join("\n");
  const nodeSnippet = buildNodeToml(nodeName, nodeUrl, nodeRole);
  const agentNodeEnvSnippet = buildAgentNodeEnv(nodeName);
  const linuxAgentInstallSnippet = buildLinuxAgentInstall(nodeName);
  const ollamaSnippet = buildOllamaEnv(ollamaEndpoints);
  const activeIndex = steps.findIndex((step) => step.id === activeStep);
  const hasObservedModels = models.length > 0;
  const hasRegisteredNodes = nodes.length > 0;
  const hasRouting = routingRules.length > 0;

  function goNext() {
    setActiveStep(steps[Math.min(activeIndex + 1, steps.length - 1)].id);
  }

  function goBack() {
    setActiveStep(steps[Math.max(activeIndex - 1, 0)].id);
  }

  return (
    <OverlaySurface
      isOpen={isOpen}
      onClose={onClose}
      labelledBy="setup-wizard-title"
      describedBy="setup-wizard-description"
      size="wide"
      className="setup-wizard-drawer"
    >
      <OverlayHeader
        titleId="setup-wizard-title"
        title="First-run setup wizard"
        kicker="Setup / Local"
        description="Configure Vantage without surrendering control. Generate snippets, review them, then paste them into your local files."
        descriptionId="setup-wizard-description"
        closeLabel="Close setup wizard"
        onClose={onClose}
        headingLevel={3}
      />

      <div className="drawer-content setup-wizard-content">
          <nav className="setup-stepper" aria-label="Setup steps">
            {steps.map((step, index) => (
              <button
                key={step.id}
                type="button"
                className={step.id === activeStep ? "is-active" : index < activeIndex ? "is-complete" : ""}
                onClick={() => setActiveStep(step.id)}
              >
                <span>{index + 1}</span>
                {step.label}
              </button>
            ))}
          </nav>

          {activeStep === "token" ? (
            <section className="setup-step-panel">
              <h4>1. Generate independent installation secrets</h4>
              <p>
                Vantage needs an agent token, a separate operator-login token, and an independent session-signing key.
                The audit key enables signed evidence exports. This wizard generates them locally and does not store
                them.
              </p>
              <div className="setup-inline-row">
                <button type="button" className="action-button" onClick={() => setSecrets(generateRequiredSecrets())}>
                  Regenerate secrets
                </button>
                <span className="meta-chip">local browser only</span>
              </div>
              <SetupCodeBlock label="Required .env values" value={envSnippet} />
              <p className="action-copy">
                Save the control-plane token in your password manager: it is the value you enter on the Vantage login
                screen. Never reuse any generated value for another setting.
              </p>
            </section>
          ) : null}

          {activeStep === "nodes" ? (
            <section className="setup-step-panel">
              <h4>2. Add a worker node</h4>
              <p>
                Add this TOML block to `config/vantage.bootstrap.toml`. Example names are safe to replace with your own
                homelab naming scheme.
              </p>
              <div className="setup-form-grid">
                <label>
                  Node name
                  <input
                    name="setup-node-name"
                    autoComplete="off"
                    spellCheck={false}
                    value={nodeName}
                    onChange={(event) => setNodeName(event.target.value)}
                  />
                </label>
                <label>
                  Agent URL
                  <input
                    name="setup-agent-url"
                    type="url"
                    autoComplete="off"
                    spellCheck={false}
                    value={nodeUrl}
                    onChange={(event) => setNodeUrl(event.target.value)}
                  />
                </label>
                <label>
                  Role
                  <select
                    name="setup-node-role"
                    autoComplete="off"
                    value={nodeRole}
                    onChange={(event) => setNodeRole(event.target.value)}
                  >
                    <option value="remote">remote</option>
                    <option value="primary">primary</option>
                    <option value="worker">worker</option>
                  </select>
                </label>
              </div>
              <SetupCodeBlock label="config/vantage.bootstrap.toml" value={nodeSnippet} />
              <SetupCodeBlock label="remote agent env" value={agentNodeEnvSnippet} />
              <SetupCodeBlock label="Linux agent install" value={linuxAgentInstallSnippet} />
              <p className="action-copy">
                The installer prompts for the shared agent secret without placing it in shell history. On the worker,
                allow TCP 9110 only from the control-plane machine or its trusted VPN address; do not expose the agent
                port to the internet. Vantage does not scan the LAN, so repeat this install-and-register step for each
                worker you intentionally trust.
              </p>
            </section>
          ) : null}

          {activeStep === "ollama" ? (
            <section className="setup-step-panel">
              <h4>3. Point Vantage at local Ollama</h4>
              <p>
                Docker Desktop usually reaches host Ollama through `host.docker.internal`. Use comma-separated URLs if
                you run multiple local Ollama ports.
              </p>
              <label className="setup-wide-label">
                Local Ollama base URLs
                <input
                  name="setup-ollama-endpoints"
                  autoComplete="off"
                  spellCheck={false}
                  value={ollamaEndpoints}
                  onChange={(event) => setOllamaEndpoints(event.target.value)}
                />
              </label>
              <SetupCodeBlock label=".env" value={ollamaSnippet} />
              <div className="setup-signal-grid">
                <article className={hasObservedModels ? "onboarding-check is-complete" : "onboarding-check"}>
                  <span aria-hidden="true">{hasObservedModels ? "OK" : "!"}</span>
                  <div>
                    <strong>{models.length} model names currently visible</strong>
                    <p>{hasObservedModels ? "Model inventory is already flowing." : "Run a poll after saving env."}</p>
                  </div>
                </article>
              </div>
            </section>
          ) : null}

          {activeStep === "verify" ? (
            <section className="setup-step-panel">
              <h4>4. Restart and verify</h4>
              <p>
                After saving `.env` and `config/vantage.bootstrap.toml`, restart the stack and use readiness plus the UI
                stream to confirm the control plane is truthful.
              </p>
              <SetupCodeBlock
                label="Restart commands"
                value={[
                  "docker compose down",
                  "docker compose up --build -d",
                  "Invoke-RestMethod http://127.0.0.1:8000/api/health/ready",
                ].join("\n")}
              />
              <div className="setup-signal-grid">
                {[
                  {
                    label: "Stream",
                    complete: streamStatus === "live",
                    detail: streamStatus === "live" ? "SSE is live." : `Current state: ${streamStatus}.`,
                  },
                  {
                    label: "Nodes",
                    complete: hasRegisteredNodes,
                    detail: `${nodes.length} registered.`,
                  },
                  {
                    label: "Models",
                    complete: hasObservedModels,
                    detail: `${models.length} model names observed.`,
                  },
                  {
                    label: "Routing",
                    complete: hasRouting,
                    detail: `${routingRules.length} policies visible.`,
                  },
                ].map((check) => (
                  <article key={check.label} className={check.complete ? "onboarding-check is-complete" : "onboarding-check"}>
                    <span aria-hidden="true">{check.complete ? "OK" : "!"}</span>
                    <div>
                      <strong>{check.label}</strong>
                      <p>{check.detail}</p>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          <footer className="setup-wizard-footer">
            <button type="button" className="action-button is-secondary" onClick={goBack} disabled={activeIndex === 0}>
              Back
            </button>
            {activeIndex < steps.length - 1 ? (
              <button type="button" className="action-button" onClick={goNext}>
                Next
              </button>
            ) : (
              <button type="button" className="action-button" onClick={onClose}>
                Finish
              </button>
            )}
          </footer>
      </div>
    </OverlaySurface>
  );
}
