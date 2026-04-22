import type { ModelRecord } from "../../api/client";

type ModelsPageProps = {
  models: ModelRecord[];
};

export function ModelsPage({ models }: ModelsPageProps) {
  const orderedModels = [...models].sort((left, right) => left.model_name.localeCompare(right.model_name));

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
        <div className="info-grid">
          {orderedModels.map((model) => (
            <article className="info-card" key={model.model_name}>
              <p className="info-kicker">Model tag</p>
              <h3>{model.model_name}</h3>
              <p className="info-copy">{model.placements.join(", ")}</p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
