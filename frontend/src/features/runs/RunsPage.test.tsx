import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RunsPage } from "./RunsPage";

const runsPayload = {
  items: [
    {
      run_id: "run-1",
      summary: "Restart Bastet agent",
      status: "submitted_unverified",
      node_id: "bastet",
      started_at: "2026-04-23T22:50:00Z",
    },
  ],
  total: 1,
  limit: 10,
  offset: 0,
  filters: {
    status: null,
    node_id: null,
    detail_type: null,
  },
};

describe("RunsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders submitted_unverified honestly from the backend run query", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => runsPayload,
    } as Response);

    render(
      <RunsPage
        runs={[
          {
            run_id: "run-1",
            summary: "Restart Bastet agent",
            status: "submitted_unverified",
            node_id: "bastet",
          },
        ]}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Restart Bastet agent")).toBeTruthy();
    });

    expect(screen.getByText("Restart Bastet agent")).toBeTruthy();
    expect(screen.getByText("submitted_unverified")).toBeTruthy();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/runs?limit=10", {
      headers: {
        Accept: "application/json",
      },
    });
  });

  it("pushes filtering to the runs API instead of filtering in the browser", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        ...runsPayload,
        items: [],
        total: 0,
        filters: {
          ...runsPayload.filters,
          status: "failed",
        },
      }),
    } as Response);

    render(<RunsPage runs={[]} />);

    fireEvent.click(screen.getByRole("button", { name: "Failed" }));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith("/api/runs?status=failed&limit=10", {
        headers: {
          Accept: "application/json",
        },
      });
    });

    expect(screen.getByRole("link", { name: "Export CSV" }).getAttribute("href")).toBe(
      "/api/runs/export.csv?status=failed",
    );
    expect(screen.getByRole("link", { name: "Export JSON" }).getAttribute("href")).toBe(
      "/api/runs/export.json?status=failed",
    );
  });
});
