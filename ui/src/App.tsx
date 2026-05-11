import { useState } from "react";
import type { ReactNode } from "react";

import { AppShell, PageKey } from "./layout/AppShell";
import { ComparisonPage } from "./pages/ComparisonPage";
import { DataPage } from "./pages/DataPage";
import { GroundTruthPage } from "./pages/GroundTruthPage";
import { ParametersPage } from "./pages/ParametersPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { SavedExperimentsPage } from "./pages/SavedExperimentsPage";
import { SettingsPage } from "./pages/SettingsPage";

const pages: Record<PageKey, ReactNode> = {
  projects: <ProjectsPage />,
  data: <DataPage />,
  parameters: <ParametersPage />,
  groundTruth: <GroundTruthPage />,
  savedExperiments: <SavedExperimentsPage />,
  comparison: <ComparisonPage />,
  settings: <SettingsPage />,
};

export default function App() {
  const [activePage, setActivePage] = useState<PageKey>("projects");

  return (
    <AppShell activePage={activePage} onPageChange={setActivePage}>
      {pages[activePage]}
    </AppShell>
  );
}
