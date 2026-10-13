import type { Project, SavedExperiment } from "../api/client";

export function buildExperimentExport(
  project: Pick<Project, "id" | "name">,
  experiment: SavedExperiment,
  exportedAt = new Date().toISOString(),
) {
  return {
    schema_version: "raglab.experiment_export.v1",
    exported_at: exportedAt,
    project: { id: project.id, name: project.name },
    analysis_context: {
      evaluation_scope: "retrieval",
      metrics_population: "completed questions contributing to each metric",
      metric_denominators_field: "metrics_summary_json.metric_question_counts",
      failed_questions_are_zero_scores: false,
      gt_page_index_base: 0,
      retrieved_page_number_base: 1,
      retrieved_text_included: false,
      pre_reranking_candidates_included: false,
      scope: "all saved results, independent of UI filters",
    },
    saved_experiment: experiment,
  };
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
