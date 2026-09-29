import Link from "next/link";

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.replaceAll("_", " ");
  return <span className={`badge badge-${status.toLowerCase()}`}>{normalized}</span>;
}

export function RoleBadge({ role }: { role: string }) {
  return <span className="badge badge-role">{role.replaceAll("_", " ")}</span>;
}

export function MetricCard({
  label,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  value: string | number;
  detail?: string;
  tone?: "default" | "good" | "warn" | "bad" | "accent";
}) {
  return (
    <div className={`metric metric-${tone}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {detail ? <div className="metric-detail">{detail}</div> : null}
    </div>
  );
}

export function ProgressBar({
  value,
  label,
  detail,
}: {
  value: number;
  label?: string;
  detail?: string;
}) {
  const safe = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
  return (
    <div className="progress-wrap">
      {(label || detail) && (
        <div className="progress-head">
          {label ? <span>{label}</span> : <span />}
          {detail ? <span className="muted">{detail}</span> : null}
        </div>
      )}
      <div className="progress">
        <div style={{ width: `${safe}%` }} />
      </div>
    </div>
  );
}

export function SectionTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <h2>{title}</h2>
        {description ? <p className="muted section-description">{description}</p> : null}
      </div>
      {action ? <div className="section-action">{action}</div> : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  href,
  action,
}: {
  title: string;
  description: string;
  href?: string;
  action?: string;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">○</div>
      <h3>{title}</h3>
      <p className="muted">{description}</p>
      {href && action ? (
        <Link className="button" href={href}>
          {action}
        </Link>
      ) : null}
    </div>
  );
}

export function TagList({ tags, limit = 8 }: { tags: string[]; limit?: number }) {
  const visible = tags.slice(0, limit);
  return (
    <div className="tag-list">
      {visible.map((tag) => (
        <span className="tag" key={tag}>
          {tag}
        </span>
      ))}
      {tags.length > limit ? <span className="tag tag-muted">+{tags.length - limit}</span> : null}
    </div>
  );
}

export function LoadingGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid">
      {Array.from({ length: count }).map((_, index) => (
        <div className="card skeleton-card" key={index}>
          <div className="skeleton skeleton-line wide" />
          <div className="skeleton skeleton-line" />
          <div className="skeleton skeleton-block" />
        </div>
      ))}
    </div>
  );
}

export function CodeValue({ children }: { children: React.ReactNode }) {
  return <span className="code-value">{children}</span>;
}
