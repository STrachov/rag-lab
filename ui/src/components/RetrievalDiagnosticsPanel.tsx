import type { ReactNode } from "react";
import type { RetrievalPreviewResponse } from "../api/client";

function score(value: number | null): ReactNode {
  return value === null ? "—" : <span title={String(value)}>{value.toPrecision(7)}</span>;
}

function Table({ title, headers, rows }: { title: string; headers: string[]; rows: ReactNode[][] }) {
  return <div className="hybrid-diagnostic-table">
    <h4>{title}</h4>
    {rows.length ? <div className="hybrid-diagnostic-scroll"><table>
      <thead><tr>{headers.map(header => <th key={header} scope="col">{header}</th>)}</tr></thead>
      <tbody>{rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody>
    </table></div> : <p>No candidates.</p>}
  </div>;
}

export function RetrievalDiagnosticsPanel({ retrieval }: { retrieval: RetrievalPreviewResponse }) {
  const d = retrieval.diagnostics;
  if (!["dense", "hybrid"].includes(retrieval.mode) || !d) return null;
  const aggregation = d.parent_page_aggregation;
  return <details className="hybrid-diagnostics">
    <summary>Retrieval diagnostics</summary>
    <p>{d.fusion ? `${d.fusion.toUpperCase()} (${d.rrf_k})` : "Dense"} · Candidate stages before reranking · Up to 30 candidates / 5 parent pages</p>
    <Table title="Dense top candidates" headers={["Rank", "Page / parent", "chunk_id", "Score"]}
      rows={d.dense_candidates.slice(0, 30).map(r => [r.dense_rank, r.page ?? r.parent_id ?? "—", r.chunk_id, score(r.dense_score)])} />
    {retrieval.mode === "hybrid" ? <>
    <Table title="Sparse top candidates" headers={["Rank", "Page", "chunk_id", "Score"]}
      rows={d.sparse_candidates.slice(0, 30).map(r => [r.sparse_rank, r.page ?? "—", r.chunk_id, score(r.sparse_score)])} />
    <Table title="RRF candidates" headers={["Rank", "Page", "chunk_id", "dense_rank", "sparse_rank",
      "dense_contribution", "sparse_contribution", "fused_score"]}
      rows={d.fused_candidates.slice(0, 30).map(r => [r.fused_rank, r.page ?? "—", r.chunk_id,
        r.dense_rank ?? "—", r.sparse_rank ?? "—", score(r.dense_contribution),
        score(r.sparse_contribution), score(r.fused_score)])} />
    </> : null}
    {aggregation.applied ? <p>Parent aggregation displays only the top 5 parents (or fewer when top_k is smaller). Reranking uses all parent candidates, not just these displayed rows.</p> : null}
    {aggregation.applied ? <Table title={`Parent aggregation (${aggregation.parent_score})`}
      headers={["Rank", "Page", "Aggregate score", "Contributing child chunks"]}
      rows={aggregation.pages.slice(0, 5).map(r => [r.rank, r.page ?? "—", score(r.page_score),
        <ul className="hybrid-diagnostic-children">{r.child_chunks.map((child, i) => <li key={i}>
          <code>{child.chunk_id}</code> · {retrieval.mode === "hybrid" ? "RRF" : "Dense"} rank {child.rank} · {score(child.score)}
          {r.max_child_chunk_ids.includes(child.chunk_id) ? <strong> · max</strong> : null}
        </li>)}</ul>])} /> : <p>Parent-page aggregation was not applied ({aggregation.strategy}).</p>}
    {d.reranking?.length ? <Table title="Parent reranking"
      headers={["Final parent rank", "Pre-rerank parent rank", "Page / parent", "rerank_child_id", "Child retrieval rank",
        "Child retrieval score", "Original parent score", "Rerank score"]}
      rows={d.reranking.slice(0, 5).map(r => [r.final_parent_rank, r.pre_rerank_parent_rank, r.page ?? r.parent_id,
        r.rerank_child_id, r.selected_child_rank, score(r.selected_child_score),
        score(r.original_parent_score), score(r.rerank_score)])} /> : null}
  </details>;
}
