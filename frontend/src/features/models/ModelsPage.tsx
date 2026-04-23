import { useState } from "react";

import { submitCapabilityCheck, type ModelRecord, type RunRecord } from "../../api/client";

type ModelsPageProps = {
  models: ModelRecord[];
};

function formatCapabilityMessage(run: RunRecord): string {
  const preview = typeof run.metadata_json?.response_preview === "string" ? run.metadata_json.response_preview : null;
  const duration = typeof run.duration_ms === "number" ? `${run.duration_ms} ms` : null;
  const segments = [duration, preview].filter(Boolean);
  return segments.length > 0 ? segments.join(" | ") : run.summary;
}

export function ModelsPage({ models }: ModelsPageProps) {
  const [checkStateByPlacement, setCheckStateByPlacement] = useState<
    Record<
      string,
      {
        phase: "idle" | "submitting" | "success" | "error";
        status?: string;
        message?: string;
      }
    >
  >({});
  const orderedModels = [...models].sort((left, right) => left.model_name.localeCompare(right.model_name));
  const mirroredModels = orderedModels.filter((model) => model.placements.length > 1).length;
  const totalPlacements = orderedModels.reduce((total, model) => total + model.placements.length, 0);

  async function handleCapabilityCheck(modelName: string, nodeId: string) {
    const placementKey = `${modelName}:${nodeId}`;
    setCheckStateByPlacement((current) => ({
      ...current,
      [placementKey]: {
        phase: "submitting",
        message: "Running live capability check against the selected node...",
      },
    }));

    try {
      const run = await submitCapabilityCheck(modelName, nodeId);
      setCheckStateByPlacement((current) => ({
        ...current,
        [placementKey]: {
          phase: run.status === "success" ? "success" : "error",
          status: run.status,
          message: formatCapabilityMessage(run),
        },
      }));
    } catch (error) {
      setCheckStateByPlacement((current) => ({
        ...current,
        [placementKey]: {
          phase: "error",
          message: error instanceof Error ? error.message : "Capability check failed.",
        },
      }));
    }
  }

  return (
    <section className="panel-section" aria-labelledby="models-title">
      <header className="section-header">
        <div>
          <p className="section-kicker">Models</p>
          <h2 id="models-title">Merged inventory across every registered node</h2>
        </div>
        <p className="section-copy">
          The same tag can exist on multiple machines, so Vantage shows placements explicitly instead of implying a
          single source of truth.
        </p>
      </header>

      {orderedModels.length === 0 ? (
        <div className="empty-state">No models have been observed yet.</div>
      ) : (
        <>
          <div className="metric-strip">
            <article className="metric-card">
              <p className="info-kicker">Total inventory</p>
              <strong>{orderedModels.length} models</strong>
            </article>
            <article className="metric-card">
              <p className="info-kicker">Replicated</p>
              <strong>{mirroredModels} mirrored</strong>
            </article>
            <article className="metric-card">
              <p className="info-kicker">Placements</p>
              <strong>{totalPlacements} node slots</strong>
            </article>
          </div>

          <div className="table-shell">
            <table className="inventory-table">
              <thead>
                <tr>
                  <th scope="col">Model Name</th>
                  <th scope="col">Node Placement</th>
                  <th scope="col">Coverage</th>
                  <th scope="col">Presence</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {orderedModels.map((model) => (
                  <tr key={model.model_name}>
                    <td>{model.model_name}</td>
                    <td>
                      <div className="placement-stack">
                        {model.placement_details.map((placement) => (
                          <span key={`${model.model_name}-${placement.node_id}`} className="meta-chip placement-chip">
                            {placement.node_id}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>{model.placements.length > 1 ? "Replicated" : "Single node"}</td>
                    <td>{model.placements.length > 1 ? "Cluster visible" : "Node visible"}</td>
                    <td className="table-action-cell">
                      <div className="action-stack">
                        {model.placement_details.map((placement) => {
                          const placementKey = `${model.model_name}:${placement.node_id}`;
                          const capabilityState = checkStateByPlacement[placementKey];
                          return (
                            <div key={placementKey} className="inline-action-row">
                              <button
                                type="button"
                                className="action-button"
                                onClick={() => handleCapabilityCheck(model.model_name, placement.node_id)}
                                disabled={capabilityState?.phase === "submitting"}
                              >
                                {capabilityState?.phase === "submitting"
                                  ? `Checking ${placement.node_id}...`
                                  : `Check on ${placement.node_id}`}
                              </button>
                              {capabilityState?.message ? (
                                <div className="inline-result">
                                  {capabilityState.status ? (
                                    <span className={`status-chip is-${capabilityState.status}`}>
                                      {capabilityState.status}
                                    </span>
                                  ) : null}
                                  <span
                                    className={
                                      capabilityState.phase === "error" ? "action-copy is-error" : "action-copy"
                                    }
                                  >
                                    {capabilityState.message}
                                  </span>
                                </div>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
