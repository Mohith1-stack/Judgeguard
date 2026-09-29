"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "../../../../lib/api";
import { MetricCard, ProgressBar, SectionTitle, StatusBadge, TagList } from "../../../../components/ui";

type Event = { id: string; name: string; status: string };
type Analytics = any;

function percent(value: unknown, digits = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

function shortId(value: unknown) {
  const text = String(value ?? "");
  return text ? `${text.slice(0, 8)}…` : "—";
}

function statusForRecommendation(adaptive: any) {
  const rec = adaptive?.run?.result?.recommendation;
  if (!rec) return adaptive?.current_recommendation?.status ?? "—";
  return adaptive?.current_recommendation?.status ?? rec.status ?? "—";
}

export default function IntegrityPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [event, setEvent] = useState<Event | null>(null);
  const [integrity, setIntegrity] = useState<Analytics | null>(null);
  const [influence, setInfluence] = useState<Analytics | null>(null);
  const [stability, setStability] = useState<Analytics | null>(null);
  const [adaptive, setAdaptive] = useState<Analytics | null>(null);
  const [audit, setAudit] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [eventData, integrityRun, influenceRun, stabilityRun, adaptiveRun, auditData] = await Promise.all([
        apiFetch<Event>(`/events/${eventId}`),
        apiFetch<any>(`/events/${eventId}/integrity/latest`).catch(() => null),
        apiFetch<any>(`/events/${eventId}/judging/influence/latest`).catch(() => null),
        apiFetch<any>(`/events/${eventId}/judging/stability/latest`).catch(() => null),
        apiFetch<any>(`/events/${eventId}/judging/adaptive-review/latest`).catch(() => null),
        apiFetch<any[]>(`/events/${eventId}/audit`).catch(() => []),
      ]);
      setEvent(eventData);
      setIntegrity(integrityRun?.run?.result ?? integrityRun?.result ?? null);
      setInfluence(influenceRun?.run?.result ?? influenceRun?.result ?? null);
      setStability(stabilityRun?.run?.result ?? stabilityRun?.result ?? null);
      setAdaptive(adaptiveRun ?? null);
      setAudit(auditData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load integrity center");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [eventId]);

  async function runIntegrity() {
    setWorking("integrity"); setError(""); setMessage("");
    try {
      await apiFetch(`/events/${eventId}/integrity/run`, {
        method: "POST",
        body: JSON.stringify({
          normalization_method: "robust_zscore",
          bootstrap_iterations: 500,
          attack_max_coalition: 3,
          sensitivity_delta: 0.05,
        }),
      });
      setMessage("Full integrity analysis completed.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Integrity analysis failed");
    } finally { setWorking(null); }
  }

  async function runInfluence() {
    setWorking("influence"); setError(""); setMessage("");
    try {
      await apiFetch(`/events/${eventId}/judging/influence/analyze`, {
        method: "POST",
        body: JSON.stringify({
          normalization_method: "robust_zscore",
          min_observations: 3,
          clip: true,
          max_coalition: 3,
          max_exact_judges: 40,
          max_reported_coalitions: 10,
        }),
      });
      setMessage("Influence analysis completed.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Influence analysis failed");
    } finally { setWorking(null); }
  }

  async function runStability() {
    setWorking("stability"); setError(""); setMessage("");
    try {
      await apiFetch(`/events/${eventId}/judging/stability/analyze`, {
        method: "POST",
        body: JSON.stringify({
          normalization_method: "robust_zscore",
          min_observations: 3,
          clip: true,
          bootstrap_iterations: 1000,
          seed: 0,
          top_k: 3,
          pairwise_top_n: 5,
          sensitivity_delta: 0.05,
          sensitivity_steps: 4,
        }),
      });
      setMessage("Ranking stability analysis completed.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stability analysis failed");
    } finally { setWorking(null); }
  }

  async function recommend() {
    setWorking("adaptive"); setError(""); setMessage("");
    try {
      await apiFetch(`/events/${eventId}/judging/adaptive-review/recommend`, {
        method: "POST",
        body: JSON.stringify({ target_rank_limit: 5, max_candidates: 20, minimum_priority: 0.05 }),
      });
      setMessage("Adaptive review recommendation generated.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Adaptive review recommendation failed");
    } finally { setWorking(null); }
  }

  async function decide(recommendationId: string, accept: boolean) {
    setWorking("decision"); setError(""); setMessage("");
    try {
      await apiFetch(`/events/${eventId}/judging/adaptive-review/recommendations/${recommendationId}/decision`, {
        method: "POST",
        body: JSON.stringify({ accept }),
      });
      setMessage(accept ? "Adaptive review accepted and assignment created." : "Adaptive review rejected.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Adaptive review decision failed");
    } finally { setWorking(null); }
  }

  async function recalculate(recommendationId: string) {
    setWorking("recalculate"); setError(""); setMessage("");
    try {
      await apiFetch(`/events/${eventId}/judging/adaptive-review/recommendations/${recommendationId}/recalculate`, {
        method: "POST",
        body: JSON.stringify({ bootstrap_iterations: 500, attack_max_coalition: 3, sensitivity_delta: 0.05 }),
      });
      setMessage("Post-review integrity evidence recalculated.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recalculation failed");
    } finally { setWorking(null); }
  }

  const ranking = stability?.baseline?.ranking ?? integrity?.ranking ?? [];
  const bootstrap = stability?.bootstrap ?? integrity?.stability ?? {};
  const attack = influence?.attack_surface ?? integrity?.attack_surface ?? integrity?.minimum_flip_set ?? {};
  const sensitivity = stability?.rubric_sensitivity ?? integrity?.rubric_sensitivity ?? {};
  const winner = ranking[0]?.submission_id ?? integrity?.ranking?.[0]?.submission_id ?? null;
  const winnerFrequency = winner ? bootstrap?.rank1_frequency?.[winner] : null;
  const recommendation = adaptive?.run?.result?.recommendation ?? adaptive?.current_recommendation ?? null;
  const recommendationId = recommendation?.id;

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">JUDGING INTEGRITY CENTER</div>
          <h1>{event?.name ?? "Integrity Center"}</h1>
          <p className="muted">Counterfactual influence, ranking resilience, rubric sensitivity, and adaptive review.</p>
        </div>
        <div className="heading-actions">
          <Link className="button ghost" href={`/organizer/${eventId}`}>Event console</Link>
          <Link className="button ghost" href={`/gallery/${eventId}`}>Public gallery</Link>
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
      {message ? <div className="success-banner">{message}</div> : null}

      <section className="integrity-hero">
        <div className="integrity-hero-copy">
          <div className="eyebrow">LIVE EVIDENCE CHAIN</div>
          <h2>From raw evaluations to a tested leaderboard.</h2>
          <p>
            JudgeGuard keeps the underlying scores immutable and layers reproducible analytics over them.
            Each stage below can be rerun against the persisted event data.
          </p>
          <div className="evidence-chain">
            {[
              ["01", "Normalize", "criterion-specific"],
              ["02", "Influence", "judge-removal"],
              ["03", "Stability", "panel bootstrap"],
              ["04", "Sensitivity", "rubric perturbation"],
              ["05", "Adaptive", "next review"],
            ].map(([n, title, detail]) => (
              <div className="evidence-step" key={title}>
                <span>{n}</span><strong>{title}</strong><small>{detail}</small>
              </div>
            ))}
          </div>
        </div>
        <div className="integrity-hero-status">
          <div className="status-orbit">
            <div className="orbit-center">JG</div>
            <div className="orbit-label orbit-top">AUDITABLE</div>
            <div className="orbit-label orbit-right">REPRODUCIBLE</div>
            <div className="orbit-label orbit-bottom">ADAPTIVE</div>
            <div className="orbit-label orbit-left">ISOLATED</div>
          </div>
        </div>
      </section>

      <section className="stats-grid">
        <MetricCard label="Current winner" value={shortId(winner)} detail="baseline leaderboard" tone="accent" />
        <MetricCard label="Rank-1 frequency" value={percent(winnerFrequency)} detail="whole-panel bootstrap" tone={Number(winnerFrequency) >= 0.8 ? "good" : "warn"} />
        <MetricCard label="Minimum flip size" value={String(attack?.minimum_flip_size ?? integrity?.minimum_flip_set?.minimum_size ?? "—")} detail="smallest judge coalition that changes winner" tone="warn" />
        <MetricCard label="Winner-changing scenarios" value={String(sensitivity?.diagnostics?.winner_change_count ?? 0)} detail={`of ${sensitivity?.diagnostics?.scenario_count ?? 0} rubric scenarios`} />
      </section>

      <section className="panel">
        <SectionTitle
          eyebrow="CONTROL ROOM"
          title="Run the evidence pipeline"
          description="Use the existing backend analyzers. The frontend never fabricates analytics."
        />
        <div className="action-grid">
          <button className="action-card" onClick={() => void runIntegrity()} disabled={loading || !!working}>
            <span className="action-icon">◎</span>
            <strong>{working === "integrity" ? "Running…" : "Run full integrity"}</strong>
            <small>Normalization + influence + stability evidence</small>
          </button>
          <button className="action-card" onClick={() => void runInfluence()} disabled={loading || !!working}>
            <span className="action-icon">↔</span>
            <strong>{working === "influence" ? "Analyzing…" : "Analyze influence"}</strong>
            <small>Judge removal and minimum flip sets</small>
          </button>
          <button className="action-card" onClick={() => void runStability()} disabled={loading || !!working}>
            <span className="action-icon">≈</span>
            <strong>{working === "stability" ? "Bootstrapping…" : "Analyze stability"}</strong>
            <small>Panel perturbation and rubric sensitivity</small>
          </button>
          <button className="action-card action-card-accent" onClick={() => void recommend()} disabled={loading || !!working || !stability}>
            <span className="action-icon">↗</span>
            <strong>{working === "adaptive" ? "Selecting…" : "Recommend adaptive review"}</strong>
            <small>Choose the next independent review from live evidence</small>
          </button>
        </div>
      </section>

      <div className="two-col">
        <section className="panel">
          <SectionTitle eyebrow="RANKING" title="Leaderboard stability" description={bootstrap?.iterations ? `${bootstrap.iterations} deterministic bootstrap replicates · seed ${bootstrap.seed ?? "—"}` : "Run stability analysis to populate this view."} />
          {ranking.length ? (
            <div className="ranking-list">
              {ranking.map((item: any, index: number) => {
                const id = String(item.submission_id);
                const rank1 = Number(bootstrap?.rank1_frequency?.[id] ?? 0);
                const topK = Number(bootstrap?.top_k_frequency?.[id] ?? 0);
                return (
                  <div className="ranking-row" key={id}>
                    <div className="rank-number">{String(index + 1).padStart(2, "0")}</div>
                    <div className="rank-project"><strong>{shortId(id)}</strong><span className="muted">score {Number(item.score).toFixed(4)}</span></div>
                    <div className="rank-metrics">
                      <div><span>rank 1</span><strong>{percent(rank1)}</strong><ProgressBar value={rank1 * 100} /></div>
                      <div><span>top {bootstrap?.top_k ?? 3}</span><strong>{percent(topK)}</strong><ProgressBar value={topK * 100} /></div>
                    </div>
                    <div className="rank-score">{Number(bootstrap?.mean_rank?.[id] ?? index + 1).toFixed(2)}<small>mean rank</small></div>
                  </div>
                );
              })}
            </div>
          ) : <div className="empty-inline">No stability run is available yet.</div>}
        </section>

        <section className="panel">
          <SectionTitle eyebrow="INFLUENCE" title="Judge impact surface" description={attack?.search_mode ? `${attack.search_mode} coalition search · ${attack.tested_combinations ?? 0} combinations` : "Run influence analysis to populate this view."} />
          <div className="mini-metrics">
            <MetricCard label="Single-judge flips" value={String(attack?.single_judge_flip_count ?? 0)} />
            <MetricCard label="Flip rate" value={percent(attack?.single_judge_flip_rate)} />
            <MetricCard label="Critical judges" value={String((attack?.critical_judges ?? []).length)} />
          </div>
          <div className="critical-list">
            {(attack?.critical_judges ?? []).slice(0, 8).map((judgeId: string) => (
              <span className="tag tag-alert" key={judgeId}>{shortId(judgeId)}</span>
            ))}
            {!attack?.critical_judges?.length ? <span className="muted">No critical coalition reported.</span> : null}
          </div>
          <div className="attack-note">
            <strong>Counterfactual model</strong>
            <span>Normalization stays frozen while a judge or coalition is removed. This isolates evaluator contribution from recalibration.</span>
          </div>
        </section>
      </div>

      <div className="two-col">
        <section className="panel">
          <SectionTitle eyebrow="SENSITIVITY" title="Rubric perturbation" description="Criterion weights are perturbed while total rubric weight remains conserved." />
          <div className="sensitivity-summary">
            <div className="sensitivity-ring">
              <span>{sensitivity?.diagnostics?.winner_change_count ? "Δ" : "—"}</span>
            </div>
            <div>
              <strong>{sensitivity?.diagnostics?.winner_change_count ?? 0} winner-changing scenarios</strong>
              <p className="muted">{sensitivity?.diagnostics?.scenario_count ?? 0} scenarios tested across the active rubric.</p>
            </div>
          </div>
          <div className="scenario-list">
            {(sensitivity?.scenarios ?? []).filter((scenario: any) => scenario.winner_changed).slice(0, 6).map((scenario: any, index: number) => (
              <div className="scenario" key={`${scenario.criterion_id}-${scenario.delta}-${index}`}>
                <span className="tag tag-alert">{scenario.delta > 0 ? "+" : ""}{scenario.delta}</span>
                <div><strong>{shortId(scenario.criterion_id)}</strong><span className="muted">{shortId(scenario.baseline_winner)} → {shortId(scenario.winner)}</span></div>
              </div>
            ))}
            {!((sensitivity?.scenarios ?? []).some((scenario: any) => scenario.winner_changed)) ? <span className="muted">No winner-changing scenarios in the stored run.</span> : null}
          </div>
        </section>

        <section className="panel">
          <SectionTitle eyebrow="ADAPTIVE REVIEW" title="Close the loop" description="The next review is selected from the current stability and influence evidence." />
          {recommendation ? (
            <>
              <div className="adaptive-target">
                <div>
                  <span className="eyebrow">TARGET SUBMISSION</span>
                  <strong>{shortId(recommendation.submission_id)}</strong>
                </div>
                <div className="adaptive-arrow">→</div>
                <div>
                  <span className="eyebrow">RECOMMENDED JUDGE</span>
                  <strong>{recommendation.judge_id ? shortId(recommendation.judge_id) : "None eligible"}</strong>
                </div>
              </div>
              <div className="adaptive-factors">
                <div><span>Expected review value</span><strong>{Number(recommendation.estimated_review_value ?? recommendation.expected_gain ?? 0).toFixed(3)}</strong></div>
                <div><span>Status</span><StatusBadge status={statusForRecommendation(adaptive)} /></div>
              </div>
              <p className="muted">{recommendation.reason}</p>
              <div className="row">
                {recommendationId && recommendation.judge_id && statusForRecommendation(adaptive) === "RECOMMENDED" ? (
                  <button onClick={() => void decide(recommendationId, true)} disabled={!!working}>Accept review</button>
                ) : null}
                {recommendationId && statusForRecommendation(adaptive) === "RECOMMENDED" ? (
                  <button className="button ghost" onClick={() => void decide(recommendationId, false)} disabled={!!working}>Reject</button>
                ) : null}
                {recommendationId && statusForRecommendation(adaptive) === "REVIEW_PENDING" ? (
                  <button onClick={() => void recalculate(recommendationId)} disabled={!!working}>Recalculate</button>
                ) : null}
              </div>
              {adaptive?.latest_recalculation?.result ? (
                <div className="before-after">
                  <div><span>Before</span><strong>{shortId(adaptive.latest_recalculation.result.before?.winner)}</strong></div>
                  <div className="before-after-arrow">→</div>
                  <div><span>After</span><strong>{shortId(adaptive.latest_recalculation.result.after?.winner)}</strong></div>
                </div>
              ) : null}
            </>
          ) : (
            <div className="empty-inline">Run stability analysis, then request an adaptive review recommendation.</div>
          )}
        </section>
      </div>

      <section className="panel">
        <SectionTitle eyebrow="AUDIT TRAIL" title="Recent integrity actions" description="Read-only event history from the audit API." />
        {audit.length ? (
          <div className="audit-list">
            {audit.slice(0, 10).map((item) => (
              <div className="audit-row" key={item.id}>
                <span className="audit-time mono">{new Date(item.created_at).toLocaleString()}</span>
                <span className="audit-action">{item.action}</span>
                <span className="audit-entity mono">{shortId(item.entity_id)}</span>
              </div>
            ))}
          </div>
        ) : <div className="empty-inline">No audit entries are available for this event.</div>}
      </section>

      <div className="integrity-footnote">
        <span>Evidence is computed from live PostgreSQL-backed records.</span>
        <span className="mono">raw evaluations immutable</span>
      </div>
    </>
  );
}
