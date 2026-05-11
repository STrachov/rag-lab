import { useState } from "react";

import { AppShell, PageKey } from "./layout/AppShell";
import { AnswerPlaygroundPage } from "./pages/AnswerPlaygroundPage";
import { ChunkExplorerPage } from "./pages/ChunkExplorerPage";
import { DatasetsPage } from "./pages/DatasetsPage";
import { ExperimentComparisonPage } from "./pages/ExperimentComparisonPage";
import { RecipesPage } from "./pages/RecipesPage";
import { ReportsPage } from "./pages/ReportsPage";
import { RetrievalPlaygroundPage } from "./pages/RetrievalPlaygroundPage";

const pages: Record<PageKey, React.ReactNode> = {
  datasets: <DatasetsPage />,
  chunks: <ChunkExplorerPage />,
  retrieval: <RetrievalPlaygroundPage />,
  answer: <AnswerPlaygroundPage />,
  experiments: <ExperimentComparisonPage />,
  reports: <ReportsPage />,
  recipes: <RecipesPage />,
};

export default function App() {
  const [activePage, setActivePage] = useState<PageKey>("datasets");

  return (
    <AppShell activePage={activePage} onPageChange={setActivePage}>
      {pages[activePage]}
    </AppShell>
  );
}
