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
  slice_metrics?: Record<string, SliceMetricSummary>;
};

type SliceMetricSummary = {
  filter?: Record<string, unknown>;
  label?: string;
  metric_averages?: Record<string, unknown>;
  question_count?: number;
  warnings?: string[];
};

export function ExperimentResultsPage({ currentProject }: ExperimentResultsPageProps) {
  const { experimentId } = useParams();
  const [experiment, setExperiment] = useState<SavedExperiment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState("");
  const [difficultyFilter, setDifficultyFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");

  useEffect(() => {
    if (!currentProject || !experimentId) {
      setExperiment(null);
      return;
    }
    getSavedExperiment(currentProject.id, experimentId)
      .then((result) => {
        setExperiment(result);
        setSourceFilter("");
        setDifficultyFilter("");
        setTagFilter("");
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
  const sliceMetrics = summary.slice_metrics ?? {};
  const sourceOptions = metadataOptions(questions, "source");
  const difficultyOptions = metadataOptions(questions, "difficulty");
  const tagOptions = metadataOptions(questions, "tags");
  const filteredQuestions = questions.filter((question) =>
    questionMatchesFilters(question, sourceFilter, difficultyFilter, tagFilter),
  );

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

          {Object.keys(sliceMetrics).length > 0 ? (
            <div className="parameter-section">
              <h2>Performance by question slice</h2>
              <SliceMetricsTable
                metricAverages={metricAverages}
                questionCount={numericValue(evaluation.question_count)}
                slices={sliceMetrics}
              />
            </div>
          ) : null}

          <div className="parameter-section">
            <h2>API Usage</h2>
            <ApiUsageSummary usage={evaluation.usage} />
          </div>

          <div className="parameter-section">
            <h2>Questions</h2>
            {questions.length === 0 ? (
              <div className="nested-empty">No per-question results recorded.</div>
            ) : (
              <>
                <div className="question-filter-bar">
                  <MetadataFilter label="Source" onChange={setSourceFilter} options={sourceOptions} value={sourceFilter} />
                  <MetadataFilter
                    label="Difficulty"
                    onChange={setDifficultyFilter}
                    options={difficultyOptions}
                    value={difficultyFilter}
                  />
                  <MetadataFilter label="Tag" onChange={setTagFilter} options={tagOptions} value={tagFilter} />
                  <span>{filteredQuestions.length} of {questions.length} questions</span>
                </div>
                {filteredQuestions.length === 0 ? (
                  <div className="nested-empty">No questions match the selected metadata filters.</div>
                ) : (
                  <div className="table">
                    <div className="table-row experiment-result-table table-head">
                      <span>Question</span>
                      <span>Status</span>
                      <span>Top Result</span>
                      <span>Hit</span>
                      <span>Warnings</span>
                    </div>
                    {filteredQuestions.map((question, index) => (
                      <details className="table-row experiment-result-table" key={String(question.question_id ?? index)}>
                        <summary>
                          <span>
                            {formatQuestionOption(String(question.question ?? question.question_id ?? ""))}
                            <QuestionMetadataBadges value={question.question_metadata} />
                          </span>
                          <span>{String(question.status ?? "")}</span>
                          <span>{formatEvaluationResultSummary(question)}</span>
                          <span>{formatEvaluationHit(question.metrics)}</span>
                          <span>{Array.isArray(question.warnings) ? question.warnings.length : 0}</span>
                        </summary>
                        {question.error_json ? (
                          <div className="notice">
                            Failed: {errorMessage(question.error_json)}
                            {errorStage(question.error_json) ? ` (${errorStage(question.error_json)})` : ""}
                          </div>
                        ) : null}
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
              </>
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

function SliceMetricsTable({
  metricAverages,
  questionCount,
  slices,
}: {
  metricAverages: Record<string, unknown>;
  questionCount: number | null;
  slices: Record<string, SliceMetricSummary>;
}) {
  const metricKeys = Array.from(new Set([
    ...Object.keys(metricAverages),
    ...Object.values(slices).flatMap((slice) => Object.keys(slice.metric_averages ?? {})),
  ])).sort();
  const rows = [
    { id: "all", label: "All questions", metric_averages: metricAverages, question_count: questionCount, warnings: [] },
    ...Object.entries(slices).map(([id, slice]) => ({ id, ...slice })),
  ];
  return (
    <div className="comparison-table-wrap">
      <table className="comparison-table slice-metrics-table">
        <thead>
          <tr>
            <th>Slice</th>
            <th>Questions</th>
            {metricKeys.map((key) => <th key={key}>{formatMetricName(key)}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <th>
                {row.label ?? row.id}
                {row.warnings?.length ? <small className="slice-warning">{row.warnings.join(" ")}</small> : null}
              </th>
              <td>{typeof row.question_count === "number" ? row.question_count : "-"}</td>
              {metricKeys.map((key) => {
                const value = row.metric_averages?.[key];
                return <td key={key}>{typeof value === "number" ? formatMetricValue(value) : "-"}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetadataFilter({ label, onChange, options, value }: { label: string; onChange: (value: string) => void; options: string[]; value: string }) {
  if (options.length === 0) {
    return null;
  }
  return (
    <label>
      <span>{label}</span>
      <select onChange={(event) => onChange(event.target.value)} value={value}>
        <option value="">All</option>
        {options.map((option) => <option key={option} value={option}>{formatMetadataLabel(option)}</option>)}
      </select>
    </label>
  );
}

function QuestionMetadataBadges({ value }: { value: unknown }) {
  const metadata = objectValue(value);
  const tags = Array.isArray(metadata.tags) ? metadata.tags.filter((tag): tag is string => typeof tag === "string") : [];
  const badges = [
    typeof metadata.source === "string" ? metadata.source : "",
    typeof metadata.difficulty === "string" ? metadata.difficulty : "",
    ...tags,
  ].filter(Boolean);
  return badges.length > 0 ? (
    <span className="question-metadata-badges">
      {badges.map((badge, index) => <span className="badge muted" key={`${badge}-${index}`}>{formatMetadataLabel(badge)}</span>)}
    </span>
  ) : null;
}

function metadataOptions(questions: Array<Record<string, unknown>>, key: string): string[] {
  const values = new Set<string>();
  questions.forEach((question) => {
    const value = objectValue(question.question_metadata)[key];
    if (Array.isArray(value)) {
      value.forEach((item) => { if (typeof item === "string" && item) values.add(item); });
    } else if (typeof value === "string" && value) {
      values.add(value);
    }
  });
  return Array.from(values).sort((left, right) => left.localeCompare(right));
}

function questionMatchesFilters(question: Record<string, unknown>, source: string, difficulty: string, tag: string): boolean {
  const metadata = objectValue(question.question_metadata);
  const tags = Array.isArray(metadata.tags) ? metadata.tags : [];
  return (!source || metadata.source === source)
    && (!difficulty || metadata.difficulty === difficulty)
    && (!tag || tags.includes(tag));
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function numericValue(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatMetadataLabel(value: string): string {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function ApiUsageSummary({ usage }: { usage: unknown }) {
  if (!usage || typeof usage !== "object") {
    return <div className="nested-empty">No API usage recorded.</div>;
  }
  const usageMap = usage as Record<string, unknown>;
  const reranking = usageMap.reranking;
  if (!reranking || typeof reranking !== "object") {
    return <div className="nested-empty">No API reranking usage recorded.</div>;
  }
  const data = reranking as Record<string, unknown>;
  const tokens = numericUsageValue(data.total_tokens) ?? numericUsageValue(data.estimated_tokens);
  const cost = numericUsageValue(data.estimated_cost_usd);
  const items = [
    stringUsageValue(data.provider),
    stringUsageValue(data.model),
    usageBadge(data.request_count, "requests"),
    usageBadge(data.candidate_count, "candidates"),
    tokens !== null ? `${formatInteger(tokens)} tokens` : "",
    usageBadge(data.retry_count, "retries"),
    cost !== null && cost > 0 ? `${formatUsd(cost)} estimated` : "",
    usageDuration(data.duration_seconds),
  ].filter(Boolean);
  if (items.length === 0) {
    return <div className="nested-empty">No API usage recorded.</div>;
  }
  return (
    <div className="asset-mini-summary api-usage-summary">
      {items.map((item, index) => (
        <span key={`${item}-${index}`}>{item}</span>
      ))}
    </div>
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

function errorStage(value: unknown): string {
  if (value && typeof value === "object" && "failed_stage" in value) {
    return String((value as { failed_stage?: unknown }).failed_stage ?? "");
  }
  return "";
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

function formatInteger(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}

function formatUsd(value: number): string {
  return new Intl.NumberFormat(undefined, {
    currency: "USD",
    maximumFractionDigits: 6,
    minimumFractionDigits: 2,
    style: "currency",
  }).format(value);
}

function numericUsageValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return null;
}

function stringUsageValue(value: unknown): string {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function usageBadge(value: unknown, label: string): string {
  const numberValue = numericUsageValue(value);
  return numberValue !== null ? `${formatInteger(numberValue)} ${label}` : "";
}

function usageDuration(value: unknown): string {
  const numberValue = numericUsageValue(value);
  return numberValue !== null ? `${numberValue.toFixed(2)} sec` : "";
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

function formatEvaluationResultSummary(question: Record<string, unknown>): string {
  if (question.status === "failed") {
    return `Failed: ${errorMessage(question.error_json)}`;
  }
  return formatEvaluationTopResult(question.top_result);
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
