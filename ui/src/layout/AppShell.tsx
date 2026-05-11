import type { ReactNode } from "react";

export type PageKey =
  | "datasets"
  | "chunks"
  | "retrieval"
  | "answer"
  | "experiments"
  | "reports"
  | "recipes";

const navItems: Array<{ key: PageKey; label: string }> = [
  { key: "datasets", label: "Datasets" },
  { key: "chunks", label: "Chunk Explorer" },
  { key: "retrieval", label: "Retrieval Playground" },
  { key: "answer", label: "Answer Playground" },
  { key: "experiments", label: "Experiment Comparison" },
  { key: "reports", label: "Reports" },
  { key: "recipes", label: "Recipes" },
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
            <span>Experiment workbench</span>
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
