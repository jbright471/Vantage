import type { ModelRecord } from "../../api/client";

type ModelsPageProps = {
  models: ModelRecord[];
};

export function ModelsPage({ models }: ModelsPageProps) {
  const orderedModels = [...models].sort((left, right) => left.model_name.localeCompare(right.model_name));
  const mirroredModels = orderedModels.filter((model) => model.placements.length > 1).length;
  const totalPlacements = orderedModels.reduce((total, model) => total + model.placements.length, 0);

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
                </tr>
              </thead>
              <tbody>
                {orderedModels.map((model) => (
                  <tr key={model.model_name}>
                    <td>{model.model_name}</td>
                    <td>{model.placements.join(", ")}</td>
                    <td>{model.placements.length > 1 ? "Replicated" : "Single node"}</td>
                    <td>{model.placements.length > 1 ? "Cluster visible" : "Node visible"}</td>
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
