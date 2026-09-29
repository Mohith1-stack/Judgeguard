"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "../../../lib/api";

type Criterion = {
  id?: string;
  name: string;
  description: string;
  weight: number;
  min_score: number;
  max_score: number;
  sort_order: number;
};

type Rubric = {
  id: string;
  event_id: string;
  name: string;
  version: number;
  is_active: boolean;
  criteria: Criterion[];
};

type Judge = {
  id: string;
  user_id: string;
  email: string;
  display_name: string;
  role: string;
  capacity: number;
  expertise: string[];
  notes: string;
};

type Conflict = {
  id: string;
  judge_id: string;
  team_id: string;
  reason: string;
};

export default function JudgingManagementPage() {
  const { eventId } = useParams<{ eventId: string }>();

  const [rubrics, setRubrics] = useState<Rubric[]>([]);
  const [judges, setJudges] = useState<Judge[]>([]);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [rubricName, setRubricName] = useState("Evaluation Rubric");
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [judgeUserId, setJudgeUserId] = useState("");
  const [capacity, setCapacity] = useState(10);
  const [expertise, setExpertise] = useState("");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const activeRubric = useMemo(
    () => rubrics.find((rubric) => rubric.is_active),
    [rubrics],
  );

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [rubricData, judgeData, conflictData] = await Promise.all([
        apiFetch<Rubric[]>(`/events/${eventId}/rubrics`),
        apiFetch<Judge[]>(`/events/${eventId}/judges`),
        apiFetch<Conflict[]>(`/events/${eventId}/judge-conflicts`),
      ]);
      setRubrics(rubricData);
      setJudges(judgeData);
      setConflicts(conflictData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load judging configuration");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [eventId]);

  function addCriterion() {
    setCriteria((current) => [
      ...current,
      {
        name: "",
        description: "",
        weight: 0,
        min_score: 1,
        max_score: 5,
        sort_order: current.length,
      },
    ]);
  }

  async function createRubric() {
    if (!criteria.length) {
      setError("Add at least one criterion.");
      return;
    }

    setWorking(true);
    setError("");
    setMessage("");
    try {
      const rubric = await apiFetch<Rubric>(`/events/${eventId}/rubrics`, {
        method: "POST",
        body: JSON.stringify({ name: rubricName }),
      });

      for (const criterion of criteria) {
        await apiFetch(`/rubrics/${rubric.id}/criteria`, {
          method: "POST",
          body: JSON.stringify(criterion),
        });
      }

      await apiFetch(`/rubrics/${rubric.id}/activate`, { method: "POST" });
      setCriteria([]);
      setRubricName("Evaluation Rubric");
      setMessage("Rubric created and activated.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create rubric");
    } finally {
      setWorking(false);
    }
  }

  async function addJudge() {
    if (!judgeUserId.trim()) {
      setError("Enter the real user UUID for the judge.");
      return;
    }

    setWorking(true);
    setError("");
    setMessage("");
    try {
      await apiFetch(`/events/${eventId}/judges`, {
        method: "POST",
        body: JSON.stringify({
          user_id: judgeUserId.trim(),
          capacity,
          expertise: expertise
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
        }),
      });
      setJudgeUserId("");
      setExpertise("");
      setMessage("Judge profile saved.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save judge");
    } finally {
      setWorking(false);
    }
  }

  if (loading) {
    return <main className="shell">Loading judging configuration…</main>;
  }

  return (
    <main className="shell">
      <div className="nav">
        <div>
          <div className="brand">JUDGEGUARD</div>
          <div className="muted">Rubrics + Judge Management</div>
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {message && <div className="success">{message}</div>}

      <div className="grid">
        <section className="card">
          <h2>Create rubric version</h2>
          <p className="muted">
            Draft versions can be edited. Activation freezes that version for judging.
          </p>

          <div className="field">
            <div className="label">Rubric name</div>
            <input value={rubricName} onChange={(event) => setRubricName(event.target.value)} />
          </div>

          {criteria.map((criterion, index) => (
            <div className="card" key={index}>
              <div className="field">
                <div className="label">Criterion name</div>
                <input
                  value={criterion.name}
                  onChange={(event) =>
                    setCriteria((current) =>
                      current.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, name: event.target.value } : item,
                      ),
                    )
                  }
                />
              </div>

              <div className="field">
                <div className="label">Description</div>
                <textarea
                  value={criterion.description}
                  onChange={(event) =>
                    setCriteria((current) =>
                      current.map((item, itemIndex) =>
                        itemIndex === index ? { ...item, description: event.target.value } : item,
                      ),
                    )
                  }
                />
              </div>

              <div className="grid">
                <div className="field">
                  <div className="label">Weight</div>
                  <input
                    type="number"
                    min="0.000001"
                    max="1"
                    step="0.01"
                    value={criterion.weight}
                    onChange={(event) =>
                      setCriteria((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, weight: Number(event.target.value) } : item,
                        ),
                      )
                    }
                  />
                </div>

                <div className="field">
                  <div className="label">Minimum score</div>
                  <input
                    type="number"
                    value={criterion.min_score}
                    onChange={(event) =>
                      setCriteria((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, min_score: Number(event.target.value) } : item,
                        ),
                      )
                    }
                  />
                </div>

                <div className="field">
                  <div className="label">Maximum score</div>
                  <input
                    type="number"
                    value={criterion.max_score}
                    onChange={(event) =>
                      setCriteria((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, max_score: Number(event.target.value) } : item,
                        ),
                      )
                    }
                  />
                </div>
              </div>
            </div>
          ))}

          <div className="row">
            <button className="secondary" type="button" onClick={addCriterion}>
              Add criterion
            </button>
            <button type="button" onClick={createRubric} disabled={working}>
              Create + activate rubric
            </button>
          </div>
        </section>

        <section className="card">
          <h2>Current rubrics</h2>
          {rubrics.length === 0 && <p className="muted">No rubric versions yet.</p>}
          {rubrics.map((rubric) => (
            <div className="card" key={rubric.id}>
              <div className="row">
                <strong>{rubric.name}</strong>
                <span className="pill">v{rubric.version}</span>
                {rubric.is_active && <span className="pill">ACTIVE</span>}
              </div>
              <p className="muted">{rubric.criteria.length} criteria</p>
              {rubric.criteria.map((criterion) => (
                <div key={criterion.id} className="row">
                  <span>{criterion.name}</span>
                  <span className="muted">{criterion.weight}</span>
                </div>
              ))}
            </div>
          ))}
          {activeRubric && (
            <p className="success">
              Active rubric: v{activeRubric.version} · {activeRubric.name}
            </p>
          )}
        </section>
      </div>

      <section className="card">
        <h2>Judge profiles</h2>
        <p className="muted">
          Use a real registered user UUID. Capacity and expertise are persisted in PostgreSQL.
        </p>

        <div className="grid">
          <div className="field">
            <div className="label">User UUID</div>
            <input value={judgeUserId} onChange={(event) => setJudgeUserId(event.target.value)} />
          </div>
          <div className="field">
            <div className="label">Capacity</div>
            <input
              type="number"
              min="1"
              max="500"
              value={capacity}
              onChange={(event) => setCapacity(Number(event.target.value))}
            />
          </div>
          <div className="field">
            <div className="label">Expertise (comma separated)</div>
            <input value={expertise} onChange={(event) => setExpertise(event.target.value)} />
          </div>
        </div>
        <button type="button" onClick={addJudge} disabled={working}>Save judge</button>
      </section>

      <section className="card">
        <h2>Configured judges</h2>
        {judges.length === 0 && <p className="muted">No judges configured.</p>}
        {judges.map((judge) => (
          <div className="card" key={judge.id}>
            <div className="row">
              <strong>{judge.display_name}</strong>
              <span className="pill">{judge.role}</span>
            </div>
            <p>{judge.email}</p>
            <p className="muted">Capacity: {judge.capacity}</p>
            <p className="muted">Expertise: {judge.expertise.join(", ") || "—"}</p>
          </div>
        ))}
      </section>

      <section className="card">
        <h2>Judge conflicts</h2>
        {conflicts.length === 0 ? (
          <p className="muted">No conflicts configured.</p>
        ) : (
          conflicts.map((conflict) => (
            <div className="row" key={conflict.id}>
              <span className="mono">{conflict.judge_id}</span>
              <span>↔</span>
              <span className="mono">{conflict.team_id}</span>
              <span className="muted">{conflict.reason}</span>
            </div>
          ))
        )}
      </section>
    </main>
  );
}
