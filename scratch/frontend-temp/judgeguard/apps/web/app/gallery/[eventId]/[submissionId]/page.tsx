"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "../../../../lib/api";
import { TagList } from "../../../../components/ui";

type Media = { id: string; url: string; caption: string; sort_order: number };
type Item = {
  id: string;
  event_id: string;
  team_id: string;
  team_name: string;
  track_name: string | null;
  name: string;
  tagline: string;
  description: string;
  thumbnail_url: string | null;
  demo_video_url: string | null;
  repository_url: string | null;
  live_url: string | null;
  tech_tags: string[];
  submitted_at: string;
  media: Media[];
};

export default function GallerySubmissionPage() {
  const { eventId, submissionId } = useParams<{ eventId: string; submissionId: string }>();
  const [item, setItem] = useState<Item | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Item>(`/events/${eventId}/gallery/${submissionId}`)
      .then(setItem)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load project"));
  }, [eventId, submissionId]);

  if (error) return <div className="error-banner">{error}</div>;
  if (!item) return <div className="card"><div className="skeleton skeleton-line wide" /><div className="skeleton skeleton-block" /></div>;

  return (
    <>
      <div className="page-heading">
        <div>
          <Link className="text-link" href={`/gallery/${eventId}`}>← Back to gallery</Link>
          <div className="project-badges">
            {item.track_name ? <span className="badge badge-role">{item.track_name}</span> : null}
            <span className="badge badge-role">Team · {item.team_name}</span>
          </div>
          <h1>{item.name}</h1>
          <p className="hero-lead detail-lead">{item.tagline}</p>
        </div>
      </div>

      <div className="detail-layout">
        <article className="detail-main">
          <div className="detail-hero">
            {item.thumbnail_url ? <img src={item.thumbnail_url} alt={item.name} /> : <div className="detail-placeholder"><span>JG</span></div>}
          </div>
          <div className="detail-panel">
            <div className="eyebrow">PROJECT BRIEF</div>
            <p className="detail-description">{item.description}</p>
            <TagList tags={item.tech_tags} limit={20} />
          </div>

          {item.media.length ? (
            <section className="detail-panel">
              <div className="section-title">
                <div><div className="eyebrow">MEDIA</div><h2>Project media</h2></div>
              </div>
              <div className="media-grid">
                {item.media.map((media) => (
                  <figure className="media-card" key={media.id}>
                    <img src={media.url} alt={media.caption || item.name} />
                    {media.caption ? <figcaption>{media.caption}</figcaption> : null}
                  </figure>
                ))}
              </div>
            </section>
          ) : null}
        </article>

        <aside className="detail-side">
          <div className="card sticky-card">
            <div className="eyebrow">SUBMISSION</div>
            <div className="meta-list">
              <div><span>Team</span><strong>{item.team_name}</strong></div>
              <div><span>Track</span><strong>{item.track_name ?? "Unassigned"}</strong></div>
              <div><span>Submitted</span><strong>{new Date(item.submitted_at).toLocaleString()}</strong></div>
            </div>
            <div className="divider" />
            <div className="stack-actions">
              {item.live_url ? <a className="button" href={item.live_url} target="_blank" rel="noreferrer">Open live demo ↗</a> : null}
              {item.repository_url ? <a className="button ghost" href={item.repository_url} target="_blank" rel="noreferrer">Repository ↗</a> : null}
              {item.demo_video_url ? <a className="button ghost" href={item.demo_video_url} target="_blank" rel="noreferrer">Demo video ↗</a> : null}
            </div>
          </div>
        </aside>
      </div>
    </>
  );
}
