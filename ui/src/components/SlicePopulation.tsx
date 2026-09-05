export type SliceMetricSummary = {
  filter?: Record<string, unknown>;
  label?: string;
  question_count?: number | null;
  completed_question_count?: number | null;
  error_count?: number | null;
  metric_averages?: Record<string, unknown>;
  metric_question_counts?: Record<string, number>;
  warnings?: string[];
};

export function SlicePopulation({ slice }: { slice: SliceMetricSummary }) {
  const total = slice.question_count;
  const completed = slice.completed_question_count;
  const recorded = typeof total === "number" && typeof completed === "number";
  const incomplete = recorded && completed < total;
  return (
    <span>
      {recorded ? `${completed}/${total} completed` : `${total ?? "-"} questions (completion not recorded)`}
      {typeof slice.error_count === "number" ? ` (${slice.error_count} errors)` : ""}
      {incomplete ? (
        <strong className="slice-warning">
          {completed === 0 ? "Incomplete: no questions completed successfully." : "Incomplete: metrics use completed rows only."}
        </strong>
      ) : null}
      {slice.warnings?.map((warning, index) => <small className="slice-warning" key={index}>{warning}</small>)}
    </span>
  );
}

export function SliceMetricValue({ value, count }: { value: unknown; count?: number }) {
  return (
    <span>
      {typeof value === "number" ? value.toFixed(3) : "-"}
      {typeof count === "number" ? ` (n=${count})` : ""}
    </span>
  );
}
