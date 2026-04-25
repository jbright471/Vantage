import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { NodesPage } from "./NodesPage";

describe("NodesPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders node freshness and status", () => {
    render(
      <NodesPage
        nodes={[
          {
            node_id: "bastet",
            base_url: "http://192.168.50.209:9110",
            display_name: "Bastet",
            observed_status: "degraded",
            freshness: "stale",
            last_seen_at: "2026-04-22T12:00:00Z",
            gpu_stats: [],
            cpu_usage_percent: null,
            memory_used_mb: null,
            ollama_status: "error",
            ollama_errors: [],
            model_count: 0,
          },
        ]}
        runs={[]}
      />,
    );

    expect(screen.getByText("Bastet")).toBeTruthy();
    expect(screen.getByText("degraded")).toBeTruthy();
    expect(screen.getByText(/stale/i)).toBeTruthy();
    expect(screen.getByText("Heartbeat")).toBeTruthy();
    expect(screen.getByText("Signal age")).toBeTruthy();
  });

  it("submits a refresh action and keeps the status explicitly unverified", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        run_id: "run-1",
        summary: "Refresh Bastet node",
        status: "submitted_unverified",
        node_id: "bastet",
        started_at: "2026-04-22T12:00:00Z",
        idempotency_key: "refresh-bastet",
      }),
    } as Response);

    render(
      <NodesPage
        nodes={[
          {
            node_id: "bastet",
            base_url: "http://192.168.50.209:9110",
            display_name: "Bastet",
            observed_status: "healthy",
            freshness: "live",
            last_seen_at: "2026-04-22T12:00:00Z",
            gpu_stats: [],
            cpu_usage_percent: null,
            memory_used_mb: null,
            ollama_status: "ok",
            ollama_errors: [],
            model_count: 0,
          },
        ]}
        runs={[]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /refresh node/i }));

    await waitFor(() => {
      expect(screen.getByText(/completion has not been verified yet/i)).toBeTruthy();
    });

    expect(screen.getByText("submitted_unverified")).toBeTruthy();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/actions/refresh-node/bastet", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    });
  });

  it("renders the remote focus panel with bastet telemetry and recent runs", () => {
    render(
      <NodesPage
        nodes={[
          {
            node_id: "bastet",
            display_name: "Bastet",
            base_url: "http://192.168.50.209:9110",
            observed_status: "healthy",
            freshness: "live",
            last_seen_at: "2026-04-22T12:00:00Z",
            gpu_stats: [{ name: "RTX 3090", memory_total_mb: 24576, temperature_c: 42 }],
            cpu_usage_percent: null,
            memory_used_mb: 32768,
            ollama_status: "ok",
            ollama_errors: [],
            model_count: 3,
            role: "remote",
          },
        ]}
        runs={[
          {
            run_id: "run-remote",
            summary: "Refresh Bastet node",
            status: "submitted_unverified",
            node_id: "bastet",
            started_at: "2026-04-22T12:00:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByText(/remote node telemetry and recent operations/i)).toBeTruthy();
    expect(screen.getByText("RTX 3090")).toBeTruthy();
    expect(screen.getByText("http://192.168.50.209:9110")).toBeTruthy();
    expect(screen.getByText(/latest bastet-side activity/i)).toBeTruthy();
  });
});
