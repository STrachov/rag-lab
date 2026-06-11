import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getSavedExperiment, Project, SavedExperiment } from "../api/client";

type ExperimentResultsPageProps = {
  currentProject: Project | null;
};

type EvaluationSummary = {
  evaluation?: Record<string, unknown>;
  metric_averages?: Record<string, unknown>;
  questions?: Array<Record<string, unknown>>;
};

export function ExperimentResultsPage({ currentProject }: ExperimentResultsPageProps) {
  const { experimentId } = useParams();
  const [experiment, setExperiment] = useState<SavedExperiment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!currentProject || !experimentId) {
      setExperiment(null);
      return;
    }
    getSavedExperiment(currentProject.id, experimentId)
      .then((result) => {
        setExperiment(result);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }, [currentProject, experimentId]);

  if (!currentProject) {
    return (
      <section className="page">
        <header className="page-header">
          <p className="eyebrow">Experiments</p>
          <h1>Experiment Results</h1>
          <p>Select or create a project first.</p>
        </header>
        <div className="empty-state">No project selected.</div>
      </section>
    );
  }

  const summary = (experiment?.metrics_summary_json ?? {}) as EvaluationSummary;
  const evaluation = summary.evaluation ?? {};
  const metricAverages = summary.metric_averages ?? {};
  const questions = summary.questions ?? [];

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Experiments</p>
        <h1>{experiment?.name ?? "Experiment Results"}</h1>
        <p>Saved evaluation results and per-question metrics for this experiment.</p>
      </header>

      <Link className="text-action" to={`/projects/${currentProject.id}/saved-experiments`}>
        Back to Saved Experiments
      </Link>

      {error ? <div className="notice">Experiment unavailable: {error}</div> : null}
      {!experiment && !error ? <div className="empty-state">Loading experiment...</div> : null}

      {experiment ? (
        <div className="stage-details">
          <div className="parameter-section">
            <h2>Summary</h2>
            <div className="asset-mini-summary">
              <span>{experiment.status}</span>
              <span>{String(evaluation.completed_question_count ?? 0)} completed</span>
              <span>{String(evaluation.error_count ?? 0)} errors</span>
              <span>{String(evaluation.warning_count ?? 0)} warnings</span>
              <span>{String(evaluation.duration_seconds ?? 0)} sec</span>
            </div>
            {experiment.error_json ? (
              <div className="notice">Last error: {errorMessage(experiment.error_json)}</div>
            ) : null}
          </div>

          <div className="parameter-section">
            <h2>Aggregate Metrics</h2>
            {Object.keys(metricAverages).length === 0 ? (
              <div className="nested-empty">No aggregate metrics recorded.</div>
            ) : (
              <div className="metric-strip retrieval-metrics-strip">
                {Object.entries(metricAverages).map(([name, value]) => (
                  <div key={name}>
                    <span>{formatMetricName(name)}</span>
                    <strong>{typeof value === "number" ? formatMetricValue(value) : "-"}</strong>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="parameter-section">
            <h2>Questions</h2>
            {questions.length === 0 ? (
              <div className="nested-empty">No per-question results recorded.</div>
            ) : (
              <div className="table">
                <div className="table-row experiment-result-table table-head">
                  <span>Question</span>
                  <span>Status</span>
                  <span>Top Result</span>
                  <span>Hit</span>
                  <span>Warnings</span>
                </div>
                {questions.map((question, index) => (
                  <details className="table-row experiment-result-table" key={String(question.question_id ?? index)}>
                    <summary>
                      <span>{formatQuestionOption(String(question.question ?? question.question_id ?? ""))}</span>
                      <span>{String(question.status ?? "")}</span>
                      <span>{formatEvaluationTopResult(question.top_result)}</span>
                      <span>{formatEvaluationHit(question.metrics)}</span>
                      <span>{Array.isArray(question.warnings) ? question.warnings.length : 0}</span>
                    </summary>
                    <div className="experiment-question-details">
                      <div>
                        <h3>Ground Truth</h3>
                        <GroundTruthSummary value={question.ground_truth} />
                      </div>
                      <div>
                        <h3>Retrieved</h3>
                        <RetrievedSummary value={question.retrieved} />
                      </div>
                    </div>
                    <pre className="json-preview">{JSON.stringify(question, null, 2)}</pre>
                  </details>
                ))}
              </div>
            )}
          </div>

          <div className="parameter-section">
            <h2>Snapshot</h2>
            <pre className="json-preview">{JSON.stringify(experiment.params_snapshot_json, null, 2)}</pre>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function GroundTruthSummary({ value }: { value: unknown }) {
  if (!value || typeof value !== "object") {
    return <div className="nested-empty">No ground truth details recorded.</div>;
  }
  const gt = value as Record<string, unknown>;
  const relevantPages = Array.isArray(gt.relevant_pages) ? gt.relevant_pages : [];
  const relevantChunks = Array.isArray(gt.relevant_chunks) ? gt.relevant_chunks : [];
  return (
    <div className="stage-details">
      <div className="asset-mini-summary">
        <span>{String(gt.expected_answer_type ?? "unknown")}</span>
        {gt.expected_answer_brief ? <span>{String(gt.expected_answer_brief)}</span> : null}
      </div>
      {relevantPages.length > 0 ? (
        <div className="asset-mini-summary">
          {relevantPages.map((page, index) => (
            <span key={index}>{formatGroundTruthPage(page)}</span>
          ))}
        </div>
      ) : null}
      {relevantChunks.length > 0 ? (
        <div className="asset-mini-summary">
          {relevantChunks.map((chunk, index) => (
            <span key={index}>{formatGroundTruthChunk(chunk)}</span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function RetrievedSummary({ value }: { value: unknown }) {
  if (!Array.isArray(value) || value.length === 0) {
    return <div className="nested-empty">No retrieved results recorded.</div>;
  }
  return (
    <div className="index-cache-list">
      {value.map((item, index) => {
        const result = item && typeof item === "object" ? (item as Record<string, unknown>) : {};
        return (
          <div className="cache-item" key={index}>
            <strong>{formatRetrievedTitle(result)}</strong>
            <span>{formatRetrievedScores(result)}</span>
            <small>{formatRetrievedMeta(result)}</small>
          </div>
        );
      })}
    </div>
  );
}

function errorMessage(value: unknown): string {
  if (value && typeof value === "object" && "message" in value) {
    return String((value as { message?: unknown }).message ?? "Unknown error");
  }
  return "Unknown error";
}

function formatMetricName(name: string): string {
  return name.replace(/_/g, " ");
}

function formatMetricValue(value: number): string {
  if (!Number.isFinite(value)) {
    return "-";
  }
  if (Number.isInteger(value) && Math.abs(value) >= 10) {
    return String(value);
  }
  return value.toFixed(3);
}

function formatEvaluationHit(value: unknown): string {
  if (!value || typeof value !== "object") {
    return "-";
  }
  const metrics = value as Record<string, unknown>;
  const hit = metrics.hit_at_k ?? metrics.page_hit_at_k ?? metrics.expected_not_found;
  return typeof hit === "number" ? formatMetricValue(hit) : "-";
}

function formatEvaluationTopResult(value: unknown): string {
  if (!value || typeof value !== "object") {
    return "-";
  }
  const result = value as Record<string, unknown>;
  const parts = [
    result.source_name ? String(result.source_name) : "",
    typeof result.page === "number" ? `page ${result.page}` : "",
    typeof result.page_start === "number" ? `page ${result.page_start}` : "",
    result.chunk_id ? String(result.chunk_id) : "",
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" / ") : "-";
}

function formatGroundTruthPage(value: unknown): string {
  if (!value || typeof value !== "object") {
    return "page";
  }
  const page = value as Record<string, unknown>;
  const pageNumber = page.page_number;
  const pageIndex = page.page_index;
  const pdfSha1 = page.pdf_sha1 ? ` / ${String(page.pdf_sha1).slice(0, 8)}` : "";
  if (typeof pageNumber === "number" && typeof pageIndex === "number") {
    return `page ${pageNumber} / index ${pageIndex}${pdfSha1}`;
  }
  return `page${pdfSha1}`;
}

function formatGroundTruthChunk(value: unknown): string {
  if (!value || typeof value !== "object") {
    return "chunk";
  }
  const chunk = value as Record<string, unknown>;
  const relevance = typeof chunk.relevance === "number" ? ` / rel ${chunk.relevance}` : "";
  return `${String(chunk.chunk_id ?? "chunk")}${relevance}`;
}

function formatRetrievedTitle(result: Record<string, unknown>): string {
  const rank = typeof result.rank === "number" ? `#${result.rank}` : "#";
  return `${rank} ${String(result.chunk_id ?? result.source_name ?? "result")}`;
}

function formatRetrievedScores(result: Record<string, unknown>): string {
  return [
    typeof result.score === "number" ? `score ${result.score.toFixed(4)}` : "",
    typeof result.rerank_score === "number" ? `rerank ${result.rerank_score.toFixed(4)}` : "",
    typeof result.dense_score === "number" ? `dense ${result.dense_score.toFixed(4)}` : "",
    typeof result.sparse_score === "number" ? `sparse ${result.sparse_score.toFixed(4)}` : "",
  ]
    .filter(Boolean)
    .join(" / ") || "score n/a";
}

function formatRetrievedMeta(result: Record<string, unknown>): string {
  return [
    result.source_name ? String(result.source_name) : "",
    typeof result.page === "number" ? `page ${result.page}` : "",
    typeof result.page_start === "number" ? `page ${result.page_start}` : "",
    typeof result.token_count === "number" ? `${result.token_count} tokens` : "",
  ]
    .filter(Boolean)
    .join(" / ") || "-";
}

function formatQuestionOption(question: string): string {
  const normalized = question.replace(/\s+/g, " ").trim();
  return normalized.length > 96 ? `${normalized.slice(0, 93)}...` : normalized;
}
