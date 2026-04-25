import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RoutingPage } from "./RoutingPage";

describe("RoutingPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the preferred node order", () => {
    render(
      <RoutingPage
        rules={[
          {
            rule_id: "scheduled-default",
            priority_class: "scheduled",
            preferred_nodes: ["jedi", "bastet"],
          },
        ]}
        availableNodes={["jedi", "bastet"]}
      />,
    );

    expect(screen.getByText("scheduled")).toBeTruthy();
    expect(screen.getByText("jedi → bastet")).toBeTruthy();
  });

  it("requires strict confirmation before promoting a preferred node", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        rule_id: "scheduled-default",
        priority_class: "scheduled",
        model_name: null,
        preferred_nodes: ["bastet", "jedi"],
      }),
    } as Response);

    render(
      <RoutingPage
        rules={[
          {
            rule_id: "scheduled-default",
            priority_class: "scheduled",
            preferred_nodes: ["jedi", "bastet"],
          },
        ]}
        availableNodes={["jedi", "bastet"]}
        nodeSummaries={[
          {
            node_id: "jedi",
            display_name: "Jedi",
            observed_status: "healthy",
            freshness: "live",
            model_count: 4,
          },
          {
            node_id: "bastet",
            display_name: "Bastet",
            observed_status: "healthy",
            freshness: "live",
            model_count: 8,
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /prefer bastet/i }));

    expect(screen.getByRole("dialog", { name: /confirm preferred node change/i })).toBeTruthy();
    expect(screen.getByText("Target node state")).toBeTruthy();
    expect(screen.getByText(/target node is currently healthy and live/i)).toBeTruthy();
    expect(globalThis.fetch).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /confirm routing change/i }));

    await waitFor(() => {
      expect(screen.getByText(/preferred node updated/i)).toBeTruthy();
    });

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/routing/scheduled-default", {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        preferred_nodes: ["bastet", "jedi"],
      }),
    });
  });

  it("warns before promoting a stale or degraded target node", () => {
    render(
      <RoutingPage
        rules={[
          {
            rule_id: "interactive-default",
            priority_class: "interactive",
            preferred_nodes: ["jedi", "bastet"],
          },
        ]}
        availableNodes={["jedi", "bastet"]}
        nodeSummaries={[
          {
            node_id: "jedi",
            display_name: "Jedi",
            observed_status: "healthy",
            freshness: "live",
            model_count: 4,
          },
          {
            node_id: "bastet",
            display_name: "Bastet",
            observed_status: "degraded",
            freshness: "stale",
            model_count: 8,
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /prefer bastet/i }));

    expect(screen.getByText("Target node state")).toBeTruthy();
    expect(screen.getByText("degraded")).toBeTruthy();
    expect(screen.getByText("stale")).toBeTruthy();
    expect(screen.getByText(/not currently healthy and live/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /confirm override/i })).toBeTruthy();
  });
});
