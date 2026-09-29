# JudgeGuard Frontend Makeover

This patch is built directly from the supplied `judgeguard.zip` codebase.

## Scope

The backend is untouched. The frontend is a visual and interaction layer over the existing FastAPI endpoints and PostgreSQL-backed records.

Updated:
- `app/layout.tsx` — authenticated top navigation + role-aware links.
- `app/page.tsx` — live landing/dashboard using `/events` and `/auth/me`.
- `app/events/page.tsx` — searchable event directory.
- `app/gallery/page.tsx` — public gallery directory.
- `app/gallery/[eventId]/page.tsx` — dynamic event gallery with API-backed filters.
- `app/gallery/[eventId]/[submissionId]/page.tsx` — project detail.
- `app/judge/page.tsx` — judge workspace entry.
- `app/judge/[eventId]/page.tsx` — isolated judge queue and rubric evaluation UI.
- `app/organizer/[eventId]/page.tsx` — integrity/security navigation additions.
- `app/organizer/[eventId]/integrity/page.tsx` — primary JudgeGuard demo dashboard.
- `app/organizer/[eventId]/security/page.tsx` — T4 webhook + signing-key/certificate UI.
- `app/embed/[eventId]/page.tsx` — polished embeddable gallery shell.
- `app/globals.css` — complete visual system.
- `components/ui.tsx` — reusable display primitives.

## Data integrity

No demo users, projects, scores, judge identities, analytics, or leaderboard values are inserted by this patch.

The frontend displays API responses only. Labels, lifecycle option names, and workflow descriptions are static UI copy.

## Runtime

Keep the existing `.env` values from the supplied project. In Docker, the existing `NEXT_PUBLIC_API_BASE_URL` controls the browser API target.

Recommended:
```powershell
cd D:\judgeguard
Copy-Item apps\web apps\web-before-frontend-makeover -Recurse
Expand-Archive "$HOME\Downloads\judgeguard-frontend-makeover.zip" -DestinationPath D:\judgeguard -Force
docker compose up -d --build
```

Open:
- http://localhost:3000
- http://localhost:8000/docs

## Suggested demo route

Open an actual event as an organizer:

`/organizer/<REAL_EVENT_ID>/integrity`

Then use:
1. Run full integrity
2. Analyze stability / influence
3. Recommend adaptive review
4. Accept if eligible
5. Submit the added review through the judge workspace
6. Recalculate
7. Open Security Center for webhook and cryptographic evidence
