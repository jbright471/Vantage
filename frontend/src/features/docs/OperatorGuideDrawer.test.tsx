import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { OperatorGuideDrawer } from "./OperatorGuideDrawer";


describe("OperatorGuideDrawer", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("stays out of the DOM and avoids fetching until opened", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    render(<OperatorGuideDrawer isOpen={false} onClose={vi.fn()} />);

    expect(screen.queryByRole("dialog", { name: "Operator Guide" })).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("renders backend-served markdown with GitHub-flavored tables when opened", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      text: async () =>
        [
          "# Daily Operations",
          "",
          "| Setting | Default |",
          "| --- | --- |",
          "| `poll_interval_seconds` | `10` |",
        ].join("\n"),
    } as Response);

    render(<OperatorGuideDrawer isOpen={true} onClose={vi.fn()} />);

    expect(screen.getByRole("dialog", { name: "Operator Guide" })).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Daily Operations" })).toBeTruthy();
    });

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/docs/operator-guide.md", {
      headers: {
        Accept: "text/markdown",
      },
    });
    expect(screen.getByText("poll_interval_seconds")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Open raw markdown" }).getAttribute("href")).toBe(
      "/api/docs/operator-guide.md",
    );
  });

  it("closes from the Escape key", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise<Response>(() => undefined));
    const onClose = vi.fn();

    render(<OperatorGuideDrawer isOpen={true} onClose={onClose} />);
    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders an operator-facing error when the guide cannot be fetched", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
    } as Response);

    render(<OperatorGuideDrawer isOpen={true} onClose={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Guide unavailable" })).toBeTruthy();
    });

    expect(screen.getByText(/Confirm the backend is running/)).toBeTruthy();
  });
});
