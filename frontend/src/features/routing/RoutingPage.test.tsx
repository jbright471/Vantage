import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { RoutingPage } from "./RoutingPage";

describe("RoutingPage", () => {
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

  it("lets the operator promote a preferred node", async () => {
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
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /prefer bastet/i }));

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
});
