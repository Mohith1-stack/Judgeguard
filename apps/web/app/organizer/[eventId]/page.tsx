"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, apiUrl } from "../../../lib/api";

type Event = { id: string; name: string; status: string };
type Submission = { id: string; name: string; status: string };
type Audit = {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  payload: unknown;
  created_at: string;
};
type Criterion = { name: string; description: string; weight: number; min_score: number; max_score: number };

export default function OrganizerPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [event, setEvent] = useState<Event | null>(null);
  const [subs, setSubs] = useState<Submission[]>([]);
  const [userId, setUserId] = useState("");
  const [capacity, setCapacity] = useState(10);
  const [expertise, setExpertise] = useState("");
  const [reviews, setReviews] = useState(3);
  const [rubricName, setRubricName] = useState("Evaluation Rubric");
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [audit, setAudit] = useState<Audit[]>([]);

  async function load() {
    try {
      const [e, s, a] = await Promise.all([
        apiFetch<Event>(`/events/${eventId}`),
        apiFetch<Submission[]>(`/events/${eventId}/submissions`),
        apiFetch<Audit[]>(`/events/${eventId}/audit`),
      ]);
      setEvent(e);
      setSubs(s);
      setAudit(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  useEffect(() => {
    void load();
  }, [eventId]);

  async function createRubric() {
    try {
      const r = await apiFetch<{ id: string }>(`/events/${eventId}/rubrics`, {
        method: "POST",
        body: JSON.stringify({ name: rubricName }),
      });
      for (const c of criteria) {
        await apiFetch(`/rubrics/${r.id}/criteria`, { method: "POST", body: JSON.stringify(c) });
      }
      setMessage("Rubric created.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  async function addJudge() {
    try {
      if (!userId.trim()) throw new Error("Enter the judge user ID");
      await apiFetch(`/events/${eventId}/judges`, {
        method: "POST",
        body: JSON.stringify({ user_id: userId, capacity, expertise: expertise.split(",").map((x) => x.trim()).filter(Boolean) }),
      });
      setMessage("Judge profile added.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  async function assign() {
    try {
      await apiFetch(`/events/${eventId}/judging/assign`, {
        method: "POST",
        body: JSON.stringify({ reviews_per_submission: reviews }),
      });
      setMessage("Assignments created.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <main>
      {error && <div className="error">{error}</div>}
      {message && <div className="success">{message}</div>}
      {event && (
        <div className="card">
          <span className="pill">{event.status}</span>
          <h2>{event.name} · Organizer</h2>
          <div className="row">
            <Link className="button secondary" href={`/organizer/${eventId}/integrity`}>JudgeGuard Integrity</Link>
            <Link className="button secondary" href={`/gallery/${eventId}`}>Public Gallery</Link>
            <a className="button secondary" href={apiUrl(`/events/${eventId}/export.json`)} target="_blank" rel="noreferrer">Export JSON</a>
          </div>
        </div>
      )}

      <div className="grid">
        <div className="card">
          <h3>Rubric</h3>
          <div className="field"><div className="label">Name</div><input value={rubricName} onChange={(e) => setRubricName(e.target.value)} /></div>
          {criteria.map((c, i) => (
            <div className="card" key={i}>
              <div className="field"><div className="label">Criterion name</div><input value={c.name} onChange={(e) => setCriteria((v) => v.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} /></div>
              <div className="field"><div className="label">Weight (0–1)</div><input type="number" min="0.0001" max="1" step="0.01" value={c.weight} onChange={(e) => setCriteria((v) => v.map((x, j) => j === i ? { ...x, weight: Number(e.target.value) } : x))} /></div>
              <div className="field"><div className="label">Description</div><input value={c.description} onChange={(e) => setCriteria((v) => v.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} /></div>
            </div>
          ))}
          <div className="row">
            <button className="secondary" type="button" onClick={() => setCriteria((v) => [...v, { name: "", description: "", weight: 0, min_score: 1, max_score: 5 }])}>Add criterion</button>
            <button onClick={createRubric} disabled={criteria.length === 0}>Create active rubric</button>
          </div>
        </div>

        <div className="card">
          <h3>Judge profile</h3>
          <div className="field"><div className="label">Judge user ID</div><input value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="UUID from admin users" /></div>
          <div className="field"><div className="label">Capacity</div><input type="number" min="1" value={capacity} onChange={(e) => setCapacity(Number(e.target.value))} /></div>
          <div className="field"><div className="label">Expertise tags</div><input value={expertise} onChange={(e) => setExpertise(e.target.value)} /></div>
          <button onClick={addJudge}>Add judge</button>
        </div>

        <div className="card">
          <h3>Assignments</h3>
          <p>{subs.length} submitted projects</p>
          <div className="field"><div className="label">Reviews per submission</div><input type="number" min="1" max="20" value={reviews} onChange={(e) => setReviews(Number(e.target.value))} /></div>
          <button onClick={assign}>Generate judging plan</button>
        </div>
      </div>

      <div className="card">
        <h3>Audit trail</h3>
        <p className="muted">Organizer-readable event history. Analytics do not mutate raw evaluation records.</p>
        {audit.length ? (
          <div style={{ overflowX: "auto" }}>
            <table className="table">
              <thead><tr><th>Time</th><th>Action</th><th>Entity</th><th>Actor</th></tr></thead>
              <tbody>{audit.map((item) => (
                <tr key={item.id}>
                  <td className="mono">{item.created_at}</td>
                  <td>{item.action}</td>
                  <td>{item.entity_type} · {item.entity_id}</td>
                  <td className="mono">{item.actor_user_id ?? "system/public"}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        ) : <p className="muted">No audit events recorded yet.</p>}
      </div>
    </main>
  );
}
