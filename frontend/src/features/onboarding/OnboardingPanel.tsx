import { useState } from "react";

const DISMISS_KEY = "vantage:onboarding-dismissed";

type StreamStatus = "connecting" | "live" | "reconnecting" | "error" | string;

export interface OnboardingPanelProps {
  streamStatus: StreamStatus;
  nodeCount: number;
  modelCount: number;
  runCount: number;
  routingRuleCount: number;
  onOpenDocs: () => void;
  onOpenSetupWizard: () => void;
}

function readDismissed(): boolean {
  try {
    return window.localStorage.getItem(DISMISS_KEY) === "1";
  } catch {
    return false;
  }
}

function writeDismissed(): void {
  try {
    window.localStorage.setItem(DISMISS_KEY, "1");
  } catch {
    // Local storage may be disabled in hardened browser profiles. The button still hides for this session.
  }
}

export function OnboardingPanel({
  streamStatus,
  nodeCount,
  modelCount,
  runCount,
  routingRuleCount,
  onOpenDocs,
  onOpenSetupWizard,
}: OnboardingPanelProps) {
  const [isDismissed, setIsDismissed] = useState(readDismissed);

  if (isDismissed) {
    return null;
  }

  const checks = [
    {
      label: "API stream connected",
      complete: streamStatus === "live",
      detail: streamStatus === "live" ? "SSE is live." : "Start the backend or wait for reconnect.",
    },
    {
      label: "Nodes registered",
      complete: nodeCount > 0,
      detail: nodeCount > 0 ? `${nodeCount} node ${nodeCount === 1 ? "record" : "records"} visible.` : "Add nodes in config/vantage.bootstrap.toml.",
    },
    {
      label: "Models observed",
      complete: modelCount > 0,
      detail: modelCount > 0 ? `${modelCount} model ${modelCount === 1 ? "name" : "names"} indexed.` : "Run a poll cycle or enable demo mode.",
    },
    {
      label: "Runs auditable",
      complete: runCount > 0,
      detail: runCount > 0 ? `${runCount} run ${runCount === 1 ? "record" : "records"} stored.` : "Trigger a refresh, route action, or eval attempt.",
    },
    {
      label: "Routing policy visible",
      complete: routingRuleCount > 0,
      detail:
        routingRuleCount > 0
          ? `${routingRuleCount} routing policies loaded.`
          : "Seed routing from bootstrap config or use demo mode.",
    },
  ];
  const completeCount = checks.filter((check) => check.complete).length;

  function dismiss() {
    writeDismissed();
    setIsDismissed(true);
  }

  return (
    <section className="onboarding-panel" aria-labelledby="onboarding-title">
      <div className="onboarding-copy">
        <p className="section-kicker">Open-source quickstart</p>
        <h2 id="onboarding-title">Bring a new Vantage instance online</h2>
        <p>
          This checklist is intentionally local-first: verify the stream, confirm observed state, then decide whether to
          keep demo data or connect real worker nodes.
        </p>
        <div className="onboarding-action-row">
          <button type="button" className="action-button" onClick={onOpenSetupWizard}>
            Launch setup wizard
          </button>
          <button type="button" className="action-button" onClick={onOpenDocs}>
            Read operator guide
          </button>
          <button type="button" className="text-action-button" onClick={onOpenDocs}>
            Review release checklist
          </button>
          <button type="button" className="text-action-button" onClick={dismiss}>
            Dismiss
          </button>
        </div>
      </div>

      <div className="onboarding-checklist" aria-label={`${completeCount} of ${checks.length} setup checks complete`}>
        <div className="onboarding-progress">
          <strong>
            {completeCount}/{checks.length}
          </strong>
          <span>checks complete</span>
        </div>
        {checks.map((check) => (
          <article key={check.label} className={check.complete ? "onboarding-check is-complete" : "onboarding-check"}>
            <span aria-hidden="true">{check.complete ? "OK" : "!"}</span>
            <div>
              <strong>{check.label}</strong>
              <p>{check.detail}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
