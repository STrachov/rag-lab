import type { Project, SavedExperiment } from "../api/client";

export function buildExperimentExport(
  project: Pick<Project, "id" | "name">,
  experiment: SavedExperiment,
  exportedAt = new Date().toISOString(),
) {
  const snapshot = record(experiment.params_snapshot_json);
  const results = record(experiment.metrics_summary_json);
  const evaluation = record(results.evaluation);
  const data = record(snapshot.data);
  const sources: Json[] = [];
  const sourceIds = new Map<string, string>();
  const sourceId = (identity: string, name?: string): string => {
    const existing = sourceIds.get(identity);
    if (existing) return existing;
    const id = `s${sources.length + 1}`;
    sourceIds.set(identity, id);
    sources.push({ id, identity, name });
    return id;
  };
  const questions = array(results.questions).map((value) => {
    const question = record(value);
    const gt = record(question.ground_truth);
    const relevantPages = array(gt.relevant_pages).map((value) => {
      const page = record(value);
      const identity = text(page.pdf_sha1);
      return {
        ...without(page, ["pdf_sha1", "page_index", "page_number"]),
        source_id: identity ? sourceId(identity) : undefined,
        page_number: typeof page.page_index === "number" ? page.page_index + 1 : page.page_number,
      };
    });
    const retrieved = array(question.retrieved).map((value) => {
      const item = record(value);
      const name = text(item.source_name);
      // Hash-named source PDFs use the same identity as GT pdf_sha1.
      const identity = name.replace(/\.pdf$/i, "");
      const id = name ? sourceId(identity, name) : undefined;
      if (id) {
        const source = sources.find((entry) => entry.id === id);
        if (source && !source.name) source.name = name;
      }
      return { ...without(item, ["source_name"]), source_id: id };
    });
    const usage = Object.fromEntries(Object.entries(record(question.usage)).map(([stage, value]) =>
      [stage, without(record(value), ["provider", "model"])],
    ));
    return {
      ...without(question, ["top_result", "ground_truth", "retrieved", "usage", "expected_answer_type", "expected_answer_brief"]),
      ground_truth: {
        ...gt,
        expected_answer_type: gt.expected_answer_type ?? question.expected_answer_type,
        expected_answer_brief: gt.expected_answer_brief ?? question.expected_answer_brief,
        relevant_pages: relevantPages,
      },
      retrieved,
      usage,
    };
  });
  const gt = record(snapshot.ground_truth);
  const summary = {
    ...without(evaluation, ["ground_truth_set_id", "ground_truth_manifest_hash", "canonical_sha256", "input_chunks_sha256", "semantics", "code", "ground_truth_schema_version", "ground_truth_annotation_schema_version", "ground_truth_annotation_version", "index_cache_id", "reranking", "retrieval", "schema_version", "status"]),
    ...without(results, ["evaluation", "questions"]),
  };
  return compact({
    schema_version: "raglab.experiment_export.v2",
    exported_at: exportedAt,
    project: { name: project.name },
    analysis_context: {
      evaluation_scope: "retrieval",
      metrics_population: "completed questions contributing to each metric",
      metric_denominators_field: "summary.metric_question_counts",
      failed_questions_are_zero_scores: false,
      page_number_base: 1,
      retrieved_text_included: false,
      pre_reranking_candidates_included: false,
      scope: "all saved results, independent of UI filters",
      omitted_values: "null, empty arrays and empty objects; missing metrics are unavailable, not zero",
    },
    experiment: {
      id: experiment.id, name: experiment.name, status: experiment.status, notes: experiment.notes,
      created_at: experiment.created_at, started_at: experiment.started_at, finished_at: experiment.finished_at,
      error: experiment.error_json,
    },
    configuration: {
      preparation: without(record(data.preparation), ["service", "source_manifest_hash"]),
      chunking: without(record(snapshot.chunking), ["cache_id", "cache_key", "chunks_file_sha256"]),
      embedding: snapshot.embedding,
      sparse: without(record(snapshot.sparse), ["stats_file_sha256", "schema_version"]),
      index: without(record(snapshot.index), ["cache_id", "cache_key", "collection_name", "params_hash", "input_chunks_sha256"]),
      retrieval: snapshot.retrieval, reranking: snapshot.reranking,
      ground_truth: without(gt, ["ground_truth_set_id", "manifest_hash", "canonical_sha256", ...(results.slice_metrics ? ["evaluation_slices"] : [])]),
    },
    provenance: {
      params_hash: experiment.params_hash, code: evaluation.code ?? { commit: experiment.code_commit },
      pipeline_version: experiment.pipeline_version, semantics: snapshot.semantics,
      source: manifestProvenance(data.source), prepared: manifestProvenance(data.prepared),
      ground_truth: { canonical_sha256: gt.canonical_sha256, manifest_hash: gt.manifest_hash },
      chunks_sha256: record(snapshot.chunking).chunks_file_sha256,
      sparse_stats_sha256: record(snapshot.sparse).stats_file_sha256,
    },
    sources,
    summary,
    questions,
  });
}

type Json = Record<string, unknown>;
function record(value: unknown): Json {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Json : {};
}
function array(value: unknown): unknown[] { return Array.isArray(value) ? value : []; }
function text(value: unknown): string { return typeof value === "string" ? value : ""; }
function without(value: Json, keys: string[]): Json {
  return Object.fromEntries(Object.entries(value).filter(([key]) => !keys.includes(key)));
}
function manifestProvenance(value: unknown): Json {
  const manifest = record(value);
  return {
    manifest_hash: manifest.manifest_hash,
    files: array(manifest.files).map((value) => without(record(value), ["stored_path", "source", "size_bytes", "content_type"])),
  };
}
function compact(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(compact);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, compact(item)])
      .filter(([, item]) => item !== null && item !== undefined &&
        !(typeof item === "object" && Object.keys(item).length === 0)));
  }
  return value;
}

export function downloadExperimentExport(project: Project, experiment: SavedExperiment): void {
  const content = JSON.stringify(buildExperimentExport(project, experiment), null, 2);
  const blob = new Blob([content], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `raglab-experiment-${experiment.id.slice(0, 12)}.json`;
  document.body.appendChild(anchor);
  try {
    anchor.click();
  } finally {
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
