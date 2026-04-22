import { render, screen } from "@testing-library/react";

import { RunsPage } from "./RunsPage";

describe("RunsPage", () => {
  it("renders submitted_unverified honestly", () => {
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

    expect(screen.getByText("Restart Bastet agent")).toBeTruthy();
    expect(screen.getByText("submitted_unverified")).toBeTruthy();
  });
});
