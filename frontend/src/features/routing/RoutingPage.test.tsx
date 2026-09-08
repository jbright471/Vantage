import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { RoutingRuleRecord } from "../../api/client";
import { RoutingPage } from "./RoutingPage";

function routingRule(overrides: Partial<RoutingRuleRecord>): RoutingRuleRecord {
  return {
    rule_id: "scheduled-default",
    priority_class: "scheduled",
    model_name: null,
    preferred_nodes: ["control-plane", "remote-worker"],
    enabled: true,
    allow_degraded: false,
    allow_stale: false,
    allow_unreachable: false,
    minimum_eval_pass_rate: null,
    ...overrides,
  };
}

describe("RoutingPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the preferred node order", () => {
    render(
      <RoutingPage
        rules={[
          routingRule({
            rule_id: "scheduled-default",
            priority_class: "scheduled",
            preferred_nodes: ["control-plane", "remote-worker"],
          }),
        ]}
        availableNodes={["control-plane", "remote-worker"]}
      />,
    );

    expect(screen.getAllByText("scheduled").length).toBeGreaterThan(0);
    expect(screen.getByText("control-plane → remote-worker")).toBeTruthy();
  });

  it("requires strict confirmation before promoting a preferred node", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/dry-run")) {
        return {
          ok: true,
          json: async () => ({
            rule_id: "scheduled-default",
            priority_class: "scheduled",
            model_name: null,
            candidate_order: ["remote-worker", "control-plane"],
            selected_node: "remote-worker",
            decisions: [
              {
                node_id: "remote-worker",
                display_name: "Remote Worker",
                decision: "selected",
                observed_status: "healthy",
                freshness: "live",
                signal_age_seconds: 0.5,
                model_available: null,
                eval_pass_rate: null,
                reasons: ["selected:first_eligible"],
              },
              {
                node_id: "control-plane",
                display_name: "Control Plane",
                decision: "skipped",
                observed_status: "healthy",
                freshness: "live",
                signal_age_seconds: 0.7,
                model_available: null,
                eval_pass_rate: null,
                reasons: ["lower_priority_than_selected"],
              },
            ],
            warnings: [],
          }),
        } as Response;
      }

      return {
        ok: true,
        json: async () => ({
          rule_id: "scheduled-default",
          priority_class: "scheduled",
          model_name: null,
          enabled: true,
          allow_degraded: false,
          allow_stale: false,
          allow_unreachable: false,
          minimum_eval_pass_rate: null,
          preferred_nodes: ["remote-worker", "control-plane"],
        }),
      } as Response;
    });

    render(
      <RoutingPage
        rules={[
          routingRule({
            rule_id: "scheduled-default",
            priority_class: "scheduled",
            preferred_nodes: ["control-plane", "remote-worker"],
          }),
        ]}
        availableNodes={["control-plane", "remote-worker"]}
        nodeSummaries={[
          {
            node_id: "control-plane",
            display_name: "Control Plane",
            observed_status: "healthy",
            freshness: "live",
            model_count: 4,
          },
          {
            node_id: "remote-worker",
            display_name: "Remote Worker",
            observed_status: "healthy",
            freshness: "live",
            model_count: 8,
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /prefer remote-worker/i }));

    expect(screen.getByRole("dialog", { name: /confirm preferred node change/i })).toBeTruthy();
    expect(screen.getByText("Target node state")).toBeTruthy();
    expect(screen.getByText(/target node is currently healthy and live/i)).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText(/dry-run found an eligible route/i)).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /confirm routing change/i }));

    await waitFor(() => {
      expect(screen.getByText(/preferred node updated/i)).toBeTruthy();
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/routing/scheduled-default/dry-run", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        preferred_nodes: ["remote-worker", "control-plane"],
      }),
    });
    expect(fetchMock).toHaveBeenCalledWith("/api/routing/scheduled-default", {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        preferred_nodes: ["remote-worker", "control-plane"],
      }),
    });
  });

  it("warns before promoting a stale or degraded target node", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        rule_id: "interactive-default",
        priority_class: "interactive",
        model_name: null,
        candidate_order: ["remote-worker", "control-plane"],
        selected_node: "control-plane",
        decisions: [
          {
            node_id: "remote-worker",
            display_name: "Remote Worker",
            decision: "rejected",
            observed_status: "degraded",
            freshness: "stale",
            signal_age_seconds: 22,
            model_available: null,
            eval_pass_rate: null,
            reasons: ["health:degraded", "freshness:stale"],
          },
          {
            node_id: "control-plane",
            display_name: "Control Plane",
            decision: "selected",
            observed_status: "healthy",
            freshness: "live",
            signal_age_seconds: 0.4,
            model_available: null,
            eval_pass_rate: null,
            reasons: ["selected:first_eligible"],
          },
        ],
        warnings: ["Preferred node 'remote-worker' would be skipped; 'control-plane' is first eligible."],
      }),
    } as Response);

    render(
      <RoutingPage
        rules={[
          routingRule({
            rule_id: "interactive-default",
            priority_class: "interactive",
            preferred_nodes: ["control-plane", "remote-worker"],
          }),
        ]}
        availableNodes={["control-plane", "remote-worker"]}
        nodeSummaries={[
          {
            node_id: "control-plane",
            display_name: "Control Plane",
            observed_status: "healthy",
            freshness: "live",
            model_count: 4,
          },
          {
            node_id: "remote-worker",
            display_name: "Remote Worker",
            observed_status: "degraded",
            freshness: "stale",
            model_count: 8,
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /prefer remote-worker/i }));

    expect(screen.getByText("Target node state")).toBeTruthy();
    expect(screen.getByText("degraded")).toBeTruthy();
    expect(screen.getByText("stale")).toBeTruthy();
    expect(screen.getByText(/not currently healthy and live/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /confirm override/i })).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText(/preferred node 'remote-worker' would be skipped/i)).toBeTruthy();
    });
  });

  it("creates a model-specific routing rule and displays route history", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/routing" && init?.method === "POST") {
        return {
          ok: true,
          json: async () => routingRule({
            rule_id: "qwen-batch",
            priority_class: "batch",
            model_name: "qwen3.5:27b",
            preferred_nodes: ["remote-worker", "control-plane"],
            minimum_eval_pass_rate: 0.75,
          }),
        } as Response;
      }
      if (url === "/api/routing/qwen-batch/history") {
        return {
          ok: true,
          json: async () => [
            {
              history_id: 1,
              rule_id: "qwen-batch",
              action_type: "create",
              changed_at: new Date("2026-05-08T12:00:00Z").toISOString(),
              summary: "Created routing rule qwen-batch",
              before_json: null,
              after_json: {},
            },
          ],
        } as Response;
      }
      return { ok: false, status: 404, json: async () => ({}) } as Response;
    });

    render(<RoutingPage rules={[]} availableNodes={["control-plane", "remote-worker"]} />);

    fireEvent.change(screen.getByPlaceholderText("e.g., llama-batch…"), { target: { value: "qwen-batch" } });
    fireEvent.change(screen.getByPlaceholderText("e.g., qwen3.5:27b…"), { target: { value: "qwen3.5:27b" } });
    fireEvent.change(screen.getByPlaceholderText("e.g., remote-worker, control-plane…"), { target: { value: "remote-worker, control-plane" } });
    fireEvent.change(screen.getByPlaceholderText("e.g., 0.75…"), { target: { value: "0.75" } });
    fireEvent.click(screen.getByRole("button", { name: /create rule/i }));

    await waitFor(() => {
      expect(screen.getByText("qwen-batch")).toBeTruthy();
    });
    expect(screen.getByText("qwen3.5:27b")).toBeTruthy();
    expect(screen.getByText("eval ≥ 75%")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /history/i }));

    await waitFor(() => {
      expect(screen.getByText("Created routing rule qwen-batch")).toBeTruthy();
    });
  });
});
