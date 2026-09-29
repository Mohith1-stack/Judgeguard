from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.models import (
    AnalyticsRun,
    AuditEvent,
    Certificate,
    Comment,
    Event,
    EventPrize,
    EventStatus,
    EventTrack,
    Evaluation,
    EvaluationScore,
    JudgeAssignment,
    JudgeConflict,
    JudgeProfile,
    Rubric,
    RubricCriterion,
    Submission,
    SubmissionStatus,
    Team,
    TeamMember,
    User,
    UserRole,
    Vote,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.schemas.judging import WebhookCreate
from app.schemas.t4 import BulkImportRequest
from app.security.auth import current_user
from app.security.authorization import event_manager
from app.services.audit import list_audit_events, record_audit
from app.services.certificates import issue_certificate
from app.services.signing import legacy_hmac_signature, public_key_hex, sign_bytes, signature_payload, verify_bytes
from app.services.webhooks import deliver_webhook, register_webhook

router = APIRouter(tags=["T4"])


def _event_export(db: Session, event_id: UUID) -> dict:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    teams = db.scalars(select(Team).where(Team.event_id == event_id).order_by(Team.name)).all()
    submissions = db.scalars(select(Submission).where(Submission.event_id == event_id).order_by(Submission.created_at)).all()
    assignments = db.scalars(select(JudgeAssignment).where(JudgeAssignment.event_id == event_id).order_by(JudgeAssignment.queue_position)).all()
    evaluations = db.scalars(select(Evaluation).where(Evaluation.event_id == event_id).order_by(Evaluation.submitted_at)).all()
    judges = db.scalars(select(JudgeProfile).where(JudgeProfile.event_id == event_id)).all()
    conflicts = db.scalars(select(JudgeConflict).where(JudgeConflict.event_id == event_id)).all()
    rubric = db.scalar(select(Rubric).where(Rubric.event_id == event_id).order_by(Rubric.version.desc()))
    comments = db.scalars(
        select(Comment).join(Submission, Comment.submission_id == Submission.id).where(Submission.event_id == event_id)
    ).all()
    votes = db.scalars(select(Vote).where(Vote.event_id == event_id)).all()
    audit = db.scalars(select(AuditEvent).where(AuditEvent.event_id == event_id).order_by(AuditEvent.created_at)).all()

    user_ids = {m.user_id for t in teams for m in t.members}
    user_ids.update(p.user_id for p in judges)
    user_map = {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
    submission_map = {s.id: s for s in submissions}

    result = {
        "format": "judgeguard.event-export",
        "version": 2,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "event": {
            "id": str(event.id),
            "name": event.name,
            "slug": event.slug,
            "description": event.description,
            "status": event.status.value,
            "voting_access": event.voting_access.value,
            "voting_results_published": event.voting_results_published,
            "registration_opens_at": event.registration_opens_at.isoformat() if event.registration_opens_at else None,
            "registration_closes_at": event.registration_closes_at.isoformat() if event.registration_closes_at else None,
            "submission_opens_at": event.submission_opens_at.isoformat() if event.submission_opens_at else None,
            "submission_deadline": event.submission_deadline.isoformat() if event.submission_deadline else None,
            "judging_opens_at": event.judging_opens_at.isoformat() if event.judging_opens_at else None,
            "judging_deadline": event.judging_deadline.isoformat() if event.judging_deadline else None,
            "voting_opens_at": event.voting_opens_at.isoformat() if event.voting_opens_at else None,
            "voting_deadline": event.voting_deadline.isoformat() if event.voting_deadline else None,
        },
        "tracks": [
            {"name": t.name, "slug": t.slug, "description": t.description}
            for t in db.scalars(select(EventTrack).where(EventTrack.event_id == event_id).order_by(EventTrack.slug)).all()
        ],
        "prizes": [
            {"name": p.name, "description": p.description, "amount": p.amount, "rank": p.rank}
            for p in db.scalars(select(EventPrize).where(EventPrize.event_id == event_id).order_by(EventPrize.rank, EventPrize.name)).all()
        ],
        "rubric": (
            {
                "name": rubric.name,
                "version": rubric.version,
                "is_active": rubric.is_active,
                "criteria": [
                    {"name": c.name, "description": c.description, "weight": c.weight, "min_score": c.min_score, "max_score": c.max_score, "sort_order": c.sort_order}
                    for c in db.scalars(select(RubricCriterion).where(RubricCriterion.rubric_id == rubric.id).order_by(RubricCriterion.sort_order, RubricCriterion.id)).all()
                ],
            }
            if rubric
            else None
        ),
        "teams": [
            {
                "name": t.name,
                "members": [
                    {"email": user_map[m.user_id].email, "display_name": user_map[m.user_id].display_name, "is_owner": m.is_owner}
                    for m in t.members
                    if m.user_id in user_map
                ],
            }
            for t in teams
        ],
        "submissions": [
            {
                "team_name": submission_map[s.id].team.name if submission_map.get(s.id) and submission_map[s.id].team else None,
                "track_slug": submission_map[s.id].track.slug if submission_map.get(s.id) and submission_map[s.id].track else None,
                "name": s.name,
                "tagline": s.tagline,
                "description": s.description,
                "repository_url": s.repository_url,
                "live_url": s.live_url,
                "demo_video_url": s.demo_video_url,
                "tech_tags": s.tech_tags or [],
                "custom_answers": s.custom_answers or {},
                "status": s.status.value,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
            }
            for s in submissions
        ],
        # Operational history is export-only. Import never accepts these fields.
        "judges": [
            {"email": user_map[p.user_id].email, "display_name": user_map[p.user_id].display_name, "capacity": p.capacity, "expertise": p.expertise or []}
            for p in judges
            if p.user_id in user_map
        ],
        "conflicts": [
            {"judge_id": str(c.judge_id), "team_id": str(c.team_id), "reason": c.reason}
            for c in conflicts
        ],
        "assignments": [
            {"id": str(a.id), "judge_id": str(a.judge_id), "submission_id": str(a.submission_id), "queue_position": a.queue_position, "status": a.status.value}
            for a in assignments
        ],
        "evaluations": [
            {
                "id": str(e.id),
                "assignment_id": str(e.assignment_id),
                "judge_id": str(e.judge_id),
                "submission_id": str(e.submission_id),
                "overall_comment": e.overall_comment,
                "submitted_at": e.submitted_at.isoformat(),
                "scores": [
                    {"criterion_id": str(score.criterion_id), "score": score.score}
                    for score in db.scalars(select(EvaluationScore).where(EvaluationScore.evaluation_id == e.id)).all()
                ],
            }
            for e in evaluations
        ],
        "votes": [
            {"submission_id": str(v.submission_id), "voter_user_id": str(v.voter_user_id) if v.voter_user_id else None, "created_at": v.created_at.isoformat() if v.created_at else None}
            for v in votes
        ],
        "comments": [
            {"submission_id": str(c.submission_id), "user_id": str(c.user_id) if c.user_id else None, "body": c.body, "created_at": c.created_at.isoformat() if c.created_at else None}
            for c in comments
        ],
        "analytics_runs": [
            {"id": str(a.id), "kind": a.kind, "method": a.method, "input_hash": a.input_hash, "result": a.result, "created_at": a.created_at.isoformat() if a.created_at else None, "created_by": str(a.created_by)}
            for a in db.scalars(select(AnalyticsRun).where(AnalyticsRun.event_id == event_id).order_by(AnalyticsRun.created_at)).all()
        ],
        "audit": [
            {"id": str(a.id), "actor_user_id": str(a.actor_user_id) if a.actor_user_id else None, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id, "payload": a.payload, "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in audit
        ],
    }
    return result


@router.get("/events/{event_id}/export.json")
def export_event(event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    result = _event_export(db, event.id)
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="EVENT_EXPORTED", entity_type="event", entity_id=str(event.id), payload={"version": result["version"]})
    db.commit()
    return result


@router.post("/events/{event_id}/import", status_code=201)
def import_event_data(
    event_id: UUID,
    payload: BulkImportRequest,
    event: Event = Depends(event_manager),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if event.status in {EventStatus.JUDGING, EventStatus.VOTING, EventStatus.RESULTS_PUBLISHED, EventStatus.ARCHIVED}:
        raise HTTPException(status_code=409, detail="Bulk content import is disabled after judging begins")

    created = {"tracks": 0, "prizes": 0, "teams": 0, "members": 0, "submissions": 0, "unresolved_members": 0, "skipped_submissions": 0}
    track_by_slug = {t.slug: t for t in db.scalars(select(EventTrack).where(EventTrack.event_id == event_id)).all()}
    team_by_name = {t.name: t for t in db.scalars(select(Team).where(Team.event_id == event_id)).all()}

    for data in payload.tracks:
        track = track_by_slug.get(data.slug)
        if track is None:
            track = EventTrack(event_id=event_id, name=data.name.strip(), slug=data.slug, description=data.description.strip())
            db.add(track)
            db.flush()
            track_by_slug[track.slug] = track
            created["tracks"] += 1

    existing_prizes = {p.name.strip().lower() for p in db.scalars(select(EventPrize).where(EventPrize.event_id == event_id)).all()}
    for data in payload.prizes:
        if data.name.strip().lower() in existing_prizes:
            continue
        db.add(EventPrize(event_id=event_id, name=data.name.strip(), description=data.description.strip(), amount=data.amount, rank=data.rank))
        existing_prizes.add(data.name.strip().lower())
        created["prizes"] += 1

    for data in payload.teams:
        team = team_by_name.get(data.name)
        if team is None:
            team = Team(event_id=event_id, name=data.name.strip())
            db.add(team)
            db.flush()
            team_by_name[data.name] = team
            created["teams"] += 1
        for member in data.members:
            target = db.scalar(select(User).where(User.email == member.email))
            if target is None:
                created["unresolved_members"] += 1
                continue
            exists = db.scalar(select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == target.id))
            if exists is None:
                db.add(TeamMember(team_id=team.id, user_id=target.id, is_owner=member.is_owner))
                created["members"] += 1

    for data in payload.submissions:
        team = team_by_name.get(data.team_name)
        if team is None:
            created["skipped_submissions"] += 1
            continue
        existing = db.scalar(select(Submission).where(Submission.event_id == event_id, Submission.team_id == team.id))
        track_id = track_by_slug.get(data.track_slug).id if data.track_slug and track_by_slug.get(data.track_slug) else None
        if existing is None:
            submission = Submission(
                event_id=event_id,
                team_id=team.id,
                track_id=track_id,
                name=data.name.strip(),
                tagline=data.tagline.strip(),
                description=data.description,
                repository_url=data.repository_url,
                live_url=data.live_url,
                demo_video_url=data.demo_video_url,
                tech_tags=[x.strip().lower() for x in data.tech_tags if x.strip()],
                custom_answers=data.custom_answers,
                status=SubmissionStatus.SUBMITTED,
                submitted_at=datetime.now(timezone.utc),
            )
            db.add(submission)
            created["submissions"] += 1
        else:
            created["skipped_submissions"] += 1

    record_audit(db, event_id=event_id, actor_user_id=user.id, action="EVENT_IMPORTED", entity_type="event", entity_id=str(event_id), payload=created)
    db.commit()
    return created


@router.post("/events/{event_id}/webhooks", status_code=201)
def add_webhook(payload: WebhookCreate, event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    try:
        endpoint = register_webhook(db, event.id, payload.url, payload.secret)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="WEBHOOK_CREATED", entity_type="webhook_endpoint", entity_id=str(endpoint.id), payload={"url": endpoint.url})
    db.commit()
    return {"id": str(endpoint.id), "url": endpoint.url, "active": endpoint.active, "secret_storage": "sha256(secret)"}


@router.get("/events/{event_id}/webhooks")
def list_webhooks(event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.event_id == event.id).order_by(WebhookEndpoint.created_at.desc())).all()
    return [{"id": str(w.id), "url": w.url, "active": w.active, "created_at": w.created_at} for w in rows]


@router.delete("/events/{event_id}/webhooks/{webhook_id}", status_code=204)
def disable_webhook(webhook_id: UUID, event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    endpoint = db.get(WebhookEndpoint, webhook_id)
    if endpoint is None or endpoint.event_id != event.id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    endpoint.active = False
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="WEBHOOK_DISABLED", entity_type="webhook_endpoint", entity_id=str(endpoint.id))
    db.commit()


@router.post("/events/{event_id}/webhooks/{webhook_id}/test")
def test_webhook(webhook_id: UUID, event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    endpoint = db.get(WebhookEndpoint, webhook_id)
    if endpoint is None or endpoint.event_id != event.id:
        raise HTTPException(status_code=404, detail="Webhook not found")
    delivery = deliver_webhook(
        db,
        endpoint=endpoint,
        action="webhook.test",
        payload={"message": "JudgeGuard webhook test", "event_id": str(event.id)},
    )
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="WEBHOOK_TESTED", entity_type="webhook_delivery", entity_id=str(delivery.id), payload={"status_code": delivery.status_code})
    db.commit()
    return {"delivery_id": str(delivery.id), "status_code": delivery.status_code}


@router.get("/events/{event_id}/webhook-deliveries")
def list_webhook_deliveries(event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(
        select(WebhookDelivery)
        .join(WebhookEndpoint, WebhookDelivery.webhook_endpoint_id == WebhookEndpoint.id)
        .where(WebhookEndpoint.event_id == event.id)
        .order_by(WebhookDelivery.attempted_at.desc())
        .limit(200)
    ).all()
    return [
        {"id": str(r.id), "webhook_endpoint_id": str(r.webhook_endpoint_id), "action": r.action, "status_code": r.status_code, "attempted_at": r.attempted_at}
        for r in rows
    ]


@router.get("/events/{event_id}/audit")
def event_audit(
    event: Event = Depends(event_manager),
    limit: int = Query(default=100, ge=1, le=200),
    action: str | None = Query(default=None, max_length=120),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rows = list_audit_events(db, event_id=event.id, limit=limit, action=action)
    return [
        {
            "id": str(r.id),
            "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "payload": r.payload,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/events/{event_id}/certificates", status_code=201)
def create_certificate(
    event_id: UUID,
    recipient_user_id: UUID,
    certificate_type: str,
    details: dict | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if user.role not in {UserRole.ORGANIZER, UserRole.ADMIN} or (user.role != UserRole.ADMIN and event.organizer_id != user.id):
        raise HTTPException(status_code=403, detail="Organizer access required")
    recipient = db.get(User, recipient_user_id)
    if recipient is None:
        raise HTTPException(status_code=404, detail="Recipient not found")
    certificate = issue_certificate(db, event=event, recipient=recipient, certificate_type=certificate_type, details=details or {})
    record_audit(db, event_id=event.id, actor_user_id=user.id, action="CERTIFICATE_ISSUED", entity_type="certificate", entity_id=str(certificate.id))
    db.commit()
    return {"id": str(certificate.id), "signature": certificate.signature, "payload": certificate.payload, "algorithm": "Ed25519"}


@router.get("/certificates/{certificate_id}")
def verify_certificate(certificate_id: UUID, db: Session = Depends(get_db)):
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    payload_bytes = signature_payload(certificate.payload)
    valid = verify_bytes(payload_bytes, certificate.signature)
    algorithm = "Ed25519"
    if not valid and len(certificate.signature) == 64:
        valid = certificate.signature == legacy_hmac_signature(certificate.payload)
        algorithm = "HMAC-SHA256 (legacy)"
    return {
        "valid": valid,
        "id": str(certificate.id),
        "signature": certificate.signature,
        "algorithm": algorithm,
        "public_key": public_key_hex() if algorithm == "Ed25519" else None,
        "payload": certificate.payload,
        "issued_at": certificate.issued_at,
    }


@router.get("/signing/public-key")
def signing_public_key():
    return {"algorithm": "Ed25519", "public_key": public_key_hex()}


def _participation_payload(db: Session, event_id: UUID, judge_id: UUID) -> dict:
    event = db.get(Event, event_id)
    target = db.get(User, judge_id)
    if event is None or target is None:
        raise HTTPException(status_code=404, detail="Event or judge not found")
    profile = db.scalar(select(JudgeProfile).where(JudgeProfile.event_id == event_id, JudgeProfile.user_id == judge_id))
    if profile is None:
        raise HTTPException(status_code=404, detail="Judge profile not found")
    assignments = db.query(JudgeAssignment).filter(JudgeAssignment.event_id == event_id, JudgeAssignment.judge_id == judge_id).count()
    completed = db.query(JudgeAssignment).filter(JudgeAssignment.event_id == event_id, JudgeAssignment.judge_id == judge_id, JudgeAssignment.status == "COMPLETED").count()
    return {
        "event_id": str(event_id),
        "event_name": event.name,
        "judge_id": str(judge_id),
        "judge_name": target.display_name,
        "assignments": assignments,
        "completed": completed,
        "completion_ratio": (completed / assignments) if assignments else 0.0,
    }


@router.get("/events/{event_id}/judges/{judge_id}/participation-record")
def signed_judge_participation_record(judge_id: UUID, event: Event = Depends(event_manager), db: Session = Depends(get_db), user: User = Depends(current_user)):
    payload = _participation_payload(db, event.id, judge_id)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    signature = sign_bytes(signature_payload(payload))
    return {"payload": payload, "signature": signature, "algorithm": "Ed25519", "public_key": public_key_hex()}


@router.get("/public/participation-records/{event_id}/{judge_id}")
def public_judge_participation_record(event_id: UUID, judge_id: UUID, db: Session = Depends(get_db)):
    payload = _participation_payload(db, event_id, judge_id)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    signature = sign_bytes(signature_payload(payload))
    return {"payload": payload, "signature": signature, "algorithm": "Ed25519", "public_key": public_key_hex()}


@router.get("/events/{event_id}/embed", response_class=HTMLResponse)
def embed_gallery(event_id: UUID):
    settings = get_settings()
    api_url = html.escape(f"{settings.public_api_url}/events/{event_id}/gallery", quote=True)
    title = html.escape("JudgeGuard Gallery")
    script = f"""
<script>
(async () => {{
  const response = await fetch({json.dumps(api_url)});
  const data = await response.json();
  const root = document.getElementById('judgeguard-gallery');
  root.textContent = '';
  for (const item of (data.items || [])) {{
    const article = document.createElement('article');
    const heading = document.createElement('h3');
    const tagline = document.createElement('p');
    const tags = document.createElement('small');
    heading.textContent = item.name || '';
    tagline.textContent = item.tagline || '';
    tags.textContent = (item.tech_tags || []).join(', ');
    article.append(heading, tagline, tags);
    root.appendChild(article);
  }}
  if (!(data.items || []).length) {{
    root.textContent = 'No public submissions.';
  }}
}})().catch(() => {{
  document.getElementById('judgeguard-gallery').textContent = 'Gallery unavailable.';
}});
</script>
"""
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title></head><body><div id='judgeguard-gallery'>Loading…</div>{script}</body></html>"
    )
