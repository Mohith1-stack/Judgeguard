"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiFetch } from "../../../../lib/api";

type Track = {
  id: string;
  event_id: string;
  name: string;
  slug: string;
  description: string;
};

type Prize = {
  id: string;
  event_id: string;
  name: string;
  description: string;
  amount: number | null;
  rank: number | null;
};

type Event = {
  id: string;
  organizer_id: string;
  name: string;
  slug: string;
  description: string;
  status: string;
  voting_access: string;
  voting_results_published: boolean;
  registration_opens_at: string | null;
  registration_closes_at: string | null;
  submission_opens_at: string | null;
  submission_deadline: string | null;
  judging_opens_at: string | null;
  judging_deadline: string | null;
  voting_opens_at: string | null;
  voting_deadline: string | null;
  created_at: string;
  updated_at: string;
  tracks: Track[];
  prizes: Prize[];
};

const NEXT_STATUS: Record<string, string | null> = {
  DRAFT: "REGISTRATION_OPEN",
  REGISTRATION_OPEN: "SUBMISSION_OPEN",
  SUBMISSION_OPEN: "JUDGING",
  JUDGING: "VOTING",
  VOTING: "RESULTS_PUBLISHED",
  RESULTS_PUBLISHED: "ARCHIVED",
  ARCHIVED: null,
};

function toInputDate(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function fromInputDate(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

export default function ManageEventPage() {
  const { eventId } = useParams<{ eventId: string }>();

  const [event, setEvent] = useState<Event | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [form, setForm] = useState({
    name: "",
    description: "",
    registration_opens_at: "",
    registration_closes_at: "",
    submission_opens_at: "",
    submission_deadline: "",
    judging_opens_at: "",
    judging_deadline: "",
    voting_opens_at: "",
    voting_deadline: "",
    voting_access: "AUTHENTICATED",
    voting_results_published: false,
  });

  const [track, setTrack] = useState({
    name: "",
    slug: "",
    description: "",
  });

  const [prize, setPrize] = useState({
    name: "",
    description: "",
    amount: "",
    rank: "",
  });

  const canEdit = useMemo(
    () => event?.status !== "ARCHIVED",
    [event?.status],
  );

  async function load() {
    setLoading(true);
    setError("");

    try {
      const data = await apiFetch<Event>(`/events/${eventId}`);
      setEvent(data);
      setForm({
        name: data.name,
        description: data.description,
        registration_opens_at: toInputDate(data.registration_opens_at),
        registration_closes_at: toInputDate(data.registration_closes_at),
        submission_opens_at: toInputDate(data.submission_opens_at),
        submission_deadline: toInputDate(data.submission_deadline),
        judging_opens_at: toInputDate(data.judging_opens_at),
        judging_deadline: toInputDate(data.judging_deadline),
        voting_opens_at: toInputDate(data.voting_opens_at),
        voting_deadline: toInputDate(data.voting_deadline),
        voting_access: data.voting_access,
        voting_results_published: data.voting_results_published,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load event");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [eventId]);

  function setField(
    key: keyof typeof form,
    value: string | boolean,
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function eventUpdateBody() {
    return {
      name: form.name,
      description: form.description,
      registration_opens_at: fromInputDate(form.registration_opens_at),
      registration_closes_at: fromInputDate(form.registration_closes_at),
      submission_opens_at: fromInputDate(form.submission_opens_at),
      submission_deadline: fromInputDate(form.submission_deadline),
      judging_opens_at: fromInputDate(form.judging_opens_at),
      judging_deadline: fromInputDate(form.judging_deadline),
      voting_opens_at: fromInputDate(form.voting_opens_at),
      voting_deadline: fromInputDate(form.voting_deadline),
      voting_access: form.voting_access,
      voting_results_published: form.voting_results_published,
    };
  }

  async function saveEvent(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");

    try {
      await apiFetch(`/events/${eventId}`, {
        method: "PATCH",
        body: JSON.stringify(eventUpdateBody()),
      });
      setMessage("Event settings saved.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save event");
    } finally {
      setSaving(false);
    }
  }

  async function advanceStatus() {
    if (!event) return;
    const next = NEXT_STATUS[event.status];
    if (!next) return;

    setSaving(true);
    setError("");
    setMessage("");

    try {
      await apiFetch(`/events/${eventId}/status`, {
        method: "POST",
        body: JSON.stringify({ status: next }),
      });
      setMessage(`Event moved to ${next}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change event status");
    } finally {
      setSaving(false);
    }
  }

  async function addTrack(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");

    try {
      await apiFetch(`/events/${eventId}/tracks`, {
        method: "POST",
        body: JSON.stringify(track),
      });
      setTrack({ name: "", slug: "", description: "" });
      setMessage("Track added.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add track");
    }
  }

  async function deleteTrack(trackId: string) {
    if (!window.confirm("Delete this track? Existing submissions will lose the track assignment.")) {
      return;
    }

    try {
      await apiFetch(`/events/${eventId}/tracks/${trackId}`, {
        method: "DELETE",
      });
      setMessage("Track deleted.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete track");
    }
  }

  async function addPrize(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");

    try {
      await apiFetch(`/events/${eventId}/prizes`, {
        method: "POST",
        body: JSON.stringify({
          name: prize.name,
          description: prize.description,
          amount: prize.amount === "" ? null : Number(prize.amount),
          rank: prize.rank === "" ? null : Number(prize.rank),
        }),
      });
      setPrize({ name: "", description: "", amount: "", rank: "" });
      setMessage("Prize added.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add prize");
    }
  }

  async function deletePrize(prizeId: string) {
    if (!window.confirm("Delete this prize?")) return;

    try {
      await apiFetch(`/events/${eventId}/prizes/${prizeId}`, {
        method: "DELETE",
      });
      setMessage("Prize deleted.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete prize");
    }
  }

  if (loading) {
    return <main><p className="muted">Loading event...</p></main>;
  }

  if (!event) {
    return <main><div className="error">{error || "Event not found."}</div></main>;
  }

  const nextStatus = NEXT_STATUS[event.status];

  return (
    <main>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 18 }}>
        <div>
          <p className="muted mono">EVENT MANAGEMENT</p>
          <h2 style={{ marginBottom: 4 }}>{event.name}</h2>
          <span className="pill">{event.status}</span>
        </div>
        <div className="row">
          <Link className="button secondary" href={`/events/${eventId}`}>Event page</Link>
          <Link className="button secondary" href={`/organizer/${eventId}`}>Organizer console</Link>
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {message && <div className="success">{message}</div>}

      <section className="card">
        <h3>Event settings</h3>
        <p className="muted">Slug: <span className="mono">{event.slug}</span></p>
        {!canEdit && <p className="warnText">Archived events are read-only.</p>}

        <form onSubmit={saveEvent}>
          <div className="field">
            <div className="label">Event name</div>
            <input disabled={!canEdit || saving} value={form.name} onChange={(e) => setField("name", e.target.value)} required />
          </div>

          <div className="field">
            <div className="label">Description</div>
            <textarea disabled={!canEdit || saving} rows={5} value={form.description} onChange={(e) => setField("description", e.target.value)} />
          </div>

          <h4>Registration</h4>
          <div className="grid">
            <DateField label="Opens" value={form.registration_opens_at} disabled={!canEdit || saving} onChange={(v) => setField("registration_opens_at", v)} />
            <DateField label="Closes" value={form.registration_closes_at} disabled={!canEdit || saving} onChange={(v) => setField("registration_closes_at", v)} />
          </div>

          <h4>Submissions</h4>
          <div className="grid">
            <DateField label="Opens" value={form.submission_opens_at} disabled={!canEdit || saving} onChange={(v) => setField("submission_opens_at", v)} />
            <DateField label="Deadline" value={form.submission_deadline} disabled={!canEdit || saving} onChange={(v) => setField("submission_deadline", v)} />
          </div>

          <h4>Judging</h4>
          <div className="grid">
            <DateField label="Opens" value={form.judging_opens_at} disabled={!canEdit || saving} onChange={(v) => setField("judging_opens_at", v)} />
            <DateField label="Deadline" value={form.judging_deadline} disabled={!canEdit || saving} onChange={(v) => setField("judging_deadline", v)} />
          </div>

          <h4>Voting</h4>
          <div className="grid">
            <DateField label="Opens" value={form.voting_opens_at} disabled={!canEdit || saving} onChange={(v) => setField("voting_opens_at", v)} />
            <DateField label="Deadline" value={form.voting_deadline} disabled={!canEdit || saving} onChange={(v) => setField("voting_deadline", v)} />
          </div>

          <div className="grid">
            <div className="field">
              <div className="label">Voting access</div>
              <select disabled={!canEdit || saving} value={form.voting_access} onChange={(e) => setField("voting_access", e.target.value)}>
                <option value="OPEN">Open link</option>
                <option value="EMAIL_GATED">Email-gated</option>
                <option value="AUTHENTICATED">Authenticated</option>
              </select>
            </div>
            <div className="field">
              <div className="label">Voting results published</div>
              <select disabled={!canEdit || saving} value={String(form.voting_results_published)} onChange={(e) => setField("voting_results_published", e.target.value === "true")}>
                <option value="false">No</option>
                <option value="true">Yes</option>
              </select>
            </div>
          </div>

          <button disabled={!canEdit || saving} type="submit">
            {saving ? "Saving..." : "Save event settings"}
          </button>
        </form>
      </section>

      <section className="card">
        <h3>Event lifecycle</h3>
        <p className="muted">The backend enforces the allowed lifecycle transitions.</p>
        <div className="row">
          <span className="pill">Current: {event.status}</span>
          {nextStatus ? (
            <button className="secondary" disabled={!canEdit || saving} type="button" onClick={advanceStatus}>
              Move to {nextStatus}
            </button>
          ) : (
            <span className="muted">No further transition.</span>
          )}
        </div>
      </section>

      <div className="grid">
        <section className="card">
          <h3>Tracks</h3>
          {event.tracks.length === 0 ? (
            <p className="muted">No tracks configured.</p>
          ) : (
            event.tracks.map((item) => (
              <div className="row" style={{ justifyContent: "space-between", borderBottom: "1px solid var(--line)", padding: "10px 0" }} key={item.id}>
                <div>
                  <strong>{item.name}</strong>
                  <div className="muted mono">{item.slug}</div>
                  {item.description && <div className="muted">{item.description}</div>}
                </div>
                <button className="danger" disabled={!canEdit} type="button" onClick={() => deleteTrack(item.id)}>Delete</button>
              </div>
            ))
          )}

          <form onSubmit={addTrack} style={{ marginTop: 16 }}>
            <div className="field"><div className="label">Name</div><input disabled={!canEdit} value={track.name} onChange={(e) => setTrack({ ...track, name: e.target.value })} required /></div>
            <div className="field"><div className="label">Slug</div><input disabled={!canEdit} value={track.slug} onChange={(e) => setTrack({ ...track, slug: e.target.value })} pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$" required /></div>
            <div className="field"><div className="label">Description</div><input disabled={!canEdit} value={track.description} onChange={(e) => setTrack({ ...track, description: e.target.value })} /></div>
            <button disabled={!canEdit} type="submit">Add track</button>
          </form>
        </section>

        <section className="card">
          <h3>Prizes</h3>
          {event.prizes.length === 0 ? (
            <p className="muted">No prizes configured.</p>
          ) : (
            event.prizes.map((item) => (
              <div className="row" style={{ justifyContent: "space-between", borderBottom: "1px solid var(--line)", padding: "10px 0" }} key={item.id}>
                <div>
                  <strong>{item.rank ? `#${item.rank} · ` : ""}{item.name}</strong>
                  <div className="muted">{item.amount === null ? "Amount not specified" : item.amount}</div>
                  {item.description && <div className="muted">{item.description}</div>}
                </div>
                <button className="danger" disabled={!canEdit} type="button" onClick={() => deletePrize(item.id)}>Delete</button>
              </div>
            ))
          )}

          <form onSubmit={addPrize} style={{ marginTop: 16 }}>
            <div className="field"><div className="label">Name</div><input disabled={!canEdit} value={prize.name} onChange={(e) => setPrize({ ...prize, name: e.target.value })} required /></div>
            <div className="field"><div className="label">Description</div><input disabled={!canEdit} value={prize.description} onChange={(e) => setPrize({ ...prize, description: e.target.value })} /></div>
            <div className="grid">
              <div className="field"><div className="label">Amount</div><input disabled={!canEdit} type="number" min="0" step="0.01" value={prize.amount} onChange={(e) => setPrize({ ...prize, amount: e.target.value })} /></div>
              <div className="field"><div className="label">Rank</div><input disabled={!canEdit} type="number" min="1" step="1" value={prize.rank} onChange={(e) => setPrize({ ...prize, rank: e.target.value })} /></div>
            </div>
            <button disabled={!canEdit} type="submit">Add prize</button>
          </form>
        </section>
      </div>
    </main>
  );
}

function DateField({ label, value, disabled, onChange }: { label: string; value: string; disabled?: boolean; onChange: (value: string) => void }) {
  return (
    <div className="field">
      <div className="label">{label}</div>
      <input type="datetime-local" disabled={disabled} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
