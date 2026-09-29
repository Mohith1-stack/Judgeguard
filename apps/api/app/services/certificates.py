from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Certificate, Event, User
from app.services.signing import sign_bytes, signature_payload


def issue_certificate(
    db: Session,
    *,
    event: Event,
    recipient: User,
    certificate_type: str,
    details: dict,
) -> Certificate:
    payload = {
        "event_id": str(event.id),
        "event_name": event.name,
        "recipient_user_id": str(recipient.id),
        "recipient_name": recipient.display_name,
        "certificate_type": certificate_type.strip(),
        "details": details,
    }
    signature = sign_bytes(signature_payload(payload))
    certificate = Certificate(
        event_id=event.id,
        recipient_user_id=recipient.id,
        certificate_type=certificate_type.strip(),
        payload=payload,
        signature=signature,
    )
    db.add(certificate)
    db.commit()
    db.refresh(certificate)
    return certificate
