import { render, screen } from "@testing-library/react";

import { ModelsPage } from "./ModelsPage";

describe("ModelsPage", () => {
  it("renders the merged inventory placements", () => {
    render(
      <ModelsPage
        models={[
          {
            model_name: "qwen3.6:latest",
            placements: ["jedi", "bastet"],
          },
        ]}
      />,
    );

    expect(screen.getByText("qwen3.6:latest")).toBeTruthy();
    expect(screen.getByText("jedi, bastet")).toBeTruthy();
  });
});
