# Step 15 Implementation Notes

## 1. Voting integrity

The API now requires both the configured voting time window and `EventStatus.VOTING` before a vote is accepted. This removes the class of bugs where a timestamp is configured but lifecycle state has moved elsewhere.

Duplicate detection remains database-enforced through `UNIQUE(event_id, voter_key)`. Authentication mode uses the user UUID; anonymous mode uses a random HTTP-only cookie identifier. The cookie is not considered a security proof by itself, so the request path is also rate-limited by a one-way client fingerprint.

The system does not claim that IP-based controls prove human identity. The fingerprint is an abuse-control signal only.

## 2. Rate limiting

The limiter is a bounded sliding-window counter suitable for the single-process Docker profile. Limits are configuration, not source-level event data:

- `VOTE_RATE_LIMIT`
- `VOTE_RATE_WINDOW_SECONDS`
- `COMMENT_RATE_LIMIT`
- `COMMENT_RATE_WINDOW_SECONDS`
- `LOGIN_RATE_LIMIT`
- `LOGIN_RATE_WINDOW_SECONDS`

Horizontal deployments still need a shared limiter. This is documented rather than hidden.

## 3. Webhooks

The database stores `sha256(secret)`, never the supplied secret. On delivery the stored digest is used as the HMAC key. A receiver that possesses the original secret can reproduce the digest and then verify the body signature.

Headers include:

- `X-JudgeGuard-Signature`
- `X-JudgeGuard-Event`
- `X-JudgeGuard-Delivery-ID`

Each delivery receives a database record. A status code of `0` is reserved for a blocked private-network target; `NULL` indicates a network/transport failure.

## 4. Signing

New certificates and participation records use Ed25519. The private key is deterministically derived from `SHA-256(SIGNING_SECRET)` so no additional secret file is required for the self-hosted deployment.

The public verification surface exposes:

`GET /api/v1/signing/public-key`

For compatibility, certificates whose signature is a 64-character SHA-256 HMAC hex digest continue to verify through the legacy path.

## 5. Bulk import/export

Export format:

`judgeguard.event-export` version `2`

Portable content is represented with human-stable identifiers where practical: team names, track slugs and user emails. Operational objects such as assignments, evaluations, analytics runs and audit history are export-only. Import accepts only tracks, prizes, teams, members and submission content.

Users are never synthesized from imported data.

## 6. Embed hardening

The embedded gallery previously rendered untrusted submission text through `innerHTML`. Step 15 builds DOM nodes and assigns untrusted text through `textContent`, preventing submission fields from becoming executable markup.

## 7. Acceptance

Use:

```bash
./scripts/acceptance.sh
```

or:

```powershell
./scripts/verify.ps1
```

The scripts verify compilation, tests, Compose configuration, container startup and health endpoints. The target environment should add the live role-isolation, deadline, evaluation, vote-abuse and signed-record checks to the final acceptance report.
