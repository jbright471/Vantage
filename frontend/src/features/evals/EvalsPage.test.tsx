import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { EvalsPage } from "./EvalsPage";

describe("EvalsPage", () => {
  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("renders the eval lab foundation empty state", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/evals/score-history") {
        return {
          ok: true,
          json: async () => ({ total_runs: 0, placements: [], suites: [], cases: [], recent_runs: [] }),
        } as Response;
      }
      if (url === "/api/evals/schedules") {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }
      return {
        ok: true,
        json: async () => [],
      } as Response;
    });

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
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/evals/score-history") {
        return {
          ok: true,
          json: async () => ({ total_runs: 0, placements: [], suites: [], cases: [], recent_runs: [] }),
        } as Response;
      }
      if (url === "/api/evals/schedules") {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }
      if (url === "/api/evals/suites" && init?.method === "POST") {
        return { ok: true, json: async () => createdSuite } as Response;
      }
      if (url === "/api/evals/suites/suite-1/cases") {
        return { ok: true, json: async () => suiteWithCase } as Response;
      }
      return { ok: true, json: async () => [] } as Response;
    });

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
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url === "/api/evals/score-history") {
        return {
          ok: true,
          json: async () => ({
            total_runs: 1,
            placements: [
              {
                model_name: "llama3.2:latest",
                node_id: "jedi",
                run_count: 1,
                passed_count: 1,
                failed_count: 0,
                pass_rate: 1,
                latest_started_at: "2026-04-29T12:01:00Z",
              },
            ],
            suites: [],
            cases: [
              {
                suite_id: "suite-1",
                suite_name: "Reasoning Smoke",
                case_id: "case-1",
                case_name: "JSON Answer",
                run_count: 1,
                passed_count: 1,
                failed_count: 0,
                pass_rate: 1,
                latest_started_at: "2026-04-29T12:01:00Z",
              },
            ],
            recent_runs: [
              {
                run_id: "run-1",
                suite_id: "suite-1",
                suite_name: "Reasoning Smoke",
                case_id: "case-1",
                case_name: "JSON Answer",
                model_name: "llama3.2:latest",
                node_id: "jedi",
                status: "success",
                passed: true,
                score: 1,
                reason: "expected_subset_matched",
                missing_or_mismatched: [],
                response_preview: "{\"shape\":\"answer\"}",
                response_json: { shape: "answer" },
                started_at: "2026-04-29T12:01:00Z",
                duration_ms: 1000,
              },
            ],
          }),
        } as Response;
      }
      if (url === "/api/evals/schedules") {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }
      if (url === "/api/evals/suites/suite-1/attempts") {
        return {
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
        } as Response;
      }
      if (url === "/api/evals/runs/run-1/execute") {
        return {
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
        } as Response;
      }
      return {
        ok: true,
        json: async () => [suite],
      } as Response;
    });

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

    fireEvent.click(screen.getByRole("button", { name: /^execute$/i }));

    await waitFor(() => {
      expect(screen.getByText("success")).toBeTruthy();
    });
    expect(screen.getByText("Placement comparison")).toBeTruthy();
    expect(screen.getAllByText("100%").length).toBeGreaterThan(0);
    expect(screen.getByText("Lowest passing cases")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /inspect score/i }));

    expect(screen.getByText("Score detail")).toBeTruthy();
    expect(screen.getByText("expected_subset_matched")).toBeTruthy();
    expect(screen.getByText("{\"shape\":\"answer\"}")).toBeTruthy();
  });

  it("creates a recurring eval schedule", async () => {
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
    const createdSchedule = {
      schedule_id: "schedule-1",
      suite_id: "suite-1",
      suite_name: "Reasoning Smoke",
      model_name: "llama3.2:latest",
      node_id: "jedi",
      interval_minutes: 30,
      enabled: true,
      auto_execute: true,
      created_at: "2026-04-29T12:00:00Z",
      updated_at: "2026-04-29T12:00:00Z",
      next_run_at: "2026-04-29T12:30:00Z",
      last_queued_at: null,
      metadata_json: {},
    };
    const queuedSchedule = {
      ...createdSchedule,
      updated_at: "2026-04-29T12:05:00Z",
      last_queued_at: "2026-04-29T12:05:00Z",
      metadata_json: {
        last_manual_queue: {
          queued_at: "2026-04-29T12:05:00Z",
          run_count: 1,
          run_ids: ["schedule-run-1"],
        },
      },
    };
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/evals/score-history") {
        return {
          ok: true,
          json: async () => ({ total_runs: 0, placements: [], suites: [], cases: [], recent_runs: [] }),
        } as Response;
      }
      if (url === "/api/evals/schedules" && init?.method === "POST") {
        return {
          ok: true,
          json: async () => createdSchedule,
        } as Response;
      }
      if (url === "/api/evals/schedules/schedule-1/queue-now") {
        return {
          ok: true,
          json: async () => ({
            attempt_id: "attempt-schedule-1",
            suite_id: "suite-1",
            suite_name: "Reasoning Smoke",
            model_name: "llama3.2:latest",
            node_id: "jedi",
            run_count: 1,
            runs: [
              {
                run_id: "schedule-run-1",
                summary: "Queued eval case 'JSON Answer' for llama3.2:latest on jedi",
                status: "queued",
                source_type: "eval",
                detail_type: "eval_attempt",
                node_id: "jedi",
                model_name: "llama3.2:latest",
                action_type: "eval",
                started_at: "2026-04-29T12:05:00Z",
                metadata_json: {
                  attempt_id: "attempt-schedule-1",
                  trigger: "schedule_manual",
                  schedule_id: "schedule-1",
                },
              },
            ],
            schedule: queuedSchedule,
          }),
        } as Response;
      }
      if (url === "/api/evals/schedules") {
        return {
          ok: true,
          json: async () => [],
        } as Response;
      }
      return {
        ok: true,
        json: async () => [suite],
      } as Response;
    });

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

    fireEvent.change(screen.getByLabelText("Schedule suite"), {
      target: { value: "suite-1" },
    });
    fireEvent.change(screen.getByLabelText("Schedule placement"), {
      target: { value: "llama3.2:latest::jedi" },
    });
    fireEvent.change(screen.getByLabelText("Interval minutes"), {
      target: { value: "30" },
    });
    fireEvent.click(screen.getByLabelText("Auto-execute when due"));
    fireEvent.click(screen.getByRole("button", { name: /create schedule/i }));

    await waitFor(() => {
      expect(screen.getByText("Recurring eval schedules")).toBeTruthy();
    });
    expect(screen.getByText("Every 30 min")).toBeTruthy();
    expect(screen.getByText("Auto-execute")).toBeTruthy();
    expect(screen.getByText(/Next queue:/)).toBeTruthy();
    expect(screen.getByText(/8:30/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /^queue now$/i }));

    await waitFor(() => {
      expect(screen.getByText(/1 run queued for llama3.2:latest on jedi/i)).toBeTruthy();
    });
    expect(screen.getByText(/Last queued:/)).toBeTruthy();
    expect(screen.getAllByText(/8:05/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Queued eval case 'JSON Answer'/)).toBeTruthy();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/evals/schedules/schedule-1/queue-now", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    });
  });

  it("removes eval schedules, cases, and empty suites from the lab", async () => {
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
    const suiteWithoutCases = {
      ...suite,
      case_count: 0,
      cases: [],
    };
    const schedule = {
      schedule_id: "schedule-1",
      suite_id: "suite-1",
      suite_name: "Reasoning Smoke",
      model_name: "llama3.2:latest",
      node_id: "jedi",
      interval_minutes: 30,
      enabled: true,
      auto_execute: false,
      created_at: "2026-04-29T12:00:00Z",
      updated_at: "2026-04-29T12:00:00Z",
      next_run_at: "2026-04-29T12:30:00Z",
      last_queued_at: null,
      metadata_json: {},
    };

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/evals/score-history") {
        return {
          ok: true,
          json: async () => ({ total_runs: 0, placements: [], suites: [], cases: [], recent_runs: [] }),
        } as Response;
      }
      if (url === "/api/evals/schedules/schedule-1" && init?.method === "DELETE") {
        return { ok: true, status: 204, text: async () => "" } as Response;
      }
      if (url === "/api/evals/suites/suite-1/cases/case-1" && init?.method === "DELETE") {
        return { ok: true, json: async () => suiteWithoutCases } as Response;
      }
      if (url === "/api/evals/suites/suite-1" && init?.method === "DELETE") {
        return { ok: true, status: 204, text: async () => "" } as Response;
      }
      if (url === "/api/evals/schedules") {
        return {
          ok: true,
          json: async () => [schedule],
        } as Response;
      }
      return {
        ok: true,
        json: async () => [suite],
      } as Response;
    });

    render(<EvalsPage />);

    await waitFor(() => {
      expect(screen.getByText("Recurring eval schedules")).toBeTruthy();
    });
    expect(screen.getByText("JSON Answer")).toBeTruthy();
    expect(screen.getByRole<HTMLButtonElement>("button", { name: /delete suite reasoning smoke/i }).disabled).toBe(
      true,
    );

    fireEvent.click(screen.getByRole("button", { name: /delete schedule reasoning smoke/i }));

    await waitFor(() => {
      expect(screen.queryByText("Recurring eval schedules")).toBeNull();
    });

    fireEvent.click(screen.getByRole("button", { name: /delete case json answer/i }));

    await waitFor(() => {
      expect(screen.getByText("No cases")).toBeTruthy();
    });

    fireEvent.click(screen.getByRole("button", { name: /delete suite reasoning smoke/i }));

    await waitFor(() => {
      expect(screen.getByText(/no eval suites have been defined yet/i)).toBeTruthy();
    });
  });

  it("generates an optional assisted eval summary", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === "/api/evals/score-history") {
        return {
          ok: true,
          json: async () => ({
            total_runs: 1,
            placements: [],
            suites: [],
            cases: [],
            recent_runs: [
              {
                run_id: "eval-run-1",
                suite_id: "suite-1",
                suite_name: "Reasoning Smoke",
                case_id: "case-1",
                case_name: "JSON Answer",
                model_name: "llama3.2:latest",
                node_id: "jedi",
                status: "failed",
                passed: false,
                score: 0,
                reason: "expected_subset_mismatch",
                missing_or_mismatched: ["answer"],
                response_preview: "{}",
                response_json: {},
                started_at: "2026-04-29T12:01:00Z",
                duration_ms: 1000,
              },
            ],
            operator_summary: {
              headline: "1 repeated eval failure cluster detected.",
              regression_count: 0,
              flaky_case_count: 0,
              failure_cluster_count: 1,
            },
          }),
        } as Response;
      }
      if (url === "/api/evals/schedules") {
        return { ok: true, json: async () => [] } as Response;
      }
      if (url === "/api/evals/assisted-summary" && init?.method === "POST") {
        return {
          ok: true,
          json: async () => ({
            run_id: "summary-run-1",
            summary: "Generated assisted eval summary with llama3.2:latest on jedi",
            status: "success",
            source_type: "eval",
            detail_type: "eval_assisted_summary",
            node_id: "jedi",
            model_name: "llama3.2:latest",
            started_at: "2026-04-29T12:02:00Z",
            metadata_json: {
              response_text: "## Situation\nThe eval failure is concentrated in JSON Answer.",
            },
          }),
        } as Response;
      }
      return { ok: true, json: async () => [] } as Response;
    });

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
      expect(screen.getByText(/1 repeated eval failure cluster detected/i)).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText("Summary model placement"), {
      target: { value: "llama3.2:latest::jedi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate summary/i }));

    await waitFor(() => {
      expect(screen.getByText("Local model summary")).toBeTruthy();
    });
    expect(screen.getByText(/failure is concentrated in JSON Answer/i)).toBeTruthy();
  });

  it("applies eval intelligence chart controls through backend query params", async () => {
    const requestedUrls: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      requestedUrls.push(url);
      if (url.startsWith("/api/evals/score-history")) {
        return {
          ok: true,
          json: async () => ({
            total_runs: 1,
            placements: [
              {
                model_name: "llama3.2:latest",
                node_id: "jedi",
                run_count: 1,
                passed_count: 1,
                failed_count: 0,
                pass_rate: 1,
                latest_started_at: "2026-04-29T12:01:00Z",
              },
            ],
            suites: [],
            cases: [],
            recent_runs: [],
            filters: {
              window_days: url.includes("window_days=7") ? 7 : 30,
              model_name: url.includes("model_name=") ? "llama3.2:latest" : null,
              node_id: url.includes("node_id=") ? "jedi" : null,
              recent_limit: 20,
            },
            thresholds: {
              flakiness_min_rate: url.includes("flakiness_min_rate=0.1") ? 0.1 : 0.2,
              failure_cluster_min_count: url.includes("failure_cluster_min_count=3") ? 3 : 2,
            },
          }),
        } as Response;
      }
      if (url === "/api/evals/schedules") {
        return { ok: true, json: async () => [] } as Response;
      }
      return { ok: true, json: async () => [] } as Response;
    });

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
      expect(screen.getByText("Eval intelligence window")).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText("Time window"), { target: { value: "7" } });
    fireEvent.change(screen.getByLabelText("Placement filter"), { target: { value: "llama3.2:latest::jedi" } });
    fireEvent.change(screen.getByLabelText("Flakiness sensitivity"), { target: { value: "0.1" } });
    fireEvent.change(screen.getByLabelText("Failure cluster minimum"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: /apply controls/i }));

    await waitFor(() => {
      expect(requestedUrls.some((url) => url.includes("window_days=7"))).toBe(true);
    });
    const filteredUrl = requestedUrls.find((url) => url.includes("window_days=7")) ?? "";
    expect(filteredUrl).toContain("model_name=llama3.2%3Alatest");
    expect(filteredUrl).toContain("node_id=jedi");
    expect(filteredUrl).toContain("flakiness_min_rate=0.1");
    expect(filteredUrl).toContain("failure_cluster_min_count=3");
    expect(screen.getByText("7d window")).toBeTruthy();
    expect(screen.getAllByText("llama3.2:latest / jedi").length).toBeGreaterThan(0);
  });

  it("saves and reapplies local eval intelligence presets", async () => {
    const requestedUrls: string[] = [];
    vi.spyOn(window, "prompt").mockReturnValue("Fast flaky review");
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      requestedUrls.push(url);
      if (url.startsWith("/api/evals/score-history")) {
        return {
          ok: true,
          json: async () => ({
            total_runs: 0,
            placements: [],
            suites: [],
            cases: [],
            recent_runs: [],
            filters: {
              window_days: url.includes("window_days=7") ? 7 : 30,
              model_name: null,
              node_id: null,
              recent_limit: 20,
            },
            thresholds: {
              flakiness_min_rate: url.includes("flakiness_min_rate=0.1") ? 0.1 : 0.2,
              failure_cluster_min_count: 2,
            },
          }),
        } as Response;
      }
      if (url === "/api/evals/schedules") {
        return { ok: true, json: async () => [] } as Response;
      }
      return { ok: true, json: async () => [] } as Response;
    });

    render(<EvalsPage />);

    await waitFor(() => {
      expect(screen.getByText("Eval intelligence window")).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText("Time window"), { target: { value: "7" } });
    fireEvent.change(screen.getByLabelText("Flakiness sensitivity"), { target: { value: "0.1" } });
    fireEvent.click(screen.getByRole("button", { name: /save preset/i }));

    const presetOption = screen.getByRole<HTMLOptionElement>("option", { name: "Fast flaky review" });
    expect(presetOption).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Time window"), { target: { value: "30" } });
    fireEvent.change(screen.getByLabelText("Saved preset"), { target: { value: presetOption.value } });
    fireEvent.click(screen.getByRole("button", { name: /apply preset/i }));

    await waitFor(() => {
      expect(requestedUrls.some((url) => url.includes("window_days=7"))).toBe(true);
    });
    expect(screen.getByText("7d window")).toBeTruthy();
  });
});
