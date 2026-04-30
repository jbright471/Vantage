import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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

  it("creates a suite and adds a prompt case", async () => {
    const createdSuite = {
      suite_id: "suite-1",
      name: "Reasoning Smoke",
      description: "Short checks",
      created_at: "2026-04-29T12:00:00Z",
      metadata_json: {},
      case_count: 0,
      cases: [],
    };
    const suiteWithCase = {
      ...createdSuite,
      case_count: 1,
      cases: [
        {
          case_id: "case-1",
          name: "JSON Answer",
          prompt: "Return JSON",
          expected_json: { shape: "answer" },
          sort_order: 0,
        },
      ],
    };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => createdSuite,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => suiteWithCase,
      } as Response);

    render(<EvalsPage />);

    await waitFor(() => {
      expect(screen.getByText(/no eval suites have been defined yet/i)).toBeTruthy();
    });

    fireEvent.change(screen.getByPlaceholderText("Reasoning smoke test"), {
      target: { value: "Reasoning Smoke" },
    });
    fireEvent.change(screen.getByPlaceholderText(/short operator note/i), {
      target: { value: "Short checks" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create suite/i }));

    await waitFor(() => {
      expect(screen.getAllByText("Reasoning Smoke").length).toBeGreaterThan(0);
    });

    fireEvent.change(screen.getByLabelText("Case name"), {
      target: { value: "JSON Answer" },
    });
    fireEvent.change(screen.getByLabelText("Prompt"), {
      target: { value: "Return JSON" },
    });
    fireEvent.change(screen.getByLabelText("Expected JSON"), {
      target: { value: "{\"shape\":\"answer\"}" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add case/i }));

    await waitFor(() => {
      expect(screen.getByText("JSON Answer")).toBeTruthy();
    });
  });

  it("queues an eval attempt for a model placement", async () => {
    const suite = {
      suite_id: "suite-1",
      name: "Reasoning Smoke",
      description: "Short checks",
      created_at: "2026-04-29T12:00:00Z",
      metadata_json: {},
      case_count: 1,
      cases: [
        {
          case_id: "case-1",
          name: "JSON Answer",
          prompt: "Return JSON",
          expected_json: { shape: "answer" },
          sort_order: 0,
        },
      ],
    };
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [suite],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          attempt_id: "attempt-1",
          suite_id: "suite-1",
          suite_name: "Reasoning Smoke",
          model_name: "llama3.2:latest",
          node_id: "jedi",
          run_count: 1,
          runs: [
            {
              run_id: "run-1",
              summary: "Queued eval case 'JSON Answer' for llama3.2:latest on jedi",
              status: "queued",
              source_type: "eval",
              detail_type: "eval_attempt",
              node_id: "jedi",
              model_name: "llama3.2:latest",
              action_type: "eval",
              started_at: "2026-04-29T12:01:00Z",
              metadata_json: { attempt_id: "attempt-1" },
            },
          ],
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          run_id: "run-1",
          summary: "Eval case 'JSON Answer' passed for llama3.2:latest on jedi",
          status: "success",
          source_type: "eval",
          detail_type: "eval_attempt",
          node_id: "jedi",
          model_name: "llama3.2:latest",
          action_type: "eval",
          started_at: "2026-04-29T12:01:00Z",
          ended_at: "2026-04-29T12:01:01Z",
          duration_ms: 1000,
          metadata_json: { score: { passed: true, score: 1 } },
        }),
      } as Response);

    render(
      <EvalsPage
        models={[
          {
            model_name: "llama3.2:latest",
            placements: ["jedi"],
            placement_details: [{ node_id: "jedi", model_digest: null, available: true }],
          },
        ]}
      />,
    );

    await waitFor(() => {
      expect(screen.getAllByText("Reasoning Smoke").length).toBeGreaterThan(0);
    });

    fireEvent.change(screen.getAllByLabelText("Suite")[1], {
      target: { value: "suite-1" },
    });
    fireEvent.change(screen.getByLabelText("Model placement"), {
      target: { value: "llama3.2:latest::jedi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /queue eval attempt/i }));

    await waitFor(() => {
      expect(screen.getByText(/1 run queued for llama3.2:latest on jedi/i)).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /execute/i }));

    await waitFor(() => {
      expect(screen.getByText("success")).toBeTruthy();
    });
  });
});
