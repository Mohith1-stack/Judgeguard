# Step 13 Implementation Notes

## Files

- `apps/api/app/engine/stability.py` — ranking bootstrap and rubric sensitivity engine.
- `apps/api/app/api/stability.py` — persisted, organizer/admin-only API.
- `apps/api/app/schemas/stability.py` — request validation.
- `apps/api/app/api/router.py` — route registration.
- `apps/api/app/engine/__init__.py` — engine exports.
- `apps/api/app/api/integrity.py` — unified integrity run now consumes the Step 13 stability model.
- `apps/web/app/organizer/[eventId]/integrity/page.tsx` — dashboard view.
- `tests/test_step13_stability.py` — deterministic and invariant-focused tests.

## Frozen normalization boundary

The Step 13 engine calls `normalize_by_judge_criterion()` exactly once against the complete current evaluation set. Bootstrap replicates only the already-normalized judge observations. Rubric sensitivity also reuses those same normalized observations.

This boundary is deliberate: repeated recalibration inside every perturbation would mix two different effects—judge panel composition and scale calibration—and make the resulting stability signal harder to interpret.

## Panel bootstrap

Let `J` be the observed judge set. For each replicate, sample `|J|` judges with replacement. Each sampled judge contributes the complete project panel actually observed for that judge. The system then recomputes the event ranking from those sampled judge/project aggregates.

For a submission `p`:

- `coverage_frequency(p)` = fraction of replicates where `p` is present.
- `rank1_frequency(p)` = rank-1 count divided by the number of replicates where `p` is present.
- `top_k_frequency(p)` = top-k count divided by the same conditional denominator.
- `mean_rank(p)` and `rank_std_dev(p)` are calculated over the observed bootstrap ranks.

This avoids silently assigning a rank to a project that is absent from a sampled panel.

## Rubric sensitivity

For each criterion and each direction, the requested absolute weight shift is applied to the target criterion and redistributed proportionally across the remaining positive-weight criteria. The total is re-normalized defensively to 1.0.

The engine evaluates an ordered grid from one step to the requested maximum delta. It reports winner changes, winner-margin changes, rank movement, and the exact resulting weight vector.

## Auditability

`AnalyticsRun.kind = "STABILITY"` and method `frozen_normalization_panel_bootstrap_v1` identify the analysis family. The stored `input_hash` covers the raw evaluation rows, active rubric criteria and request configuration. The API also records an audit event containing the run identifier, seed, iteration count and winner-change count.

No official score is mutated.
