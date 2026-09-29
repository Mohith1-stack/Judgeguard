# Step-by-step source map

The complete working source is in the repository. Each step below maps the requirements to the files to edit and test:

- 01 Foundation -> docker/config/db
- 02 Authentication -> `apps/api/app/security/auth.py`, `api/auth.py`, `schemas/auth.py`
- 03 RBAC -> `security/auth.py`, `security/authorization.py`, role-protected routers
- 04 Events -> `api/events.py`, event schemas/models
- 05 Teams -> `api/teams.py`, team schemas/models
- 06 Submissions -> `api/submissions.py`, submission schemas/models
- 07 Gallery -> `api/public.py`, gallery UI
- 08 Rubric/Judges -> `api/judging.py`, judging schemas/models
- 09 Assignment -> `engine/assignment.py`
- 10 Secure judging -> `api/judging.py`, judge UI
- 11 Normalization -> `engine/statistics.py`
- 12 Influence -> `engine/statistics.py`
- 13 Stability -> `engine/statistics.py`
- 14 Adaptive review -> `engine/adaptive.py`, `api/integrity.py`
- 15 T3/T4 -> public/admin/T4 routers and UI

Use `docs/15-STEP-IMPLEMENTATION.md` for exact sequence and verification commands.


## Step 9
See `STEP9.md` for resilient assignment planning, preview, diagnostics, and audit behavior.
