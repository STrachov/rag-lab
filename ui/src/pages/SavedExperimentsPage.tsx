import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  deleteSavedExperiment,
  listSavedExperiments,
  Project,
  renameSavedExperiment,
  SavedExperiment,
} from "../api/client";

type SavedExperimentsPageProps = {
  currentProject: Project | null;
};

export function SavedExperimentsPage({ currentProject }: SavedExperimentsPageProps) {
  const [savedExperiments, setSavedExperiments] = useState<SavedExperiment[]>([]);
  const [deletingExperimentId, setDeletingExperimentId] = useState("");
  const [renamingExperimentId, setRenamingExperimentId] = useState("");
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

  async function handleRenameExperiment(experiment: SavedExperiment) {
    if (!currentProject) {
      return;
    }
    const nextName = window.prompt("Saved experiment name", experiment.name)?.trim();
    if (!nextName || nextName === experiment.name) {
      return;
    }
    setRenamingExperimentId(experiment.id);
    try {
      const updated = await renameSavedExperiment(currentProject.id, experiment.id, { name: nextName });
      setSavedExperiments((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename saved experiment");
    } finally {
      setRenamingExperimentId("");
    }
  }

  async function handleDeleteExperiment(experiment: SavedExperiment) {
    if (!currentProject) {
      return;
    }
    if (!window.confirm(`Delete saved experiment "${experiment.name}"?`)) {
      return;
    }
    setDeletingExperimentId(experiment.id);
    try {
      const result = await deleteSavedExperiment(currentProject.id, experiment.id);
      setSavedExperiments((current) =>
        current.filter((item) => item.id !== result.deleted_saved_experiment_id),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete saved experiment");
    } finally {
      setDeletingExperimentId("");
    }
  }

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
        <p>Saved experiment records for this project, with snapshots and metrics-only results.</p>
      </header>

      {error ? <div className="notice">Saved experiments unavailable: {error}</div> : null}

      {savedExperiments.length === 0 ? (
        <div className="empty-state">No saved experiments recorded for this project yet.</div>
      ) : (
        <div className="table">
          <div className="table-row experiment-table table-head">
            {/* <span>ID</span> */}
            <span>Name</span>
            <span>Status</span>
            <span>Questions</span>
            <span>Hit</span>
            <span>Actions</span>
          </div>
          {savedExperiments.map((experiment) => (
            <div className="table-row experiment-table" key={experiment.id}>
              {/* <span>{experiment.id}</span> */}
              <span>
                <Link className="project-link" to={`/projects/${currentProject.id}/saved-experiments/${experiment.id}`}>
                  {experiment.name}
                </Link>
              </span>
              <span>{experiment.status}</span>
              <span>{experimentQuestionsLabel(experiment)}</span>
              <span>{experimentHitLabel(experiment)}</span>
              <span className="row-actions">
                <button
                  aria-label={`Rename ${experiment.name}`}
                  className="icon-action"
                  disabled={renamingExperimentId === experiment.id || deletingExperimentId === experiment.id}
                  onClick={() => handleRenameExperiment(experiment)}
                  title="Rename"
                  type="button"
                >
                  &#9998;
                </button>
                <button
                  aria-label={`Delete ${experiment.name}`}
                  className="icon-action danger"
                  disabled={deletingExperimentId === experiment.id || renamingExperimentId === experiment.id}
                  onClick={() => handleDeleteExperiment(experiment)}
                  title="Delete"
                  type="button"
                >
                  &#215;
                </button>
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function experimentQuestionsLabel(experiment: SavedExperiment): string {
  const summary = experiment.metrics_summary_json as {
    evaluation?: Record<string, unknown>;
  };
  const completed = summary.evaluation?.completed_question_count;
  const total = summary.evaluation?.question_count;
  const errors = summary.evaluation?.error_count;
  if (typeof completed === "number" && typeof total === "number") {
    return typeof errors === "number" && errors > 0 ? `${completed}/${total} (${errors} errors)` : `${completed}/${total}`;
  }
  if (typeof completed === "number") {
    return String(completed);
  }
  return "-";
}

function experimentHitLabel(experiment: SavedExperiment): string {
  const summary = experiment.metrics_summary_json as {
    metric_averages?: Record<string, unknown>;
  };
  const metricAverages = summary.metric_averages ?? {};
  const hit = metricAverages.hit_at_k ?? metricAverages.page_hit_at_k;
  return typeof hit === "number" ? hit.toFixed(3) : "-";
}
