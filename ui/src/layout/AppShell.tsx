import type { ReactNode } from "react";

import type { Project } from "../api/client";

export type PageKey =
  | "projects"
  | "data"
  | "parameters"
  | "indexing"
  | "groundTruth"
  | "savedExperiments"
  | "comparison"
  | "settings";

const navItems: Array<{ key: PageKey; label: string }> = [
  { key: "projects", label: "Projects" },
  { key: "data", label: "Data" },
  { key: "parameters", label: "Parameters" },
  { key: "indexing", label: "Indexing" },
  { key: "groundTruth", label: "Ground Truth" },
  { key: "savedExperiments", label: "Saved Experiments" },
  { key: "comparison", label: "Comparison" },
  { key: "settings", label: "Settings" },
];

type AppShellProps = {
  activePage: PageKey;
  children: ReactNode;
  currentProject: Project | null;
  onPageChange: (page: PageKey) => void;
};

export function AppShell({ activePage, children, currentProject, onPageChange }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">RL</span>
          <div>
            <strong>RAG Lab</strong>
            <span>Project workbench</span>
          </div>
        </div>
        <div className="project-context">
          <span>Current project</span>
          <strong>{currentProject ? currentProject.name : "None selected"}</strong>
          {currentProject?.domain ? <small>{currentProject.domain}</small> : null}
        </div>
        <nav className="nav-list" aria-label="Primary">
          {navItems.map((item) => (
            <button
              className={item.key === activePage ? "nav-item active" : "nav-item"}
              key={item.key}
              onClick={() => onPageChange(item.key)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="main-panel">
        {currentProject ? (
          <div className="context-bar">
            <div>
              <span>Project</span>
              <strong>{currentProject.name}</strong>
            </div>
            <div>
              <span>Status</span>
              <strong>{currentProject.status}</strong>
            </div>
            {currentProject.domain ? (
              <div>
                <span>Domain</span>
                <strong>{currentProject.domain}</strong>
              </div>
            ) : null}
          </div>
        ) : null}
        {children}
      </main>
    </div>
  );
}
