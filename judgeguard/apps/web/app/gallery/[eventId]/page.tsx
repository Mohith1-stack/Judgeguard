"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, getMe, User } from "../../../lib/api";
import { EmptyState, LoadingGrid, TagList } from "../../../components/ui";

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
  media: { id: string; url: string; caption: string; sort_order: number }[];
};
type Track = { id: string; name: string; slug: string };
type GalleryResponse = {
  event_id: string;
  event_name: string;
  items: Item[];
  tracks: Track[];
  tags: string[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  sort: string;
};

export default function EventGalleryPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [data, setData] = useState<GalleryResponse | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [query, setQuery] = useState("");
  const [track, setTrack] = useState("ALL");
  const [tag, setTag] = useState("ALL");
  const [sort, setSort] = useState("RANDOM");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busyVote, setBusyVote] = useState<string | null>(null);

  async function load(nextPage = page, nextSort = sort, nextTrack = track) {
    setError("");
    try {
      const params = new URLSearchParams({
        page: String(nextPage),
        page_size: "12",
        sort: nextSort,
      });
      if (query.trim()) params.set("q", query.trim());
      if (nextTrack !== "ALL") params.set("track_id", nextTrack);
      const [gallery, me] = await Promise.all([
        apiFetch<GalleryResponse>(`/events/${eventId}/gallery?${params.toString()}`),
        getMe().catch(() => null),
      ]);
      setData(gallery);
      setUser(me as User | null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load gallery");
    }
  }

  useEffect(() => { void load(1, sort, track); }, [eventId]); // initial load

  const visibleItems = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data?.items ?? []).filter((item) => {
      const tagMatch = tag === "ALL" || item.tech_tags.includes(tag);
      const qMatch = !q || `${item.name} ${item.tagline} ${item.description} ${item.team_name} ${item.tech_tags.join(" ")}`.toLowerCase().includes(q);
      return tagMatch && qMatch;
    });
  }, [data, query, tag]);

  async function vote(id: string) {
    setBusyVote(id);
    setMessage("");
    setError("");
    try {
      await apiFetch(`/events/${eventId}/votes`, { method: "POST", body: JSON.stringify({ submission_id: id }) });
      setMessage("Vote recorded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vote failed");
    } finally {
      setBusyVote(null);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">PUBLIC GALLERY</div>
          <h1>{data?.event_name ?? "Gallery"}</h1>
          <p className="muted">Projects are served from submitted records. Gallery order is controlled by the backend.</p>
        </div>
        <Link className="button ghost" href="/gallery">All galleries</Link>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
      {message ? <div className="success-banner">{message}</div> : null}

      <div className="toolbar toolbar-stack">
        <div className="searchbox">
          <span>⌕</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search projects, teams, descriptions, technologies…" />
        </div>
        <div className="toolbar-row">
          <select value={track} onChange={(e) => { setTrack(e.target.value); setPage(1); void load(1, sort, e.target.value); }}>
            <option value="ALL">All tracks</option>
            {(data?.tracks ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select value={tag} onChange={(e) => setTag(e.target.value)}>
            <option value="ALL">All technology</option>
            {(data?.tags ?? []).map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); void load(1, e.target.value, track); }}>
            <option value="RANDOM">Randomized</option>
            <option value="NEWEST">Newest</option>
            <option value="NAME">Name</option>
          </select>
        </div>
      </div>

      {!data ? (
        <LoadingGrid />
      ) : !visibleItems.length ? (
        <EmptyState title="No projects match the filters" description="Try a different search, technology, track, or sort order." />
      ) : (
        <>
          <div className="gallery-grid">
            {visibleItems.map((item) => (
              <article className="project-card" key={item.id}>
                <div className="project-media">
                  {item.thumbnail_url ? (
                    <img src={item.thumbnail_url} alt={item.name} />
                  ) : (
                    <div className="project-media-placeholder"><span>JG</span></div>
                  )}
                  {item.track_name ? <span className="media-tag">{item.track_name}</span> : null}
                </div>
                <div className="project-card-body">
                  <div className="project-overline">
                    <span>{item.team_name}</span>
                    <span className="mono">{new Date(item.submitted_at).toLocaleDateString()}</span>
                  </div>
                  <h2>{item.name}</h2>
                  <p className="project-tagline">{item.tagline || item.description}</p>
                  <TagList tags={item.tech_tags} />
                  <div className="project-actions">
                    <Link className="button ghost compact" href={`/gallery/${eventId}/${item.id}`}>View project</Link>
                    <button className="button compact" onClick={() => void vote(item.id)} disabled={busyVote === item.id}>
                      {busyVote === item.id ? "Voting…" : "Vote"}
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>

          {data.total_pages > 1 ? (
            <div className="pagination">
              <button className="button ghost" disabled={page <= 1} onClick={() => { const next = page - 1; setPage(next); void load(next, sort, track); }}>Previous</button>
              <span className="muted">Page {page} of {data.total_pages}</span>
              <button className="button ghost" disabled={page >= data.total_pages} onClick={() => { const next = page + 1; setPage(next); void load(next, sort, track); }}>Next</button>
            </div>
          ) : null}
        </>
      )}
    </>
  );
}
