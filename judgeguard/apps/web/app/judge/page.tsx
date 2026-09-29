"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, getMe, User } from "../../lib/api";
import { EmptyState, MetricCard, StatusBadge } from "../../components/ui";

type Event = { id: string; name: string; status: string };

export default function JudgeHome() {
  const [events, setEvents] = useState<Event[]>([]);
  const [me, setMe] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getMe().catch(() => null),
      apiFetch<Event[]>("/events").catch(() => []),
    ]).then(([user, eventData]) => {
      setMe(user as User | null);
      setEvents(eventData);
      setLoading(false);
    });
  }, []);

  if (!loading && me && me.role !== "JUDGE") {
    return (
      <>
        <div className="page-heading">
          <div>
            <div className="eyebrow">JUDGE WORKSPACE</div>
            <h1>Access restricted</h1>
            <p className="muted">The backend has not granted this account the JUDGE role.</p>
          </div>
          <Link className="button ghost" href="/events">Return to events</Link>
        </div>
        <div className="error-banner">Role isolation is enforced server-side. This screen does not bypass it.</div>
      </>
    );
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PRIVATE EVALUATOR SPACE</div>
          <h1>Judge workspace</h1>
          <p className="muted">Your queue is scoped by the authenticated judge identity.</p>
        </div>
      </div>

      {me ? (
        <div className="stats-grid">
          <MetricCard label="Signed-in as" value={me.display_name} detail={me.email} tone="accent" />
          <MetricCard label="Role" value={me.role} detail="backend enforced" />
          <MetricCard label="Events visible" value={events.length} detail="from the API" />
        </div>
      ) : (
        <div className="error-banner">Sign in to access judge assignments.</div>
      )}

      {loading ? null : events.length ? (
        <div className="event-grid event-grid-wide">
          {events.map((event) => (
            <article className="event-card event-card-large" key={event.id}>
              <div className="event-card-top">
                <StatusBadge status={event.status} />
              </div>
              <h2>{event.name}</h2>
              <p>Open the isolated judging queue for this event.</p>
              <Link className="button" href={`/judge/${event.id}`}>Open judging queue →</Link>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title="No events available" description="The API currently exposes no events for the workspace." href="/events" action="Browse events" />
      )}
    </>
  );
}
