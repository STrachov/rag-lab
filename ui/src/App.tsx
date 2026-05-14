import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  Navigate,
  Route,
  Routes,
  matchPath,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";

import { getProject, Project } from "./api/client";
import { AppShell, PageKey } from "./layout/AppShell";
import { ComparisonPage } from "./pages/ComparisonPage";
import { DataPage } from "./pages/DataPage";
import { GroundTruthPage } from "./pages/GroundTruthPage";
import { IndexingPage } from "./pages/IndexingPage";
import { ParametersPage } from "./pages/ParametersPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { SavedExperimentsPage } from "./pages/SavedExperimentsPage";
import { SettingsPage } from "./pages/SettingsPage";

const SELECTED_PROJECT_STORAGE_KEY = "rag-lab:selected-project-id";

const pagePathByKey: Record<Exclude<PageKey, "projects">, string> = {
  chunking: "chunking",
  comparison: "comparison",
  data: "data",
  groundTruth: "ground-truth",
  retrieval: "retrieval",
  savedExperiments: "saved-experiments",
  settings: "settings",
};

export default function App() {
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [isProjectLoading, setIsProjectLoading] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const routeProjectId = getRouteProjectId(location.pathname);
  const activePage = getActivePage(location.pathname);

  useEffect(() => {
    if (routeProjectId) {
      setIsProjectLoading(true);
      getProject(routeProjectId)
        .then((project) => {
          setCurrentProject(project);
          window.localStorage.setItem(SELECTED_PROJECT_STORAGE_KEY, project.id);
        })
        .catch(() => {
          setCurrentProject(null);
          window.localStorage.removeItem(SELECTED_PROJECT_STORAGE_KEY);
          navigate("/projects", { replace: true });
        })
        .finally(() => setIsProjectLoading(false));
      return;
    }

    const storedProjectId = window.localStorage.getItem(SELECTED_PROJECT_STORAGE_KEY);
    if (!storedProjectId) {
      setCurrentProject(null);
      return;
    }

    getProject(storedProjectId)
      .then(setCurrentProject)
      .catch(() => window.localStorage.removeItem(SELECTED_PROJECT_STORAGE_KEY));
  }, [navigate, routeProjectId]);

  function handleProjectOpen(project: Project) {
    setCurrentProject(project);
    window.localStorage.setItem(SELECTED_PROJECT_STORAGE_KEY, project.id);
    navigate(`/projects/${project.id}/data`);
  }

  function handlePageChange(page: PageKey) {
    if (page === "projects") {
      navigate("/projects");
      return;
    }

    if (!currentProject) {
      navigate("/projects");
      return;
    }

    navigate(`/projects/${currentProject.id}/${pagePathByKey[page]}`);
  }

  const projectScopedPage = (page: ReactNode) =>
    isProjectLoading || (routeProjectId && currentProject?.id !== routeProjectId) ? (
      <LoadingProjectPage />
    ) : (
      page
    );

  return (
    <AppShell activePage={activePage} currentProject={currentProject} onPageChange={handlePageChange}>
      <Routes>
        <Route
          element={<ProjectsPage currentProject={currentProject} onProjectOpen={handleProjectOpen} />}
          path="/projects"
        />
        <Route element={<ProjectIndexRedirect />} path="/projects/:projectId" />
        <Route
          element={projectScopedPage(<DataPage currentProject={currentProject} />)}
          path="/projects/:projectId/data"
        />
        <Route
          element={projectScopedPage(<ParametersPage currentProject={currentProject} />)}
          path="/projects/:projectId/chunking"
        />
        <Route
          element={projectScopedPage(<IndexingPage currentProject={currentProject} />)}
          path="/projects/:projectId/retrieval"
        />
        <Route element={<LegacyProjectRedirect target="chunking" />} path="/projects/:projectId/parameters" />
        <Route element={<LegacyProjectRedirect target="retrieval" />} path="/projects/:projectId/indexing" />
        <Route
          element={projectScopedPage(<GroundTruthPage currentProject={currentProject} />)}
          path="/projects/:projectId/ground-truth"
        />
        <Route
          element={projectScopedPage(<SavedExperimentsPage currentProject={currentProject} />)}
          path="/projects/:projectId/saved-experiments"
        />
        <Route
          element={projectScopedPage(<ComparisonPage currentProject={currentProject} />)}
          path="/projects/:projectId/comparison"
        />
        <Route
          element={projectScopedPage(<SettingsPage currentProject={currentProject} />)}
          path="/projects/:projectId/settings"
        />
        <Route element={<Navigate replace to="/projects" />} path="*" />
      </Routes>
    </AppShell>
  );
}

function ProjectIndexRedirect() {
  const { projectId } = useParams();
  return <Navigate replace to={projectId ? `/projects/${projectId}/data` : "/projects"} />;
}

function LegacyProjectRedirect({ target }: { target: string }) {
  const { projectId } = useParams();
  const { search } = useLocation();
  return <Navigate replace to={projectId ? `/projects/${projectId}/${target}${search}` : "/projects"} />;
}

function LoadingProjectPage() {
  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Project</p>
        <h1>Loading project</h1>
        <p>Restoring the project context from the URL.</p>
      </header>
      <div className="empty-state">Loading project...</div>
    </section>
  );
}

function getRouteProjectId(pathname: string): string | null {
  const match = matchPath("/projects/:projectId/*", pathname) ?? matchPath("/projects/:projectId", pathname);
  return match?.params.projectId ?? null;
}

function getActivePage(pathname: string): PageKey {
  if (matchPath("/projects/:projectId/data", pathname)) {
    return "data";
  }
  if (matchPath("/projects/:projectId/chunking", pathname) || matchPath("/projects/:projectId/parameters", pathname)) {
    return "chunking";
  }
  if (matchPath("/projects/:projectId/retrieval", pathname) || matchPath("/projects/:projectId/indexing", pathname)) {
    return "retrieval";
  }
  if (matchPath("/projects/:projectId/ground-truth", pathname)) {
    return "groundTruth";
  }
  if (matchPath("/projects/:projectId/saved-experiments", pathname)) {
    return "savedExperiments";
  }
  if (matchPath("/projects/:projectId/comparison", pathname)) {
    return "comparison";
  }
  if (matchPath("/projects/:projectId/settings", pathname)) {
    return "settings";
  }
  return "projects";
}
