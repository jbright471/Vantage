import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { ModelsPage } from "./features/models/ModelsPage";
import { NodesPage } from "./features/nodes/NodesPage";
import { RoutingPage } from "./features/routing/RoutingPage";
import { RunsPage } from "./features/runs/RunsPage";
import { EvalsPage } from "./features/evals/EvalsPage";
import { IntegrationHealthPanel } from "./features/integrations/IntegrationHealthPanel";
import { OnboardingPanel } from "./features/onboarding/OnboardingPanel";
import { SetupWizardDrawer } from "./features/onboarding/SetupWizardDrawer";
import { useEventSource } from "./hooks/useEventSource";
import { acknowledgeWarning } from "./api/client";
import { useSessionActions } from "./features/auth/AuthGate";

const OperatorGuideDrawer = lazy(() =>
  import("./features/docs/OperatorGuideDrawer").then((module) => ({ default: module.OperatorGuideDrawer })),
);

const navItems = [
  { href: "#nodes-title", label: "Nodes", icon: "ND" },
  { href: "#runs-title", label: "Audit Log", icon: "AL" },
  { href: "#models-title", label: "Models", icon: "MD" },
  { href: "#routing-title", label: "Routing", icon: "RT" },
  { href: "#evals-title", label: "Eval Lab", icon: "EV" },
] as const;

function readDocsSlug(): string | null {
  return new URLSearchParams(window.location.search).get("docs");
}

function writeDocsSlug(slug: string | null, replace = false) {
  const url = new URL(window.location.href);
  if (slug) {
    url.searchParams.set("docs", slug);
  } else {
    url.searchParams.delete("docs");
  }

  const nextUrl = `${url.pathname}${url.search}${url.hash}`;
  if (replace) {
    window.history.replaceState(null, "", nextUrl);
  } else {
    window.history.pushState(null, "", nextUrl);
  }
}

function formatRelativeSync(lastSyncAt: string | null): string {
  if (!lastSyncAt) {
    return "Awaiting first snapshot";
  }

  const lastSync = new Date(lastSyncAt);
  if (Number.isNaN(lastSync.valueOf())) {
    return `Last sync ${lastSyncAt}`;
  }

  return `Last sync ${new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(lastSync)}`;
}

function labelStreamStatus(streamStatus: string): string {
  switch (streamStatus) {
    case "live":
      return "Live";
    case "reconnecting":
      return "Reconnecting";
    case "error":
      return "Sync issue";
    default:
      return "Connecting";
  }
}

function labelPrimaryNode(nodes: Array<{ node_id: string; role: string; observed_status: string }>): string {
  const primaryNode = nodes.find((node) => node.role === "primary") ?? nodes[0];

  if (!primaryNode) {
    return "NO_NODES";
  }

  const status = primaryNode.observed_status === "healthy" ? "ONLINE" : primaryNode.observed_status.toUpperCase();
  return `${primaryNode.node_id.toUpperCase()}: ${status}`;
}

export function summarizeAttention(
  nodes: Array<{ enabled: boolean; observed_status: string; freshness: string }>,
  pendingRuns: number,
  warningCount: number,
): string {
  const enabledNodes = nodes.filter((node) => node.enabled);
  const staleNodes = enabledNodes.filter((node) => node.freshness !== "live").length;
  const degradedNodes = enabledNodes.filter((node) => node.observed_status !== "healthy").length;
  const issueCount = staleNodes + degradedNodes + pendingRuns + warningCount;

  if (issueCount === 0) {
    return "All lanes nominal";
  }

  return `${issueCount} signals need attention`;
}

export default function App() {
  const { state, streamStatus, lastSyncAt, errorMessage } = useEventSource("/api/stream");
  const sessionActions = useSessionActions();
  const [docsSlug, setDocsSlug] = useState<string | null>(() => readDocsSlug());
  const [activeNavHref, setActiveNavHref] = useState<(typeof navItems)[number]["href"]>("#nodes-title");
  const [isSetupWizardOpen, setIsSetupWizardOpen] = useState(false);
  const [showAllWarnings, setShowAllWarnings] = useState(false);
  const [acknowledgedWarningIds, setAcknowledgedWarningIds] = useState<Set<string>>(() => new Set());
  const [warningActionState, setWarningActionState] = useState<Record<string, "idle" | "saving" | "error">>({});

  const activeWarnings = state.warnings.filter((warning) => !acknowledgedWarningIds.has(warning.warning_id));
  const attentionNodes = state.nodes.filter((node) => node.enabled);
  const disabledNodes = state.nodes.length - attentionNodes.length;
  const liveNodes = attentionNodes.filter((node) => node.freshness === "live").length;
  const staleNodes = attentionNodes.filter((node) => node.freshness !== "live").length;
  const degradedNodes = attentionNodes.filter((node) => node.observed_status !== "healthy").length;
  const pendingRuns = state.runs.filter((run) => ["submitted_unverified", "running"].includes(run.status)).length;
  const evalRunCount = state.runs.filter((run) => run.detail_type === "eval_attempt").length;
  const mirroredModels = state.models.filter((model) => model.placements.length > 1).length;
  const activePolicyCount = state.routing.filter((rule) => rule.preferred_nodes.length > 0).length;
  const primaryNodeLabel = labelPrimaryNode(state.nodes);
  const attentionSummary = summarizeAttention(state.nodes, pendingRuns, activeWarnings.length);
  const needsAttention = degradedNodes > 0 || staleNodes > 0 || pendingRuns > 0 || activeWarnings.length > 0;
  const visibleWarningLimit = showAllWarnings ? activeWarnings.length : 2;
  const visibleWarnings = activeWarnings.slice(0, visibleWarningLimit);
  const hiddenWarningCount = Math.max(0, activeWarnings.length - visibleWarnings.length);

  useEffect(() => {
    function syncDocsFromHistory() {
      setDocsSlug(readDocsSlug());
    }

    window.addEventListener("popstate", syncDocsFromHistory);
    return () => window.removeEventListener("popstate", syncDocsFromHistory);
  }, []);

  useEffect(() => {
    if (!("IntersectionObserver" in window)) {
      return;
    }

    const targets = navItems
      .map((item) => document.querySelector<HTMLElement>(item.href))
      .filter((target): target is HTMLElement => target !== null);

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntry = entries.find((entry) => entry.isIntersecting);
        if (visibleEntry) {
          setActiveNavHref(`#${visibleEntry.target.id}` as (typeof navItems)[number]["href"]);
        }
      },
      { rootMargin: "-12% 0px -74%", threshold: 0 },
    );

    targets.forEach((target) => observer.observe(target));
    return () => observer.disconnect();
  }, []);

  const navigateDocs = useCallback((slug: string, options?: { replace?: boolean }) => {
    writeDocsSlug(slug, options?.replace);
    setDocsSlug(slug);
  }, []);

  const openDocs = useCallback(() => {
    navigateDocs(docsSlug ?? "welcome");
  }, [docsSlug, navigateDocs]);

  const closeDocs = useCallback(() => {
    writeDocsSlug(null);
    setDocsSlug(null);
  }, []);

  async function handleAcknowledgeWarning(warningId: string) {
    setWarningActionState((current) => ({ ...current, [warningId]: "saving" }));
    try {
      await acknowledgeWarning(warningId);
      setAcknowledgedWarningIds((current) => new Set(current).add(warningId));
      setWarningActionState((current) => ({ ...current, [warningId]: "idle" }));
    } catch {
      setWarningActionState((current) => ({ ...current, [warningId]: "error" }));
    }
  }

  return (
    <>
      <a className="skip-link" href="#dashboard-content">
        Skip to dashboard content
      </a>
      <main id="dashboard-content" className="command-shell">
      <aside className="side-rail">
        <div className="brand-block">
          <p className="rail-label">terminal</p>
          <h1 className="brand-title">Vantage</h1>
          <p className="brand-subtitle">CONTROL_PLANE</p>
        </div>

        <nav className="rail-nav" aria-label="Primary">
          {navItems.map((item) => {
            const count =
              item.href === "#nodes-title"
                ? state.nodes.length
                : item.href === "#runs-title"
                  ? state.runs.length
                  : item.href === "#models-title"
                    ? state.models.length
                    : item.href === "#routing-title"
                      ? state.routing.length
                      : evalRunCount;

            return (
              <a
                key={item.href}
                href={item.href}
                className={activeNavHref === item.href ? "is-active" : undefined}
                aria-current={activeNavHref === item.href ? "location" : undefined}
                onClick={() => setActiveNavHref(item.href)}
              >
                <span className="rail-nav-label">
                  <span className="rail-nav-icon" aria-hidden="true">
                    {item.icon}
                  </span>
                  {item.label}
                </span>
                <strong>{count}</strong>
              </a>
            );
          })}
        </nav>

        <section className="rail-panel">
          <p className="rail-label">{primaryNodeLabel}</p>
          <strong className={`rail-sync is-${streamStatus}`}>{labelStreamStatus(streamStatus)}</strong>
          <p className="rail-copy">{formatRelativeSync(lastSyncAt)}</p>
        </section>

        <section className="rail-panel">
          <p className="rail-label">Freshness</p>
          <dl className="rail-metrics">
            <div>
              <dt>Live</dt>
              <dd>{liveNodes}</dd>
            </div>
            <div>
              <dt>Stale</dt>
              <dd>{staleNodes}</dd>
            </div>
            <div>
              <dt>Warnings</dt>
              <dd>{activeWarnings.length}</dd>
            </div>
            <div>
              <dt>Pending</dt>
              <dd>{pendingRuns}</dd>
            </div>
          </dl>
        </section>
      </aside>

      <section className="main-column">
        <header className="command-header">
          <div>
            <p className="section-kicker">CONTROL_PLANE</p>
            <h2 className="command-title">Local AI Command Center</h2>
            <p className="command-copy">
              Vantage keeps observed state, configured state, and last-known freshness visibly separate so operators
              can trust what they are seeing under load.
            </p>
          </div>

          <div className="header-meta">
            <p className="command-breadcrumb">LOCAL / DESKTOP / VANTAGE</p>
            <div className="header-status-row">
              <span className={`status-chip is-${streamStatus}`}>{labelStreamStatus(streamStatus)}</span>
              <span className="meta-chip">{primaryNodeLabel}</span>
            </div>
            <div className="attention-ribbon" aria-label="Operator attention summary">
              <span className={needsAttention ? "attention-dot is-active" : "attention-dot"} />
              <strong>{attentionSummary}</strong>
              <small>
                {degradedNodes} degraded / {staleNodes} stale / {activeWarnings.length} warnings / {pendingRuns}{" "}
                pending
              </small>
            </div>
            <div className="header-action-row">
              <button type="button" className="docs-trigger-button" onClick={openDocs}>
                <span aria-hidden="true">?</span>
                Docs
              </button>
              {sessionActions ? (
                <button
                  type="button"
                  className="session-lock-button"
                  onClick={() => void sessionActions.lockSession()}
                >
                  Lock session
                </button>
              ) : null}
            </div>
            {sessionActions?.error ? (
              <p className="session-error" role="alert">
                {sessionActions.error}
              </p>
            ) : null}
          </div>
        </header>

        <section className="telemetry-strip" aria-label="Fleet summary">
          <article className="telemetry-tile">
            <div className="telemetry-tile-header">
              <span className="signal-label">Tracked nodes</span>
              <strong>{state.nodes.length}</strong>
            </div>
            <p>{liveNodes} live / {staleNodes} stale / {disabledNodes} disabled</p>
          </article>
          <article className="telemetry-tile">
            <div className="telemetry-tile-header">
              <span className="signal-label">Run queue</span>
              <strong>{pendingRuns}</strong>
            </div>
            <p>{state.runs.length} total observed runs</p>
          </article>
          <article className="telemetry-tile">
            <div className="telemetry-tile-header">
              <span className="signal-label">Model registry</span>
              <strong>{state.models.length}</strong>
            </div>
            <p>{mirroredModels} mirrored across nodes</p>
          </article>
          <article className="telemetry-tile">
            <div className="telemetry-tile-header">
              <span className="signal-label">Routing</span>
              <strong>{state.routing.length}</strong>
            </div>
            <p>{activePolicyCount} with configured targets</p>
          </article>
        </section>

        {errorMessage ? <p className="inline-warning">{errorMessage}</p> : null}

        <OnboardingPanel
          streamStatus={streamStatus}
          nodeCount={state.nodes.length}
          modelCount={state.models.length}
          runCount={state.runs.length}
          routingRuleCount={state.routing.length}
          onOpenDocs={openDocs}
          onOpenSetupWizard={() => setIsSetupWizardOpen(true)}
        />

        <IntegrationHealthPanel />

        {activeWarnings.length > 0 ? (
          <section className="warning-strip" aria-label="Active warnings">
            <div>
              <p className="section-kicker">Warnings</p>
              <h2>Configuration drift and operator notices</h2>
            </div>
            <div className="warning-list">
              {visibleWarnings.map((warning) => (
                <article key={warning.warning_id} className="warning-item">
                  <span className={`status-chip is-${warning.severity}`}>{warning.severity}</span>
                  <div>
                    <strong>{warning.summary}</strong>
                    <p>{warning.node_id ? `${warning.warning_type} / ${warning.node_id}` : warning.warning_type}</p>
                    {warningActionState[warning.warning_id] === "error" ? (
                      <p className="warning-action-error">Acknowledge failed. Try again.</p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="warning-ack-button"
                    disabled={warningActionState[warning.warning_id] === "saving"}
                    onClick={() => void handleAcknowledgeWarning(warning.warning_id)}
                  >
                    {warningActionState[warning.warning_id] === "saving" ? "Acknowledging…" : "Acknowledge"}
                  </button>
                </article>
              ))}
              {activeWarnings.length > 2 ? (
                <button
                  type="button"
                  className="warning-expand-button"
                  onClick={() => setShowAllWarnings((current) => !current)}
                >
                  {showAllWarnings ? "Show fewer warnings" : `+${hiddenWarningCount} more`}
                </button>
              ) : null}
            </div>
          </section>
        ) : null}

        <NodesPage nodes={state.nodes} runs={state.runs} />
        <RunsPage runs={state.runs} />
        <ModelsPage models={state.models} />
        <RoutingPage
          rules={state.routing}
          availableNodes={state.nodes.map((node) => node.node_id)}
          nodeSummaries={state.nodes.map((node) => ({
            node_id: node.node_id,
            display_name: node.display_name,
            observed_status: node.observed_status,
            freshness: node.freshness,
            model_count: node.model_count,
          }))}
        />
        <EvalsPage models={state.models} runs={state.runs} />
      </section>

      {docsSlug ? (
        <Suspense fallback={null}>
          <OperatorGuideDrawer
            isOpen={true}
            selectedSlug={docsSlug}
            onClose={closeDocs}
            onNavigate={navigateDocs}
          />
        </Suspense>
      ) : null}

      <SetupWizardDrawer
        isOpen={isSetupWizardOpen}
        onClose={() => setIsSetupWizardOpen(false)}
        nodes={state.nodes}
        models={state.models}
        routingRules={state.routing}
        streamStatus={streamStatus}
      />
      </main>
    </>
  );
}
