import { FormEvent, useEffect, useState } from "react";

import { createProject, listProjects, Project } from "../api/client";

type ProjectsPageProps = {
  currentProject: Project | null;
  onProjectOpen: (project: Project) => void;
};

export function ProjectsPage({ currentProject, onProjectOpen }: ProjectsPageProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    refreshProjects();
  }, []);

  function refreshProjects() {
    listProjects()
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

      <div className="table">
        <div className="table-row project-table table-head">
          <span>Name</span>
          <span>Domain</span>
          <span>Description</span>
          <span>Updated</span>
        </div>
        {projects.map((project) => (
          <div
            className={
              project.id === currentProject?.id
                ? "table-row project-table selected-row"
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
            <span>{new Date(project.updated_at).toLocaleString()}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
