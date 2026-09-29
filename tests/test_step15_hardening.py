from __future__ import annotations

import hashlib
import hmac
from pathlib import Path
from types import SimpleNamespace

from apps.api.app.services.rate_limit import SlidingWindowLimiter
from apps.api.app.services import signing
from apps.api.app.services.webhooks import validate_webhook_url, webhook_signature

ROOT = Path(__file__).resolve().parents[1]


def test_rate_limiter_enforces_window_limit():
    limiter = SlidingWindowLimiter()
    assert limiter.consume("x", limit=2, window_seconds=60)[0] is True
    assert limiter.consume("x", limit=2, window_seconds=60)[0] is True
    allowed, retry_after = limiter.consume("x", limit=2, window_seconds=60)
    assert allowed is False
    assert retry_after >= 1


def test_webhook_url_validation():
    assert validate_webhook_url("https://example.com/hooks") == "https://example.com/hooks"
    for value in ["ftp://example.com/hook", "https://user:password@example.com/hook", "example.com/hook"]:
        try:
            validate_webhook_url(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid webhook URL accepted: {value}")


def test_webhook_signature_uses_hashed_endpoint_secret():
    secret = "test-webhook-secret"
    secret_hash = hashlib.sha256(secret.encode()).hexdigest()
    body = b'{"event":"created"}'
    expected = "sha256=" + hmac.new(bytes.fromhex(secret_hash), body, hashlib.sha256).hexdigest()
    assert webhook_signature(secret_hash, body) == expected


def test_ed25519_public_verification(monkeypatch):
    monkeypatch.setattr(signing, "get_settings", lambda: SimpleNamespace(signing_secret="s" * 32))
    payload = {"event_id": "event-1", "recipient": "user-1", "purpose": "test"}
    raw = signing.signature_payload(payload)
    signature = signing.sign_bytes(raw)
    public_key = signing.public_key_hex()
    assert signing.verify_bytes(raw, signature, public_key) is True
    assert signing.verify_bytes(b"tampered", signature, public_key) is False


def test_step15_public_and_t4_routes_are_present():
    public_source = (ROOT / "apps/api/app/api/public.py").read_text()
    t4_source = (ROOT / "apps/api/app/api/t4.py").read_text()
    event_source = (ROOT / "apps/api/app/api/events.py").read_text()
    main_source = (ROOT / "apps/api/app/main.py").read_text()

    assert 'if event.status != EventStatus.VOTING or not is_voting_open(event):' in public_source
    assert 'PUBLIC_VOTE_CAST' in public_source
    assert 'PUBLIC_COMMENT_CREATED' in public_source
    assert '"/events/{event_id}/audit"' in t4_source
    assert '"/events/{event_id}/export.json"' in t4_source
    assert '"/events/{event_id}/import"' in t4_source
    assert '"/events/{event_id}/webhooks/{webhook_id}/test"' in t4_source
    assert '"/public/participation-records/{event_id}/{judge_id}"' in t4_source
    assert 'if next_results_published and not event.voting_results_published:' in event_source
    assert 'X-Content-Type-Options' in main_source
