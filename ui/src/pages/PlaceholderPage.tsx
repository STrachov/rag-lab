type PlaceholderPageProps = {
  eyebrow: string;
  title: string;
  body: string;
  emptyMessage?: string;
};

export function PlaceholderPage({ eyebrow, title, body, emptyMessage }: PlaceholderPageProps) {
  return (
    <section className="page">
      <header className="page-header">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{body}</p>
      </header>
      <div className="empty-state">{emptyMessage ?? "Not implemented in the foundation pass."}</div>
    </section>
  );
}
