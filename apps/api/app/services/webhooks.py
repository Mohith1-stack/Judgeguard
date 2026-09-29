from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import WebhookDelivery, WebhookEndpoint


def validate_webhook_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Webhook URL must use http or https")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Webhook URL must contain a hostname and no embedded credentials")
    return parsed.geturl()


def _is_private_host(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    if normalized in {"localhost", "localhost.localdomain", "0.0.0.0", "::1"}:
        return True
    try:
        address = ipaddress.ip_address(normalized)
        return address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(normalized, None, type=socket.SOCK_STREAM)
    except OSError:
        return True
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
            return True
    return False


def webhook_signature(secret_hash: str, body: bytes) -> str:
    """Sign using SHA-256(secret) stored by the server; the original secret is never persisted."""
    key = bytes.fromhex(secret_hash)
    return "sha256=" + hmac.new(key, body, hashlib.sha256).hexdigest()


def register_webhook(db: Session, event_id: UUID, url: str, secret: str) -> WebhookEndpoint:
    safe_url = validate_webhook_url(url)
    secret_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    endpoint = WebhookEndpoint(event_id=event_id, url=safe_url, secret_hash=secret_hash)
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


def _delivery_payload(event_id: UUID, action: str, payload: dict, delivery_id: UUID) -> bytes:
    body = {
        "action": action,
        "delivery_id": str(delivery_id),
        "event_id": str(event_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    return json.dumps(body, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")


def deliver_webhook(
    db: Session,
    *,
    endpoint: WebhookEndpoint,
    action: str,
    payload: dict,
) -> WebhookDelivery:
    delivery = WebhookDelivery(
        webhook_endpoint_id=endpoint.id,
        action=action,
        payload=payload,
    )
    db.add(delivery)
    db.flush()
    body = _delivery_payload(endpoint.event_id, action, payload, delivery.id)
    settings = get_settings()

    try:
        parsed = urlparse(endpoint.url)
        if not settings.webhook_allow_private_networks and parsed.hostname and _is_private_host(parsed.hostname):
            delivery.status_code = 0
            return delivery
        with httpx.Client(timeout=settings.webhook_timeout_seconds, follow_redirects=False) as client:
            response = client.post(
                endpoint.url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-JudgeGuard-Signature": webhook_signature(endpoint.secret_hash, body),
                    "X-JudgeGuard-Event": action,
                    "X-JudgeGuard-Delivery-ID": str(delivery.id),
                },
            )
            delivery.status_code = response.status_code
    except Exception:
        delivery.status_code = None
    return delivery


def dispatch_event(db: Session, event_id: UUID, action: str, payload: dict) -> None:
    endpoints = db.scalars(
        select(WebhookEndpoint).where(
            WebhookEndpoint.event_id == event_id,
            WebhookEndpoint.active.is_(True),
        )
    ).all()
    for endpoint in endpoints:
        deliver_webhook(db, endpoint=endpoint, action=action, payload=payload)
    if endpoints:
        db.commit()
