"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, getMe, User } from "../lib/api";
import { MetricCard, StatusBadge, TagList } from "../components/ui";

type Event = {
  id: string;
  name: string;
  slug: string;
  description: string;
  status: string;
  voting_access: string;
  voting_results_published: boolean;
  tracks: { id: string; name: string; slug: string; description: string }[];
  prizes: { id: string; name: string; description: string; amount: number | null; rank: number | null }[];
};

export default function Home() {
  const [events, setEvents] = useState<Event[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiFetch<Event[]>("/events").catch(() => []),
      getMe().catch(() => null),
    ]).then(([eventData, me]) => {
      setEvents(eventData);
      setUser(me as User | null);
      setLoading(false);
    });
  }, []);

  const statusCounts = useMemo(() => {
    return events.reduce<Record<string, number>>((acc, event) => {
      acc[event.status] = (acc[event.status] ?? 0) + 1;
      return acc;
    }, {});
  }, [events]);

  return (
    <>
      <section className="hero">
        <div className="hero-grid">
          <div className="hero-copy">
            <div className="eyebrow">SELF-HOSTED · API-FIRST · EVIDENCE-DRIVEN</div>
            <h1>Run hackathons.<br /><span>Stress-test the judging.</span></h1>
            <p className="hero-lead">
              JudgeGuard combines submission management, isolated judging, statistical normalization,
              influence analysis, ranking stability, and adaptive review in one audit-ready platform.
            </p>
            <div className="hero-actions">
              <Link className="button button-lg" href="/events">Explore live events</Link>
              <Link className="button ghost button-lg" href="/gallery">Open public gallery</Link>
            </div>
            <div className="hero-note">
              <span className="live-dot" />
              Connected to the live JudgeGuard API
            </div>
          </div>

          <div className="hero-visual">
            <div className="integrity-console">
              <div className="console-head">
                <div>
                  <span className="console-kicker">INTEGRITY ENGINE</span>
                  <strong>Leaderboard evidence</strong>
                </div>
                <span className="status-dot" />
              </div>
              <div className="console-flow">
                {["Evaluation", "Normalize", "Influence", "Stability", "Adaptive review", "Recalculate"].map((step, index) => (
                  <div className="flow-row" key={step}>
                    <span className="flow-index">{String(index + 1).padStart(2, "0")}</span>
                    <span>{step}</span>
                    <span className="flow-check">✓</span>
                  </div>
                ))}
              </div>
              <div className="console-footer">
                <span>raw scores stay immutable</span>
                <span className="mono">/integrity</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="stats-grid">
        <MetricCard label="Live events" value={loading ? "—" : events.length} detail="from PostgreSQL-backed API" tone="accent" />
        <MetricCard label="Open registration" value={loading ? "—" : statusCounts.REGISTRATION_OPEN ?? 0} detail="events accepting participants" />
        <MetricCard label="Judging active" value={loading ? "—" : statusCounts.JUDGING ?? 0} detail="events in evaluator phase" tone="good" />
        <MetricCard label="Published results" value={loading ? "—" : statusCounts.RESULTS_PUBLISHED ?? 0} detail="public results released" />
      </section>

      <section className="feature-section">
        <div className="section-title">
          <div>
            <div className="eyebrow">THE PLATFORM</div>
            <h2>One workflow, three layers of evidence.</h2>
            <p className="muted section-description">
              The frontend is a visual layer over your existing FastAPI + PostgreSQL system.
              Every number below is sourced from the API when a live event exists.
            </p>
          </div>
        </div>

        <div className="feature-grid">
          <article className="feature-card">
            <div className="feature-number">01</div>
            <h3>Operate the event</h3>
            <p>Events, tracks, teams, submissions, lifecycle controls and public gallery.</p>
            <div className="feature-tags"><span>T1</span><span>Submission</span><span>Gallery</span></div>
          </article>
          <article className="feature-card">
            <div className="feature-number">02</div>
            <h3>Protect the judging process</h3>
            <p>Weighted rubrics, conflict-aware assignment, judge isolation and normalization.</p>
            <div className="feature-tags"><span>T2</span><span>RBAC</span><span>Scoring</span></div>
          </article>
          <article className="feature-card feature-card-accent">
            <div className="feature-number">03</div>
            <h3>Stress-test the leaderboard</h3>
            <p>Influence, minimum flip sets, stability, sensitivity and adaptive review form the JudgeGuard loop.</p>
            <div className="feature-tags"><span>Integrity</span><span>Adaptive</span><span>Audit</span></div>
          </article>
        </div>
      </section>

      <section className="events-preview">
        <div className="section-title">
          <div>
            <div className="eyebrow">LIVE DATA</div>
            <h2>Recent events</h2>
          </div>
          <Link href="/events" className="button ghost">View all</Link>
        </div>

        {!events.length ? (
          <div className="empty-state compact-empty">
            <div className="empty-icon">—</div>
            <h3>No events are visible yet</h3>
            <p className="muted">Create or publish an event through the existing API to populate this view.</p>
          </div>
        ) : (
          <div className="event-grid">
            {events.slice(0, 6).map((event) => (
              <article className="event-card" key={event.id}>
                <div className="event-card-top">
                  <StatusBadge status={event.status} />
                  <span className="mono event-slug">/{event.slug}</span>
                </div>
                <h3>{event.name}</h3>
                <p>{event.description || "Event description not provided."}</p>
                <div className="event-meta">
                  <span>{event.tracks.length} tracks</span>
                  <span>{event.prizes.length} prizes</span>
                  <span>{event.voting_access.replaceAll("_", " ")}</span>
                </div>
                <TagList tags={event.tracks.map((track) => track.name)} limit={3} />
                <Link href={`/events/${event.id}`} className="text-link">Open event →</Link>
              </article>
            ))}
          </div>
        )}
      </section>

      {user ? (
        <section className="callout">
          <div>
            <div className="eyebrow">SIGNED IN</div>
            <h2>{user.display_name}</h2>
            <p className="muted">Your account is <strong>{user.role.replaceAll("_", " ")}</strong>. Use the navigation to open the workspace exposed by your role.</p>
          </div>
          <Link className="button" href={user.role === "JUDGE" ? "/judge" : "/events"}>Open workspace</Link>
        </section>
      ) : null}
    </>
  );
}
