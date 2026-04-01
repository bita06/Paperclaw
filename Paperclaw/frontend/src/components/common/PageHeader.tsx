type PageHeaderProps = {
  title: string;
  description: string;
  kicker?: string;
};

export function PageHeader({ title, description, kicker = "TSINGHUA SPPM INTERNAL PLATFORM" }: PageHeaderProps) {
  return (
    <header className="page-header">
      <span className="section-kicker page-kicker">{kicker}</span>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}
