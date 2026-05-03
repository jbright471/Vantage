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

  it("opens diagnostics for a degraded node with endpoint guidance", () => {
    render(
      <NodesPage
        nodes={[
          {
            node_id: "jedi",
            base_url: "http://127.0.0.1:8000",
            display_name: "Jedi",
            observed_status: "degraded",
            freshness: "live",
            last_seen_at: "2026-04-22T12:00:00Z",
            gpu_stats: [],
            cpu_usage_percent: null,
            memory_used_mb: null,
            ollama_status: "error",
            ollama_errors: [
              {
                base_url: "http://host.docker.internal:11435",
                error: "[Errno 101] Network is unreachable",
              },
            ],
            model_count: 4,
          },
        ]}
        runs={[]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /diagnose/i }));

    expect(screen.getByRole("dialog", { name: /jedi/i })).toBeTruthy();
    expect(screen.getByText(/one or more ollama endpoints failed/i)).toBeTruthy();
    expect(screen.getByText("http://host.docker.internal:11435")).toBeTruthy();
    expect(screen.getByText(/confirm the backend container can route/i)).toBeTruthy();
    expect(screen.getByText(/diagnosing from observed state only/i)).toBeTruthy();
  });

  it("submits a refresh action and renders verified completion", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        run_id: "run-1",
        summary: "Refresh node bastet verified",
        status: "success",
        node_id: "bastet",
        started_at: "2026-04-22T12:00:00Z",
        ended_at: "2026-04-22T12:00:01Z",
        duration_ms: 1000,
        idempotency_key: "refresh-bastet",
        metadata_json: { verified: true },
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
      expect(screen.getByText(/refresh verified/i)).toBeTruthy();
    });

    expect(screen.getByText("success")).toBeTruthy();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/actions/refresh-node/bastet", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    });
  });

  it("requires confirmation before quarantining a node", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        run_id: "run-quarantine",
        summary: "Quarantine node bastet applied",
        status: "success",
        node_id: "bastet",
        started_at: "2026-04-22T12:00:00Z",
        ended_at: "2026-04-22T12:00:01Z",
        duration_ms: 1000,
        idempotency_key: "quarantine-bastet",
        metadata_json: {
          previous_enabled: true,
          requested_enabled: false,
          removed_from_routing_rules: ["batch-default"],
        },
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
            enabled: true,
          },
        ]}
        runs={[]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /quarantine node/i }));

    expect(screen.getByRole("dialog", { name: /confirm node quarantine/i })).toBeTruthy();
    expect(screen.getByText(/host services are not stopped/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /confirm quarantine/i }));

    await waitFor(() => {
      expect(screen.getByText(/bastet quarantined/i)).toBeTruthy();
    });

    expect(screen.getByText("disabled")).toBeTruthy();
    expect(screen.getByRole("button", { name: /re-enable node/i })).toBeTruthy();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/actions/nodes/bastet/enabled", {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ enabled: false }),
    });
  });

  it("requires confirmation before disabling a failing local Ollama endpoint", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        run_id: "run-endpoint",
        summary: "Disable local Ollama endpoint http://127.0.0.1:11435 applied",
        status: "success",
        node_id: "jedi",
        started_at: "2026-04-22T12:00:00Z",
        ended_at: "2026-04-22T12:00:01Z",
        duration_ms: 1000,
        idempotency_key: "endpoint-jedi",
        metadata_json: {
          endpoint_url: "http://127.0.0.1:11435",
          requested_disabled: true,
        },
      }),
    } as Response);

    render(
      <NodesPage
        nodes={[
          {
            node_id: "jedi",
            base_url: "http://127.0.0.1:8000",
            display_name: "Jedi",
            observed_status: "degraded",
            freshness: "live",
            last_seen_at: "2026-04-22T12:00:00Z",
            gpu_stats: [],
            cpu_usage_percent: null,
            memory_used_mb: null,
            ollama_status: "error",
            ollama_errors: [
              {
                base_url: "http://127.0.0.1:11435",
                error: "Connection refused",
              },
            ],
            model_count: 4,
            role: "primary",
          },
        ]}
        runs={[]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /diagnose/i }));
    fireEvent.click(screen.getByRole("button", { name: /disable endpoint/i }));

    expect(screen.getByRole("dialog", { name: /confirm endpoint disable/i })).toBeTruthy();
    expect(screen.getByText(/ollama service itself is not stopped/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /confirm disable endpoint/i }));

    await waitFor(() => {
      expect(screen.getByText(/endpoint disabled/i)).toBeTruthy();
    });

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/actions/nodes/jedi/local-ollama-endpoint", {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        endpoint_url: "http://127.0.0.1:11435",
        disabled: true,
      }),
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
