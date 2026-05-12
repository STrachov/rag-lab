import { useEffect, useState } from "react";

import { listSavedExperiments, Project, SavedExperiment } from "../api/client";

type SavedExperimentsPageProps = {
  currentProject: Project | null;
};

export function SavedExperimentsPage({ currentProject }: SavedExperimentsPageProps) {
  const [savedExperiments, setSavedExperiments] = useState<SavedExperiment[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!currentProject) {
      setSavedExperiments([]);
      return;
    }

    listSavedExperiments(currentProject.id)
      .then((result) => {
        setSavedExperiments(result.saved_experiments);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [currentProject]);

  if (!currentProject) {
    return (
      <section className="page">
        <header className="page-header">
          <p className="eyebrow">Experiments</p>
          <h1>Saved Experiments</h1>
          <p>Select or create a project first. Saved experiments belong to the current project.</p>
        </header>
        <div className="empty-state">No project selected.</div>
      </section>
    );
  }

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Experiments</p>
        <h1>Saved Experiments</h1>
        <p>Saved experiment records for this project, with data references, snapshots, and metrics-only results.</p>
      </header>

      {error ? <div className="notice">Saved experiments unavailable: {error}</div> : null}

      {savedExperiments.length === 0 ? (
        <div className="empty-state">No saved experiments recorded for this project yet.</div>
      ) : (
        <div className="table">
          <div className="table-row experiment-table table-head">
            <span>ID</span>
            <span>Name</span>
            <span>Data asset</span>
            <span>Status</span>
            <span>Metrics</span>
          </div>
          {savedExperiments.map((experiment) => (
            <div className="table-row experiment-table" key={experiment.id}>
              <span>{experiment.id}</span>
              <span>{experiment.name}</span>
              <span>{experiment.data_asset_id}</span>
              <span>{experiment.status}</span>
              <span>{Object.keys(experiment.metrics_summary_json).length}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
