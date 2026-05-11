import type { ReactNode } from "react";

export type PageKey =
  | "projects"
  | "data"
  | "parameters"
  | "groundTruth"
  | "savedExperiments"
  | "comparison"
  | "settings";

const navItems: Array<{ key: PageKey; label: string }> = [
  { key: "projects", label: "Projects" },
  { key: "data", label: "Data" },
  { key: "parameters", label: "Parameters" },
  { key: "groundTruth", label: "Ground Truth" },
  { key: "savedExperiments", label: "Saved Experiments" },
  { key: "comparison", label: "Comparison" },
  { key: "settings", label: "Settings" },
];

type AppShellProps = {
  activePage: PageKey;
  children: ReactNode;
  onPageChange: (page: PageKey) => void;
};

export function AppShell({ activePage, children, onPageChange }: AppShellProps) {
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
      <main className="main-panel">{children}</main>
    </div>
  );
}
