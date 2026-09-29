# Step 14 Implementation Notes

## Files

- `apps/api/app/engine/adaptive.py` — deterministic target/judge selection heuristic.
- `apps/api/app/services/adaptive_review.py` — database-backed candidate discovery and hardened decision checks.
- `apps/api/app/api/adaptive.py` — dedicated Step 14 endpoints and persistence.
- `apps/api/app/api/integrity.py` — unified integrity compatibility path now uses the hardened decision service.
- `apps/api/app/api/router.py` — Step 14 route registration.
- `apps/api/app/schemas/adaptive.py` — request validation.
- `apps/web/app/organizer/[eventId]/integrity/page.tsx` — adaptive-review workflow UI.
- `tests/test_step14_adaptive.py` — deterministic and hard-exclusion tests.

## Target selection

The engine considers the current top-ranked projects reported by Step 13. It combines rank-1 uncertainty, score-boundary position, bootstrap coverage deficit and Step 12 minimum-flip fragility into a bounded review-priority heuristic.

This does not estimate a probability that a new review will change the result. The output is an operational priority used to choose where another independent observation may be useful.

## Judge selection

Eligibility is structural and hard-filtered:

1. the judge has not already been assigned the target;
2. the judge has no recorded conflict with the target team;
3. the judge is not a member of the target team;
4. the judge has remaining assignment capacity.

Eligible candidates are ordered by expertise fit, capacity slack and panel diversity. The panel-diversity term measures overlap between the candidate's existing reviewed projects and the projects already reviewed by the target's current panel.

## Revalidation at acceptance

Recommendations are advisory. At acceptance time the backend re-reads the database and checks judging-window status, submission state, judge profile, team membership, conflicts, assignment uniqueness and capacity. This prevents a stale recommendation from creating a forbidden assignment.

## Closed-loop recalculation

After the selected judge submits the new evaluation, the organizer may call the recalculation endpoint. The endpoint:

- reads the current raw evaluation set;
- reuses the recommendation's normalization configuration;
- recomputes Step 13 ranking stability;
- recomputes Step 12 influence/attack-surface diagnostics;
- records before/after target and winner information;
- persists the analysis as `ADAPTIVE_REVIEW_RESULT`;
- marks the recommendation `COMPLETED`.

No official ranking is published or mutated by this operation. It produces evidence for the organizer's existing publication workflow.

## Auditability

The recommendation run stores source analytics-run IDs, configuration, selection factors, candidate traces and an input hash. Acceptance and recalculation create explicit audit events.
