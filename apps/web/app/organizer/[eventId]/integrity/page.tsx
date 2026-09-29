"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "../../../../lib/api";

type IntegrityData = any;

function adaptiveStatus(adaptive: any, recommendationId: string) {
  const latest = adaptive?.latest_recalculation?.result;
  if (latest?.recommendation_id === recommendationId) return "COMPLETED";
  const current = adaptive?.current_recommendation;
  if (current?.id === recommendationId) return current.status ?? "RECOMMENDED";
  return adaptive?.run?.result?.recommendation?.id === recommendationId
    ? (adaptive?.run?.result?.recommendation?.status ?? "RECOMMENDED")
    : "—";
}


export default function IntegrityPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [data, setData] = useState<IntegrityData | null>(null);
  const [influence, setInfluence] = useState<any | null>(null);
  const [stability, setStability] = useState<any | null>(null);
  const [adaptive, setAdaptive] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [influenceLoading, setInfluenceLoading] = useState(false);
  const [stabilityLoading, setStabilityLoading] = useState(false);
  const [adaptiveLoading, setAdaptiveLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      const [integrityResult, influenceResult, stabilityResult, adaptiveResult, adaptiveRecommendations] = await Promise.all([
        apiFetch<any>(`/events/${eventId}/integrity/latest`),
        apiFetch<any>(`/events/${eventId}/judging/influence/latest`),
        apiFetch<any>(`/events/${eventId}/judging/stability/latest`),
        apiFetch<any>(`/events/${eventId}/judging/adaptive-review/latest`),
        apiFetch<any[]>(`/events/${eventId}/judging/adaptive-review/recommendations`),
      ]);
      setData(integrityResult.run?.result ?? null);
      setInfluence(influenceResult.run?.result ?? null);
      setStability(stabilityResult.run?.result ?? null);
      const latestRecommendation = adaptiveResult.run?.result?.recommendation;
      const currentRecommendation = latestRecommendation
        ? adaptiveRecommendations.find((item: any) => item.id === latestRecommendation.id)
        : null;
      setAdaptive({
        ...adaptiveResult,
        current_recommendation: currentRecommendation,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load integrity data");
    }
  }

  async function runIntegrity() {
    setLoading(true);
    setError("");
    try {
      const result = await apiFetch<any>(`/events/${eventId}/integrity/run`, {
        method: "POST",
        body: JSON.stringify({
          normalization_method: "robust_zscore",
          bootstrap_iterations: 500,
          attack_max_coalition: 3,
          sensitivity_delta: 0.05,
        }),
      });
      setData(result.result);
      setStability({
        baseline: {
          winner: result.result?.ranking?.[0]?.submission_id ?? null,
          ranking: result.result?.ranking ?? [],
        },
        bootstrap: result.result?.stability ?? null,
        rubric_sensitivity: result.result?.rubric_sensitivity ?? null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Integrity analysis failed");
    } finally {
      setLoading(false);
    }
  }

  async function runInfluence() {
    setInfluenceLoading(true);
    setError("");
    try {
      const result = await apiFetch<any>(
        `/events/${eventId}/judging/influence/analyze`,
        {
          method: "POST",
          body: JSON.stringify({
            normalization_method: "robust_zscore",
            min_observations: 3,
            clip: true,
            max_coalition: 3,
            max_exact_judges: 40,
            max_reported_coalitions: 10,
          }),
        },
      );
      setInfluence(result.result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Influence analysis failed");
    } finally {
      setInfluenceLoading(false);
    }
  }

  async function requestAdaptiveReview() {
    setAdaptiveLoading(true);
    setError("");
    try {
      const result = await apiFetch<any>(
        `/events/${eventId}/judging/adaptive-review/recommend`,
        {
          method: "POST",
          body: JSON.stringify({
            target_rank_limit: 5,
            max_candidates: 20,
            minimum_priority: 0.05,
            bootstrap_iterations: 500,
            attack_max_coalition: 3,
            sensitivity_delta: 0.05,
          }),
        },
      );
      setAdaptive({
        run: {
          result: {
            recommendation: { ...result.recommendation, id: result.recommendation_id },
          },
        },
        current_recommendation: result.recommendation,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Adaptive review recommendation failed");
    } finally {
      setAdaptiveLoading(false);
    }
  }

  async function decideAdaptiveReview(recommendationId: string, accept: boolean) {
    setAdaptiveLoading(true);
    setError("");
    try {
      await apiFetch<any>(
        `/events/${eventId}/judging/adaptive-review/recommendations/${recommendationId}/decision`,
        { method: "POST", body: JSON.stringify({ accept }) },
      );
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Adaptive review decision failed");
    } finally {
      setAdaptiveLoading(false);
    }
  }

  async function recalculateAdaptiveReview(recommendationId: string) {
    setAdaptiveLoading(true);
    setError("");
    try {
      const result = await apiFetch<any>(
        `/events/${eventId}/judging/adaptive-review/recommendations/${recommendationId}/recalculate`,
        {
          method: "POST",
          body: JSON.stringify({
            bootstrap_iterations: 500,
            attack_max_coalition: 3,
            sensitivity_delta: 0.05,
          }),
        },
      );
      setAdaptive((current: any) => ({
        ...(current ?? {}),
        current_recommendation: {
          ...(current?.current_recommendation ?? {}),
          id: recommendationId,
          status: "COMPLETED",
        },
        latest_recalculation: {
          id: result.run_id,
          result: result.result,
        },
      }));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Adaptive review recalculation failed");
    } finally {
      setAdaptiveLoading(false);
    }
  }

  async function runStability() {
    setStabilityLoading(true);
    setError("");
    try {
      const result = await apiFetch<any>(
        `/events/${eventId}/judging/stability/analyze`,
        {
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
        },
      );
      setStability(result.result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stability analysis failed");
    } finally {
      setStabilityLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [eventId]);

  const attack = influence?.attack_surface;
  const topJudges = influence?.judges?.slice(0, 10) ?? [];
  const stabilityBootstrap = stability?.bootstrap;
  const stabilityBaseline = stability?.baseline;
  const sensitivity = stability?.rubric_sensitivity;
  const ranking = stabilityBaseline?.ranking ?? [];

  return (
    <main>
      {error && <div className="error">{error}</div>}

      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>JudgeGuard Integrity</h2>
          <p className="muted">
            Statistical integrity, evaluator influence, and ranking resilience.
          </p>
        </div>
        <div className="row">
          <button onClick={runIntegrity} disabled={loading}>
            {loading ? "Analyzing…" : "Run integrity"}
          </button>
          <button onClick={runInfluence} disabled={influenceLoading}>
            {influenceLoading ? "Analyzing influence…" : "Analyze influence"}
          </button>
          <button onClick={runStability} disabled={stabilityLoading}>
            {stabilityLoading ? "Analyzing stability…" : "Analyze stability"}
          </button>
          <button onClick={requestAdaptiveReview} disabled={adaptiveLoading}>
            {adaptiveLoading ? "Selecting review…" : "Recommend adaptive review"}
          </button>
        </div>
      </div>

      {data && (
        <div className="grid">
          <div className="card">
            <div className="muted">Winner</div>
            <div className="stat">{data.ranking?.[0]?.submission_id ?? "—"}</div>
          </div>
          <div className="card">
            <div className="muted">Baseline winner rank-1 frequency</div>
            <div className="stat">
              {data.ranking?.length
                ? `${Math.round(
                    (data.stability?.rank1_frequency?.[data.ranking[0].submission_id] ?? 0) *
                      100,
                  )}%`
                : "—"}
            </div>
          </div>
          <div className="card">
            <div className="muted">Minimum flip set (integrity)</div>
            <div className="stat">
              {data.minimum_flip_set?.minimum_size ?? "none found"}
            </div>
          </div>
        </div>
      )}

      {influence && (
        <>
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <h3>Judge Influence Attack Surface</h3>
                <p className="muted">
                  Counterfactual judge-removal analysis with normalization frozen from
                  the complete panel.
                </p>
              </div>
              <span className="pill">
                {attack?.search_mode === "exact" ? "EXACT SEARCH" : "SCREENED SEARCH"}
              </span>
            </div>

            <div className="grid">
              <div className="card">
                <div className="muted">Single-judge winner flips</div>
                <div className="stat">{attack?.single_judge_flip_count ?? 0}</div>
              </div>
              <div className="card">
                <div className="muted">Single-judge flip rate</div>
                <div className="stat">
                  {attack
                    ? `${Math.round((attack.single_judge_flip_rate ?? 0) * 100)}%`
                    : "—"}
                </div>
              </div>
              <div className="card">
                <div className="muted">Minimum flip set</div>
                <div className="stat">
                  {attack?.minimum_flip_size ?? "none found"}
                </div>
              </div>
              <div className="card">
                <div className="muted">Coalitions tested</div>
                <div className="stat">{attack?.tested_combinations ?? 0}</div>
              </div>
            </div>

            <h4>Critical judges</h4>
            <div className="row" style={{ flexWrap: "wrap" }}>
              {(attack?.critical_judges ?? []).map((judgeId: string) => (
                <span className="pill" key={judgeId}>
                  {judgeId.slice(0, 8)}
                </span>
              ))}
              {!attack?.critical_judges?.length && (
                <span className="muted">No minimum-flip coalition found.</span>
              )}
            </div>
          </div>

          <div className="card">
            <h3>Judge Influence</h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Judge</th>
                  <th>Assignments</th>
                  <th>Winner flip</th>
                  <th>Max rank movement</th>
                  <th>Mean score delta</th>
                </tr>
              </thead>
              <tbody>
                {topJudges.map((judge: any) => (
                  <tr key={judge.judge_id}>
                    <td className="mono">{judge.judge_id}</td>
                    <td>{judge.assignment_count}</td>
                    <td>{judge.winner_changed ? "YES" : "NO"}</td>
                    <td>{judge.max_rank_movement}</td>
                    <td>{Number(judge.mean_abs_project_score_delta).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid">
            <div className="card">
              <h3>Minimum Flip Coalitions</h3>
              <pre className="mono">
                {JSON.stringify(attack?.minimum_flip_coalitions ?? [], null, 2)}
              </pre>
            </div>
            <div className="card">
              <h3>Influence Graph</h3>
              <p className="muted">
                {influence.graph?.node_count ?? 0} nodes · {influence.graph?.edge_count ?? 0}{" "}
                judge/project edges
              </p>
              <pre className="mono">
                {JSON.stringify(
                  (influence.graph?.nodes ?? []).slice(0, 12),
                  null,
                  2,
                )}
              </pre>
            </div>
          </div>
        </>
      )}

      {stability && (
        <>
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <h3>Ranking Stability</h3>
                <p className="muted">
                  {stabilityBootstrap?.iterations ?? 0} whole-panel bootstrap replicates;
                  normalization is frozen across all replicates.
                </p>
              </div>
              <span className="pill">SEED {stabilityBootstrap?.seed ?? "—"}</span>
            </div>

            <table className="table">
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Baseline rank</th>
                  <th>Baseline score</th>
                  <th>Rank-1 frequency</th>
                  <th>Top-{stabilityBootstrap?.top_k ?? 3} frequency</th>
                  <th>Mean rank</th>
                  <th>Rank SD</th>
                  <th>Coverage</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((item: any, index: number) => {
                  const id = String(item.submission_id);
                  return (
                    <tr key={id}>
                      <td className="mono">{id}</td>
                      <td>{index + 1}</td>
                      <td>{Number(item.score).toFixed(4)}</td>
                      <td>{Math.round(Number(stabilityBootstrap?.rank1_frequency?.[id] ?? 0) * 100)}%</td>
                      <td>{Math.round(Number(stabilityBootstrap?.top_k_frequency?.[id] ?? 0) * 100)}%</td>
                      <td>{Number(stabilityBootstrap?.mean_rank?.[id] ?? 0).toFixed(2)}</td>
                      <td>{Number(stabilityBootstrap?.rank_std_dev?.[id] ?? 0).toFixed(2)}</td>
                      <td>{Math.round(Number(stabilityBootstrap?.coverage_frequency?.[id] ?? 0) * 100)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="muted">
              Rank-1 and top-k frequencies are conditional on a project appearing in a
              sampled panel; coverage shows the fraction of all replicates where it was
              present.
            </p>
          </div>

          <div className="grid">
            <div className="card">
              <h3>Pairwise Stability</h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>Left project</th>
                    <th>Right project</th>
                    <th>Left wins</th>
                    <th>Comparisons</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.values(stabilityBootstrap?.pairwise_win_probability ?? {}).map(
                    (pair: any) => (
                      <tr key={`${pair.left_submission_id}|${pair.right_submission_id}`}>
                        <td className="mono">{pair.left_submission_id}</td>
                        <td className="mono">{pair.right_submission_id}</td>
                        <td>{Math.round(Number(pair.left_win_probability) * 100)}%</td>
                        <td>{pair.comparison_count}</td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>

            <div className="card">
              <h3>Rubric Sensitivity</h3>
              <p className="muted">
                Each scenario shifts one criterion by an absolute amount and redistributes
                that amount across the other active criteria.
              </p>
              <div className="mono">
                {sensitivity?.diagnostics?.winner_change_count ?? 0} winner-changing
                scenarios out of {sensitivity?.diagnostics?.scenario_count ?? 0} tested.
              </div>
              <pre className="mono">
                {JSON.stringify(
                  (sensitivity?.scenarios ?? []).filter((item: any) => item.winner_changed).slice(0, 8),
                  null,
                  2,
                )}
              </pre>
            </div>
          </div>
        </>
      )}

      {adaptive?.run?.result?.recommendation && (
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div>
              <h3>Adaptive Review</h3>
              <p className="muted">
                Step 13 stability signals select one review target and one independent judge.
                The review-value score is a transparent heuristic, not a probability.
              </p>
            </div>
            <span className="pill">
              {adaptive.run.result.recommendation.model ?? "ADAPTIVE"}
            </span>
          </div>

          <div className="grid">
            <div className="card">
              <div className="muted">Target submission</div>
              <div className="stat mono">
                {adaptive.run.result.recommendation.submission_id}
              </div>
            </div>
            <div className="card">
              <div className="muted">Recommended judge</div>
              <div className="stat mono">
                {adaptive.run.result.recommendation.judge_id ?? "None eligible"}
              </div>
            </div>
            <div className="card">
              <div className="muted">Estimated review value</div>
              <div className="stat">
                {Number(adaptive.run.result.recommendation.estimated_review_value ?? 0).toFixed(3)}
              </div>
            </div>
            <div className="card">
              <div className="muted">Status</div>
              <div className="stat">
                {(() => {
                  const id = adaptive.run.result.recommendation.id;
                  return adaptiveStatus(adaptive, id);
                })()}
              </div>
            </div>
          </div>

          <div className="grid">
            <div className="card">
              <h4>Target factors</h4>
              <pre className="mono">
                {JSON.stringify(adaptive.run.result.recommendation.target_priority, null, 2)}
              </pre>
            </div>
            <div className="card">
              <h4>Judge factors</h4>
              <pre className="mono">
                {JSON.stringify(adaptive.run.result.recommendation.judge_utility, null, 2)}
              </pre>
            </div>
          </div>

          <p className="muted">{adaptive.run.result.recommendation.reason}</p>

          {adaptive.run.result.recommendation.id && (
            <div className="row">
              <button
                onClick={() => decideAdaptiveReview(adaptive.run.result.recommendation.id, true)}
                disabled={adaptiveLoading || !adaptive.run.result.recommendation.judge_id}
              >
                Accept & create review
              </button>
              <button
                onClick={() => decideAdaptiveReview(adaptive.run.result.recommendation.id, false)}
                disabled={adaptiveLoading}
              >
                Reject
              </button>
              {adaptiveStatus(adaptive, adaptive.run.result.recommendation.id) === "REVIEW_PENDING" && (
                <button
                  onClick={() => recalculateAdaptiveReview(adaptive.run.result.recommendation.id)}
                  disabled={adaptiveLoading}
                >
                  Recalculate after evaluation
                </button>
              )}
            </div>
          )}

          {adaptive?.latest_recalculation?.result && (
            <div className="card">
              <h4>Post-review recalculation</h4>
              <div className="grid">
                <div>
                  <div className="muted">Winner before</div>
                  <div className="mono">{adaptive.latest_recalculation.result.before?.winner ?? "—"}</div>
                </div>
                <div>
                  <div className="muted">Winner after</div>
                  <div className="mono">{adaptive.latest_recalculation.result.after?.winner ?? "—"}</div>
                </div>
                <div>
                  <div className="muted">Target rank-1 frequency after</div>
                  <div>
                    {adaptive.latest_recalculation.result.after?.stability_rank1_frequency == null
                      ? "—"
                      : `${Math.round(Number(adaptive.latest_recalculation.result.after.stability_rank1_frequency) * 100)}%`}
                  </div>
                </div>
              </div>
              <p className="muted">The new analysis is stored separately; raw evaluations remain unchanged.</p>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
