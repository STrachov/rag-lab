export function RecipesPage() {
  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">Production handoff</p>
        <h1>Recipes</h1>
        <p>Validated production-ready RAG settings will be exported from this screen.</p>
      </header>
      <div className="empty-state">No recipes have been promoted yet.</div>
    </section>
  );
}
