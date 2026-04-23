import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ModelsPage } from "./ModelsPage";

describe("ModelsPage", () => {
  it("renders the merged inventory placements", () => {
    render(
      <ModelsPage
        models={[
          {
            model_name: "qwen3.6:latest",
            placements: ["jedi", "bastet"],
            placement_details: [
              { node_id: "jedi", model_digest: "sha256:111", available: true },
              { node_id: "bastet", model_digest: "sha256:222", available: true },
            ],
          },
        ]}
      />,
    );

    expect(screen.getByText("qwen3.6:latest")).toBeTruthy();
    expect(screen.getByText("jedi")).toBeTruthy();
    expect(screen.getByText("bastet")).toBeTruthy();
  });

  it("runs a capability check from a model placement", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        run_id: "run-1",
        summary: "Capability check passed for qwen3.6:latest on bastet",
        status: "success",
        node_id: "bastet",
        started_at: "2026-04-23T12:00:00Z",
        duration_ms: 812,
        metadata_json: {
          response_preview: '{"mode":"ok"}',
        },
      }),
    } as Response);

    render(
      <ModelsPage
        models={[
          {
            model_name: "qwen3.6:latest",
            placements: ["bastet"],
            placement_details: [{ node_id: "bastet", model_digest: "sha256:222", available: true }],
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /check on bastet/i }));

    await waitFor(() => {
      expect(screen.getByText("success")).toBeTruthy();
    });

    expect(globalThis.fetch).toHaveBeenCalledWith("/api/models/capability-check", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model_name: "qwen3.6:latest",
        node_id: "bastet",
      }),
    });
  });
});
