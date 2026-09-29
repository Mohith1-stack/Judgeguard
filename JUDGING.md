# Judging Method

## Weighted aggregate

For normalized criterion scores `x_pc` and rubric weights `w_c`:

`S_p = sum(w_c * x_pc) / sum(w_c)`

The API requires the active rubric weights to sum to 1.0.

## Normalization

Two transparent methods are available:

- `zscore`: `(x - mean_j) / std_j`
- `robust_zscore`: `(x - median_j) / (1.4826 * MAD_j)`

The normalized value is mapped back to the event's observed score range so it remains interpretable.

## Stability

JudgeGuard bootstraps the evaluator panel with replacement while freezing criterion-specific normalization from the complete observed dataset. Each sampled judge contributes the complete project panel actually observed for that judge. Rank-1, rank-distribution and top-k frequencies are conditional on a project being present in the sampled panel; coverage frequency is reported separately. Pairwise win probabilities are empirical bootstrap frequencies for the baseline top candidates and are not significance tests.

## Influence

Leave-one-judge-out analysis measures winner change and maximum project rank movement when an evaluator is removed.

## Minimum flip set

The engine searches evaluator coalitions up to the configured maximum and identifies the smallest tested coalition whose removal changes the current winner.

This is a structural stress test, not a claim that any judge is malicious.

## Assignment robustness

The assignment optimizer respects:

- per-judge capacity
- judge/submission uniqueness
- judge/team conflicts
- expertise overlap
- workload balance

Queue order is rotated per judge to avoid systematically placing a project first or last.

## Rubric sensitivity

Each criterion is tested over configurable increase/decrease steps while preserving the total weight by redistributing the shift across the other criteria. The same frozen normalized observations are reused for every scenario. The engine reports the exact perturbed weights, winner-margin change, rank movement and scenarios in which the winner changes.

## Adaptive review

When Step 13 identifies ranking uncertainty, the adaptive engine selects a review target using rank-1 uncertainty, ranking-boundary closeness, panel coverage deficit and Step 12 fragility signals. It then hard-filters judges for duplicate assignment, conflicts, self-review and exhausted capacity. Eligible judges are ordered by expertise fit, remaining capacity and panel diversity. The resulting review value is a deterministic heuristic, not a probability of outcome change.

Recommendations are advisory. The backend revalidates the event judging window, submission status, team membership, conflicts, assignment uniqueness and capacity before creating the new assignment. After the extra evaluation is submitted, the organizer can recompute stability and influence and compare the before/after evidence.

## Interpretation

The system should never silently alter official scores. Recommendations are explainable and auditable. Organizers choose the final publication state.

## Step 15 operational integrity

Public voting is accepted only when the event lifecycle is `VOTING` and the configured voting window is open. Results are not exposed until `voting_results_published` is enabled after the voting lifecycle guard permits publication.

Rate limits, duplicate-vote detection and the organizer-readable audit API are operational controls, not statistical claims about voter identity. New signed judge participation records use Ed25519 and expose the corresponding public key so a saved payload/signature pair can be independently verified.
