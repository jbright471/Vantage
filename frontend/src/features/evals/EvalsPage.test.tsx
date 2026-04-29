import { render, screen, waitFor } from "@testing-library/react";

import { EvalsPage } from "./EvalsPage";

describe("EvalsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the eval lab foundation empty state", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    render(<EvalsPage />);

    await waitFor(() => {
      expect(screen.getByText(/no eval suites have been defined yet/i)).toBeTruthy();
    });
    expect(screen.getByText("Eval Lab foundation")).toBeTruthy();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/evals/suites", {
      headers: {
        Accept: "application/json",
      },
    });
  });
});
