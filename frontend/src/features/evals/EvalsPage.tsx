import { useEffect, useState, type FormEvent } from "react";

import {
  buildEvalHistoryExportUrl,
  createEvalAssistedSummary,
  createEvalCase,
  createEvalSchedule,
  createEvalSuite,
  createEvalBaseline,
  deleteEvalCase,
  deleteEvalIntelligencePreset,
  deleteEvalSchedule,
  deleteEvalSuite,
  duplicateEvalCase,
  duplicateEvalSuite,
  executeEvalAttemptBatch,
  executeEvalRun,
  fetchEvalIntelligencePresets,
  fetchEvalSchedules,
  fetchEvalScoreHistory,
  fetchEvalSuites,
  importEvalSuite,
  installStarterEvalSuite,
  queueEvalAttempt,
  queueEvalScheduleNow,
  saveEvalIntelligencePreset,
  updateEvalCase,
  updateEvalSchedule,
  updateEvalSuite,
  type EvalAttemptRecord,
  type EvalHistoryQuery,
  type EvalIntelligencePresetRecord,
  type EvalScheduleRecord,
  type EvalScoreHistoryRecord,
  type EvalScoreRunRecord,
  type EvalSuiteRecord,
  type ModelRecord,
  type RunRecord,
} from "../../api/client";
import { OverlayHeader, OverlaySurface } from "../../components/OverlaySurface";

type EvalsPageProps = {
  models?: ModelRecord[];
  runs?: RunRecord[];
};

type PlacementOption = {
  key: string;
  model_name: string;
  node_id: string;
};

type EvalIntelligenceControls = {
  window_days: string;
  placement_key: string;
  flakiness_min_rate: string;
  failure_cluster_min_count: string;
};

type EvalIntelligencePreset = EvalIntelligencePresetRecord;

type JudgeConfigDraft = {
  judge_model_name: string;
  judge_node_id: string;
  rubric: string;
  pass_threshold: number;
  max_context_chars: number;
};

const DEFAULT_EVAL_CONTROLS: EvalIntelligenceControls = {
  window_days: "30",
  placement_key: "",
  flakiness_min_rate: "0.2",
  failure_cluster_min_count: "2",
};

const DEFAULT_LLM_JUDGE_CONFIG: JudgeConfigDraft = {
  judge_model_name: "",
  judge_node_id: "",
  rubric: "Pass only when the response is accurate, concise, safe, and follows the requested format.",
  pass_threshold: 0.8,
  max_context_chars: 4000,
};

const EVAL_PRESETS_STORAGE_KEY = "vantage.evalIntelligencePresets.v1";

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "Pending timestamp";
  }

  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.valueOf())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(timestamp);
}

function dedupeRuns(runs: RunRecord[]): RunRecord[] {
  const seen = new Set<string>();
  return runs.filter((run) => {
    if (seen.has(run.run_id)) {
      return false;
    }
    seen.add(run.run_id);
    return true;
  });
}

function buildEvalHistoryQuery(controls: EvalIntelligenceControls): EvalHistoryQuery {
  const [modelName, nodeId] = controls.placement_key ? controls.placement_key.split("::") : [null, null];
  return {
    window_days: Number.parseInt(controls.window_days, 10),
    model_name: modelName || null,
    node_id: nodeId || null,
    flakiness_min_rate: Number.parseFloat(controls.flakiness_min_rate),
    failure_cluster_min_count: Number.parseInt(controls.failure_cluster_min_count, 10),
    recent_limit: 20,
  };
}

function isValidEvalHistoryQuery(query: EvalHistoryQuery): boolean {
  return (
    Number.isFinite(query.window_days) &&
    Number(query.window_days) >= 1 &&
    Number.isFinite(query.flakiness_min_rate) &&
    Number(query.flakiness_min_rate) >= 0 &&
    Number(query.flakiness_min_rate) <= 1 &&
    Number.isFinite(query.failure_cluster_min_count) &&
    Number(query.failure_cluster_min_count) >= 1
  );
}

function readEvalPresets(): EvalIntelligencePreset[] {
  try {
    const rawPresets = window.localStorage.getItem(EVAL_PRESETS_STORAGE_KEY);
    const parsed = rawPresets ? JSON.parse(rawPresets) : [];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((preset): preset is EvalIntelligencePreset => {
      return (
        typeof preset?.id === "string" &&
        typeof preset?.name === "string" &&
        typeof preset?.controls?.window_days === "string" &&
        typeof preset?.controls?.placement_key === "string" &&
        typeof preset?.controls?.flakiness_min_rate === "string" &&
        typeof preset?.controls?.failure_cluster_min_count === "string"
      );
    });
  } catch {
    return [];
  }
}

function writeEvalPresets(presets: EvalIntelligencePreset[]) {
  window.localStorage.setItem(EVAL_PRESETS_STORAGE_KEY, JSON.stringify(presets));
}

function parseJsonObject(rawValue: string): Record<string, unknown> {
  try {
    const parsed = rawValue ? JSON.parse(rawValue) : {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function readJudgeConfig(rawValue: string): JudgeConfigDraft {
  const parsed = parseJsonObject(rawValue);
  return {
    judge_model_name:
      typeof parsed.judge_model_name === "string" ? parsed.judge_model_name : DEFAULT_LLM_JUDGE_CONFIG.judge_model_name,
    judge_node_id: typeof parsed.judge_node_id === "string" ? parsed.judge_node_id : DEFAULT_LLM_JUDGE_CONFIG.judge_node_id,
    rubric: typeof parsed.rubric === "string" ? parsed.rubric : DEFAULT_LLM_JUDGE_CONFIG.rubric,
    pass_threshold:
      typeof parsed.pass_threshold === "number" ? parsed.pass_threshold : DEFAULT_LLM_JUDGE_CONFIG.pass_threshold,
    max_context_chars:
      typeof parsed.max_context_chars === "number"
        ? parsed.max_context_chars
        : DEFAULT_LLM_JUDGE_CONFIG.max_context_chars,
  };
}

function serializeJudgeConfig(config: JudgeConfigDraft): string {
  return JSON.stringify(
    {
      judge_model_name: config.judge_model_name,
      judge_node_id: config.judge_node_id,
      rubric: config.rubric,
      pass_threshold: Number(config.pass_threshold.toFixed(2)),
      max_context_chars: Math.round(config.max_context_chars),
    },
    null,
    2,
  );
}

function trendToneClass(passRate: number): string {
  if (passRate < 0.5) {
    return "is-critical";
  }
  if (passRate < 0.8) {
    return "is-warning";
  }
  return "is-healthy";
}

export function EvalsPage({ models = [], runs = [] }: EvalsPageProps) {
  const [suites, setSuites] = useState<EvalSuiteRecord[]>([]);
  const [requestState, setRequestState] = useState<"loading" | "idle" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [suiteForm, setSuiteForm] = useState({ name: "", description: "" });
  const [caseForm, setCaseForm] = useState({
    suite_id: "",
    name: "",
    prompt: "",
    expected_json: "{}",
    score_type: "json_subset",
    score_config_json: "{}",
  });
  const [attemptForm, setAttemptForm] = useState({ suite_id: "", placement_key: "" });
  const [scheduleForm, setScheduleForm] = useState({
    suite_id: "",
    placement_key: "",
    interval_minutes: "60",
    auto_execute: false,
  });
  const [summaryForm, setSummaryForm] = useState({ placement_key: "" });
  const [evalControls, setEvalControls] = useState<EvalIntelligenceControls>(DEFAULT_EVAL_CONTROLS);
  const [activeEvalQuery, setActiveEvalQuery] = useState<EvalHistoryQuery>(
    buildEvalHistoryQuery(DEFAULT_EVAL_CONTROLS),
  );
  const [evalPresets, setEvalPresets] = useState<EvalIntelligencePreset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState("");
  const [attemptResult, setAttemptResult] = useState<EvalAttemptRecord | null>(null);
  const [assistedSummaryRun, setAssistedSummaryRun] = useState<RunRecord | null>(null);
  const [schedules, setSchedules] = useState<EvalScheduleRecord[]>([]);
  const [scoreHistory, setScoreHistory] = useState<EvalScoreHistoryRecord | null>(null);
  const [selectedScoreRun, setSelectedScoreRun] = useState<EvalScoreRunRecord | null>(null);
  const [queuedEvalRuns, setQueuedEvalRuns] = useState<RunRecord[]>([]);
  const [executionStateByRun, setExecutionStateByRun] = useState<Record<string, "idle" | "running" | "error">>({});
  const [scheduleQueueStateById, setScheduleQueueStateById] = useState<Record<string, "idle" | "queueing" | "error">>(
    {},
  );
  const [mutationState, setMutationState] = useState<"idle" | "saving" | "error">("idle");

  useEffect(() => {
    let isCurrent = true;
    fetchEvalIntelligencePresets()
      .then((presets) => {
        if (isCurrent) {
          setEvalPresets(presets);
          writeEvalPresets(presets);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setEvalPresets(readEvalPresets());
        }
      });

    return () => {
      isCurrent = false;
    };
  }, []);

  useEffect(() => {
    let isCurrent = true;
    setRequestState("loading");
    setErrorMessage(null);

    fetchEvalSuites()
      .then((payload) => {
        if (!isCurrent) {
          return;
        }
        setSuites(payload);
        setRequestState("idle");
      })
      .catch((error) => {
        if (!isCurrent) {
          return;
        }
        setRequestState("error");
        setErrorMessage(error instanceof Error ? error.message : "Eval suites request failed.");
      });

    return () => {
      isCurrent = false;
    };
  }, []);

  useEffect(() => {
    let isCurrent = true;

    fetchEvalSchedules()
      .then((payload) => {
        if (isCurrent) {
          setSchedules(payload);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setSchedules([]);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, []);

  useEffect(() => {
    let isCurrent = true;

    fetchEvalScoreHistory(activeEvalQuery)
      .then((payload) => {
        if (isCurrent) {
          setScoreHistory(payload);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setScoreHistory(null);
        }
      });

    return () => {
      isCurrent = false;
    };
  }, [activeEvalQuery]);

  const totalCases = suites.reduce((total, suite) => total + suite.case_count, 0);
  const starterSuiteInstalled = suites.some(
    (suite) => suite.metadata_json.template_id === "vantage-starter-smoke-v1",
  );
  const placementOptionMap = new Map<string, PlacementOption>();
  models
    .flatMap((model) =>
      model.placement_details
        .filter((placement) => placement.available)
        .map((placement) => ({
          key: `${model.model_name}::${placement.node_id}`,
          model_name: model.model_name,
          node_id: placement.node_id,
        })),
    )
    .forEach((placement) => placementOptionMap.set(placement.key, placement));
  const placementOptions: PlacementOption[] = Array.from(placementOptionMap.values()).sort((left, right) =>
    `${left.model_name}:${left.node_id}`.localeCompare(`${right.model_name}:${right.node_id}`),
  );
  const judgeConfig = readJudgeConfig(caseForm.score_config_json);
  const judgePlacementKey =
    judgeConfig.judge_model_name && judgeConfig.judge_node_id
      ? `${judgeConfig.judge_model_name}::${judgeConfig.judge_node_id}`
      : "";
  const judgeConfigIsComplete = Boolean(
    judgeConfig.judge_model_name &&
      judgeConfig.judge_node_id &&
      judgeConfig.rubric.trim() &&
      Number.isFinite(judgeConfig.pass_threshold) &&
      Number.isFinite(judgeConfig.max_context_chars),
  );
  const recentEvalRuns = dedupeRuns([
    ...queuedEvalRuns,
    ...runs.filter((run) => run.detail_type === "eval_attempt"),
  ])
    .sort((left, right) => {
      const leftTime = left.started_at ? new Date(left.started_at).valueOf() : 0;
      const rightTime = right.started_at ? new Date(right.started_at).valueOf() : 0;
      return rightTime - leftTime;
    })
    .slice(0, 5);
  const activeEvalRunCount = recentEvalRuns.filter((run) =>
    ["queued", "submitted_unverified", "running"].includes(run.status),
  ).length;

  function updateJudgeConfig(patch: Partial<JudgeConfigDraft>) {
    const nextConfig = { ...readJudgeConfig(caseForm.score_config_json), ...patch };
    setCaseForm((current) => ({
      ...current,
      score_config_json: serializeJudgeConfig(nextConfig),
    }));
  }

  function handleScoreTypeChange(nextScoreType: string) {
    setCaseForm((current) => ({
      ...current,
      score_type: nextScoreType,
      score_config_json:
        nextScoreType === "llm_judge" && Object.keys(parseJsonObject(current.score_config_json)).length === 0
          ? serializeJudgeConfig(DEFAULT_LLM_JUDGE_CONFIG)
          : current.score_config_json,
    }));
  }

  function suiteHasSchedule(suiteId: string): boolean {
    return schedules.some((schedule) => schedule.suite_id === suiteId);
  }

  function upsertSuite(updatedSuite: EvalSuiteRecord) {
    setSuites((current) => {
      const withoutSuite = current.filter((suite) => suite.suite_id !== updatedSuite.suite_id);
      return [...withoutSuite, updatedSuite].sort((left, right) => left.name.localeCompare(right.name));
    });
  }

  function upsertEvalRun(updatedRun: RunRecord) {
    setQueuedEvalRuns((current) => dedupeRuns([updatedRun, ...current.filter((run) => run.run_id !== updatedRun.run_id)]));
  }

  function assistedSummaryText(): string | null {
    const responseText = assistedSummaryRun?.metadata_json?.response_text;
    const responsePreview = assistedSummaryRun?.metadata_json?.response_preview;
    if (typeof responseText === "string" && responseText.trim()) {
      return responseText;
    }
    if (typeof responsePreview === "string" && responsePreview.trim()) {
      return responsePreview;
    }
    return null;
  }

  async function handleCreateSuite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const suite = await createEvalSuite(suiteForm);
      upsertSuite(suite);
      setSuiteForm({ name: "", description: "" });
      setCaseForm((current) => ({ ...current, suite_id: suite.suite_id }));
      setAttemptForm((current) => ({ ...current, suite_id: suite.suite_id }));
      setScheduleForm((current) => ({ ...current, suite_id: suite.suite_id }));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval suite creation failed.");
    }
  }

  async function handleInstallStarterSuite() {
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const suite = await installStarterEvalSuite();
      upsertSuite(suite);
      setCaseForm((current) => ({ ...current, suite_id: suite.suite_id }));
      setAttemptForm((current) => ({ ...current, suite_id: suite.suite_id }));
      setScheduleForm((current) => ({ ...current, suite_id: suite.suite_id }));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Starter eval suite installation failed.");
    }
  }

  async function handleQueueEvalAttempt(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMutationState("saving");
    setErrorMessage(null);

    const placement = placementOptions.find((option) => option.key === attemptForm.placement_key);
    if (!placement) {
      setMutationState("error");
      setErrorMessage("Select an available model placement before queueing an eval attempt.");
      return;
    }

    try {
      const result = await queueEvalAttempt(attemptForm.suite_id, {
        model_name: placement.model_name,
        node_id: placement.node_id,
      });
      setAttemptResult(result);
      setQueuedEvalRuns((current) => dedupeRuns([...result.runs, ...current]));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval attempt queueing failed.");
    }
  }

  async function handleExecuteEvalRun(runId: string) {
    setExecutionStateByRun((current) => ({ ...current, [runId]: "running" }));
    setErrorMessage(null);

    try {
      const run = await executeEvalRun(runId);
      upsertEvalRun(run);
      const history = await fetchEvalScoreHistory(activeEvalQuery);
      setScoreHistory(history);
      setExecutionStateByRun((current) => ({ ...current, [runId]: "idle" }));
    } catch (error) {
      setExecutionStateByRun((current) => ({ ...current, [runId]: "error" }));
      setErrorMessage(error instanceof Error ? error.message : "Eval run execution failed.");
    }
  }

  async function handleCreateSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMutationState("saving");
    setErrorMessage(null);

    const placement = placementOptions.find((option) => option.key === scheduleForm.placement_key);
    if (!placement) {
      setMutationState("error");
      setErrorMessage("Select an available model placement before creating an eval schedule.");
      return;
    }

    const intervalMinutes = Number.parseInt(scheduleForm.interval_minutes, 10);
    if (!Number.isFinite(intervalMinutes) || intervalMinutes < 1) {
      setMutationState("error");
      setErrorMessage("Schedule interval must be at least 1 minute.");
      return;
    }

    try {
      const schedule = await createEvalSchedule({
        suite_id: scheduleForm.suite_id,
        model_name: placement.model_name,
        node_id: placement.node_id,
        interval_minutes: intervalMinutes,
        enabled: true,
        auto_execute: scheduleForm.auto_execute,
      });
      setSchedules((current) => [schedule, ...current.filter((item) => item.schedule_id !== schedule.schedule_id)]);
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval schedule creation failed.");
    }
  }

  async function handleCreateAssistedSummary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const placement = placementOptions.find((option) => option.key === summaryForm.placement_key);
    if (!placement) {
      setMutationState("error");
      setErrorMessage("Select an available model placement before generating an assisted summary.");
      return;
    }
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const run = await createEvalAssistedSummary({
        model_name: placement.model_name,
        node_id: placement.node_id,
        filter_model_name: activeEvalQuery.model_name,
        filter_node_id: activeEvalQuery.node_id,
        window_days: activeEvalQuery.window_days,
        flakiness_min_rate: activeEvalQuery.flakiness_min_rate,
        failure_cluster_min_count: activeEvalQuery.failure_cluster_min_count,
      });
      setAssistedSummaryRun(run);
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval assisted summary failed.");
    }
  }

  function handleApplyEvalControls(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = buildEvalHistoryQuery(evalControls);
    if (!isValidEvalHistoryQuery(query)) {
      setMutationState("error");
      setErrorMessage("Eval intelligence controls must use a valid window, flakiness rate, and cluster minimum.");
      return;
    }
    setMutationState("idle");
    setErrorMessage(null);
    setActiveEvalQuery(query);
  }

  async function handleSaveEvalPreset() {
    const query = buildEvalHistoryQuery(evalControls);
    if (!isValidEvalHistoryQuery(query)) {
      setMutationState("error");
      setErrorMessage("Fix the Eval Intelligence controls before saving a preset.");
      return;
    }
    const name = window.prompt("Preset name", "Focused eval review");
    if (name === null) {
      return;
    }
    const trimmedName = name.trim();
    if (!trimmedName) {
      setMutationState("error");
      setErrorMessage("Preset name cannot be empty.");
      return;
    }
    const draftPreset = {
      id: selectedPresetId || undefined,
      name: trimmedName,
      controls: { ...evalControls },
    };
    try {
      const preset = await saveEvalIntelligencePreset(draftPreset);
      const nextPresets = [...evalPresets.filter((item) => item.id !== preset.id && item.name !== preset.name), preset].sort(
        (left, right) => left.name.localeCompare(right.name),
      );
      setEvalPresets(nextPresets);
      setSelectedPresetId(preset.id);
      writeEvalPresets(nextPresets);
      setMutationState("idle");
      setErrorMessage(null);
    } catch (error) {
      const fallbackPreset: EvalIntelligencePreset = {
        id: selectedPresetId || `eval-preset-${Date.now()}`,
        name: trimmedName,
        controls: { ...evalControls },
        storage: "browser-local-fallback",
      };
      const nextPresets = [
        ...evalPresets.filter((item) => item.id !== fallbackPreset.id && item.name !== fallbackPreset.name),
        fallbackPreset,
      ].sort((left, right) => left.name.localeCompare(right.name));
      setEvalPresets(nextPresets);
      setSelectedPresetId(fallbackPreset.id);
      writeEvalPresets(nextPresets);
      setMutationState("error");
      setErrorMessage(error instanceof Error ? `${error.message}; saved in browser fallback.` : "Preset saved in browser fallback.");
    }
  }

  function handleApplyEvalPreset() {
    const preset = evalPresets.find((item) => item.id === selectedPresetId);
    if (!preset) {
      setMutationState("error");
      setErrorMessage("Select a saved Eval Intelligence preset first.");
      return;
    }
    const query = buildEvalHistoryQuery(preset.controls);
    if (!isValidEvalHistoryQuery(query)) {
      setMutationState("error");
      setErrorMessage("Saved preset is no longer valid. Delete it and create a new one.");
      return;
    }
    setEvalControls(preset.controls);
    setActiveEvalQuery(query);
    setMutationState("idle");
    setErrorMessage(null);
  }

  async function handleDeleteEvalPreset() {
    const presetId = selectedPresetId;
    if (!presetId) {
      return;
    }
    const nextPresets = evalPresets.filter((item) => item.id !== presetId);
    try {
      await deleteEvalIntelligencePreset(presetId);
    } catch {
      // Browser fallback presets may not exist in managed settings yet.
    }
    setEvalPresets(nextPresets);
    setSelectedPresetId("");
    writeEvalPresets(nextPresets);
  }

  async function handleToggleSchedule(schedule: EvalScheduleRecord) {
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const updated = await updateEvalSchedule(schedule.schedule_id, { enabled: !schedule.enabled });
      setSchedules((current) =>
        current.map((item) => (item.schedule_id === updated.schedule_id ? updated : item)),
      );
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval schedule update failed.");
    }
  }

  async function handleDeleteSchedule(schedule: EvalScheduleRecord) {
    setMutationState("saving");
    setErrorMessage(null);

    try {
      await deleteEvalSchedule(schedule.schedule_id);
      setSchedules((current) => current.filter((item) => item.schedule_id !== schedule.schedule_id));
      setScheduleQueueStateById((current) => {
        const next = { ...current };
        delete next[schedule.schedule_id];
        return next;
      });
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval schedule deletion failed.");
    }
  }

  async function handleQueueScheduleNow(schedule: EvalScheduleRecord) {
    if (!schedule.enabled) {
      return;
    }

    setMutationState("saving");
    setErrorMessage(null);
    setScheduleQueueStateById((current) => ({ ...current, [schedule.schedule_id]: "queueing" }));

    try {
      const result = await queueEvalScheduleNow(schedule.schedule_id);
      setAttemptResult(result);
      setQueuedEvalRuns((current) => dedupeRuns([...result.runs, ...current]));
      if (result.schedule) {
        setSchedules((current) =>
          current.map((item) => (item.schedule_id === result.schedule?.schedule_id ? result.schedule : item)),
        );
      }
      setScheduleQueueStateById((current) => ({ ...current, [schedule.schedule_id]: "idle" }));
      setMutationState("idle");
    } catch (error) {
      setScheduleQueueStateById((current) => ({ ...current, [schedule.schedule_id]: "error" }));
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval schedule queue-now failed.");
    }
  }

  async function handleDeleteCase(suiteId: string, caseId: string) {
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const suite = await deleteEvalCase(suiteId, caseId);
      upsertSuite(suite);
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval case deletion failed.");
    }
  }

  async function handleDeleteSuite(suite: EvalSuiteRecord) {
    if (suite.case_count > 0 || suiteHasSchedule(suite.suite_id)) {
      return;
    }

    setMutationState("saving");
    setErrorMessage(null);

    try {
      await deleteEvalSuite(suite.suite_id);
      setSuites((current) => current.filter((item) => item.suite_id !== suite.suite_id));
      setCaseForm((current) => (current.suite_id === suite.suite_id ? { ...current, suite_id: "" } : current));
      setAttemptForm((current) => (current.suite_id === suite.suite_id ? { ...current, suite_id: "" } : current));
      setScheduleForm((current) => (current.suite_id === suite.suite_id ? { ...current, suite_id: "" } : current));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval suite deletion failed.");
    }
  }

  async function handleEditSuite(suite: EvalSuiteRecord) {
    const name = window.prompt("Suite name", suite.name);
    if (name === null) {
      return;
    }
    const description = window.prompt("Suite description", suite.description) ?? suite.description;
    setMutationState("saving");
    setErrorMessage(null);

    try {
      upsertSuite(await updateEvalSuite(suite.suite_id, { name, description }));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval suite update failed.");
    }
  }

  async function handleDuplicateSuite(suite: EvalSuiteRecord) {
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const duplicate = await duplicateEvalSuite(suite.suite_id);
      upsertSuite(duplicate);
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval suite duplication failed.");
    }
  }

  async function handleImportSuite() {
    const rawPayload = window.prompt("Paste exported suite JSON");
    if (rawPayload === null) {
      return;
    }
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const payload = JSON.parse(rawPayload) as Record<string, unknown>;
      const suite = await importEvalSuite(payload);
      upsertSuite(suite);
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval suite import failed.");
    }
  }

  async function handleDuplicateCase(suiteId: string, evalCase: EvalSuiteRecord["cases"][number]) {
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const suite = await duplicateEvalCase(suiteId, evalCase.case_id);
      upsertSuite(suite);
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval case duplication failed.");
    }
  }

  async function handleEditCase(suiteId: string, evalCase: EvalSuiteRecord["cases"][number]) {
    const name = window.prompt("Case name", evalCase.name);
    if (name === null) {
      return;
    }
    const prompt = window.prompt("Case prompt", evalCase.prompt);
    if (prompt === null) {
      return;
    }
    const expectedJsonRaw = window.prompt("Expected JSON", JSON.stringify(evalCase.expected_json, null, 2));
    if (expectedJsonRaw === null) {
      return;
    }
    const scoreConfigRaw = window.prompt("Score config JSON", JSON.stringify(evalCase.score_config_json ?? {}, null, 2));
    if (scoreConfigRaw === null) {
      return;
    }
    const scoreType = window.prompt("Score type", evalCase.score_type) ?? evalCase.score_type;
    const rawSortOrder = window.prompt("Sort order", String(evalCase.sort_order));
    if (rawSortOrder === null) {
      return;
    }
    const sortOrder = Number.parseInt(rawSortOrder, 10);
    if (!Number.isFinite(sortOrder) || sortOrder < 0) {
      setMutationState("error");
      setErrorMessage("Case sort order must be zero or greater.");
      return;
    }

    try {
      const expected_json = JSON.parse(expectedJsonRaw) as Record<string, unknown>;
      const score_config_json = JSON.parse(scoreConfigRaw) as Record<string, unknown>;
      setMutationState("saving");
      setErrorMessage(null);
      upsertSuite(
        await updateEvalCase(suiteId, evalCase.case_id, {
          name,
          prompt,
          expected_json,
          score_type: scoreType,
          score_config_json,
          sort_order: sortOrder,
        }),
      );
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval case update failed.");
    }
  }

  async function handleEditSchedule(schedule: EvalScheduleRecord) {
    const rawInterval = window.prompt("Interval minutes", String(schedule.interval_minutes));
    if (rawInterval === null) {
      return;
    }
    const interval = Number.parseInt(rawInterval, 10);
    if (!Number.isFinite(interval) || interval < 1) {
      setMutationState("error");
      setErrorMessage("Schedule interval must be at least 1 minute.");
      return;
    }
    const currentPlacementKey = `${schedule.model_name}::${schedule.node_id}`;
    const rawPlacementKey = window.prompt("Placement key as model::node", currentPlacementKey);
    if (rawPlacementKey === null) {
      return;
    }
    const placement = placementOptions.find((option) => option.key === rawPlacementKey);
    if (!placement) {
      setMutationState("error");
      setErrorMessage("Schedule target must match an available model placement.");
      return;
    }
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const updated = await updateEvalSchedule(schedule.schedule_id, {
        interval_minutes: interval,
        model_name: placement.model_name,
        node_id: placement.node_id,
        auto_execute: !schedule.auto_execute,
      });
      setSchedules((current) => current.map((item) => (item.schedule_id === updated.schedule_id ? updated : item)));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval schedule update failed.");
    }
  }

  async function handleExecuteQueuedAttempt() {
    if (!attemptResult) {
      return;
    }
    setMutationState("saving");
    setErrorMessage(null);

    try {
      const result = await executeEvalAttemptBatch(attemptResult.attempt_id);
      setQueuedEvalRuns((current) => dedupeRuns([...result.runs, ...current]));
      setScoreHistory(await fetchEvalScoreHistory(activeEvalQuery));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval attempt batch execution failed.");
    }
  }

  async function handleCreateBaseline(run: EvalScoreRunRecord) {
    const matchingRows = scoreHistory?.recent_runs.filter(
      (item) =>
        item.suite_id === run.suite_id && item.model_name === run.model_name && item.node_id === run.node_id,
    ) ?? [run];
    const passRate =
      matchingRows.length > 0
        ? matchingRows.filter((item) => item.passed).length / matchingRows.length
        : run.passed
          ? 1
          : 0;
    const rawMinimum = window.prompt("Minimum pass rate for this baseline", String(passRate));
    if (rawMinimum === null) {
      return;
    }
    const minimumPassRate = Number.parseFloat(rawMinimum);
    if (!Number.isFinite(minimumPassRate) || minimumPassRate < 0 || minimumPassRate > 1) {
      setMutationState("error");
      setErrorMessage("Baseline pass rate must be between 0 and 1.");
      return;
    }
    setMutationState("saving");
    setErrorMessage(null);
    try {
      await createEvalBaseline({
        suite_id: run.suite_id,
        model_name: run.model_name,
        node_id: run.node_id,
        minimum_pass_rate: minimumPassRate,
      });
      setScoreHistory(await fetchEvalScoreHistory(activeEvalQuery));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval baseline creation failed.");
    }
  }

  async function handleCreateCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMutationState("saving");
    setErrorMessage(null);

    let expectedJson: Record<string, unknown>;
    let scoreConfigJson: Record<string, unknown>;
    try {
      expectedJson = JSON.parse(caseForm.expected_json) as Record<string, unknown>;
    } catch {
      setMutationState("error");
      setErrorMessage("Expected JSON must be valid JSON.");
      return;
    }
    try {
      scoreConfigJson = JSON.parse(caseForm.score_config_json) as Record<string, unknown>;
    } catch {
      setMutationState("error");
      setErrorMessage("Score config must be valid JSON.");
      return;
    }

    try {
      const suite = await createEvalCase(caseForm.suite_id, {
        name: caseForm.name,
        prompt: caseForm.prompt,
        expected_json: expectedJson,
        score_type: caseForm.score_type,
        score_config_json: scoreConfigJson,
      });
      upsertSuite(suite);
      setCaseForm((current) => ({ ...current, name: "", prompt: "", expected_json: "{}", score_config_json: "{}" }));
      setMutationState("idle");
    } catch (error) {
      setMutationState("error");
      setErrorMessage(error instanceof Error ? error.message : "Eval case creation failed.");
    }
  }

  return (
    <section className="panel-section" aria-labelledby="evals-title">
      <header className="section-header">
        <div>
          <p className="section-kicker">Evals</p>
          <h2 id="evals-title">Measure local model behavior</h2>
        </div>
        <p className="section-copy">
          Build prompt suites, execute them on observed model placements, compare deterministic scores, schedule repeat
          checks, and export the evidence behind each result.
        </p>
        <div className="button-row">
          <button
            type="button"
            className="text-action-button"
            disabled={mutationState === "saving" || starterSuiteInstalled}
            onClick={() => void handleInstallStarterSuite()}
          >
            {starterSuiteInstalled ? "Starter suite installed" : "Install starter suite"}
          </button>
          <a className="text-action-button" href={buildEvalHistoryExportUrl("csv", activeEvalQuery)}>
            Export CSV
          </a>
          <a className="text-action-button" href={buildEvalHistoryExportUrl("json", activeEvalQuery)}>
            Export JSON
          </a>
          <button
            type="button"
            className="text-action-button"
            disabled={mutationState === "saving"}
            onClick={() => void handleImportSuite()}
          >
            Import suite JSON
          </button>
        </div>
      </header>

      <div className="metric-strip">
        <article className="metric-card">
          <p className="info-kicker">Suites</p>
          <strong>{suites.length}</strong>
        </article>
        <article className="metric-card">
          <p className="info-kicker">Cases</p>
          <strong>{totalCases}</strong>
        </article>
        <article className="metric-card">
          <p className="info-kicker">Execution</p>
          <strong>{activeEvalRunCount} active</strong>
        </article>
        <article className="metric-card">
          <p className="info-kicker">Scored</p>
          <strong>{scoreHistory?.total_runs ?? 0}</strong>
        </article>
      </div>

      <nav className="eval-jump-nav" aria-label="Eval Lab sections">
        <span>Jump to</span>
        <a href="#eval-intelligence">Intelligence</a>
        <a href="#eval-authoring">Author and run</a>
        <a href="#eval-results">Results</a>
      </nav>

      {errorMessage ? <p className="inline-warning" role="alert">{errorMessage}</p> : null}
      {scoreHistory?.operator_summary ? (
        <div className="intelligence-brief">
          <span
            className={`status-chip is-${
              scoreHistory.operator_summary.regression_count > 0 ||
              scoreHistory.operator_summary.failure_cluster_count > 0
                ? "queued"
                : "success"
            }`}
          >
            intelligence
          </span>
          <div>
            <strong>{scoreHistory.operator_summary.headline}</strong>
            <p>
              Deterministic signals first. Optional assisted summaries can explain patterns, but raw score data remains
              the source of truth.
            </p>
          </div>
        </div>
      ) : null}

      <form id="eval-intelligence" className="eval-control-panel" onSubmit={handleApplyEvalControls}>
        <div>
          <p className="section-kicker">Chart controls</p>
          <h3>Eval intelligence window</h3>
          <p>
            Tune the pass-rate window, placement scope, flakiness sensitivity, and failure-cluster size used by charts,
            exports, and assisted summaries.
          </p>
        </div>
        <div className="eval-control-grid">
          <label>
            Time window
            <select
              name="eval-window-days"
              autoComplete="off"
              value={evalControls.window_days}
              onChange={(event) => setEvalControls((current) => ({ ...current, window_days: event.target.value }))}
            >
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
              <option value="365">Last 365 days</option>
            </select>
          </label>
          <label>
            Placement filter
            <select
              name="eval-placement-filter"
              autoComplete="off"
              value={evalControls.placement_key}
              onChange={(event) => setEvalControls((current) => ({ ...current, placement_key: event.target.value }))}
            >
              <option value="">All model placements</option>
              {placementOptions.map((placement) => (
                <option key={placement.key} value={placement.key}>
                  {placement.model_name} / {placement.node_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Flakiness sensitivity
            <select
              name="eval-flakiness-sensitivity"
              autoComplete="off"
              value={evalControls.flakiness_min_rate}
              onChange={(event) =>
                setEvalControls((current) => ({ ...current, flakiness_min_rate: event.target.value }))
              }
            >
              <option value="0.1">Sensitive: 10%</option>
              <option value="0.2">Balanced: 20%</option>
              <option value="0.35">Conservative: 35%</option>
            </select>
          </label>
          <label>
            Failure cluster minimum
            <input
              name="eval-failure-cluster-minimum"
              autoComplete="off"
              type="number"
              min="1"
              max="100"
              value={evalControls.failure_cluster_min_count}
              onChange={(event) =>
                setEvalControls((current) => ({ ...current, failure_cluster_min_count: event.target.value }))
              }
            />
          </label>
        </div>
        <div className="eval-preset-row">
          <label>
            Saved preset
            <select
              name="eval-saved-preset"
              autoComplete="off"
              value={selectedPresetId}
              onChange={(event) => setSelectedPresetId(event.target.value)}
              aria-label="Saved preset"
            >
              <option value="">No preset selected</option>
              {evalPresets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.name}
                </option>
              ))}
            </select>
          </label>
          <div className="button-row">
            <button type="button" className="text-action-button" onClick={handleSaveEvalPreset}>
              Save preset
            </button>
            <button
              type="button"
              className="text-action-button"
              disabled={!selectedPresetId}
              onClick={handleApplyEvalPreset}
            >
              Apply preset
            </button>
            <button
              type="button"
              className="text-action-button is-danger"
              disabled={!selectedPresetId}
              onClick={handleDeleteEvalPreset}
            >
              Delete preset
            </button>
          </div>
        </div>
        <div className="eval-control-footer">
          <div className="state-token-row">
            <span className="state-token">
              {scoreHistory?.filters?.window_days ?? activeEvalQuery.window_days}d window
            </span>
            <span className="state-token">
              {scoreHistory?.filters?.model_name && scoreHistory.filters.node_id
                ? `${scoreHistory.filters.model_name} / ${scoreHistory.filters.node_id}`
                : "all placements"}
            </span>
            <span className="state-token">
              flaky {" >= "} {Math.round((scoreHistory?.thresholds?.flakiness_min_rate ?? 0.2) * 100)}%
            </span>
            <span className="state-token">
              clusters {" >= "} {scoreHistory?.thresholds?.failure_cluster_min_count ?? 2}
            </span>
          </div>
          <button type="submit" className="action-button" disabled={mutationState === "saving"}>
            Apply controls
          </button>
        </div>
      </form>

      <div id="eval-authoring" className="eval-form-grid">
        <form className="eval-form is-setup" autoComplete="off" onSubmit={handleCreateSuite}>
          <div>
            <p className="info-kicker">Prompt suite</p>
            <h3>Create suite</h3>
          </div>
          <label>
            <span>Name</span>
            <input
              name="eval-suite-name"
              autoComplete="off"
              required
              value={suiteForm.name}
              onChange={(event) => setSuiteForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="e.g., Reasoning smoke test…"
            />
          </label>
          <label>
            <span>Description</span>
            <textarea
              name="eval-suite-description"
              autoComplete="off"
              value={suiteForm.description}
              onChange={(event) => setSuiteForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="e.g., Measures concise reasoning output…"
            />
          </label>
          <button type="submit" className="action-button" disabled={mutationState === "saving"}>
            {mutationState === "saving" ? "Saving…" : "Create suite"}
          </button>
        </form>

        <form className="eval-form is-setup" autoComplete="off" onSubmit={handleCreateCase}>
          <div>
            <p className="info-kicker">Prompt case</p>
            <h3>Add case</h3>
          </div>
          <label>
            <span>Suite</span>
            <select
              name="eval-case-suite"
              autoComplete="off"
              required
              value={caseForm.suite_id}
              onChange={(event) => setCaseForm((current) => ({ ...current, suite_id: event.target.value }))}
              disabled={suites.length === 0}
            >
              <option value="">Select suite</option>
              {suites.map((suite) => (
                <option key={suite.suite_id} value={suite.suite_id}>
                  {suite.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Case name</span>
            <input
              name="eval-case-name"
              autoComplete="off"
              required
              value={caseForm.name}
              onChange={(event) => setCaseForm((current) => ({ ...current, name: event.target.value }))}
              placeholder="e.g., JSON format check…"
              disabled={suites.length === 0}
            />
          </label>
          <label>
            <span>Prompt</span>
            <textarea
              name="eval-case-prompt"
              autoComplete="off"
              required
              value={caseForm.prompt}
              onChange={(event) => setCaseForm((current) => ({ ...current, prompt: event.target.value }))}
              placeholder="e.g., Produce a concise answer as JSON…"
              disabled={suites.length === 0}
            />
          </label>
          <label>
            <span>Expected JSON</span>
            <textarea
              name="eval-case-expected-json"
              autoComplete="off"
              spellCheck={false}
              className="code-textarea"
              value={caseForm.expected_json}
              onChange={(event) => setCaseForm((current) => ({ ...current, expected_json: event.target.value }))}
              disabled={suites.length === 0}
            />
          </label>
          <label>
            <span>Score type</span>
            <select
              name="eval-case-score-type"
              autoComplete="off"
              value={caseForm.score_type}
              onChange={(event) => handleScoreTypeChange(event.target.value)}
              disabled={suites.length === 0}
            >
              <option value="json_subset">JSON subset</option>
              <option value="exact_match">Exact match</option>
              <option value="contains">Contains</option>
              <option value="regex">Regex</option>
              <option value="numeric_threshold">Numeric threshold</option>
              <option value="json_schema">JSON schema</option>
              <option value="llm_judge">LLM judge</option>
            </select>
          </label>
          {caseForm.score_type === "llm_judge" ? (
            <div className="judge-config-panel">
              <div className="judge-config-header">
                <div>
                  <p className="info-kicker">Guarded scorer</p>
                  <h4>LLM Judge Config</h4>
                  <p>
                    Replace brittle raw JSON editing with explicit judge controls. Vantage still writes the exact
                    config below for auditability.
                  </p>
                </div>
                <div className="state-token-row">
                  <span className="state-token is-accent">Guarded Judge</span>
                  <span className="state-token is-warning">Fails Closed</span>
                </div>
              </div>

              <div className="judge-config-grid">
                <label>
                  <span>Judge placement</span>
                  <select
                    name="eval-judge-placement"
                    autoComplete="off"
                    value={judgePlacementKey}
                    onChange={(event) => {
                      const [modelName, nodeId] = event.target.value ? event.target.value.split("::") : ["", ""];
                      updateJudgeConfig({ judge_model_name: modelName || "", judge_node_id: nodeId || "" });
                    }}
                    disabled={placementOptions.length === 0}
                  >
                    <option value="">Select judge model on node</option>
                    {placementOptions.map((placement) => (
                      <option key={placement.key} value={placement.key}>
                        {placement.model_name} on {placement.node_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Pass threshold</span>
                  <div className="judge-threshold-control">
                    <input
                      name="eval-judge-threshold-range"
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      value={judgeConfig.pass_threshold}
                      onChange={(event) => updateJudgeConfig({ pass_threshold: Number(event.target.value) })}
                      disabled={suites.length === 0}
                    />
                    <input
                      name="eval-judge-threshold"
                      autoComplete="off"
                      type="number"
                      min="0"
                      max="1"
                      step="0.05"
                      value={judgeConfig.pass_threshold}
                      onChange={(event) => updateJudgeConfig({ pass_threshold: Number(event.target.value) })}
                      disabled={suites.length === 0}
                    />
                  </div>
                </label>
                <label>
                  <span>Max context chars</span>
                  <input
                    name="eval-judge-max-context"
                    autoComplete="off"
                    type="number"
                    min="500"
                    max="12000"
                    step="500"
                    value={judgeConfig.max_context_chars}
                    onChange={(event) => updateJudgeConfig({ max_context_chars: Number(event.target.value) })}
                    disabled={suites.length === 0}
                  />
                </label>
              </div>

              <div className="judge-workbench">
                <label className="judge-rubric-field">
                  <span>Evaluation rubric</span>
                  <textarea
                    name="eval-judge-rubric"
                    autoComplete="off"
                    value={judgeConfig.rubric}
                    onChange={(event) => updateJudgeConfig({ rubric: event.target.value })}
                    disabled={suites.length === 0}
                    placeholder="e.g., Pass only when the response is accurate, concise, and safe…"
                  />
                </label>
                <aside className="judge-contract-preview" aria-label="LLM judge safety contract">
                  <div>
                    <p className="info-kicker">Safety contract</p>
                    <ul>
                      <li>Prompt and response are treated as untrusted data.</li>
                      <li>Judge must return JSON only.</li>
                      <li>Context is bounded before judging.</li>
                      <li>Decision is stored in Run metadata.</li>
                    </ul>
                  </div>
                  <pre>{`{
  "passed": boolean,
  "score": 0.0-1.0,
  "reason": "short string",
  "evidence": ["short strings"]
}`}</pre>
                </aside>
              </div>

              <div className={`judge-config-status ${judgeConfigIsComplete ? "is-ready" : "is-incomplete"}`}>
                <span>{judgeConfigIsComplete ? "Judge config ready" : "Judge config incomplete"}</span>
                <span>
                  {judgeConfigIsComplete
                    ? "The generated JSON below can be saved with this prompt case."
                    : "Select a judge placement and keep a non-empty rubric before saving."}
                </span>
              </div>
            </div>
          ) : null}
          <label>
            <span>Score config JSON</span>
            <textarea
              name="eval-case-score-config"
              autoComplete="off"
              spellCheck={false}
              className="code-textarea"
              value={caseForm.score_config_json}
              onChange={(event) =>
                setCaseForm((current) => ({ ...current, score_config_json: event.target.value }))
              }
              disabled={suites.length === 0}
            />
          </label>
          <button type="submit" className="action-button" disabled={mutationState === "saving" || suites.length === 0}>
            {mutationState === "saving" ? "Saving…" : "Add case"}
          </button>
        </form>

        <form className="eval-form is-execution" autoComplete="off" onSubmit={handleQueueEvalAttempt}>
          <div>
            <p className="info-kicker">Eval attempt</p>
            <h3>Queue attempt</h3>
          </div>
          <label>
            <span>Suite</span>
            <select
              name="eval-attempt-suite"
              autoComplete="off"
              required
              value={attemptForm.suite_id}
              onChange={(event) => setAttemptForm((current) => ({ ...current, suite_id: event.target.value }))}
              disabled={suites.length === 0}
            >
              <option value="">Select suite</option>
              {suites.map((suite) => (
                <option key={suite.suite_id} value={suite.suite_id}>
                  {suite.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Model placement</span>
            <select
              name="eval-attempt-placement"
              autoComplete="off"
              required
              value={attemptForm.placement_key}
              onChange={(event) => setAttemptForm((current) => ({ ...current, placement_key: event.target.value }))}
              disabled={placementOptions.length === 0}
            >
              <option value="">Select model on node</option>
              {placementOptions.map((placement) => (
                <option key={placement.key} value={placement.key}>
                  {placement.model_name} on {placement.node_id}
                </option>
              ))}
            </select>
          </label>
          <p className="action-copy">
            Queueing creates durable Run records for every case. Review the queue, then execute and score each attempt
            against the selected local model placement.
          </p>
          <button
            type="submit"
            className="action-button"
            disabled={mutationState === "saving" || suites.length === 0 || placementOptions.length === 0}
          >
            {mutationState === "saving" ? "Queueing…" : "Queue eval attempt"}
          </button>
          {attemptResult ? (
            <div className="inline-result">
              <span className="status-chip is-queued">queued</span>
              <span className="action-copy">
                {attemptResult.run_count} run{attemptResult.run_count === 1 ? "" : "s"} queued for{" "}
                {attemptResult.model_name} on {attemptResult.node_id}.
              </span>
              <button
                type="button"
                className="text-action-button"
                disabled={mutationState === "saving"}
                onClick={() => void handleExecuteQueuedAttempt()}
              >
                Execute queued attempt
              </button>
            </div>
          ) : null}
        </form>

        <form className="eval-form is-execution" autoComplete="off" onSubmit={handleCreateSchedule}>
          <div>
            <p className="info-kicker">Recurring eval</p>
            <h3>Create schedule</h3>
          </div>
          <label>
            <span>Schedule suite</span>
            <select
              name="eval-schedule-suite"
              autoComplete="off"
              required
              value={scheduleForm.suite_id}
              onChange={(event) => setScheduleForm((current) => ({ ...current, suite_id: event.target.value }))}
              disabled={suites.length === 0}
            >
              <option value="">Select suite</option>
              {suites.map((suite) => (
                <option key={suite.suite_id} value={suite.suite_id}>
                  {suite.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Schedule placement</span>
            <select
              name="eval-schedule-placement"
              autoComplete="off"
              required
              value={scheduleForm.placement_key}
              onChange={(event) => setScheduleForm((current) => ({ ...current, placement_key: event.target.value }))}
              disabled={placementOptions.length === 0}
            >
              <option value="">Select model on node</option>
              {placementOptions.map((placement) => (
                <option key={placement.key} value={placement.key}>
                  {placement.model_name} on {placement.node_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span>Interval minutes</span>
            <input
              name="eval-schedule-interval"
              autoComplete="off"
              required
              type="number"
              min="1"
              value={scheduleForm.interval_minutes}
              onChange={(event) =>
                setScheduleForm((current) => ({ ...current, interval_minutes: event.target.value }))
              }
              disabled={suites.length === 0 || placementOptions.length === 0}
            />
          </label>
          <label className="inline-check">
            <input
              name="eval-schedule-auto-execute"
              type="checkbox"
              checked={scheduleForm.auto_execute}
              onChange={(event) =>
                setScheduleForm((current) => ({ ...current, auto_execute: event.target.checked }))
              }
              disabled={suites.length === 0 || placementOptions.length === 0}
            />
            <span>Auto-execute when due</span>
          </label>
          <p className="action-copy">
            Queue-only is safest. Auto-execute immediately runs and scores each due eval case.
          </p>
          <button
            type="submit"
            className="action-button"
            disabled={mutationState === "saving" || suites.length === 0 || placementOptions.length === 0}
          >
            {mutationState === "saving" ? "Creating…" : "Create schedule"}
          </button>
        </form>

        <form className="eval-form is-accented" autoComplete="off" onSubmit={handleCreateAssistedSummary}>
          <div>
            <p className="info-kicker">Assisted summary</p>
            <h3>Ask local model</h3>
          </div>
          <label>
            <span>Summary model placement</span>
            <select
              name="eval-summary-placement"
              autoComplete="off"
              required
              value={summaryForm.placement_key}
              onChange={(event) => setSummaryForm({ placement_key: event.target.value })}
              disabled={placementOptions.length === 0}
            >
              <option value="">Select model on node</option>
              {placementOptions.map((placement) => (
                <option key={placement.key} value={placement.key}>
                  {placement.model_name} on {placement.node_id}
                </option>
              ))}
            </select>
          </label>
          <p className="action-copy">
            Manual only. Vantage sends a compact eval snapshot to the selected local model and stores the result as an
            auditable Run.
          </p>
          <button
            type="submit"
            className="action-button"
            disabled={mutationState === "saving" || placementOptions.length === 0 || !scoreHistory?.total_runs}
          >
            {mutationState === "saving" ? "Generating…" : "Generate summary"}
          </button>
        </form>
      </div>

      {assistedSummaryRun ? (
        <div className="assisted-summary-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Operator assistance</p>
              <h3>Local model summary</h3>
            </div>
            <span className={`status-chip is-${assistedSummaryRun.status}`}>
              {assistedSummaryRun.status}
            </span>
          </div>
          <pre>{assistedSummaryText() ?? "No assisted summary text was returned. Check the Run metadata."}</pre>
          <p className="action-copy">
            Run ID: <span className="mono-value">{assistedSummaryRun.run_id}</span>
          </p>
        </div>
      ) : null}

      <div id="eval-results" className="eval-results-divider" aria-hidden="true">
        <span>Observed results</span>
      </div>

      {schedules.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Automation</p>
              <h3>Recurring eval schedules</h3>
            </div>
            <p className="section-copy">
              Schedules create queued eval attempts on a timer while keeping execution visible in the Runs ledger.
            </p>
          </div>
          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Suite</th>
                  <th scope="col">Target</th>
                  <th scope="col">Interval</th>
                  <th scope="col">Mode</th>
                  <th scope="col">Next</th>
                  <th scope="col">Status</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((schedule) => (
                  <tr key={schedule.schedule_id}>
                    <td>{schedule.suite_name ?? schedule.suite_id}</td>
                    <td>
                      {schedule.model_name} / {schedule.node_id}
                    </td>
                    <td>Every {schedule.interval_minutes} min</td>
                    <td>{schedule.auto_execute ? "Auto-execute" : "Queue only"}</td>
                    <td>
                      <div className="placement-stack">
                        <span>Next queue: {formatTimestamp(schedule.next_run_at)}</span>
                        {schedule.last_queued_at ? (
                          <span className="meta-chip">Last queued: {formatTimestamp(schedule.last_queued_at)}</span>
                        ) : null}
                      </div>
                    </td>
                    <td>
                      <span className={`status-chip is-${schedule.enabled ? "success" : "queued"}`}>
                        {schedule.enabled ? "enabled" : "paused"}
                      </span>
                    </td>
                    <td>
                      <div className="button-row">
                        <button
                          type="button"
                          className="text-action-button"
                          disabled={mutationState === "saving"}
                          onClick={() => void handleToggleSchedule(schedule)}
                        >
                          {schedule.enabled ? "Pause" : "Resume"}
                        </button>
                        <button
                          type="button"
                          className="text-action-button"
                          disabled={mutationState === "saving"}
                          onClick={() => void handleEditSchedule(schedule)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="text-action-button"
                          disabled={
                            !schedule.enabled ||
                            mutationState === "saving" ||
                            scheduleQueueStateById[schedule.schedule_id] === "queueing"
                          }
                          onClick={() => void handleQueueScheduleNow(schedule)}
                        >
                          {scheduleQueueStateById[schedule.schedule_id] === "queueing" ? "Queueing…" : "Queue now"}
                        </button>
                        <button
                          type="button"
                          className="text-action-button is-danger"
                          disabled={mutationState === "saving"}
                          aria-label={`Delete schedule ${schedule.suite_name ?? schedule.suite_id}`}
                          onClick={() => void handleDeleteSchedule(schedule)}
                        >
                          Delete
                        </button>
                      </div>
                      {scheduleQueueStateById[schedule.schedule_id] === "error" ? (
                        <p className="action-copy is-error">Queue now failed. Check the API response.</p>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {scoreHistory?.schedule_health && scoreHistory.schedule_health.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Schedule health</p>
              <h3>Recent schedule outcomes</h3>
            </div>
            <p className="section-copy">
              Schedule health is derived from the latest scheduler metadata and warning-producing failures.
            </p>
          </div>
          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Target</th>
                  <th scope="col">Mode</th>
                  <th scope="col">Last Runs</th>
                  <th scope="col">Health</th>
                </tr>
              </thead>
              <tbody>
                {scoreHistory.schedule_health.map((schedule) => (
                  <tr key={schedule.schedule_id}>
                    <td>
                      {schedule.model_name} / {schedule.node_id}
                    </td>
                    <td>{schedule.auto_execute ? "Auto-execute" : "Queue only"}</td>
                    <td>
                      {schedule.last_runs_executed} executed / {schedule.last_runs_failed} failed
                    </td>
                    <td>
                      <span className={`status-chip is-${schedule.status === "warning" ? "queued" : "success"}`}>
                        {schedule.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {recentEvalRuns.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Eval runs</p>
              <h3>Recent attempts</h3>
            </div>
            <p className="section-copy">Queued and completed attempts share the same durable Runs ledger as actions and checks.</p>
          </div>
          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Run</th>
                  <th scope="col">Status</th>
                  <th scope="col">Target</th>
                  <th scope="col">Started</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {recentEvalRuns.map((run) => (
                  <tr key={run.run_id}>
                    <td>{run.summary}</td>
                    <td>
                      <span className={`status-chip is-${run.status}`}>{run.status}</span>
                    </td>
                    <td>
                      {run.model_name ?? "Unknown model"} / {run.node_id ?? "unknown node"}
                    </td>
                    <td>{formatTimestamp(run.started_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="action-button"
                        disabled={executionStateByRun[run.run_id] === "running" || run.status === "running"}
                        onClick={() => void handleExecuteEvalRun(run.run_id)}
                      >
                        {executionStateByRun[run.run_id] === "running" || run.status === "running"
                          ? "Executing…"
                          : run.status === "queued"
                            ? "Execute"
                            : "Re-run"}
                      </button>
                      {executionStateByRun[run.run_id] === "error" ? (
                        <p className="action-copy is-error">Execution failed. Check the run details.</p>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {scoreHistory && scoreHistory.total_runs > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Score history</p>
              <h3>Placement comparison</h3>
            </div>
            <p className="section-copy">
              Pass rates are aggregated from executed eval Run records. Higher confidence comes from repeated cases,
              not a single green result.
            </p>
          </div>
          <div className="score-grid">
            {scoreHistory.placements.slice(0, 6).map((placement) => (
              <article
                key={`${placement.model_name}-${placement.node_id}`}
                className="score-card"
                aria-label={`Score history for ${placement.model_name} on ${placement.node_id}`}
              >
                <p className="info-kicker">{placement.node_id}</p>
                <h4>{placement.model_name}</h4>
                <strong>{Math.round(placement.pass_rate * 100)}%</strong>
                <div className="score-meter" aria-hidden="true">
                  <span style={{ width: `${Math.round(placement.pass_rate * 100)}%` }} />
                </div>
                <p>
                  {placement.passed_count} passed / {placement.failed_count} failed across {placement.run_count} run
                  {placement.run_count === 1 ? "" : "s"}
                </p>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {scoreHistory?.regressions && scoreHistory.regressions.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Regression alerts</p>
              <h3>Baseline misses</h3>
            </div>
            <p className="section-copy">
              Baselines compare recent scored runs against an operator-approved minimum pass rate.
            </p>
          </div>
          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Suite</th>
                  <th scope="col">Target</th>
                  <th scope="col">Current</th>
                  <th scope="col">Minimum</th>
                </tr>
              </thead>
              <tbody>
                {scoreHistory.regressions.map((regression) => (
                  <tr key={`${regression.suite_id}-${regression.model_name}-${regression.node_id}`}>
                    <td>{regression.suite_name}</td>
                    <td>
                      {regression.model_name} / {regression.node_id}
                    </td>
                    <td>
                      <span className="status-chip is-failed">
                        {Math.round(regression.current_pass_rate * 100)}%
                      </span>
                    </td>
                    <td>{Math.round(regression.minimum_pass_rate * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {scoreHistory?.model_reports && scoreHistory.model_reports.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Model comparison</p>
              <h3>Model report</h3>
            </div>
            <p className="section-copy">This summary rolls up scored eval runs by model name across all nodes.</p>
          </div>
          <div className="score-grid">
            {scoreHistory.model_reports.slice(0, 6).map((model) => (
              <article key={model.model_name} className="score-card">
                <p className="info-kicker">Model</p>
                <h4>{model.model_name}</h4>
                <strong>{Math.round(model.pass_rate * 100)}%</strong>
                <p>
                  {model.passed_count} passed / {model.failed_count} failed across {model.run_count} scored run
                  {model.run_count === 1 ? "" : "s"}
                </p>
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {scoreHistory?.trends && scoreHistory.trends.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Trends</p>
              <h3>Recent placement trend</h3>
            </div>
            <p className="section-copy">
              Trend rows are grouped by day, model, and node from the durable eval Run history.
            </p>
          </div>
          <div className="trend-strip" aria-label="Eval pass-rate trend chart">
            {scoreHistory.trends.slice(-10).map((trend) => (
              <article
                key={`chart-${trend.bucket}-${trend.model_name}-${trend.node_id}`}
                className={`trend-card ${trendToneClass(trend.pass_rate)}`}
              >
                <div className="trend-bar-shell" aria-hidden="true">
                  <span style={{ height: `${Math.max(6, Math.round(trend.pass_rate * 100))}%` }} />
                </div>
                <div className="trend-signal-rail" aria-hidden="true">
                  {Array.from({ length: Math.min(12, Math.max(1, trend.run_count)) }).map((_, index) => {
                    const passedBoundary = Math.round(trend.pass_rate * Math.min(12, Math.max(1, trend.run_count)));
                    return <span key={index} className={index < passedBoundary ? "is-pass" : "is-fail"} />;
                  })}
                </div>
                <div>
                  <p className="info-kicker">{trend.bucket}</p>
                  <strong>{Math.round(trend.pass_rate * 100)}%</strong>
                  <span>
                    {trend.model_name} / {trend.node_id}
                  </span>
                  <span>
                    {trend.passed_count} passed / {trend.failed_count} failed
                  </span>
                </div>
              </article>
            ))}
          </div>
          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Day</th>
                  <th scope="col">Target</th>
                  <th scope="col">Pass Rate</th>
                  <th scope="col">Avg Duration</th>
                </tr>
              </thead>
              <tbody>
                {scoreHistory.trends.slice(-8).map((trend) => (
                  <tr key={`${trend.bucket}-${trend.model_name}-${trend.node_id}`}>
                    <td>{trend.bucket}</td>
                    <td>
                      {trend.model_name} / {trend.node_id}
                    </td>
                    <td>{Math.round(trend.pass_rate * 100)}%</td>
                    <td>{trend.avg_duration_ms === null ? "Unknown" : `${trend.avg_duration_ms}ms`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {scoreHistory && scoreHistory.cases.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Case analysis</p>
              <h3>Lowest passing cases</h3>
            </div>
            <p className="section-copy">Use this to spot prompts that repeatedly fail across placements.</p>
          </div>
          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Suite</th>
                  <th scope="col">Pass Rate</th>
                  <th scope="col">Runs</th>
                </tr>
              </thead>
              <tbody>
                {[...scoreHistory.cases]
                  .sort((left, right) => left.pass_rate - right.pass_rate || right.run_count - left.run_count)
                  .slice(0, 6)
                  .map((evalCase) => (
                    <tr key={`${evalCase.suite_id}-${evalCase.case_id}`}>
                      <td>{evalCase.case_name}</td>
                      <td>{evalCase.suite_name}</td>
                      <td>{Math.round(evalCase.pass_rate * 100)}%</td>
                      <td>
                        {evalCase.passed_count} passed / {evalCase.failed_count} failed
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {scoreHistory?.flaky_cases && scoreHistory.flaky_cases.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Flakiness</p>
              <h3>Mixed-result cases</h3>
            </div>
            <p className="section-copy">These cases have both passing and failing results in the scored run history.</p>
          </div>
          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Suite</th>
                  <th scope="col">Flakiness</th>
                  <th scope="col">Runs</th>
                </tr>
              </thead>
              <tbody>
                {scoreHistory.flaky_cases.map((evalCase) => (
                  <tr key={`${evalCase.suite_id}-${evalCase.case_id}`}>
                    <td>{evalCase.case_name}</td>
                    <td>{evalCase.suite_name}</td>
                    <td>{Math.round(evalCase.flakiness_rate * 100)}%</td>
                    <td>
                      {evalCase.passed_count} passed / {evalCase.failed_count} failed
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {scoreHistory?.failure_clusters && scoreHistory.failure_clusters.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Failure clustering</p>
              <h3>Repeated failure reasons</h3>
            </div>
            <p className="section-copy">
              Clusters group failed runs by score reason and missing or mismatched fields.
            </p>
          </div>
          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Reason</th>
                  <th scope="col">Fields</th>
                  <th scope="col">Count</th>
                  <th scope="col">Example</th>
                </tr>
              </thead>
              <tbody>
                {scoreHistory.failure_clusters.map((cluster) => (
                  <tr key={`${cluster.reason}-${cluster.missing_or_mismatched.join(",")}`}>
                    <td>{cluster.reason}</td>
                    <td>
                      {cluster.missing_or_mismatched.length > 0
                        ? cluster.missing_or_mismatched.join(", ")
                        : "No field list"}
                    </td>
                    <td>{cluster.run_count}</td>
                    <td>
                      {cluster.example_suite} / {cluster.example_case}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {scoreHistory && scoreHistory.recent_runs.length > 0 ? (
        <div className="eval-attempt-panel">
          <div className="section-header is-compact">
            <div>
              <p className="section-kicker">Score details</p>
              <h3>Recent scored runs</h3>
            </div>
            <p className="section-copy">Open a run to inspect score reason, response preview, and parsed JSON.</p>
          </div>
          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Case</th>
                  <th scope="col">Target</th>
                  <th scope="col">Result</th>
                  <th scope="col">Started</th>
                  <th scope="col">Details</th>
                </tr>
              </thead>
              <tbody>
                {scoreHistory.recent_runs.slice(0, 8).map((run) => (
                  <tr key={run.run_id}>
                    <td>{run.case_name}</td>
                    <td>
                      {run.model_name} / {run.node_id}
                    </td>
                    <td>
                      <span className={`status-chip is-${run.passed ? "success" : "failed"}`}>
                        {run.passed ? "passed" : "failed"}
                      </span>
                    </td>
                    <td>{formatTimestamp(run.started_at)}</td>
                    <td>
                      <div className="button-row">
                        <button type="button" className="text-action-button" onClick={() => setSelectedScoreRun(run)}>
                          Inspect score
                        </button>
                        <button
                          type="button"
                          className="text-action-button"
                          disabled={mutationState === "saving"}
                          onClick={() => void handleCreateBaseline(run)}
                        >
                          Set baseline
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {suites.length === 0 ? (
        <div className="empty-state">
          {requestState === "loading"
            ? "Loading eval suites…"
            : "No eval suites have been defined yet. Create a prompt suite to begin a repeatable local-model comparison."}
        </div>
      ) : (
        <div className="table-shell">
          <table className="inventory-table">
            <thead>
              <tr>
                <th scope="col">Suite</th>
                <th scope="col">Description</th>
                <th scope="col">Cases</th>
                <th scope="col">Case Preview</th>
                <th scope="col">Created</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {suites.map((suite) => (
                <tr key={suite.suite_id}>
                  <td>{suite.name}</td>
                  <td>{suite.description || "No description"}</td>
                  <td>{suite.case_count}</td>
                  <td>
                    {suite.cases.length > 0 ? (
                      <div className="placement-stack">
                        {suite.cases.slice(0, 3).map((evalCase) => (
                          <span key={evalCase.case_id} className="meta-chip placement-chip">
                            <span>{evalCase.name}</span>
                            <button
                              type="button"
                              className="chip-action-button"
                              aria-label={`Edit case ${evalCase.name}`}
                              disabled={mutationState === "saving"}
                              onClick={() => void handleEditCase(suite.suite_id, evalCase)}
                            >
                              e
                            </button>
                            <button
                              type="button"
                              className="chip-action-button"
                              aria-label={`Duplicate case ${evalCase.name}`}
                              disabled={mutationState === "saving"}
                              onClick={() => void handleDuplicateCase(suite.suite_id, evalCase)}
                            >
                              +
                            </button>
                            <button
                              type="button"
                              className="chip-action-button"
                              aria-label={`Delete case ${evalCase.name}`}
                              disabled={mutationState === "saving"}
                              onClick={() => void handleDeleteCase(suite.suite_id, evalCase.case_id)}
                            >
                              x
                            </button>
                          </span>
                        ))}
                      </div>
                    ) : (
                      "No cases"
                    )}
                  </td>
                  <td>{suite.created_at}</td>
                  <td>
                    <button
                      type="button"
                      className="text-action-button"
                      disabled={mutationState === "saving"}
                      onClick={() => void handleEditSuite(suite)}
                    >
                      Edit suite
                    </button>
                    <button
                      type="button"
                      className="text-action-button"
                      disabled={mutationState === "saving"}
                      onClick={() => void handleDuplicateSuite(suite)}
                    >
                      Duplicate
                    </button>
                    <a className="text-action-button" href={`/api/evals/suites/${suite.suite_id}/export`}>
                      Export suite
                    </a>
                    <button
                      type="button"
                      className="text-action-button is-danger"
                      disabled={mutationState === "saving" || suite.case_count > 0 || suiteHasSchedule(suite.suite_id)}
                      aria-label={`Delete suite ${suite.name}`}
                      onClick={() => void handleDeleteSuite(suite)}
                    >
                      Delete suite
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedScoreRun ? (
        <ScoreDetailDrawer run={selectedScoreRun} onClose={() => setSelectedScoreRun(null)} />
      ) : null}
    </section>
  );
}

function ScoreDetailDrawer({ run, onClose }: { run: EvalScoreRunRecord; onClose: () => void }) {
  return (
    <OverlaySurface isOpen onClose={onClose} labelledBy="score-detail-title">
      <OverlayHeader
        titleId="score-detail-title"
        title="Score detail"
        kicker="Eval score"
        meta={run.run_id}
        closeLabel="Close score detail"
        onClose={onClose}
        headingLevel={3}
      />
      <div className="drawer-content">
          <dl className="run-stats-grid">
            <div>
              <dt>Case</dt>
              <dd>{run.case_name}</dd>
            </div>
            <div>
              <dt>Suite</dt>
              <dd>{run.suite_name}</dd>
            </div>
            <div>
              <dt>Target</dt>
              <dd>
                {run.model_name} / {run.node_id}
              </dd>
            </div>
            <div>
              <dt>Result</dt>
              <dd>{run.passed ? "passed" : "failed"}</dd>
            </div>
            <div>
              <dt>Reason</dt>
              <dd>{run.reason ?? "No reason recorded"}</dd>
            </div>
            <div>
              <dt>Duration</dt>
              <dd>{run.duration_ms === null ? "Unknown" : `${run.duration_ms}ms`}</dd>
            </div>
          </dl>

          {run.missing_or_mismatched && run.missing_or_mismatched.length > 0 ? (
            <section className="drawer-section">
              <h4>Missing or mismatched</h4>
              <p>{run.missing_or_mismatched.join(", ")}</p>
            </section>
          ) : null}

          <section className="drawer-section">
            <h4>Response Preview</h4>
            <p>{run.response_preview || "No response preview recorded."}</p>
          </section>

          <section className="json-panel">
            <div className="json-panel-header">
              <h4>Parsed Response JSON</h4>
            </div>
            <pre>
              <code>{JSON.stringify(run.response_json ?? {}, null, 2)}</code>
            </pre>
          </section>
      </div>
    </OverlaySurface>
  );
}
