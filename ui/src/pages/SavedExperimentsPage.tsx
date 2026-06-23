import { useEffect, useMemo, useState } from "react";
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

type EvaluationSummary = {
  evaluation?: Record<string, unknown>;
  metric_averages?: Record<string, unknown>;
};

type ComparisonRow = {
  label: string;
  value: (experiment: SavedExperiment) => string;
};

export function SavedExperimentsPage({ currentProject }: SavedExperimentsPageProps) {
  const [savedExperiments, setSavedExperiments] = useState<SavedExperiment[]>([]);
  const [selectedExperimentIds, setSelectedExperimentIds] = useState<string[]>([]);
  const [deletingExperimentId, setDeletingExperimentId] = useState("");
  const [renamingExperimentId, setRenamingExperimentId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const selectedExperiments = useMemo(
    () => savedExperiments.filter((experiment) => selectedExperimentIds.includes(experiment.id)),
    [savedExperiments, selectedExperimentIds],
  );

  useEffect(() => {
    if (!currentProject) {
      setSavedExperiments([]);
      setSelectedExperimentIds([]);
      return;
    }

    listSavedExperiments(currentProject.id)
      .then((result) => {
        setSavedExperiments(result.saved_experiments);
        setSelectedExperimentIds((current) =>
          current.filter((id) => result.saved_experiments.some((experiment) => experiment.id === id)),
        );
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
      setSelectedExperimentIds((current) =>
        current.filter((id) => id !== result.deleted_saved_experiment_id),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete saved experiment");
    } finally {
      setDeletingExperimentId("");
    }
  }

  function handleSelectExperiment(experimentId: string, selected: boolean) {
    setSelectedExperimentIds((current) => {
      if (selected) {
        return current.includes(experimentId) ? current : [...current, experimentId];
      }
      return current.filter((id) => id !== experimentId);
    });
  }

  function handleSelectAllVisible(selected: boolean) {
    setSelectedExperimentIds(selected ? savedExperiments.map((experiment) => experiment.id) : []);
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
        <>
          <div className="comparison-toolbar">
            <span>{selectedExperimentIds.length} selected for comparison</span>
            <button
              className="secondary-action"
              disabled={selectedExperimentIds.length === 0}
              onClick={() => setSelectedExperimentIds([])}
              type="button"
            >
              Clear selection
            </button>
          </div>

          <div className="table">
            <div className="table-row experiment-table table-head">
              <span>
                <input
                  aria-label="Select all saved experiments for comparison"
                  checked={selectedExperimentIds.length === savedExperiments.length}
                  onChange={(event) => handleSelectAllVisible(event.target.checked)}
                  type="checkbox"
                />
              </span>
              <span>Name</span>
              <span>Status</span>
              <span>Questions</span>
              <span>Hit</span>
              <span>MRR</span>
              <span>Recall</span>
              <span>Actions</span>
            </div>
            {savedExperiments.map((experiment) => (
              <div className="table-row experiment-table" key={experiment.id}>
                <span>
                  <input
                    aria-label={`Select ${experiment.name} for comparison`}
                    checked={selectedExperimentIds.includes(experiment.id)}
                    onChange={(event) => handleSelectExperiment(experiment.id, event.target.checked)}
                    type="checkbox"
                  />
                </span>
                <span>
                  <Link className="project-link" to={`/projects/${currentProject.id}/saved-experiments/${experiment.id}`}>
                    {experiment.name}
                  </Link>
                </span>
                <span>{experiment.status}</span>
                <span>{experimentQuestionsLabel(experiment)}</span>
                <span>{experimentMetricLabel(experiment, "hit_at_k", "page_hit_at_k")}</span>
                <span>{experimentMetricLabel(experiment, "mrr_at_k", "page_mrr_at_k")}</span>
                <span>{experimentMetricLabel(experiment, "recall_at_k", "page_recall_at_k")}</span>
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

          {selectedExperiments.length > 0 ? (
            <div className="parameter-section saved-experiment-comparison">
              <h2>Comparison</h2>
              <div className="comparison-table-wrap">
                <table className="comparison-table">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      {selectedExperiments.map((experiment) => (
                        <th key={experiment.id}>
                          <Link
                            className="project-link"
                            to={`/projects/${currentProject.id}/saved-experiments/${experiment.id}`}
                          >
                            {experiment.name}
                          </Link>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <ComparisonSection
                      experiments={selectedExperiments}
                      rows={aggregateMetricRows}
                      title="Aggregate Metrics"
                    />
                    <ComparisonSection
                      experiments={selectedExperiments}
                      rows={operationalMetricRows}
                      title="Operational Metrics"
                    />
                    <tr className="comparison-section-row">
                      <th colSpan={selectedExperiments.length + 1}>Snapshot</th>
                    </tr>
                    <tr>
                      <th>params_snapshot_json</th>
                      {selectedExperiments.map((experiment) => (
                        <td key={experiment.id}>
                          <pre className="json-preview comparison-json-preview">
                            {JSON.stringify(experiment.params_snapshot_json, null, 2)}
                          </pre>
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

function ComparisonSection({
  experiments,
  rows,
  title,
}: {
  experiments: SavedExperiment[];
  rows: ComparisonRow[];
  title: string;
}) {
  return (
    <>
      <tr className="comparison-section-row">
        <th colSpan={experiments.length + 1}>{title}</th>
      </tr>
      {rows.map((row) => (
        <tr key={row.label}>
          <th>{row.label}</th>
          {experiments.map((experiment) => (
            <td key={experiment.id}>{row.value(experiment)}</td>
          ))}
        </tr>
      ))}
    </>
  );
}

const aggregateMetricRows: ComparisonRow[] = [
  { label: "Question count", value: (experiment) => experimentQuestionsLabel(experiment) },
  {
    label: "Hit@k",
    value: (experiment) => experimentMetricLabel(experiment, "hit_at_k", "page_hit_at_k"),
  },
  {
    label: "MRR@k",
    value: (experiment) => experimentMetricLabel(experiment, "mrr_at_k", "page_mrr_at_k"),
  },
  {
    label: "Recall@k",
    value: (experiment) => experimentMetricLabel(experiment, "recall_at_k", "page_recall_at_k"),
  },
];

const operationalMetricRows: ComparisonRow[] = [
  {
    label: "Duration",
    value: (experiment) => durationLabel(evaluationSummary(experiment).evaluation?.duration_seconds),
  },
  {
    label: "Warnings",
    value: (experiment) => numberLabel(evaluationSummary(experiment).evaluation?.warning_count),
  },
  {
    label: "Errors",
    value: (experiment) => numberLabel(evaluationSummary(experiment).evaluation?.error_count),
  },
  {
    label: "Rerank provider",
    value: (experiment) => stringLabel(rerankingUsage(experiment).provider),
  },
  {
    label: "Rerank model",
    value: (experiment) => stringLabel(rerankingUsage(experiment).model),
  },
  {
    label: "Requests",
    value: (experiment) => numberLabel(rerankingUsage(experiment).request_count),
  },
  {
    label: "Candidates",
    value: (experiment) => numberLabel(rerankingUsage(experiment).candidate_count),
  },
  {
    label: "Tokens",
    value: (experiment) =>
      numberLabel(rerankingUsage(experiment).total_tokens ?? rerankingUsage(experiment).estimated_tokens),
  },
  {
    label: "Retries",
    value: (experiment) => numberLabel(rerankingUsage(experiment).retry_count),
  },
  {
    label: "Estimated cost",
    value: (experiment) => costLabel(rerankingUsage(experiment).estimated_cost_usd),
  },
];

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

function experimentMetricLabel(
  experiment: SavedExperiment,
  primaryKey: string,
  fallbackKey: string,
): string {
  const summary = experiment.metrics_summary_json as {
    metric_averages?: Record<string, unknown>;
  };
  const metricAverages = summary.metric_averages ?? {};
  const value = metricAverages[primaryKey] ?? metricAverages[fallbackKey];
  return typeof value === "number" ? value.toFixed(3) : "-";
}

function evaluationSummary(experiment: SavedExperiment): EvaluationSummary {
  return (experiment.metrics_summary_json ?? {}) as EvaluationSummary;
}

function rerankingUsage(experiment: SavedExperiment): Record<string, unknown> {
  const usage = evaluationSummary(experiment).evaluation?.usage;
  if (!usage || typeof usage !== "object") {
    return {};
  }
  const reranking = (usage as Record<string, unknown>).reranking;
  return reranking && typeof reranking === "object" ? (reranking as Record<string, unknown>) : {};
}

function formatInteger(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function numberLabel(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? formatInteger(value) : "-";
}

function stringLabel(value: unknown): string {
  return typeof value === "string" && value.trim() ? value : "-";
}

function durationLabel(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(2)} sec` : "-";
}

function costLabel(value: unknown): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return new Intl.NumberFormat(undefined, {
    currency: "USD",
    maximumFractionDigits: 6,
    minimumFractionDigits: 2,
    style: "currency",
  }).format(value);
}
