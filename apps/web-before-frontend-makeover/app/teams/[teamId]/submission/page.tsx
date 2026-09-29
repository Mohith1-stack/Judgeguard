"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch, getMe, User } from "../../../../lib/api";

type Question = {
  id: string; key: string; label: string; description: string;
  question_type: "TEXT" | "LONG_TEXT" | "URL" | "NUMBER" | "SINGLE_SELECT" | "MULTI_SELECT";
  required: boolean; options: string[]; sort_order: number;
};

type Team = { id: string; event_id: string; name: string };
type Submission = { id: string; name: string; tagline: string; description: string; thumbnail_url?: string|null; demo_video_url?: string|null; repository_url?: string|null; live_url?: string|null; tech_tags: string[]; custom_answers: Record<string, unknown>; status: string; current_version: number };

export default function SubmissionEditor() {
  const params = useParams<{ teamId: string }>();
  const teamId = params.teamId;
  const [me, setMe] = useState<User | null>(null);
  const [team, setTeam] = useState<Team | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [form, setForm] = useState<Record<string, any>>({ name: "", tagline: "", description: "", thumbnail_url: "", demo_video_url: "", repository_url: "", live_url: "", tech_tags: "", custom_answers: {} });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([getMe(), apiFetch<Team>(`/teams/${teamId}`)])
      .then(([user, loadedTeam]) => {
        setMe(user);
        setTeam(loadedTeam);
        return Promise.all([
          apiFetch<Question[]>(`/events/${loadedTeam.event_id}/submission-questions`),
          apiFetch<Submission | null>(`/teams/${teamId}/submissions/mine`),
        ]);
      })
      .then(([loadedQuestions, loadedSubmission]) => {
        setQuestions(loadedQuestions);
        setSubmission(loadedSubmission);
        if (loadedSubmission) {
          setForm({
            ...loadedSubmission,
            tech_tags: loadedSubmission.tech_tags.join(", "),
            custom_answers: loadedSubmission.custom_answers ?? {},
          });
        }
      })
      .catch((error) => setMessage(error.message));
  }, [teamId]);

  const updateAnswer = (key: string, value: unknown) =>
    setForm((current) => ({ ...current, custom_answers: { ...(current.custom_answers || {}), [key]: value } }));

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const payload = {
        name: form.name, tagline: form.tagline, description: form.description,
        thumbnail_url: form.thumbnail_url || null, demo_video_url: form.demo_video_url || null,
        repository_url: form.repository_url || null, live_url: form.live_url || null,
        tech_tags: String(form.tech_tags || "").split(",").map((x: string) => x.trim()).filter(Boolean),
        custom_answers: form.custom_answers || {},
      };
      const saved = submission
        ? await apiFetch<Submission>(`/submissions/${submission.id}`, { method: "PATCH", body: JSON.stringify(payload) })
        : await apiFetch<Submission>(`/teams/${teamId}/submissions`, { method: "POST", body: JSON.stringify(payload) });
      setSubmission(saved);
      setForm((current) => ({ ...current, ...saved, tech_tags: saved.tech_tags.join(", "), custom_answers: saved.custom_answers }));
      setMessage(`Draft saved. Version ${saved.current_version}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Save failed");
    } finally { setBusy(false); }
  }

  async function finalize() {
    if (!submission) { setMessage("Save the draft before finalizing."); return; }
    setBusy(true);
    try {
      const result = await apiFetch<Submission>(`/submissions/${submission.id}/submit`, { method: "POST" });
      setSubmission(result);
      setMessage("Submission finalized successfully.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Finalization failed"); }
    finally { setBusy(false); }
  }

  if (!me || !team) return <main><p>Loading…</p>{message && <div className="error">{message}</div>}</main>;
  if (me.role !== "PARTICIPANT") return <main><div className="error">Only participants can edit team submissions.</div></main>;

  const locked = submission?.status === "LOCKED";

  return <main><div className="card">
    <p className="muted mono">SUBMISSION WORKSPACE · {team.name}</p>
    <h1>{submission ? "Edit submission" : "Create submission draft"}</h1>
    {submission && <p className="muted">Status: {submission.status} · Version {submission.current_version}</p>}
    {message && <div className={message.includes("success") || message.includes("saved") ? "notice" : "error"}>{message}</div>}
    <form onSubmit={save}>
      <label>Name<input required disabled={locked} value={form.name ?? ""} onChange={(e)=>setForm({...form,name:e.target.value})}/></label>
      <label>Tagline<input disabled={locked} value={form.tagline ?? ""} onChange={(e)=>setForm({...form,tagline:e.target.value})}/></label>
      <label>Description<textarea disabled={locked} rows={8} value={form.description ?? ""} onChange={(e)=>setForm({...form,description:e.target.value})}/></label>
      <label>Thumbnail URL<input disabled={locked} value={form.thumbnail_url ?? ""} onChange={(e)=>setForm({...form,thumbnail_url:e.target.value})}/></label>
      <label>Demo video URL<input disabled={locked} value={form.demo_video_url ?? ""} onChange={(e)=>setForm({...form,demo_video_url:e.target.value})}/></label>
      <label>Repository URL<input disabled={locked} value={form.repository_url ?? ""} onChange={(e)=>setForm({...form,repository_url:e.target.value})}/></label>
      <label>Live URL<input disabled={locked} value={form.live_url ?? ""} onChange={(e)=>setForm({...form,live_url:e.target.value})}/></label>
      <label>Tech tags<input disabled={locked} value={form.tech_tags ?? ""} onChange={(e)=>setForm({...form,tech_tags:e.target.value})}/></label>
      {questions.map((q) => <div key={q.id} className="card">
        <label>{q.label}{q.required ? " *" : ""}<small className="muted">{q.description}</small>
          {q.question_type === "LONG_TEXT" ? <textarea disabled={locked} rows={5} value={String(form.custom_answers?.[q.key] ?? "")} onChange={(e)=>updateAnswer(q.key,e.target.value)}/> :
           q.question_type === "SINGLE_SELECT" ? <select disabled={locked} value={String(form.custom_answers?.[q.key] ?? "")} onChange={(e)=>updateAnswer(q.key,e.target.value)}><option value="">Select…</option>{q.options.map(o=><option key={o} value={o}>{o}</option>)}</select> :
           q.question_type === "MULTI_SELECT" ? <select multiple disabled={locked} value={Array.isArray(form.custom_answers?.[q.key]) ? form.custom_answers[q.key] : []} onChange={(e)=>updateAnswer(q.key,Array.from(e.target.selectedOptions).map(o=>o.value))}>{q.options.map(o=><option key={o} value={o}>{o}</option>)}</select> :
           <input disabled={locked} type={q.question_type === "NUMBER" ? "number" : q.question_type === "URL" ? "url" : "text"} value={String(form.custom_answers?.[q.key] ?? "")} onChange={(e)=>updateAnswer(q.key,q.question_type === "NUMBER" ? Number(e.target.value) : e.target.value)}/>}
        </label>
      </div>)}
      <div className="row">
        <button className="button" disabled={busy || locked}>{busy ? "Saving…" : "Save draft"}</button>
        <button type="button" className="button secondary" disabled={busy || !submission || locked} onClick={finalize}>Finalize submission</button>
      </div>
    </form>
  </div></main>;
}
