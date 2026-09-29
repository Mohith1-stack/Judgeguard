# Threat Model

## Assets

- unpublished evaluations
- judge assignments
- event administration
- unpublished voting results
- certificates and signed records
- leaderboard integrity

## Threats

- peer-score disclosure
- privilege escalation
- cross-event access
- duplicate voting
- deadline bypass
- judge/team conflicts
- session theft
- evaluator concentration
- score manipulation through a small coalition
- presentation-order influence

## Controls

- backend RBAC
- hashed session tokens
- assignment ownership checks
- immutable raw evaluations
- unique vote identity per event
- deadline validation
- conflict-aware assignment
- randomized/counterbalanced public and judge ordering
- audit trail
- influence/flip-set stress tests
- adaptive re-review with stale-recommendation revalidation
- signed certificate records

## Known limitations

- single-process vote rate limiter; horizontal deployments need a shared limiter
- optional email-gated voting relies on admin-managed email verification because no external mail provider is required
- adaptive review-value calculation is a deterministic heuristic, not a learned or probabilistic model
- adaptive recommendations can identify a useful next review but cannot guarantee that the extra evaluation changes ranking certainty
- coalition testing defaults to evaluator removal and does not claim to model every possible malicious scoring strategy

## Step 15 hardening controls

- login throttling by normalized account identity
- configurable vote/comment request limits
- lifecycle check on voting and result publication
- organizer/admin audit API
- last-active-admin protection
- webhook URL syntax validation and private-network target blocking by default
- per-endpoint webhook HMAC signatures with secrets excluded from persistent storage
- Ed25519 signatures for new public records
- backwards-compatible verification of earlier HMAC certificates
- DOM `textContent` rendering in the embeddable gallery
- portable import that never creates users implicitly

### Step 15 limitations

The request limiter is process-local; clustered deployments require a shared rate-limit store. Anonymous-voter controls are anti-abuse measures rather than proof of unique human identity. Private-network webhook blocking can be intentionally disabled for trusted self-hosted integrations through `WEBHOOK_ALLOW_PRIVATE_NETWORKS=true`.
