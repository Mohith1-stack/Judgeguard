"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "../../../lib/api";

type Item = { id: string; name: string; tagline: string; tech_tags: string[]; thumbnail_url: string | null; track_name: string | null };

export default function EmbedPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [items, setItems] = useState<Item[]>([]);

  useEffect(() => {
    apiFetch<{ items: Item[] }>(`/events/${eventId}/gallery?sort=RANDOM&page=1&page_size=12`)
      .then((data) => setItems(data.items))
      .catch(() => setItems([]));
  }, [eventId]);

  return (
    <main className="embed-shell">
      <div className="embed-head">
        <div>
          <div className="eyebrow">JUDGE <span>GUARD</span></div>
          <h1>Public gallery</h1>
        </div>
        <span className="badge badge-results_published">LIVE DATA</span>
      </div>
      <div className="embed-grid">
        {items.map((item) => (
          <article className="project-card" key={item.id}>
            <div className="project-media">
              {item.thumbnail_url ? <img src={item.thumbnail_url} alt={item.name} /> : <div className="project-media-placeholder"><span>JG</span></div>}
              {item.track_name ? <span className="media-tag">{item.track_name}</span> : null}
            </div>
            <div className="project-card-body">
              <h2>{item.name}</h2>
              <p className="project-tagline">{item.tagline}</p>
              <div className="tag-list">{item.tech_tags.slice(0, 5).map((tag) => <span className="tag" key={tag}>{tag}</span>)}</div>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
