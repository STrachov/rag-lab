import { SavedExperiment } from "../api/client";

type Json = Record<string, unknown>;
type Snapshot = {
  data: { source: { files: Array<{ original_name: string }>; manifest_hash: string };
    prepared: { manifest_hash: string }; preparation: Json };
  chunking: { strategy: string; params: Json; size_unit: string; chunks_file_sha256: string };
  embedding: Json;
  sparse: Json | null;
  index: { cache_id: string; collection_name: string; mode: string; distance: string };
  retrieval: Json;
  reranking: Json | null;
  ground_truth: { canonical_sha256: string };
  semantics: Json;
};

function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
    .map(([key, item]) => `${JSON.stringify(key)}:${stable(item)}`).join(",")}}`;
  return JSON.stringify(value) ?? "null";
}

export function provenanceRows(experiment: SavedExperiment) {
  const s = experiment.params_snapshot_json as unknown as Snapshot;
  const evaluation = experiment.metrics_summary_json.evaluation as { code?: { dirty: boolean | null } } | undefined;
  const dirty = evaluation?.code?.dirty;
  return [
    ["Source files", s.data.source.files.map((file) => file.original_name).join(", ")],
    ["Source manifest", s.data.source.manifest_hash],
    ["Prepared manifest", s.data.prepared.manifest_hash],
    ["Preparation", stable(s.data.preparation)],
    ["Chunking", `${s.chunking.strategy}: ${s.chunking.params.chunk_size} / ${s.chunking.params.chunk_overlap} ${s.chunking.size_unit}`],
    ["Chunks SHA-256", s.chunking.chunks_file_sha256],
    ["Embedding", stable(s.embedding)],
    ["Sparse", stable(s.sparse ? Object.fromEntries(Object.entries(s.sparse).filter(([key]) => key !== "stats_file_sha256")) : null)],
    ["Index", `${s.index.cache_id} / ${s.index.collection_name}`],
    ["Index configuration", `${s.index.mode} / ${s.index.distance}`],
    ["Retrieval", stable(s.retrieval)],
    ["Reranker", stable(s.reranking)],
    ["GT canonical SHA-256", s.ground_truth.canonical_sha256],
    ["Semantics", stable(s.semantics)],
    ["Code commit", experiment.code_commit ?? "unavailable / not evaluated"],
    ["Working tree", dirty === true ? "dirty" : dirty === false ? "clean" : "unknown / not evaluated"],
  ];
}

function display(label: string, value: string) {
  return label.includes("SHA-256") || label.includes("manifest") ? `${value.slice(0, 18)}…` : value;
}

export function ExperimentProvenance({ experiment }: { experiment: SavedExperiment }) {
  return <div className="parameter-section"><h2>Reproducibility</h2>
    <dl className="provenance-fields">{provenanceRows(experiment).map(([label, value]) =>
      <div key={label}><dt>{label}</dt><dd title={value}>{display(label, value)}</dd></div>,
    )}</dl>
  </div>;
}

export function ProvenanceComparison({ experiments }: { experiments: SavedExperiment[] }) {
  const rows = experiments.map(provenanceRows);
  return <>
    <tr className="comparison-section-row"><th colSpan={experiments.length + 1}>Controlled variables and lineage</th></tr>
    {rows[0].map(([label], index) => {
      const values = rows.map((row) => row[index][1]);
      const differs = new Set(values).size > 1;
      return <tr key={label} className={differs ? "provenance-difference" : undefined}>
        <th>{label}{differs ? " — differs" : ""}</th>
        {values.map((value, i) => <td key={experiments[i].id} title={value}>{display(label, value)}</td>)}
      </tr>;
    })}
  </>;
}
