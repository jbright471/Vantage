import { fireEvent, render, screen } from "@testing-library/react";

import { SetupWizardDrawer } from "./SetupWizardDrawer";
import type { ModelRecord, NodeRecord, RoutingRuleRecord } from "../../api/client";


const nodes: NodeRecord[] = [
  {
    node_id: "demo-control",
    display_name: "Demo Control",
    base_url: "http://127.0.0.1:8000",
    role: "primary",
    enabled: true,
    created_from: "demo",
    observed_status: "healthy",
    freshness: "live",
    last_seen_at: "2026-05-09T20:00:00Z",
    gpu_stats: [],
    cpu_usage_percent: 12,
    memory_used_mb: 2048,
    ollama_status: "ok",
    ollama_errors: [],
    model_count: 1,
  },
];

const models: ModelRecord[] = [
  {
    model_name: "llama3.1:8b",
    placements: ["demo-control"],
    placement_details: [{ node_id: "demo-control", model_digest: "sha256:demo", available: true }],
  },
];

const routingRules: RoutingRuleRecord[] = [
  {
    rule_id: "interactive-default",
    priority_class: "interactive",
    model_name: "llama3.1:8b",
    enabled: true,
    allow_degraded: false,
    allow_stale: false,
    allow_unreachable: false,
    minimum_eval_pass_rate: null,
    preferred_nodes: ["demo-control"],
  },
];

describe("SetupWizardDrawer", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("renders nothing when closed", () => {
    render(
      <SetupWizardDrawer
        isOpen={false}
        onClose={vi.fn()}
        nodes={nodes}
        models={models}
        routingRules={routingRules}
        streamStatus="live"
      />,
    );

    expect(screen.queryByRole("dialog", { name: "First-run setup wizard" })).toBeNull();
  });

  it("generates token, node, Ollama, and verification snippets", () => {
    render(
      <SetupWizardDrawer
        isOpen={true}
        onClose={vi.fn()}
        nodes={nodes}
        models={models}
        routingRules={routingRules}
        streamStatus="live"
      />,
    );

    expect(screen.getByText(".env")).toBeTruthy();
    expect(screen.getByText(/VANTAGE_AGENT_SHARED_TOKEN=/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Node name"), { target: { value: "Render Worker" } });
    expect(screen.getByText(/node_id = "render-worker"/)).toBeTruthy();
    expect(screen.getByText(/base_url = "http:\/\/<remote-agent-ip>:9110"/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText(/VANTAGE_LOCAL_OLLAMA_BASE_URLS=http:\/\/host.docker.internal:11434/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Restart commands")).toBeTruthy();
    expect(screen.getByText(/docker compose up --build -d/)).toBeTruthy();
    expect(screen.getByText("SSE is live.")).toBeTruthy();
  });
});
