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
            display_name: "Bastet",
            observed_status: "degraded",
            freshness: "stale",
            last_seen_at: "2026-04-22T12:00:00Z",
          },
        ]}
      />,
    );

    expect(screen.getByText("Bastet")).toBeTruthy();
    expect(screen.getByText("degraded")).toBeTruthy();
    expect(screen.getByText(/stale/i)).toBeTruthy();
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
            display_name: "Bastet",
            observed_status: "healthy",
            freshness: "live",
            last_seen_at: "2026-04-22T12:00:00Z",
          },
        ]}
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
});
