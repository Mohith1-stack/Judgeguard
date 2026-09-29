"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";
import { EmptyState, LoadingGrid, StatusBadge, TagList } from "../../components/ui";

type Event = {
  id: string;
  name: string;
  slug: string;
  description: string;
  status: string;
  voting_access: string;
  voting_results_published: boolean;
  registration_opens_at: string | null;
  registration_closes_at: string | null;
  judging_deadline: string | null;
  tracks: { id: string; name: string; slug: string; description: string }[];
  prizes: { id: string; name: string; description: string; amount: number | null; rank: number | null }[];
};

export default function EventsPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Event[]>("/events")
      .then(setEvents)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load events"))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return events.filter((event) => {
      const matchesQuery =
        !q ||
        `${event.name} ${event.slug} ${event.description} ${event.tracks.map((x) => x.name).join(" ")}`
          .toLowerCase()
          .includes(q);
      const matchesStatus = status === "ALL" || event.status === status;
      return matchesQuery && matchesStatus;
    });
  }, [events, query, status]);

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">EVENT DIRECTORY</div>
          <h1>Events</h1>
          <p className="muted">Live event metadata from the JudgeGuard API.</p>
        </div>
        <div className="heading-actions">
          <Link className="button ghost" href="/gallery">Public gallery</Link>
          <Link className="button" href="/events/new">Create event</Link>
        </div>
      </div>

      <div className="toolbar">
        <div className="searchbox">
          <span>⌕</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search events, tracks, descriptions…" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="ALL">All statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="REGISTRATION_OPEN">Registration open</option>
          <option value="SUBMISSION_OPEN">Submission open</option>
          <option value="JUDGING">Judging</option>
          <option value="VOTING">Voting</option>
          <option value="RESULTS_PUBLISHED">Results published</option>
          <option value="ARCHIVED">Archived</option>
        </select>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      {loading ? (
        <LoadingGrid />
      ) : filtered.length === 0 ? (
        <EmptyState title="No matching events" description="The API returned no events matching the current filters." href="/events/new" action="Create an event" />
      ) : (
        <div className="event-grid event-grid-wide">
          {filtered.map((event) => (
            <article className="event-card event-card-large" key={event.id}>
              <div className="event-card-top">
                <StatusBadge status={event.status} />
                <span className="mono event-slug">/{event.slug}</span>
              </div>
              <h2>{event.name}</h2>
              <p>{event.description || "No description provided."}</p>

              <div className="event-stat-row">
                <div><span>{event.tracks.length}</span><small>tracks</small></div>
                <div><span>{event.prizes.length}</span><small>prizes</small></div>
                <div><span>{event.voting_results_published ? "Live" : "Hidden"}</span><small>results</small></div>
              </div>

              <TagList tags={event.tracks.map((x) => x.name)} limit={5} />

              <div className="event-card-bottom">
                <span className="muted">Voting: {event.voting_access.replaceAll("_", " ")}</span>
                <Link className="text-link" href={`/events/${event.id}`}>Open event →</Link>
              </div>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
