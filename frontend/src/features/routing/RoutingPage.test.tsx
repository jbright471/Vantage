import { render, screen } from "@testing-library/react";

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
      />,
    );

    expect(screen.getByText("scheduled")).toBeTruthy();
    expect(screen.getByText("jedi → bastet")).toBeTruthy();
  });
});
