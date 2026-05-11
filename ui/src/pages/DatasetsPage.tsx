import { useEffect, useState } from "react";

import { Dataset, listDatasets } from "../api/client";

export function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDatasets()
      .then((result) => setDatasets(result.datasets))
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Datasets</p>
        <h1>Document collections</h1>
        <p>Track source sets before ingestion, chunking, and indexing are implemented.</p>
      </header>
      {error ? <div className="notice">Backend unavailable: {error}</div> : null}
      <div className="table">
        <div className="table-row table-head">
          <span>ID</span>
          <span>Name</span>
          <span>Domain</span>
          <span>Documents</span>
          <span>Status</span>
        </div>
        {datasets.map((dataset) => (
          <div className="table-row" key={dataset.dataset_id}>
            <span>{dataset.dataset_id}</span>
            <span>{dataset.name}</span>
            <span>{dataset.domain ?? "-"}</span>
            <span>{dataset.document_count}</span>
            <span>{String(dataset.metadata.status ?? "local")}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
