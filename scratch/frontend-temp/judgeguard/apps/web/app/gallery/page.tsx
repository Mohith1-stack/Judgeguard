"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";
import { EmptyState, LoadingGrid, StatusBadge, TagList } from "../../components/ui";

type Event = { id: string; name: string; slug: string; description: string; status: string };
type Gallery = { event_id: string; event_name: string; total_items: number; total_pages: number };

export default function GalleryIndexPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [counts, setCounts] = useState<Record<string, Gallery>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<Event[]>("/events").then(async (data) => {
      setEvents(data);
      const visible = data.slice(0, 12);
      const results = await Promise.all(
        visible.map(async (event) => {
          try {
            return [event.id, await apiFetch<Gallery>(`/events/${event.id}/gallery?page=1&page_size=1&sort=NEWEST`)] as const;
          } catch {
            return null;
          }
        }),
      );
      setCounts(Object.fromEntries(results.filter(Boolean) as [string, Gallery][]));
    }).finally(() => setLoading(false));
  }, []);

  const published = useMemo(
    () => events.filter((e) => e.status !== "DRAFT"),
    [events],
  );

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PUBLIC SHOWCASE</div>
          <h1>Gallery</h1>
          <p className="muted">Browse public submissions published through JudgeGuard.</p>
        </div>
        <Link className="button ghost" href="/events">Events</Link>
      </div>

      {loading ? <LoadingGrid count={4} /> : null}

      {!loading && !published.length ? (
        <EmptyState title="No public events yet" description="Publish event submissions through the existing event workflow to populate the gallery." />
      ) : (
        <div className="event-grid">
          {published.map((event) => {
            const count = counts[event.id]?.total_items;
            return (
              <article className="event-card" key={event.id}>
                <div className="event-card-top">
                  <StatusBadge status={event.status} />
                  {typeof count === "number" ? <span className="count-badge">{count} projects</span> : null}
                </div>
                <h2>{event.name}</h2>
                <p>{event.description || "Explore submitted projects."}</p>
                <div className="event-meta">
                  <span>slug /{event.slug}</span>
                  <span>status {event.status.replaceAll("_", " ")}</span>
                </div>
                <Link className="button" href={`/gallery/${event.id}`}>Open gallery</Link>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}
