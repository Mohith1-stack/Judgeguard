# Data Model

## Identity

- `users`
- `user_sessions`

## Event lifecycle

- `events`
- `event_tracks`
- `event_prizes`
- `teams`
- `team_members`
- `team_invites`
- `submissions`
- `submission_versions`
- `submission_media`

## Judging

- `judge_profiles`
- `judge_invites`
- `judge_conflicts`
- `judge_assignments`
- `rubrics`
- `rubric_criteria`
- `evaluations`
- `evaluation_scores`
- `calibration_anchors`

## JudgeGuard analytics

- `analytics_runs`
- `review_recommendations`

Every run stores an input hash, method/configuration and result. Raw scores are retained. Adaptive review uses `review_recommendations` for the human decision/assignment lifecycle and `analytics_runs` for the selection trace and post-review recalculation; no additional table or migration is required for Step 14.

## Public layer

- `votes`
- `comments`

## Operational / T4

- `audit_events`
- `webhook_endpoints`
- `webhook_deliveries`
- `certificates`

## Core integrity constraints

- One team cannot create more than one submission per event.
- One judge can only have one assignment per submission.
- One assignment can only have one final evaluation.
- One evaluator/criterion pair inside one evaluation can only have one score.
- One voter identity can vote once per event.
- Session tokens are stored only as SHA-256 hashes.

## Step 15 data movement

`GET /api/v1/events/{event_id}/export.json` produces `judgeguard.event-export` version `2`. Portable content uses event-local names/slugs and user emails where needed for reattachment. Password hashes, sessions and webhook secrets are never exported.

`POST /api/v1/events/{event_id}/import` accepts only tracks, prizes, teams, existing users as members, and submission content. It does not create users and it is blocked after judging begins.

Community votes, comments, analytics, assignments and audit history are included in the export as operational history but are deliberately not accepted by the bulk import endpoint.
