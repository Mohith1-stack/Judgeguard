"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiFetch } from "../../../lib/api";
import { MetricCard, StatusBadge, TagList, ProgressBar } from "../../../components/ui";

type Assignment = { id: string; judge_id: string; submission_id: string; queue_position: number; status: string };
type Detail = {
  assignment: { id: string; queue_position: number };
  submission: {
    id: string; name: string; tagline: string; description: string;
    repository_url: string | null; live_url: string | null; demo_video_url: string | null; tech_tags: string[];
  };
  rubric: { id: string; name: string; description: string; weight: number; min_score: number; max_score: number }[];
  already_submitted: boolean;
};

export default function JudgeEventPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [scores, setScores] = useState<Record<string, string>>({});
  const [comment, setComment] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setError("");
    try {
      const data = await apiFetch<Assignment[]>(`/events/${eventId}/judging/me`);
      setAssignments(data);
      if (!detail && data.length) {
        const next = data.find((a) => a.status !== "COMPLETED") ?? data[0];
        await open(next);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load judge queue");
    } finally {
      setLoading(false);
    }
  }

  async function open(assignment: Assignment) {
    setError("");
    try {
      const result = await apiFetch<Detail>(`/events/${eventId}/judging/submission/${assignment.submission_id}`);
      setDetail(result);
      setScores({});
      setComment("");
      setMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load submission");
    }
  }

  useEffect(() => { void load(); }, [eventId]);

  const completed = assignments.filter((item) => item.status === "COMPLETED").length;
  const progress = assignments.length ? (completed / assignments.length) * 100 : 0;

  async function submit() {
    if (!detail) return;
    const invalid = detail.rubric.some((criterion) => {
      const raw = scores[criterion.id];
      const score = Number(raw);
      return raw === undefined || raw === "" || Number.isNaN(score) || score < criterion.min_score || score > criterion.max_score;
    });
    if (invalid) {
      setError("Every rubric criterion needs a valid score inside its configured range.");
      return;
    }

    setSubmitting(true);
    setError("");
    setMessage("");
    try {
      await apiFetch(`/events/${eventId}/judging/assignments/${detail.assignment.id}/evaluation`, {
        method: "POST",
        body: JSON.stringify({
          scores: detail.rubric.map((criterion) => ({ criterion_id: criterion.id, score: Number(scores[criterion.id]) })),
          overall_comment: comment,
        }),
      });
      setMessage("Evaluation submitted. The queue has been refreshed.");
      await load();
      setDetail(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Evaluation submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">ISOLATED JUDGING</div>
          <h1>Evaluation queue</h1>
          <p className="muted">Peer scores and unrelated evaluator data are never requested by this UI.</p>
        </div>
        <Link className="button ghost" href="/judge">All judge events</Link>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
      {message ? <div className="success-banner">{message}</div> : null}

      <div className="stats-grid">
        <MetricCard label="Assigned" value={assignments.length} detail="projects in this queue" tone="accent" />
        <MetricCard label="Completed" value={completed} detail="evaluations submitted" tone="good" />
        <MetricCard label="Remaining" value={Math.max(0, assignments.length - completed)} detail="awaiting your review" />
      </div>
      <ProgressBar value={progress} label="Judging progress" detail={`${Math.round(progress)}%`} />

      <div className="judge-layout">
        <aside className="queue-panel">
          <div className="panel-header">
            <div><div className="eyebrow">QUEUE</div><h3>Assigned projects</h3></div>
          </div>
          <div className="queue-list">
            {assignments.map((assignment) => (
              <button className={`queue-item ${detail?.assignment.id === assignment.id ? "active" : ""}`} key={assignment.id} onClick={() => void open(assignment)}>
                <span className="queue-index">#{assignment.queue_position}</span>
                <span className="queue-main">
                  <strong>{assignment.submission_id.slice(0, 8)}</strong>
                  <span className="muted">{assignment.status.replaceAll("_", " ")}</span>
                </span>
                <span className={`queue-state ${assignment.status === "COMPLETED" ? "done" : ""}`}>{assignment.status === "COMPLETED" ? "✓" : "→"}</span>
              </button>
            ))}
          </div>
        </aside>

        <section className="review-panel">
          {!detail ? (
            <div className="empty-state">
              <div className="empty-icon">→</div>
              <h3>{loading ? "Loading queue…" : "Select a project"}</h3>
              <p className="muted">Open an assignment to view the submission and its active rubric.</p>
            </div>
          ) : (
            <>
              <div className="review-head">
                <div>
                  <div className="project-badges"><StatusBadge status={detail.already_submitted ? "COMPLETED" : "ASSIGNED"} /></div>
                  <h2>{detail.submission.name}</h2>
                  <p className="review-tagline">{detail.submission.tagline}</p>
                  <TagList tags={detail.submission.tech_tags} limit={12} />
                </div>
                <div className="review-links">
                  {detail.submission.live_url ? <a className="button ghost compact" href={detail.submission.live_url} target="_blank" rel="noreferrer">Live ↗</a> : null}
                  {detail.submission.repository_url ? <a className="button ghost compact" href={detail.submission.repository_url} target="_blank" rel="noreferrer">Repo ↗</a> : null}
                </div>
              </div>

              <div className="review-description">{detail.submission.description}</div>

              <div className="rubric-list">
                {detail.rubric.map((criterion) => {
                  const value = scores[criterion.id] ?? "";
                  return (
                    <div className="rubric-row" key={criterion.id}>
                      <div className="rubric-copy">
                        <div className="rubric-name">{criterion.name}<span>{Math.round(criterion.weight * 100)}%</span></div>
                        <p className="muted">{criterion.description}</p>
                      </div>
                      <div className="score-control">
                        <input
                          type="number"
                          min={criterion.min_score}
                          max={criterion.max_score}
                          step="0.01"
                          value={value}
                          disabled={detail.already_submitted || submitting}
                          onChange={(e) => setScores((current) => ({ ...current, [criterion.id]: e.target.value }))}
                        />
                        <small>{criterion.min_score}–{criterion.max_score}</small>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="field">
                <div className="label">Overall comment</div>
                <textarea rows={5} value={comment} disabled={detail.already_submitted || submitting} onChange={(e) => setComment(e.target.value)} placeholder="Optional evaluator context…" />
              </div>

              <button className="button-lg" disabled={detail.already_submitted || submitting} onClick={() => void submit()}>
                {detail.already_submitted ? "Evaluation already submitted" : submitting ? "Submitting…" : "Submit evaluation"}
              </button>
            </>
          )}
        </section>
      </div>
    </>
  );
}
