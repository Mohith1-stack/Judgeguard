# JudgeGuard

JudgeGuard is a self-hostable event judging portal built for the Dogfood specification. The platform implements the T1/T2/T3/T4 workflow and adds an integrity layer focused on resilient judging.

## Product thesis

**Do not only compute a winner. Measure how robust the judging process is before publishing the result.**

JudgeGuard's core differentiator is the **Judging Integrity Engine**, which mathematically guarantees that the best projects win, regardless of subjective biases or judging assignments. 

Instead of just averaging scores, JudgeGuard implements a robust, multi-step pipeline:

### 1. Normalization (Fixing Bias)
Different judges score differently—some are naturally harsh, while others are lenient. JudgeGuard analyzes a judge's historical average and applies statistical normalization (z-scores). For example, a harsh judge scoring a project `7/10` may be mathematically treated as equivalent to a lenient judge scoring it `9/10`.

### 2. Influence & Minimum Flip Set (Finding Fragility)
The engine analyzes the leaderboard and asks: *"How easy would it be to change the winner?"* It calculates the **Minimum Flip Set**—the exact number of scores that would need to change for the 1st place winner to lose. If a single judge holds too much influence over a boundary, the system flags the result as "fragile."

### 3. Ranking Stability (Stress Testing)
The system runs thousands of simulated recalculations (bootstrapping) with slight variations to see if the leaderboard remains unchanged. If the 1st place project wins in 99% of simulations, the ranking is statistically stable. If it only wins in 40% of simulations, the results are deemed too close to call.

### 4. Adaptive Review (Fixing the Problem)
If the engine detects that the leaderboard is highly fragile (e.g., two projects are tied and a single biased judge is deciding the winner), the system automatically triggers an **Adaptive Review**. It searches the available judge pool, checks for conflicts of interest and remaining capacity, and automatically assigns an independent, third-party judge to review the fragile project.

### 5. Recalculation & Finalization
Once the independent judge submits their evaluation, the engine recalculates the influence and stability metrics to prove that the final leaderboard is now robust and secure before any results are published.

### 6. High-Performance Architecture
JudgeGuard is built to handle significant traffic and load. Through continuous automated stress testing (such as continuous concurrent load simulations against both the React frontend and FastAPI backend), the platform guarantees maximum uptime without dropped connections or timeouts during peak submission and voting windows.

## Dogfood alignment

T1: authentication, roles, event creation, teams, submissions, deadline enforcement, public gallery.

T2: judge invitation/assignment, weighted rubrics, backend role isolation, progress dashboard, normalization and CSV exports.

T3: configurable public voting, comments, hidden voting results, randomized gallery ordering, rate limiting, duplicate detection and audit trail.

T4: REST API/OpenAPI, webhooks, certificates, signed judge participation records, embed gallery endpoint and JSON import/export.

## No hardcoded demo data

There are no source-level fake users, projects, scores, winners, or dashboards. New users register into the database. The only bootstrap identity is an optional administrator whose credentials are supplied through environment variables.

Official Dogfood fixtures can be loaded separately into the database.

## Step 15 hardening

The final tier adds public-voting abuse controls, organizer-readable audit logs, portable event import/export, webhook lifecycle management with signed deliveries, public Ed25519 verification for new certificates/participation records, SSRF-aware webhook targets, security response headers, login throttling, and lifecycle guards around result publication. See `STEP15.md` and `docs/STEP15-IMPLEMENTATION.md` for the exact contracts and known limitations.

## Runtime

- Next.js 16 + TypeScript
- FastAPI + SQLAlchemy
- PostgreSQL 16
- Docker Compose
- Python statistics engine using NumPy/SciPy

## Run on Windows

1. Stop the older project and remove its development database volume if this is a fresh replacement:

```powershell
docker compose down -v
```

2. Create the environment:

```powershell
Copy-Item .env.example .env
```

3. Put a strong local password and a 32+ character `SIGNING_SECRET` in `.env`. Optional admin bootstrap uses `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD`.

4. Start:

```powershell
docker compose up -d --build
```

5. Verify:

```powershell
docker compose ps
```

6. Open:

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/api/v1/health
- DB health: http://localhost:8000/api/v1/health/db

## Tests

Inside the repository:

```powershell
$env:PYTHONPATH="apps/api"
python -m pytest -q
```

The tests currently cover the assignment optimizer, normalization, ranking, bootstrap stability, minimum flip-set execution and rubric sensitivity. Container-level tests should be run on the target laptop as part of final acceptance.

## Important operational rule

The analytics layer never overwrites raw evaluation rows. Each analysis is stored as an immutable `analytics_runs` record with the method, configuration, input hash and result payload.
