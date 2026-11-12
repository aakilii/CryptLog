'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  AlertTriangle,
  ArrowLeft,
  ClipboardCheck,
  Download,
  Eye,
  FilePlus2,
  FileText,
  Link2,
  PencilLine,
  ShieldCheck,
  Upload,
} from 'lucide-react';
import { api } from '@operation-room/lib/api';

const ACTION_ICONS = {
  CASE_CREATED: FilePlus2,
  CASE_UPDATED: PencilLine,
  IMPORT: Download,
  VERIFY_HASH: ShieldCheck,
  NO_DATA_FOUND: AlertTriangle,
  VIEW: Eye,
  EXPORT: Upload,
};

const formatAction = (action) =>
  action
    .toLowerCase()
    .split('_')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');

export default function ChainOfCustodyPage() {
  const { id } = useParams();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getChainOfCustody(id)
      .then(setEvents)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="loading-overlay"><div className="spinner" /><span>Loading chain of custody…</span></div>;
  }

  return (
    <>
      <div className="page-header animate-in">
        <div>
          <h1>Chain of Custody</h1>
          <p>Complete audit trail of all evidence-handling actions</p>
        </div>
        <Link href={`/cases/${id}`} className="btn btn-ghost">
          <ArrowLeft size={14} />
          Back to Case
        </Link>
      </div>

      <div className="glass-card-static animate-in animate-in-delay-1" style={{ marginBottom: 24 }}>
        <div style={{
          display: 'flex', gap: 20, fontSize: 13, color: 'var(--text-muted)',
          padding: '12px 16px', background: 'rgba(99, 102, 241, 0.05)',
          borderRadius: 'var(--radius-sm)', marginBottom: 10,
        }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <Link2 size={14} />
            <strong style={{ color: '#1e293b' }}>{events.length}</strong> events recorded
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <ShieldCheck size={14} />
            Append-only, tamper-evident ledger
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <ClipboardCheck size={14} />
            NIST SP 800-86 compliant
          </span>
        </div>
      </div>

      {events.length === 0 ? (
        <div className="glass-card-static empty-state">
          <Link2 size={40} className="empty-state-glyph" />
          <h3>No Events Yet</h3>
          <p>Chain of custody events will appear here as you interact with the case.</p>
        </div>
      ) : (
        <div className="coc-timeline animate-in animate-in-delay-2">
          {events.map((ev) => {
            const ActionIcon = ACTION_ICONS[ev.action] || FileText;

            return (
            <div key={ev.event_id} className="coc-event">
              <div className="coc-event-header">
                <span className="coc-event-action">
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <ActionIcon size={14} />
                    {formatAction(ev.action)}
                  </span>
                </span>
                <span className="coc-event-time">
                  {new Date(ev.timestamp).toLocaleString()}
                </span>
              </div>
              <div className="coc-event-body">
                <p>
                  <span className="actor-name">{ev.actor}</span>
                  {' → '}
                  <strong>{ev.target_artefact}</strong>
                </p>
                {ev.justification && (
                  <p style={{ marginTop: 6, fontStyle: 'italic', color: 'var(--text-muted)' }}>
                    "{ev.justification}"
                  </p>
                )}
                {(ev.hash_before || ev.hash_after) && (
                  <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {ev.hash_before && (
                      <div style={{ fontSize: 12 }}>
                        <span style={{ color: 'var(--text-muted)' }}>Hash before: </span>
                        <span className="hash-value">{ev.hash_before.slice(0, 24)}…</span>
                      </div>
                    )}
                    {ev.hash_after && (
                      <div style={{ fontSize: 12 }}>
                        <span style={{ color: 'var(--text-muted)' }}>Hash after: </span>
                        <span className="hash-value">{ev.hash_after.slice(0, 24)}…</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
            )})}
        </div>
      )}
    </>
  );
}
