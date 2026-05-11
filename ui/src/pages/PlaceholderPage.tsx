type PlaceholderPageProps = {
  eyebrow: string;
  title: string;
  body: string;
};

export function PlaceholderPage({ eyebrow, title, body }: PlaceholderPageProps) {
  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{body}</p>
      </header>
      <div className="empty-state">Not implemented in the foundation pass.</div>
    </section>
  );
}
