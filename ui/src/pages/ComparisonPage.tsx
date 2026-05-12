import { PlaceholderPage } from "./PlaceholderPage";
import type { Project } from "../api/client";

type ComparisonPageProps = {
  currentProject: Project | null;
};

export function ComparisonPage({ currentProject }: ComparisonPageProps) {
  if (!currentProject) {
    return (
      <PlaceholderPage
        eyebrow="Comparison"
        title="Metrics Comparison"
        body="Select or create a project first. Comparisons are made across saved experiments in the current project."
        emptyMessage="No project selected."
      />
    );
  }

  return (
    <PlaceholderPage
      eyebrow="Comparison"
      title="Metrics Comparison"
      body={`Saved experiments in ${currentProject.name} will be compared by retrieval, citation, quality, latency, and cost metrics.`}
    />
  );
}
