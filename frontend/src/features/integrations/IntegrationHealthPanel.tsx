import { useEffect, useState } from "react";

import { fetchIntegrationHealth, type IntegrationHealthRecord } from "../../api/client";

function formatLastDispatch(health: IntegrationHealthRecord): string {
  if (!health.last_dispatch?.dispatched_at) {
    return "No dispatch recorded";
  }
  return `${health.last_dispatch.adapter ?? "unknown"} / ${health.last_dispatch.event_count ?? 0} events`;
}

export function IntegrationHealthPanel() {
  const [health, setHealth] = useState<IntegrationHealthRecord | null>(null);

  useEffect(() => {
    let isCurrent = true;
    fetchIntegrationHealth()
      .then((payload) => {
        if (isCurrent) {
          setHealth(payload);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setHealth(null);
        }
      });
    return () => {
      isCurrent = false;
    };
  }, []);

  if (!health) {
    return null;
  }

  const activeTargets = Object.entries(health.configured_targets)
    .filter(([, configured]) => configured)
    .map(([name]) => name);

  return (
    <section className="integration-health-panel" aria-label="Integration health">
      <div>
        <p className="section-kicker">Integrations</p>
        <h2>Automation surface</h2>
        <p>
          {health.external_api_token_configured ? "External API token configured" : "External API token not configured"} /
          {" "}
          {activeTargets.length ? `${activeTargets.join(", ")} target${activeTargets.length === 1 ? "" : "s"} ready` : "no dispatch targets"}
        </p>
      </div>
      <dl>
        <div>
          <dt>Last Dispatch</dt>
          <dd>{formatLastDispatch(health)}</dd>
        </div>
        <div>
          <dt>Security Counters</dt>
          <dd>{health.security_event_counters.length}</dd>
        </div>
      </dl>
    </section>
  );
}
