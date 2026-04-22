import { render, screen } from "@testing-library/react";

import { NodesPage } from "./NodesPage";

describe("NodesPage", () => {
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
});
