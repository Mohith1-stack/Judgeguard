"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiFetch, apiUrl } from "../../../../lib/api";
import { EmptyState, MetricCard, StatusBadge, SectionTitle } from "../../../../components/ui";

type Webhook = { id: string; url: string; active: boolean; created_at: string };
type Delivery = { id: string; webhook_endpoint_id: string; action: string; status_code: number | null; attempted_at: string };
type Audit = { id: string; action: string; entity_type: string; entity_id: string; actor_user_id: string | null; created_at: string };
type Event = { id: string; name: string; status: string };

export default function SecurityPage() {
  const { eventId } = useParams<{ eventId: string }>();
  const [event, setEvent] = useState<Event | null>(null);
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [signingKey, setSigningKey] = useState("");
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [certificateUserId, setCertificateUserId] = useState("");
  const [certificateType, setCertificateType] = useState("");
  const [certificateResult, setCertificateResult] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    setError("");
    try {
      const [eventData, webhookData, deliveryData, auditData, keyData] = await Promise.all([
        apiFetch<Event>(`/events/${eventId}`),
        apiFetch<Webhook[]>(`/events/${eventId}/webhooks`),
        apiFetch<Delivery[]>(`/events/${eventId}/webhook-deliveries`),
        apiFetch<Audit[]>(`/events/${eventId}/audit?limit=30`),
        apiFetch<{ algorithm: string; public_key: string }>("/signing/public-key"),
      ]);
      setEvent(eventData);
      setWebhooks(webhookData);
      setDeliveries(deliveryData);
      setAudit(auditData);
      setSigningKey(keyData.public_key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load security center");
    }
  }

  useEffect(() => { void load(); }, [eventId]);

  async function addWebhook(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      await apiFetch(`/events/${eventId}/webhooks`, {
        method: "POST",
        body: JSON.stringify({ url, secret }),
      });
      setUrl(""); setSecret(""); setMessage("Webhook registered.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Webhook registration failed");
    } finally { setBusy(false); }
  }

  async function testWebhook(id: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await apiFetch<{ delivery_id: string; status_code: number | null }>(`/events/${eventId}/webhooks/${id}/test`, { method: "POST" });
      setMessage(`Test delivery ${result.status_code ?? "pending"}.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Webhook test failed");
    } finally { setBusy(false); }
  }

  async function disableWebhook(id: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiFetch(`/events/${eventId}/webhooks/${id}`, { method: "DELETE" });
      setMessage("Webhook disabled.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Webhook disable failed");
    } finally { setBusy(false); }
  }

  async function issueCertificate(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(""); setMessage(""); setCertificateResult(null);
    try {
      const params = new URLSearchParams({
        recipient_user_id: certificateUserId,
        certificate_type: certificateType,
      });
      const result = await apiFetch<any>(`/events/${eventId}/certificates?${params.toString()}`, { method: "POST" });
      setCertificateResult(result);
      setMessage(`Certificate issued using ${result.algorithm}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Certificate issuance failed");
    } finally { setBusy(false); }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">T4 SECURITY CENTER</div>
          <h1>{event?.name ?? "Security"}</h1>
          <p className="muted">Webhooks, audit evidence, signing keys, and cryptographic records.</p>
        </div>
        <div className="heading-actions">
          <Link className="button ghost" href={`/organizer/${eventId}`}>Event console</Link>
          <Link className="button ghost" href={`/organizer/${eventId}/integrity`}>Integrity center</Link>
        </div>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}
      {message ? <div className="success-banner">{message}</div> : null}

      <div className="stats-grid">
        <MetricCard label="Webhooks" value={webhooks.length} detail={`${webhooks.filter((x) => x.active).length} active`} tone="accent" />
        <MetricCard label="Deliveries" value={deliveries.length} detail="latest 200 attempts" />
        <MetricCard label="Audit entries" value={audit.length} detail="latest 30 entries" />
        <MetricCard label="Signing" value="Ed25519" detail="public verification key exposed" tone="good" />
      </div>

      <div className="two-col">
        <section className="panel">
          <SectionTitle eyebrow="WEBHOOKS" title="Event integrations" description="Private-network targets are validated by the backend before registration." />
          <form onSubmit={addWebhook}>
            <div className="grid">
              <div className="field">
                <div className="label">Endpoint URL</div>
                <input type="url" required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/judgeguard" />
              </div>
              <div className="field">
                <div className="label">Secret</div>
                <input required minLength={16} value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="minimum 16 characters" />
              </div>
            </div>
            <button disabled={busy}>Register webhook</button>
          </form>

          <div className="audit-list" style={{ marginTop: 18 }}>
            {webhooks.map((hook) => (
              <div className="audit-row" key={hook.id}>
                <div>
                  <strong style={{ fontSize: 11 }}>{hook.url}</strong>
                  <span className="muted mono" style={{ display: "block", marginTop: 4 }}>{new Date(hook.created_at).toLocaleString()}</span>
                </div>
                <StatusBadge status={hook.active ? "ACTIVE" : "ARCHIVED"} />
                <div className="row">
                  {hook.active ? <button className="button ghost compact" disabled={busy} onClick={() => void testWebhook(hook.id)}>Test</button> : null}
                  {hook.active ? <button className="button ghost compact" disabled={busy} onClick={() => void disableWebhook(hook.id)}>Disable</button> : null}
                </div>
              </div>
            ))}
            {!webhooks.length ? <div className="empty-inline">No webhook endpoints are configured for this event.</div> : null}
          </div>
        </section>

        <section className="panel">
          <SectionTitle eyebrow="CRYPTOGRAPHIC IDENTITY" title="Signing key" description="The API exposes the public key used to verify Ed25519 records." />
          <div className="card">
            <div className="label">Algorithm</div>
            <div className="stat" style={{ fontSize: 22, marginTop: 8 }}>Ed25519</div>
          </div>
          <div className="field">
            <div className="label">Public key</div>
            <textarea rows={6} readOnly value={signingKey} />
          </div>
          <p className="muted">Keep the public key; the signing secret remains server-side.</p>

          <form onSubmit={issueCertificate} style={{ marginTop: 18 }}>
            <div className="eyebrow">ISSUE RECORD</div>
            <div className="field">
              <div className="label">Recipient user UUID</div>
              <input required value={certificateUserId} onChange={(e) => setCertificateUserId(e.target.value)} placeholder="real registered user UUID" />
            </div>
            <div className="field">
              <div className="label">Certificate type</div>
              <input required value={certificateType} onChange={(e) => setCertificateType(e.target.value)} placeholder="e.g. judge_participation" />
            </div>
            <button disabled={busy}>Issue signed certificate</button>
          </form>

          {certificateResult ? (
            <div className="card" style={{ marginTop: 16 }}>
              <div className="success">Certificate issued.</div>
              <div className="label">Certificate ID</div>
              <div className="mono" style={{ marginTop: 6, fontSize: 11 }}>{certificateResult.id}</div>
              <div className="label" style={{ marginTop: 14 }}>Signature</div>
              <textarea rows={5} readOnly value={certificateResult.signature ?? ""} />
              <Link className="button ghost compact" href={apiUrl(`/certificates/${certificateResult.id}`)} target="_blank">Open verification response</Link>
            </div>
          ) : null}
        </section>
      </div>

      <section className="panel">
        <SectionTitle eyebrow="DELIVERIES" title="Webhook delivery history" description="Delivery attempts are persisted by the backend." />
        {deliveries.length ? (
          <div className="audit-list">
            {deliveries.slice(0, 30).map((delivery) => (
              <div className="audit-row" key={delivery.id}>
                <span className="mono">{new Date(delivery.attempted_at).toLocaleString()}</span>
                <span>{delivery.action}</span>
                <span className={delivery.status_code && delivery.status_code < 400 ? "goodText" : "dangerText"}>{delivery.status_code ?? "—"}</span>
              </div>
            ))}
          </div>
        ) : <EmptyState title="No deliveries recorded" description="Test a configured webhook to create a persisted delivery record." />}
      </section>

      <section className="panel">
        <SectionTitle eyebrow="AUDIT" title="Security activity" description="Read-only event audit entries." />
        {audit.length ? (
          <div className="audit-list">
            {audit.slice(0, 20).map((item) => (
              <div className="audit-row" key={item.id}>
                <span className="mono">{new Date(item.created_at).toLocaleString()}</span>
                <span>{item.action}</span>
                <span className="mono">{item.actor_user_id?.slice(0, 8) ?? "system"}</span>
              </div>
            ))}
          </div>
        ) : <div className="empty-inline">No audit events yet.</div>}
      </section>
    </>
  );
}
