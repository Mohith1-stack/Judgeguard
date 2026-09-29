"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, getMe, User } from "../../../lib/api";

type Item = {
  id: string;
  name: string;
  tagline: string;
  description: string;
  tech_tags: string[];
};
type Comment = { id: string; body: string; user_id: string | null; created_at: string };

type PublicResults = { submission_id: string; votes: number }[];

export default function Gallery() {
  const { eventId } = useParams<{ eventId: string }>();
  const [items, setItems] = useState<Item[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [comments, setComments] = useState<Record<string, Comment[]>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<PublicResults | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const [gallery, me] = await Promise.all([
        apiFetch<{ items: Item[] }>(`/events/${eventId}/gallery`),
        getMe().catch(() => null),
      ]);
      setItems(gallery.items);
      setUser(me as User | null);
      try {
        const published = await apiFetch<PublicResults>(`/events/${eventId}/votes/results`);
        setResults(published);
      } catch {
        setResults(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load gallery");
    }
  }

  useEffect(() => {
    void load();
  }, [eventId]);

  async function vote(id: string) {
    setMessage("");
    setError("");
    try {
      await apiFetch(`/events/${eventId}/votes`, {
        method: "POST",
        body: JSON.stringify({ submission_id: id }),
      });
      setMessage("Vote recorded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Vote failed");
    }
  }

  async function loadComments(id: string) {
    try {
      const data = await apiFetch<Comment[]>(`/submissions/${id}/comments`);
      setComments((current) => ({ ...current, [id]: data }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load comments");
    }
  }

  async function toggleComments(id: string) {
    const next = !open[id];
    setOpen((current) => ({ ...current, [id]: next }));
    if (next && comments[id] === undefined) await loadComments(id);
  }

  async function addComment(id: string) {
    const body = (drafts[id] ?? "").trim();
    if (!body) return;
    setError("");
    try {
      await apiFetch(`/submissions/${id}/comments`, {
        method: "POST",
        body: JSON.stringify({ body }),
      });
      setDrafts((current) => ({ ...current, [id]: "" }));
      await loadComments(id);
      setMessage("Comment posted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comment failed");
    }
  }

  const voteMap = Object.fromEntries((results ?? []).map((row) => [row.submission_id, row.votes]));

  return (
    <main>
      {error && <div className="error">{error}</div>}
      {message && <div className="success">{message}</div>}
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Public Gallery</h2>
          <p className="muted">Projects are randomized by the backend for each gallery request.</p>
        </div>
      </div>

      <div className="grid">
        {items.map((item) => (
          <article className="card" key={item.id}>
            <h3>{item.name}</h3>
            <p>{item.tagline}</p>
            <p>{item.description}</p>
            <p className="muted">{item.tech_tags.join(" · ")}</p>
            <div className="row">
              <button onClick={() => vote(item.id)}>Vote</button>
              <button className="secondary" onClick={() => void toggleComments(item.id)}>
                {open[item.id] ? "Hide comments" : "Comments"}
              </button>
              {results && <span className="pill">Published votes: {voteMap[item.id] ?? 0}</span>}
            </div>

            {open[item.id] && (
              <div className="card" style={{ marginTop: 16 }}>
                <h4>Comments</h4>
                {(comments[item.id] ?? []).map((comment) => (
                  <div key={comment.id} style={{ marginBottom: 12 }}>
                    <div className="muted mono">{comment.created_at}</div>
                    <div>{comment.body}</div>
                  </div>
                ))}
                {(comments[item.id] ?? []).length === 0 && <p className="muted">No comments yet.</p>}
                {user ? (
                  <div className="field">
                    <div className="label">Add a comment</div>
                    <textarea
                      rows={3}
                      value={drafts[item.id] ?? ""}
                      onChange={(event) =>
                        setDrafts((current) => ({ ...current, [item.id]: event.target.value }))
                      }
                      maxLength={5000}
                    />
                    <button className="secondary" onClick={() => void addComment(item.id)}>
                      Post comment
                    </button>
                  </div>
                ) : (
                  <p className="muted">Sign in to comment.</p>
                )}
              </div>
            )}
          </article>
        ))}
        {items.length === 0 && (
          <div className="card">
            <p>No public submissions.</p>
          </div>
        )}
      </div>
    </main>
  );
}
