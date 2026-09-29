# JudgeGuard: 15-Step Implementation Order

The repository already contains the final baseline. The following is the order in which the system should be built, tested and demonstrated.

## 01 — Foundation

Files:
- `docker-compose.yml`
- `.env.example`
- `apps/api/Dockerfile`
- `apps/api/app/config.py`
- `apps/api/app/db/session.py`

Test:
- `docker compose up -d --build`
- `docker compose ps`
- `/api/v1/health`
- `/api/v1/health/db`

## 02 — Authentication

Files:
- `apps/api/app/security/auth.py`
- `apps/api/app/api/auth.py`
- `apps/api/app/schemas/auth.py`

Flow:
- register -> participant
- login -> server session
- logout -> revoke
- me -> authenticated identity

## 03 — RBAC

Roles:
- visitor
- participant
- judge
- organizer
- admin

Security rule:
Authorization is enforced in FastAPI dependencies, not in React.

## 04 — Event Management

Files:
- `apps/api/app/api/events.py`
- `apps/api/app/models/core.py`

Supports configurable event dates, tracks, prizes and status.

## 05 — Teams

Files:
- `apps/api/app/api/teams.py`
- `apps/api/app/schemas/team.py`

Supports team creation, ownership and invite-token joining.

## 06 — Submissions

Files:
- `apps/api/app/api/submissions.py`
- `apps/api/app/schemas/submission.py`

Supports draft/edit/versioning and deadline-checked final submission.

## 07 — Public Gallery

Files:
- `apps/api/app/api/public.py`
- `apps/web/app/gallery/[eventId]/page.tsx`

Supports search/filter query parameters and randomized ordering.

## 08 — Rubric + Judges

Files:
- `apps/api/app/api/judging.py`
- `apps/api/app/models/core.py`

Supports weighted criteria, judge profiles, conflicts and invitation acceptance.

## 09 — Judge Assignment

Files:
- `apps/api/app/engine/assignment.py`
- `apps/api/app/api/judging.py`

The optimizer balances capacity, expertise, conflicts and assignment structure.

## 10 — Secure Judging

Files:
- `apps/api/app/api/judging.py`
- `apps/web/app/judge/[eventId]/page.tsx`

A judge can only open and submit their own assignments. Progress is visible to organizers.

## 11 — Normalization + Calibration

Files:
- `apps/api/app/engine/statistics.py`
- `calibration_anchors` data model

Methods:
- z-score
- robust z-score
- anchor analysis
- score drift

## 12 — Influence + Attack Surface

Files:
- `apps/api/app/engine/statistics.py`

Outputs:
- judge influence
- leave-one-out impact
- minimum flip set

## 13 — Ranking Robustness

Files:
- `apps/api/app/engine/statistics.py`
- `apps/web/app/organizer/[eventId]/integrity/page.tsx`

Outputs:
- current ranking
- bootstrap rank stability
- rubric sensitivity

## 14 — Adaptive Review

Files:
- `apps/api/app/engine/adaptive.py`
- `apps/api/app/api/integrity.py`

Flow:
- identify uncertainty
- select target
- select independent judge
- create recommendation
- accept recommendation
- create new assignment
- recalculate

## 15 — Public/T4 + Hardening

Files:
- `apps/api/app/api/public.py`
- `apps/api/app/api/t4.py`
- `apps/api/app/api/admin.py`
- `apps/web/app/admin/page.tsx`

Includes:
- configurable voting
- comments
- rate limits
- duplicate detection
- audit
- OpenAPI/REST
- webhooks
- certificates
- signed participation records
- embed gallery
- JSON import/export

Final acceptance:
- fresh clone
- empty `.env` filled locally
- `docker compose up -d --build`
- role-isolation tests
- deadline tests
- evaluation tests
- analytics tests
- offline run
- acceptance report
