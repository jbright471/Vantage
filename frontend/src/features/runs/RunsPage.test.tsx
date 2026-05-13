import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RunsPage } from "./RunsPage";

const runsPayload = {
  items: [
    {
      run_id: "99653acc5b7a4e41873652bbbf67a911b3af246b56176fe3d75f02beea467d40",
      summary: "Restart Remote Worker agent",
      status: "submitted_unverified",
      node_id: "remote-worker",
      started_at: "2026-04-23T22:50:00Z",
      ended_at: null,
      duration_ms: null,
      metadata_json: {
        source: "test",
      },
    },
  ],
  total: 1,
  limit: 5,
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

  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  it("renders submitted_unverified honestly from the backend run query", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => runsPayload,
    } as Response);

    render(<RunsPage runs={runsPayload.items} />);

    await waitFor(() => {
      expect(screen.getByText("Restart Remote Worker agent")).toBeTruthy();
    });

    expect(screen.getByText("Restart Remote Worker agent")).toBeTruthy();
    expect(screen.getByText("submitted_unverified")).toBeTruthy();
    expect(screen.getByText("99653acc...")).toBeTruthy();
    expect(screen.queryByText("Request sent; Vantage has not verified completion yet.")).toBeNull();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/runs?limit=5", {
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
      expect(globalThis.fetch).toHaveBeenCalledWith("/api/runs?status=failed&limit=5", {
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
    expect(screen.getByRole("link", { name: "Export Signed Bundle" }).getAttribute("href")).toBe(
      "/api/runs/export.bundle.json?status=failed",
    );
  });

  it("expands all runs in place instead of navigating to an unimplemented route", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({
        ok: true,
        json: async () => runsPayload,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          ...runsPayload,
          items: runsPayload.items,
          total: 7,
          limit: 500,
        }),
      } as Response);

    render(<RunsPage runs={[]} />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "View All Runs" })).toBeTruthy();
    });

    expect(screen.queryByRole("link", { name: "View All Runs" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "View All Runs" }));

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith("/api/runs?limit=500", {
        headers: {
          Accept: "application/json",
        },
      });
    });

    expect(screen.getByRole("button", { name: "Show Recent Runs" })).toBeTruthy();
  });

  it("copies full run IDs and opens deep details in a drawer", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => runsPayload,
    } as Response);

    render(<RunsPage runs={[]} />);

    await waitFor(() => {
      expect(screen.getByText("Restart Remote Worker agent")).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /copy full run id/i }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "99653acc5b7a4e41873652bbbf67a911b3af246b56176fe3d75f02beea467d40",
    );
    expect(screen.queryByRole("dialog", { name: "Run Details" })).toBeNull();

    fireEvent.click(screen.getByText("Restart Remote Worker agent"));

    expect(screen.getByRole("dialog", { name: "Run Details" })).toBeTruthy();
    expect(screen.getByText("99653acc5b7a4e41873652bbbf67a911b3af246b56176fe3d75f02beea467d40")).toBeTruthy();
    expect(screen.getByText("2026-04-23T22:50:00Z")).toBeTruthy();
    expect(screen.getByText(/"metadata_json"/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Copy Payload" }));

    expect(navigator.clipboard.writeText).toHaveBeenLastCalledWith(JSON.stringify({ source: "test" }, null, 2));
  });
});
