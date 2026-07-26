import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { OperatorGuideDrawer } from "./OperatorGuideDrawer";


const guideMarkdown = [
  "# Vantage Operator Guide",
  "",
  "Welcome to the local control plane.",
  "",
  "## Core Concepts",
  "",
  "Read this context before operating Vantage.",
  "",
  "### Truth Over Appearance",
  "",
  "Trust observed state.",
  "",
  "### Observed State",
  "",
  "| Setting | Default |",
  "| --- | --- |",
  "| `poll_interval_seconds` | `10` |",
].join("\n");

function renderDrawer(overrides: Partial<React.ComponentProps<typeof OperatorGuideDrawer>> = {}) {
  return render(
    <OperatorGuideDrawer
      isOpen={true}
      selectedSlug="welcome"
      onClose={vi.fn()}
      onNavigate={vi.fn()}
      {...overrides}
    />,
  );
}

describe("OperatorGuideDrawer", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("stays out of the DOM and avoids fetching until opened", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    renderDrawer({ isOpen: false });

    expect(screen.queryByRole("dialog", { name: "Operator Guide" })).toBeNull();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("renders one selected section and keeps GitHub-flavored tables", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      text: async () => guideMarkdown,
    } as Response);

    renderDrawer({ selectedSlug: "observed-state" });

    expect(screen.getByRole("dialog", { name: "Operator Guide" })).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Observed State", level: 2 })).toBeTruthy();
    });

    expect(screen.queryByText("Trust observed state.")).toBeNull();
    expect(screen.getByText("poll_interval_seconds")).toBeTruthy();
    expect(screen.getByText("Section 3 of 3")).toBeTruthy();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/docs/operator-guide.md", {
      headers: {
        Accept: "text/markdown",
      },
    });
    expect(screen.getByRole("link", { name: "Open Markdown" }).getAttribute("href")).toBe(
      "/api/docs/operator-guide.md",
    );
  });

  it("filters section navigation using titles and section content", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      text: async () => guideMarkdown,
    } as Response);

    renderDrawer();
    const search = await screen.findByRole("searchbox", { name: "Search guide" });
    fireEvent.change(search, { target: { value: "poll_interval" } });

    expect(screen.getByText("1 section")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Observed State" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Truth Over Appearance" })).toBeNull();
  });

  it("reports navigation and normalizes an unknown URL selection", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      text: async () => guideMarkdown,
    } as Response);
    const onNavigate = vi.fn();

    renderDrawer({ selectedSlug: "missing-section", onNavigate });

    await waitFor(() => {
      expect(onNavigate).toHaveBeenCalledWith("welcome", { replace: true });
    });

    fireEvent.click(screen.getByRole("link", { name: "Truth Over Appearance" }));
    expect(onNavigate).toHaveBeenCalledWith("truth-over-appearance");
  });

  it("closes from the Escape key", () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => new Promise<Response>(() => undefined));
    const onClose = vi.fn();

    renderDrawer({ onClose });
    fireEvent.keyDown(window, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("renders an operator-facing error when the guide cannot be fetched", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
    } as Response);

    renderDrawer();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Guide unavailable" })).toBeTruthy();
    });

    expect(screen.getByText(/Confirm the backend is running/)).toBeTruthy();
  });
});
