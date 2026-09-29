"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { apiFetch } from "../../../../lib/api";

type Media = { id: string; url: string; caption: string; sort_order: number };
type Item = {
  id: string;
  event_id: string;
  team_id: string;
  team_name: string;
  track_id: string | null;
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
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load project."));
  }, [eventId, submissionId]);

  if (error) return <main><div className="error">{error}</div></main>;
  if (!item) return <main><div className="card"><p>Loading project…</p></div></main>;

  return (
    <main>
      <Link className="button secondary" href={`/gallery/${eventId}`}>← Back to gallery</Link>

      <article className="card" style={{ marginTop: 18 }}>
        <div className="row">
          {item.track_name && <span className="pill">{item.track_name}</span>}
          <span className="pill">Team: {item.team_name}</span>
        </div>

        <h1>{item.name}</h1>
        <p style={{ fontSize: 18 }}>{item.tagline}</p>
        <p className="muted">Submitted {new Date(item.submitted_at).toLocaleString()}</p>

        {item.thumbnail_url ? (
          <img
            src={item.thumbnail_url}
            alt={`${item.name} thumbnail`}
            style={{ width: "100%", maxHeight: 520, objectFit: "cover", borderRadius: 14, margin: "18px 0" }}
          />
        ) : null}

        <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>{item.description}</p>

        <div className="row" style={{ marginTop: 18 }}>
          {item.tech_tags.map((tech) => <span key={tech} className="pill">{tech}</span>)}
        </div>

        <div className="row" style={{ marginTop: 18 }}>
          {item.live_url && <a className="button" href={item.live_url} target="_blank" rel="noreferrer">Open live demo</a>}
          {item.repository_url && <a className="button secondary" href={item.repository_url} target="_blank" rel="noreferrer">Repository</a>}
          {item.demo_video_url && <a className="button secondary" href={item.demo_video_url} target="_blank" rel="noreferrer">Demo video</a>}
        </div>
      </article>

      {item.media.length > 0 && (
        <section>
          <h2>Project media</h2>
          <div className="grid">
            {item.media.map((media) => (
              <figure className="card" key={media.id}>
                <img src={media.url} alt={media.caption || item.name} style={{ width: "100%", borderRadius: 12 }} />
                {media.caption && <figcaption className="muted" style={{ marginTop: 8 }}>{media.caption}</figcaption>}
              </figure>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
