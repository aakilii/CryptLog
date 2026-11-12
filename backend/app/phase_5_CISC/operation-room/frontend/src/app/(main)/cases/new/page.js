'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  AlertTriangle,
  AppWindow,
  ArrowLeft,
  ArrowRight,
  Check,
  Database,
  FolderArchive,
  Globe2,
  KeyRound,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { api } from '@operation-room/lib/api';

const LOG_SOURCES = [
  { id: 'AUTH', label: 'Authentication Logs', desc: 'AD, LDAP, SSO, MFA', icon: KeyRound },
  { id: 'VPN', label: 'VPN Logs', desc: 'VPN gateway sessions', icon: Globe2 },
  { id: 'FW', label: 'Firewall Logs', desc: 'Allow/deny/drop rules', icon: Shield },
  { id: 'DB', label: 'Database Logs', desc: 'Query & audit logs', icon: Database },
  { id: 'APP', label: 'Application Logs', desc: 'Web/API access logs', icon: AppWindow },
  { id: 'EPP', label: 'Endpoint Security', desc: 'EDR, antivirus, HIDS', icon: ShieldAlert },
  { id: 'FILE', label: 'File System Logs', desc: 'File access & DLP', icon: FolderArchive },
];

const PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const CLASSIFICATIONS = ['UNCLASSIFIED', 'CONFIDENTIAL', 'SECRET', 'TOP SECRET'];

const STEPS = ['Case Details', 'Scope & Suspects', 'Log Sources', 'Review & Create'];

export default function NewCasePage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [form, setForm] = useState({
    title: '',
    description: '',
    classification: 'UNCLASSIFIED',
    priority: 'MEDIUM',
    lead_investigator: 'analyst',
    investigation_reason: '',
    suspects: '',
    log_sources: [],
    time_start: '',
    time_end: '',
    target_systems: '',
  });

  const set = (key, val) => setForm((f) => ({ ...f, [key]: val }));

  const toggleSource = (id) => {
    setForm((f) => ({
      ...f,
      log_sources: f.log_sources.includes(id)
        ? f.log_sources.filter((s) => s !== id)
        : [...f.log_sources, id],
    }));
  };

  const canNext = () => {
    if (step === 0) return form.title.trim().length > 0;
    if (step === 1) return form.time_start && form.time_end;
    if (step === 2) return form.log_sources.length > 0;
    return true;
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const suspectsArr = form.suspects
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      const systemsArr = form.target_systems
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

      const scope = form.log_sources.map((src) => ({
        source_type: src,
        time_start: new Date(form.time_start).toISOString(),
        time_end: new Date(form.time_end).toISOString(),
        target_actors: suspectsArr,
        target_systems: systemsArr,
      }));

      const payload = {
        title: form.title,
        description: form.description,
        classification: form.classification,
        priority: form.priority,
        lead_investigator: form.lead_investigator,
        investigation_reason: form.investigation_reason,
        suspects: suspectsArr,
        log_sources: form.log_sources,
        scope,
      };

      const result = await api.createCase(payload);
      router.push(`/cases/${result.case_id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div className="page-header animate-in">
        <div>
          <h1>Create New Case</h1>
          <p>Forensic investigation case wizard</p>
        </div>
      </div>

      {/* ── Wizard Steps ──────────────────────────── */}
      <div className="wizard-steps animate-in animate-in-delay-1">
        {STEPS.map((label, i) => (
          <div
            key={label}
            className={`wizard-step ${i === step ? 'active' : ''} ${i < step ? 'completed' : ''}`}
            onClick={() => i < step && setStep(i)}
            style={{ cursor: i < step ? 'pointer' : 'default' }}
          >
            <div className="wizard-step-number">
              {i < step ? <Check size={12} strokeWidth={3} /> : i + 1}
            </div>
            {label}
          </div>
        ))}
      </div>

      <div className="glass-card-static animate-in animate-in-delay-2" style={{ maxWidth: 720 }}>
        {/* ── Step 0: Details ─────────────────────── */}
        {step === 0 && (
          <>
            <div className="form-group">
              <label className="form-label">Case Title *</label>
              <input className="form-input" placeholder="e.g. Suspected Insider Threat — J. Doe"
                     value={form.title} onChange={(e) => set('title', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea className="form-textarea" rows={3} placeholder="Background context for the investigation…"
                        value={form.description} onChange={(e) => set('description', e.target.value)} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="form-group">
                <label className="form-label">Classification</label>
                <select className="form-select" value={form.classification}
                        onChange={(e) => set('classification', e.target.value)}>
                  {CLASSIFICATIONS.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Priority</label>
                <select className="form-select" value={form.priority}
                        onChange={(e) => set('priority', e.target.value)}>
                  {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Investigation Reason</label>
              <textarea className="form-textarea" rows={2} placeholder="Why is this investigation being opened?"
                        value={form.investigation_reason} onChange={(e) => set('investigation_reason', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Lead Investigator</label>
              <input className="form-input" value={form.lead_investigator}
                     onChange={(e) => set('lead_investigator', e.target.value)} />
            </div>
          </>
        )}

        {/* ── Step 1: Scope & Suspects ────────────── */}
        {step === 1 && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div className="form-group">
                <label className="form-label">Time Range Start *</label>
                <input className="form-input" type="datetime-local"
                       value={form.time_start} onChange={(e) => set('time_start', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Time Range End *</label>
                <input className="form-input" type="datetime-local"
                       value={form.time_end} onChange={(e) => set('time_end', e.target.value)} />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Suspected Users / IPs</label>
              <input className="form-input" placeholder="jdoe, asmith, 10.0.1.42 (comma‑separated)"
                     value={form.suspects} onChange={(e) => set('suspects', e.target.value)} />
              <div className="form-hint">Comma‑separated list of usernames or IP addresses under investigation.</div>
            </div>
            <div className="form-group">
              <label className="form-label">Target Systems</label>
              <input className="form-input" placeholder="dc01, db-prod-01, vpn-gw (comma‑separated)"
                     value={form.target_systems} onChange={(e) => set('target_systems', e.target.value)} />
              <div className="form-hint">Comma‑separated list of hosts or services of interest.</div>
            </div>
          </>
        )}

        {/* ── Step 2: Log Sources ─────────────────── */}
        {step === 2 && (
          <>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 18 }}>
              Select the log sources to include in this case. Evidence will be fetched for each selected source.
            </p>
            <div className="checkbox-grid">
              {LOG_SOURCES.map((src) => (
                <label key={src.id}
                       className={`checkbox-item ${form.log_sources.includes(src.id) ? 'selected' : ''}`}
                       onClick={() => toggleSource(src.id)}>
                  <input type="checkbox" checked={form.log_sources.includes(src.id)} readOnly />
                  <div>
                    <div className="checkbox-item-title">
                      <src.icon size={14} />
                      <span>{src.label}</span>
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{src.desc}</div>
                  </div>
                </label>
              ))}
            </div>
          </>
        )}

        {/* ── Step 3: Review ──────────────────────── */}
        {step === 3 && (
          <>
            <h3 style={{ marginBottom: 16, fontSize: 16, fontWeight: 600 }}>Review Your Case</h3>
            <table className="data-table" style={{ marginBottom: 20 }}>
              <tbody>
                <tr><td style={{ fontWeight: 600, width: 180 }}>Title</td><td>{form.title}</td></tr>
                <tr><td style={{ fontWeight: 600 }}>Classification</td><td>{form.classification}</td></tr>
                <tr><td style={{ fontWeight: 600 }}>Priority</td><td>{form.priority}</td></tr>
                <tr><td style={{ fontWeight: 600 }}>Lead Investigator</td><td>{form.lead_investigator}</td></tr>
                <tr><td style={{ fontWeight: 600 }}>Time Range</td><td>{form.time_start} → {form.time_end}</td></tr>
                <tr><td style={{ fontWeight: 600 }}>Suspects</td><td>{form.suspects || '—'}</td></tr>
                <tr><td style={{ fontWeight: 600 }}>Target Systems</td><td>{form.target_systems || '—'}</td></tr>
                <tr><td style={{ fontWeight: 600 }}>Log Sources</td><td>{form.log_sources.join(', ')}</td></tr>
                <tr><td style={{ fontWeight: 600 }}>Reason</td><td>{form.investigation_reason || '—'}</td></tr>
              </tbody>
            </table>

            {error && (
              <div style={{ color: 'var(--accent-rose)', marginBottom: 12, fontSize: 13 }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={14} />
                  {error}
                </span>
              </div>
            )}
          </>
        )}

        {/* ── Navigation ──────────────────────────── */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 28 }}>
          <button className="btn btn-ghost" onClick={() => step > 0 && setStep(step - 1)}
                  disabled={step === 0} style={{ opacity: step === 0 ? 0.3 : 1 }}>
            <ArrowLeft size={14} />
            Back
          </button>
          {step < STEPS.length - 1 ? (
            <button className="btn btn-primary" onClick={() => setStep(step + 1)} disabled={!canNext()}>
              Next
              <ArrowRight size={14} />
            </button>
          ) : (
            <button className="btn btn-primary btn-lg" onClick={handleSubmit} disabled={submitting}>
              {submitting ? (
                <>
                  <div className="spinner" />
                  Creating...
                </>
              ) : (
                <>
                  <ShieldCheck size={15} />
                  Create Case and Initialize Vault
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </>
  );
}
