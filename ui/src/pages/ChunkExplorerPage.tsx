export function ChunkExplorerPage() {
  return <PlaceholderPage title="Chunk Explorer" body="Chunk manifests and source-aware text units will appear here." />;
}

function PlaceholderPage({ title, body }: { title: string; body: string }) {
  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Workbench</p>
        <h1>{title}</h1>
        <p>{body}</p>
      </header>
      <div className="empty-state">Not implemented in the initial skeleton.</div>
    </section>
  );
}
