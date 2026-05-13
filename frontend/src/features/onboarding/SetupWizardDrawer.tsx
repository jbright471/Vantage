import { useState } from "react";

import type { ModelRecord, NodeRecord, RoutingRuleRecord } from "../../api/client";

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
    `base_url = "${nodeUrl.trim() || "http://10.0.0.25:9110"}"`,
    `role = "${nodeRole}"`,
    "enabled = true",
  ].join("\n");
}

function buildAgentNodeEnv(nodeName: string): string {
  return `VANTAGE_AGENT_NODE_ID=${slugify(nodeName) || "gpu-worker"}`;
}

function buildOllamaEnv(endpointList: string): string {
  const normalized = endpointList
    .split(",")
    .map((endpoint) => endpoint.trim())
    .filter(Boolean)
    .join(",");
  return `VANTAGE_LOCAL_OLLAMA_BASE_URLS=${normalized || "http://host.docker.internal:11434"}`;
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
  const [token, setToken] = useState(() => generateToken());
  const [nodeName, setNodeName] = useState("gpu-worker-a");
  const [nodeUrl, setNodeUrl] = useState("http://10.0.0.25:9110");
  const [nodeRole, setNodeRole] = useState("remote");
  const [ollamaEndpoints, setOllamaEndpoints] = useState("http://host.docker.internal:11434");

  if (!isOpen) {
    return null;
  }

  const envSnippet = [
    `VANTAGE_AGENT_SHARED_TOKEN=${token}`,
    "VANTAGE_AGENT_AUTH_MODE=bearer",
    "VANTAGE_AGENT_ALLOWED_ACTIONS=read,capability_check,eval_attempt",
    "VANTAGE_AUDIT_SIGNING_KEY=",
    "VANTAGE_AUDIT_KEY_ID=local-audit-key",
    "VANTAGE_EXTERNAL_API_TOKEN=",
    "VANTAGE_WEBHOOK_ALLOWED_HOSTS=",
  ].join("\n");
  const nodeSnippet = buildNodeToml(nodeName, nodeUrl, nodeRole);
  const agentNodeEnvSnippet = buildAgentNodeEnv(nodeName);
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
    <div className="run-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="run-drawer setup-wizard-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="First-run setup wizard"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="drawer-header">
          <div>
            <p className="section-kicker">Setup wizard</p>
            <h3>Configure Vantage without surrendering control</h3>
            <p className="drawer-run-id">Generate snippets, review them, then paste into your local files.</p>
          </div>
          <button type="button" className="drawer-close-button" onClick={onClose} aria-label="Close setup wizard">
            x
          </button>
        </header>

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
              <h4>1. Generate the shared agent token</h4>
              <p>
                Vantage needs the same token in the control-plane backend and any remote node agent. This wizard does
                not store the token; it only helps you generate the `.env` line.
              </p>
              <div className="setup-inline-row">
                <button type="button" className="action-button" onClick={() => setToken(generateToken())}>
                  Regenerate token
                </button>
                <span className="meta-chip">local browser only</span>
              </div>
              <SetupCodeBlock label=".env" value={envSnippet} />
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
                  <input value={nodeName} onChange={(event) => setNodeName(event.target.value)} />
                </label>
                <label>
                  Agent URL
                  <input value={nodeUrl} onChange={(event) => setNodeUrl(event.target.value)} />
                </label>
                <label>
                  Role
                  <select value={nodeRole} onChange={(event) => setNodeRole(event.target.value)}>
                    <option value="remote">remote</option>
                    <option value="primary">primary</option>
                    <option value="worker">worker</option>
                  </select>
                </label>
              </div>
              <SetupCodeBlock label="config/vantage.bootstrap.toml" value={nodeSnippet} />
              <SetupCodeBlock label="remote agent env" value={agentNodeEnvSnippet} />
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
                <input value={ollamaEndpoints} onChange={(event) => setOllamaEndpoints(event.target.value)} />
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
      </aside>
    </div>
  );
}
