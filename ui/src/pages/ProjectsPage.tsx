import { FormEvent, useEffect, useState } from "react";

import {
  createProject,
  listProjects,
  Project,
  ProjectStatus,
  updateProject,
} from "../api/client";

const ACTIVE_ONLY_STORAGE_KEY = "rag-lab:projects-active-only";

type ProjectsPageProps = {
  currentProject: Project | null;
  onProjectOpen: (project: Project) => void;
  onProjectUpdated: (project: Project) => void;
};

export function ProjectsPage({
  currentProject,
  onProjectOpen,
  onProjectUpdated,
}: ProjectsPageProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [activeOnly, setActiveOnly] = useState(
    () => window.localStorage.getItem(ACTIVE_ONLY_STORAGE_KEY) !== "false",
  );

  useEffect(() => {
    refreshProjects();
  }, [activeOnly]);

  function refreshProjects() {
    listProjects(activeOnly ? "active" : undefined)
      .then((result) => {
        setProjects(result.projects);
        setError(null);
      })
      .catch((err: Error) => setError(err.message));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      return;
    }

    try {
      const project = await createProject({
        description: description.trim() || undefined,
        domain: domain.trim() || undefined,
        name: name.trim(),
      });
      setProjects((current) => [...current, project]);
      onProjectOpen(project);
      setName("");
      setDomain("");
      setDescription("");
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    }
  }

  function handleActiveOnlyChange(checked: boolean) {
    setActiveOnly(checked);
    window.localStorage.setItem(ACTIVE_ONLY_STORAGE_KEY, String(checked));
  }

  async function handleStatusChange(project: Project) {
    const status: ProjectStatus = project.status === "active" ? "archived" : "active";
    try {
      const updated = await updateProject(project.id, { status });
      onProjectUpdated(updated);
      setProjects((current) => {
        if (activeOnly && updated.status !== "active") {
          return current.filter((item) => item.id !== updated.id);
        }
        return current.map((item) => (item.id === updated.id ? updated : item));
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update project");
    }
  }

  function handleProjectSaved(project: Project) {
    onProjectUpdated(project);
    setProjects((current) => {
      if (activeOnly && project.status !== "active") {
        return current.filter((item) => item.id !== project.id);
      }
      return current.map((item) => (item.id === project.id ? project : item));
    });
    setEditingProject(null);
    setError(null);
  }

  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Projects</p>
        <h1>Project workspaces</h1>
        <p>Create durable RAG evaluation workspaces for data, parameters, ground truth, and metrics.</p>
      </header>

      {currentProject ? (
        <div className="notice neutral">
          Open project: <strong>{currentProject.name}</strong>. Data, parameters, ground truth, and
          experiments now load in this project context.
        </div>
      ) : null}

      <form className="form-panel" onSubmit={handleSubmit}>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Domain
          <input value={domain} onChange={(event) => setDomain(event.target.value)} />
        </label>
        <label className="form-wide">
          Description
          <input value={description} onChange={(event) => setDescription(event.target.value)} />
        </label>
        <button type="submit">Create Project</button>
      </form>

      {error ? <div className="notice">Backend unavailable: {error}</div> : null}

      <div className="project-list-toolbar">
        <label className="check-row">
          <input
            checked={activeOnly}
            onChange={(event) => handleActiveOnlyChange(event.target.checked)}
            type="checkbox"
          />
          Show active projects only
        </label>
        <span>
          {projects.length} {projects.length === 1 ? "project" : "projects"}
        </span>
      </div>

      <div className="table project-list-table">
        <div className="table-row project-table table-head">
          <span>Name</span>
          <span>Domain</span>
          <span>Description</span>
          <span>Status</span>
          <span>Updated</span>
          <span>Actions</span>
        </div>
        {projects.map((project) => (
          <div
            className={
              project.id === currentProject?.id
                ? "table-row project-table selected-row"
                : project.status === "archived"
                  ? "table-row project-table archived-row"
                  : "table-row project-table"
            }
            key={project.id}
          >
            <span>
              <button
                className="project-link"
                onClick={() => onProjectOpen(project)}
                type="button"
              >
                {project.name}
              </button>
              {project.id === currentProject?.id ? <small className="current-tag">Current</small> : null}
            </span>
            <span>{project.domain ?? "-"}</span>
            <span>{project.description ?? "-"}</span>
            <span>
              <span className={`status-tag ${project.status}`}>{project.status}</span>
            </span>
            <span>{new Date(project.updated_at).toLocaleString()}</span>
            <span className="row-actions">
              <button
                aria-label={`Edit ${project.name}`}
                className="icon-action"
                onClick={() => setEditingProject(project)}
                title="Edit project"
                type="button"
              >
                ✎
              </button>
              <button
                aria-label={
                  project.status === "active"
                    ? `Archive ${project.name}`
                    : `Activate ${project.name}`
                }
                className="icon-action"
                onClick={() => handleStatusChange(project)}
                title={project.status === "active" ? "Archive project" : "Activate project"}
                type="button"
              >
                {project.status === "active" ? <ArchiveIcon /> : <RestoreIcon />}
              </button>
            </span>
          </div>
        ))}
        {projects.length === 0 ? (
          <div className="project-list-empty">
            {activeOnly ? "No active projects." : "No projects yet."}
          </div>
        ) : null}
      </div>

      {editingProject ? (
        <ProjectEditModal
          onClose={() => setEditingProject(null)}
          onSaved={handleProjectSaved}
          project={editingProject}
        />
      ) : null}
    </section>
  );
}

function ArchiveIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" className="lucide lucide-archive-icon lucide-archive">
      <rect width="20" height="5" x="2" y="3" rx="1"/>
      <path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/>
      <path d="M10 12h4"/>
    </svg>
  );
}

function RestoreIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" className="lucide lucide-archive-restore-icon lucide-archive-restore">
      <rect width="20" height="5" x="2" y="3" rx="1"/>
      <path d="M4 8v11a2 2 0 0 0 2 2h2"/>
      <path d="M20 8v11a2 2 0 0 1-2 2h-2"/>
      <path d="m9 15 3-3 3 3"/>
      <path d="M12 12v9"/>
    </svg>
  );
}

function ProjectEditModal({
  onClose,
  onSaved,
  project,
}: {
  onClose: () => void;
  onSaved: (project: Project) => void;
  project: Project;
}) {
  const [name, setName] = useState(project.name);
  const [domain, setDomain] = useState(project.domain ?? "");
  const [description, setDescription] = useState(project.description ?? "");
  const [status, setStatus] = useState<ProjectStatus>(project.status);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Project name cannot be empty");
      return;
    }
    setSaving(true);
    try {
      const updated = await updateProject(project.id, {
        description: description.trim() || null,
        domain: domain.trim() || null,
        name: name.trim(),
        status,
      });
      onSaved(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update project");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <div aria-modal="true" className="modal-panel project-edit-modal" role="dialog">
        <header className="modal-header">
          <h2>Edit project</h2>
          <button className="text-action" onClick={onClose} type="button">
            Close
          </button>
        </header>
        <form className="modal-form two-column" onSubmit={handleSubmit}>
          <label>
            Name
            <input
              autoFocus
              maxLength={255}
              onChange={(event) => setName(event.target.value)}
              required
              value={name}
            />
          </label>
          <label>
            Domain
            <input
              maxLength={255}
              onChange={(event) => setDomain(event.target.value)}
              value={domain}
            />
          </label>
          <label className="wide-field">
            Description
            <textarea
              onChange={(event) => setDescription(event.target.value)}
              rows={5}
              value={description}
            />
          </label>
          <label>
            Status
            <select
              onChange={(event) => setStatus(event.target.value as ProjectStatus)}
              value={status}
            >
              <option value="active">Active</option>
              <option value="archived">Archived</option>
            </select>
          </label>
          {error ? <div className="notice wide-field">{error}</div> : null}
          <button className="primary-action" disabled={saving} type="submit">
            {saving ? "Saving..." : "Save changes"}
          </button>
        </form>
      </div>
    </div>
  );
}
