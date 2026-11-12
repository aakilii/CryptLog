'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@operation-room/lib/api';
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid,
  ResponsiveContainer, Tooltip as RTooltip, Cell,
  PieChart, Pie, BarChart, Bar, Legend,
} from 'recharts';

/* ── Constants ────────────────────────────────────── */
const SRC = {
  AUTH: { color: '#2563eb', icon: 'AU' }, VPN: { color: '#0ea5e9', icon: 'VN' },
  FW: { color: '#fb7185', icon: 'FW' }, DB: { color: '#d97706', icon: 'DB' },
  APP: { color: '#059669', icon: 'AP' }, EPP: { color: '#7c3aed', icon: 'EP' },
  FILE: { color: '#94a3b8', icon: 'FI' },
};
const SEV = {
  HIGH:   { bg: 'rgba(248,113,113,0.15)', color: '#dc2626' },
  MEDIUM: { bg: 'rgba(251,191,36,0.15)',  color: '#d97706' },
  INFO:   { bg: 'rgba(129,140,248,0.10)', color: '#3b82f6' },
};
const mono = { fontFamily: "'JetBrains Mono', monospace" };
const SHAP_COLORS = { pos: '#dc2626', neg: '#059669' };
const PAGE_SIZE = 10;

function quantile(sortedVals, q) {
  if (!sortedVals.length) return 0;
  const idx = (sortedVals.length - 1) * q;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sortedVals[lo];
  return sortedVals[lo] + (sortedVals[hi] - sortedVals[lo]) * (idx - lo);
}

/* ── Tooltip Component ──────────────────────────── */
function Tip({ text, children }) {
  const [show, setShow] = useState(false);
  return (
    <span style={{ position: 'relative', cursor: 'help' }}
      onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && text && (
        <div style={{
          position: 'absolute', bottom: '100%', left: '50%', transform: 'translateX(-50%)',
          padding: '8px 12px', background: '#ffffff', border: '1px solid #e2e8f0',
          borderRadius: 8, fontSize: 11, color: '#1e293b', whiteSpace: 'normal', width: 240,
          zIndex: 999, marginBottom: 6, lineHeight: 1.5, boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          backdropFilter: 'blur(12px)',
        }}>
          {text}
          <div style={{ position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)',
            width: 0, height: 0, borderLeft: '6px solid transparent', borderRight: '6px solid transparent',
            borderTop: '6px solid rgba(37,99,235,0.12)' }} />
        </div>
      )}
    </span>
  );
}

/* ── Card helper ─────────────────────────────────── */
const card = (accent) => ({
  padding: '20px 24px', background: 'var(--bg-card)', border: '1px solid var(--border-color)',
  borderRadius: 14, borderTop: `3px solid ${accent}`,
});
const sectionHead = (icon, text, tip) => (
  <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '0.1em', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
    {icon ? <span>{icon}</span> : null}
    {text}
    {tip && <Tip text={tip}><span style={{ fontSize: 10, opacity: 0.5 }}>ⓘ</span></Tip>}
  </h3>
);

/* ── SHAP Bar Component ──────────────────────────── */
function ShapBar({ value, maxVal, label, desc }) {
  const pct = Math.min(100, (Math.abs(value) / Math.max(maxVal, 0.0001)) * 100);
  const isNeg = value < 0;
  return (
    <Tip text={desc}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0' }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', width: 130, textAlign: 'right', flexShrink: 0 }}>{label}</span>
        <div style={{ flex: 1, height: 10, background: 'rgba(37,99,235,0.03)', borderRadius: 999, overflow: 'hidden', position: 'relative' }}>
          <div style={{
            height: '100%', width: `${pct}%`, borderRadius: 999,
            background: isNeg
              ? 'linear-gradient(90deg, #dc2626, #fb7185)'
              : 'linear-gradient(90deg, #059669, #0ea5e9)',
            transition: 'width 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
            boxShadow: `0 0 8px ${isNeg ? '#dc262630' : '#05966930'}`,
          }} />
        </div>
        <span style={{ ...mono, fontSize: 10, color: isNeg ? '#dc2626' : '#059669', width: 60, textAlign: 'right', fontWeight: 700 }}>
          {value > 0 ? '+' : ''}{value.toFixed(4)}
        </span>
      </div>
    </Tip>
  );
}

/* ═══════════════════════════════════════════════════ */
export default function AnomalyPage() {
  const { id } = useParams();

  const [modelType, setModelType] = useState('ensemble');
  const [contamination, setContamination] = useState(0.1);
  const [nEstimators, setNEstimators] = useState(100);
  const [srcFilters, setSrcFilters] = useState([]);

  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [summary, setSummary] = useState(null);
  const [results, setResults] = useState([]);
  const [runs, setRuns] = useState([]);
  const [anomOnly, setAnomOnly] = useState(false);
  const [expandedShap, setExpandedShap] = useState(null);
  const [topPage, setTopPage] = useState(1);
  const [shapPage, setShapPage] = useState(1);
  const [tab, setTab] = useState('overview');

  const loadResults = useCallback(async () => {
    setLoading(true);
    try {
      const [r, s, rs] = await Promise.all([
        api.getAnomalies(id, anomOnly ? { anomalies_only: 'true' } : {}),
        api.getAnomalySummary(id),
        api.getAnomalyRuns(id),
      ]);
      setResults(r);
      if (!s.error) setSummary(s);
      setRuns(rs);
    } catch {} finally { setLoading(false); }
  }, [id, anomOnly]);

  useEffect(() => { loadResults(); }, [loadResults]);

  const handleRun = async () => {
    setRunning(true);
    try {
      const result = await api.runAnomalyDetection(id, {
        model_type: modelType, contamination, n_estimators: nEstimators,
        source_filters: srcFilters,
      });
      setSummary(result);
      await loadResults();
    } catch (err) { alert('Detection failed: ' + err.message); }
    finally { setRunning(false); }
  };

  const toggleSrc = (src) => setSrcFilters(prev => prev.includes(src) ? prev.filter(s => s !== src) : [...prev, src]);

  const filteredResults = useMemo(() => {
    if (srcFilters.length === 0) return results;
    return results.filter(r => srcFilters.includes(r.source_type));
  }, [results, srcFilters]);

  const derivedSummary = useMemo(() => {
    const totalEvents = filteredResults.length;
    const anomalies = filteredResults.filter(r => r.is_anomaly);
    const anomalyCount = anomalies.length;
    const anomalyRate = totalEvents > 0 ? ((anomalyCount / totalEvents) * 100) : 0;
    const scores = filteredResults
      .map(r => Number(r.anomaly_score) || 0)
      .sort((a, b) => a - b);

    const bySource = {};
    const byActor = {};
    for (const ev of filteredResults) {
      const src = ev.source_type || 'UNKNOWN';
      const actor = ev.actor || 'unknown';
      if (!bySource[src]) bySource[src] = { total: 0, anomalies: 0 };
      if (!byActor[actor]) byActor[actor] = { total: 0, anomalies: 0 };
      bySource[src].total += 1;
      byActor[actor].total += 1;
      if (ev.is_anomaly) {
        bySource[src].anomalies += 1;
        byActor[actor].anomalies += 1;
      }
    }

    const topAnomalies = [...anomalies]
      .sort((a, b) => (b.anomaly_score || 0) - (a.anomaly_score || 0))
      .slice(0, 10)
      .map(a => ({
        tl_event_id: a.tl_event_id,
        score: Number(a.anomaly_score) || 0,
        is_anomaly: Boolean(a.is_anomaly),
        timestamp: a.normalised_ts,
        actor: a.actor,
        source_type: a.source_type,
        action: a.action,
        target: a.target,
        severity: a.severity,
      }));

    return {
      total_events: totalEvents,
      anomaly_count: anomalyCount,
      anomaly_rate: anomalyRate.toFixed(2),
      explainability_type: summary?.explainability_type || 'shap',
      score_stats: {
        min: scores.length ? scores[0] : 0,
        max: scores.length ? scores[scores.length - 1] : 0,
        p95: quantile(scores, 0.95),
      },
      by_source: bySource,
      by_actor: byActor,
      top_anomalies: topAnomalies,
    };
  }, [filteredResults]);

  const displaySummary = srcFilters.length > 0 ? derivedSummary : summary;
  const displayResults = filteredResults;
  const explainabilityType = displaySummary?.explainability_type || summary?.explainability_type || 'shap';
  const explainabilityLabel = explainabilityType === 'context_heuristic' ? 'Context Explainability' : 'SHAP Explainability';
  const shapGlobal = summary?.shap_global_importance || [];
  const shapEvents = srcFilters.length > 0
    ? (summary?.shap_per_event || []).filter(ev => srcFilters.includes(ev.source_type))
    : (summary?.shap_per_event || []);
  const maxGlobalShap = shapGlobal.length > 0 ? Math.max(...shapGlobal.map(f => f.importance)) : 1;

  const displayTopAnomalies = useMemo(() => {
    return [...displayResults]
      .sort((a, b) => (b.anomaly_score || 0) - (a.anomaly_score || 0))
      .map(a => ({
        tl_event_id: a.tl_event_id,
        score: Number(a.anomaly_score) || 0,
        is_anomaly: Boolean(a.is_anomaly),
        timestamp: a.normalised_ts,
        actor: a.actor,
        source_type: a.source_type,
        action: a.action,
        target: a.target,
        severity: a.severity,
      }));
  }, [displayResults]);

  const topPages = Math.max(1, Math.ceil(displayTopAnomalies.length / PAGE_SIZE));
  const shapPages = Math.max(1, Math.ceil(shapEvents.length / PAGE_SIZE));

  useEffect(() => {
    setTopPage(1);
    setShapPage(1);
    setExpandedShap(null);
  }, [id, srcFilters.length, tab]);

  useEffect(() => {
    if (topPage > topPages) setTopPage(topPages);
  }, [topPage, topPages]);

  useEffect(() => {
    if (shapPage > shapPages) setShapPage(shapPages);
  }, [shapPage, shapPages]);

  const topPageItems = useMemo(() => {
    const start = (topPage - 1) * PAGE_SIZE;
    return displayTopAnomalies.slice(start, start + PAGE_SIZE);
  }, [displayTopAnomalies, topPage]);

  const shapPageItems = useMemo(() => {
    const start = (shapPage - 1) * PAGE_SIZE;
    return shapEvents.slice(start, start + PAGE_SIZE);
  }, [shapEvents, shapPage]);

  const renderPager = (page, pages, onPage) => {
    if (pages <= 1) return null;
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'center', marginTop: 12, flexWrap: 'wrap' }}>
        <button
          onClick={() => onPage(Math.max(1, page - 1))}
          disabled={page === 1}
          style={{
            padding: '4px 8px', borderRadius: 8, border: '1px solid var(--border-color)',
            background: page === 1 ? 'rgba(148,163,184,0.08)' : 'var(--bg-card)',
            color: page === 1 ? 'var(--text-muted)' : 'var(--text-secondary)',
            cursor: page === 1 ? 'not-allowed' : 'pointer', fontSize: 11, fontWeight: 700,
          }}
        >
          ◀
        </button>
        {Array.from({ length: pages }, (_, i) => i + 1).map(p => (
          <button
            key={p}
            onClick={() => onPage(p)}
            style={{
              width: 28, height: 28, borderRadius: 999,
              border: `1px solid ${p === page ? '#2563eb' : 'var(--border-color)'}`,
              background: p === page ? '#2563eb' : 'var(--bg-card)',
              color: p === page ? '#fff' : 'var(--text-secondary)',
              fontSize: 11, fontWeight: 700, cursor: 'pointer',
            }}
          >
            {p}
          </button>
        ))}
        <button
          onClick={() => onPage(Math.min(pages, page + 1))}
          disabled={page === pages}
          style={{
            padding: '4px 8px', borderRadius: 8, border: '1px solid var(--border-color)',
            background: page === pages ? 'rgba(148,163,184,0.08)' : 'var(--bg-card)',
            color: page === pages ? 'var(--text-muted)' : 'var(--text-secondary)',
            cursor: page === pages ? 'not-allowed' : 'pointer', fontSize: 11, fontWeight: 700,
          }}
        >
          ▶
        </button>
      </div>
    );
  };

  const TABS = [
    { id: 'overview', icon: 'OV', label: 'Overview' },
    { id: 'explain',  icon: 'SH', label: 'SHAP Explainability' },
    { id: 'events',   icon: 'EV', label: 'Scored Events' },
    { id: 'history',  icon: 'RH', label: 'Run History' },
  ];

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* ── Header ─────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24, paddingBottom: 20, borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em',
            color: '#1e293b' }}>
            Anomaly Detection Agent
          </h1>
          <div style={{ ...mono, fontSize: 11.5, marginTop: 6, color: 'var(--text-muted)', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Tip text="The pipeline runs 7 nodes: LoadData → ExtractFeatures → TrainAndScore → SHAP Explain → StoreResults → UpdateCoC → GenerateSummary">
              <span>LangGraph 7-Node Pipeline</span>
            </Tip>
            <span style={{ opacity: 0.3 }}>·</span>
            <Tip text="Isolation Forest isolates anomalies by random feature partitioning. LOF measures local density deviation. Ensemble combines both (60% IF + 40% LOF). DistilBERT is currently wired to a context-based fallback explanation path.">
              <span>IF + LOF Ensemble</span>
            </Tip>
            <span style={{ opacity: 0.3 }}>·</span>
            <Tip text="SHAP (SHapley Additive exPlanations) uses game theory to explain each prediction by computing the contribution of each feature.">
              <span>SHAP Explainability</span>
            </Tip>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link href={`/cases/${id}/timeline`} className="btn btn-ghost">Timeline</Link>
          <Link href={`/cases/${id}`} className="btn btn-ghost">← Case</Link>
        </div>
      </div>

      {/* ── Config Panel ───────────────────────────── */}
      <div style={{ ...card('#2563eb'), marginBottom: 20 }}>
        {sectionHead('', 'Detection Configuration', 'Configure the ML models, anomaly threshold (contamination), and data filters before running the pipeline.')}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, display: 'block' }}>
              <Tip text="Ensemble combines Isolation Forest (60%) and LOF (40%) for robust detection. DistilBERT uses a context-based fallback explainability path for now.">Model Type ⓘ</Tip>
            </label>
            <select className="form-select" value={modelType} onChange={e => setModelType(e.target.value)} style={{ width: '100%', padding: '8px 12px' }}>
              <option value="ensemble">Ensemble (IF + LOF)</option>
              <option value="IsolationForest">Isolation Forest</option>
              <option value="LOF">Local Outlier Factor</option>
              <option value="DistilBERT">DistilBERT (Context)</option>
            </select>
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, display: 'block' }}>
              <Tip text="The estimated proportion of anomalies in the dataset. Higher values flag more events as anomalous. Typical: 5-15% for insider-threat cases.">
                Contamination: {(contamination * 100).toFixed(0)}% ⓘ
              </Tip>
            </label>
            <input type="range" min="0.01" max="0.5" step="0.01" value={contamination}
              onChange={e => setContamination(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: '#2563eb' }} />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, display: 'block' }}>
              <Tip text="Number of decision trees in the Isolation Forest. More trees = more stable results but slower. 100-200 is optimal for most datasets.">
                Estimators (IF) ⓘ
              </Tip>
            </label>
            <input className="form-input" type="number" min={50} max={500} value={nEstimators}
              onChange={e => setNEstimators(parseInt(e.target.value) || 100)}
              style={{ width: '100%', padding: '8px 12px' }} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center' }}>
          <Tip text="Filter detection to specific log sources. Leave empty to analyse all sources."><span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Sources ⓘ</span></Tip>
          {Object.keys(SRC).map(src => {
            const active = srcFilters.includes(src);
            return (<button key={src} onClick={() => toggleSrc(src)} style={{
              padding: '4px 10px', borderRadius: 999, fontSize: 10, fontWeight: 700,
              background: active ? SRC[src].color : `${SRC[src].color}15`,
              color: active ? '#fff' : SRC[src].color,
              border: `1px solid ${active ? SRC[src].color : 'transparent'}`,
              cursor: 'pointer', transition: 'all 0.2s',
            }}>{SRC[src].icon} {src}</button>);
          })}
          {srcFilters.length > 0 && <button onClick={() => setSrcFilters([])} style={{ fontSize: 10, background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>Clear filters</button>}
        </div>
        <button className="btn btn-primary" onClick={handleRun} disabled={running} style={{ padding: '10px 24px', fontSize: 13, fontWeight: 700 }}>
          {running ? '⟳ Running LangGraph Pipeline…' : modelType === 'DistilBERT' ? 'Run Anomaly Detection + Context Explainability' : 'Run Anomaly Detection + SHAP'}
        </button>
      </div>

      {/* ── Tabs ──────────────────────────────────── */}
      {displaySummary && !displaySummary.error && (
        <>
          <div className="tl-view-tabs" style={{ marginBottom: 18 }}>
            {TABS.map(t => (
              <button key={t.id} className={`tl-view-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
                {t.icon ? <span className="tab-icon">{t.icon}</span> : null}
                {t.label}
              </button>
            ))}
          </div>

          {/* ═════ TAB: OVERVIEW ═════ */}
          {tab === 'overview' && (
            <>
              {/* Stats */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
                {[
                  { icon: 'EV', val: displaySummary.total_events?.toLocaleString(), lbl: 'Events Scored', c: '#2563eb', tip: 'Total events processed from the unified timeline' },
                  { icon: 'AL', val: displaySummary.anomaly_count, lbl: 'Anomalies', c: '#dc2626', tip: 'Events flagged as anomalous by the ensemble model' },
                  { icon: 'RT', val: `${displaySummary.anomaly_rate}%`, lbl: 'Anomaly Rate', c: '#d97706', tip: 'Percentage of events classified as anomalous' },
                  { icon: 'MX', val: displaySummary.score_stats?.max?.toFixed(3), lbl: 'Max Score', c: '#0ea5e9', tip: 'Highest anomaly score (0=normal, 1=most anomalous)' },
                  { icon: 'P95', val: displaySummary.score_stats?.p95?.toFixed(3), lbl: 'P95 Score', c: '#059669', tip: '95th percentile score - events above this are highly anomalous' },
                ].map((c, i) => (
                  <Tip key={i} text={c.tip}>
                    <div style={card(c.c)}>
                      {c.icon ? <div style={{ fontSize: 18 }}>{c.icon}</div> : null}
                      <div style={{ fontSize: 22, fontWeight: 800, color: c.c, ...mono }}>{c.val}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600 }}>{c.lbl}</div>
                    </div>
                  </Tip>
                ))}
              </div>

              {/* ── Anomaly Score Timeline Scatter ─── */}
              {displayResults.length > 0 && (
                <div style={{ ...card('#2563eb'), marginBottom: 20 }}>
                  {sectionHead('', 'Anomaly Score Timeline', 'Each dot is an event plotted by time (X) and anomaly score (Y). Red dots = flagged anomalies. Clusters of red dots indicate attack phases.')}
                  <ResponsiveContainer width="100%" height={260}>
                    <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                      <XAxis type="number" dataKey="timeNum" name="Time"
                        tick={{ fill: '#94a3b8', fontSize: 9 }}
                        tickFormatter={v => { try { return new Date(v).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); } catch { return ''; } }}
                        domain={['dataMin', 'dataMax']} />
                      <YAxis type="number" dataKey="anomaly_score" name="Score"
                        tick={{ fill: '#94a3b8', fontSize: 10 }} domain={[0, 1]}
                        label={{ value: 'Anomaly Score', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 }} />
                      <ZAxis range={[20, 80]} />
                      <RTooltip content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0].payload;
                        return (
                          <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                            <div style={{ fontSize: 12, fontWeight: 700, color: '#1e293b' }}>{d.action} — {d.actor}</div>
                            <div style={{ fontSize: 10, color: '#3b82f6' }}>Score: <strong style={{ color: d.is_anomaly ? '#dc2626' : '#059669' }}>{d.anomaly_score?.toFixed(4)}</strong></div>
                            <div style={{ fontSize: 10, color: '#3b82f6' }}>Source: {d.source_type} | {d.severity}</div>
                            <div style={{ fontSize: 9, color: '#94a3b8' }}>{d.normalised_ts}</div>
                          </div>
                        );
                      }} />
                      <Scatter data={displayResults.slice(0, 500).map(r => ({ ...r, timeNum: new Date(r.normalised_ts).getTime() }))} animationDuration={600}>
                        {displayResults.slice(0, 500).map((r, i) => (
                          <Cell key={i} fill={r.is_anomaly ? '#dc2626' : '#475569'} fillOpacity={r.is_anomaly ? 0.9 : 0.3} />
                        ))}
                      </Scatter>
                    </ScatterChart>
                  </ResponsiveContainer>
                  <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 6 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#dc2626' }} /> Anomaly</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#94a3b8' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#475569' }} /> Normal</span>
                  </div>
                </div>
              )}

              {/* ── Source Donut + Actor Anomaly Bar ── */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 20 }}>
                {/* Source Donut */}
                <div style={card('#0ea5e9')}>
                  {sectionHead('', 'Anomalies by Source', 'Which log sources produced the most anomalies — helps prioritise investigation targets')}
                  {(() => {
                    const srcData = Object.entries(displaySummary.by_source || {}).map(([src, d]) => ({ name: src, value: d.anomalies, total: d.total }));
                    return srcData.length > 0 ? (
                      <>
                        <ResponsiveContainer width="100%" height={200}>
                          <PieChart>
                            <Pie data={srcData} cx="50%" cy="50%" innerRadius={45} outerRadius={75}
                              paddingAngle={3} dataKey="value" stroke="none" animationDuration={800}>
                              {srcData.map(d => <Cell key={d.name} fill={SRC[d.name]?.color || '#666'} />)}
                            </Pie>
                            <RTooltip content={({ active, payload }) => {
                              if (!active || !payload?.length) return null;
                              const d = payload[0].payload;
                              return (
                                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                                  <div style={{ fontSize: 12, fontWeight: 700, color: SRC[d.name]?.color }}>{SRC[d.name]?.icon} {d.name}</div>
                                  <div style={{ fontSize: 10, color: '#3b82f6' }}>Anomalies: <strong>{d.value}</strong> / {d.total} ({((d.value / Math.max(d.total, 1)) * 100).toFixed(1)}%)</div>
                                </div>
                              );
                            }} />
                          </PieChart>
                        </ResponsiveContainer>
                        <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
                          {srcData.map(d => (
                            <span key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9, color: SRC[d.name]?.color }}>
                              <span style={{ width: 6, height: 6, borderRadius: '50%', background: SRC[d.name]?.color }} />
                              {d.name} ({d.value})
                            </span>
                          ))}
                        </div>
                      </>
                    ) : null;
                  })()}
                </div>

                {/* Actor Anomaly Bar */}
                <div style={card('#059669')}>
                  {sectionHead('', 'Actor Anomaly Rate', 'Anomaly rate per actor — actors with unusually high rates should be investigated')}
                  {(() => {
                    const actData = Object.entries(displaySummary.by_actor || {}).map(([actor, d]) => ({
                      name: actor, anomalies: d.anomalies, normal: d.total - d.anomalies,
                      rate: ((d.anomalies / Math.max(d.total, 1)) * 100).toFixed(1),
                    })).sort((a, b) => b.anomalies - a.anomalies);
                    return actData.length > 0 ? (
                      <ResponsiveContainer width="100%" height={Math.max(160, actData.length * 32)}>
                        <BarChart data={actData} layout="vertical" margin={{ left: 50, right: 20 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                          <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                          <YAxis type="category" dataKey="name" tick={{ fill: '#1e293b', fontSize: 11, fontWeight: 600 }} width={50} />
                          <RTooltip content={({ active, payload }) => {
                            if (!active || !payload?.length) return null;
                            const d = payload[0].payload;
                            return (
                              <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: '#1e293b' }}>{d.name}</div>
                                <div style={{ fontSize: 10, color: '#dc2626' }}>Anomalies: <strong>{d.anomalies}</strong></div>
                                <div style={{ fontSize: 10, color: '#059669' }}>Normal: <strong>{d.normal}</strong></div>
                                <div style={{ fontSize: 10, color: '#d97706' }}>Anomaly Rate: <strong>{d.rate}%</strong></div>
                              </div>
                            );
                          }} />
                          <Bar dataKey="anomalies" stackId="a" fill="#dc2626" name="Anomalies" radius={[0, 0, 0, 0]} />
                          <Bar dataKey="normal" stackId="a" fill="rgba(52,211,153,0.3)" name="Normal" radius={[0, 4, 4, 0]} />
                          <Legend wrapperStyle={{ fontSize: 10 }} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : null;
                  })()}
                </div>
              </div>

              {/* Top Anomalies */}
              <div style={{ ...card('#dc2626'), marginBottom: 20 }}>
                {sectionHead('', `Top Anomalies (${displayTopAnomalies.length})`, 'Highest-scoring events with page navigation in blocks of 10.')}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {topPageItems.map((a, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
                      background: a.is_anomaly ? 'rgba(248,113,113,0.06)' : 'rgba(0,0,0,0.015)',
                      borderRadius: 10, borderLeft: `3px solid ${a.is_anomaly ? '#dc2626' : '#475569'}`,
                    }}>
                      <Tip text={`Anomaly score: ${a.score.toFixed(4)}`}>
                        <span style={{ ...mono, fontSize: 14, fontWeight: 800, color: a.is_anomaly ? '#dc2626' : '#94a3b8', width: 50, textAlign: 'right' }}>{a.score.toFixed(3)}</span>
                      </Tip>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: SRC[a.source_type]?.color || '#666' }} />
                      <span style={{ fontSize: 11, fontWeight: 700, color: SRC[a.source_type]?.color }}>{a.source_type}</span>
                      <span style={{ fontSize: 12, fontWeight: 600 }}>{a.action}</span>
                      <span style={{ fontSize: 11, color: '#0ea5e9', fontWeight: 600 }}>{a.actor}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>→ {a.target}</span>
                      <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>
                        {a.timestamp ? new Date(a.timestamp).toLocaleString() : ''}
                      </span>
                      <span style={{ padding: '2px 7px', borderRadius: 999, fontSize: 9, fontWeight: 700, background: SEV[a.severity]?.bg, color: SEV[a.severity]?.color }}>{a.severity}</span>
                    </div>
                  ))}
                </div>
                {renderPager(topPage, topPages, setTopPage)}
              </div>
            </>
          )}

          {/* ═════ TAB: SHAP EXPLAINABILITY ═════ */}
          {tab === 'explain' && (
            <>
              {/* Global Feature Importance */}
              <div style={{ ...card('#2563eb'), marginBottom: 20 }}>
                {sectionHead('', `Global Feature Importance (${explainabilityLabel})`, explainabilityType === 'context_heuristic'
                  ? 'Heuristic context contributions used while the DistilBERT runtime is being wired up. Higher values indicate features that push events toward anomalous behavior.'
                  : 'Mean |SHAP value| across all events. Higher values indicate features that contribute more to anomaly decisions. Based on Shapley values from cooperative game theory.')}
                {shapGlobal.length > 0 ? (
                  <div>
                    {shapGlobal.map((feat, i) => (
                      <Tip key={feat.feature} text={feat.description}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: i < shapGlobal.length - 1 ? '1px solid rgba(148,163,184,0.06)' : 'none' }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: '#1e293b', width: 140, display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                            {feat.feature.replace(/_/g, ' ')}
                            <span style={{ fontSize: 9, opacity: 0.4 }}>ⓘ</span>
                          </span>
                          <div style={{ flex: 1, height: 14, background: 'rgba(37,99,235,0.03)', borderRadius: 999, overflow: 'hidden', position: 'relative' }}>
                            <div style={{
                              height: '100%', width: `${feat.importance_pct}%`, borderRadius: 999,
                              background: `linear-gradient(90deg, #2563eb, ${i < 3 ? '#dc2626' : '#0ea5e9'})`,
                              transition: 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)',
                              boxShadow: i < 3 ? '0 0 12px rgba(248,113,113,0.2)' : 'none',
                            }} />
                          </div>
                          <span style={{ ...mono, fontSize: 11, fontWeight: 700, color: i < 3 ? '#dc2626' : '#2563eb', width: 50, textAlign: 'right' }}>
                            {feat.importance_pct}%
                          </span>
                          <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', width: 60, textAlign: 'right' }}>
                            {feat.importance.toFixed(4)}
                          </span>
                        </div>
                      </Tip>
                    ))}
                  </div>
                ) : (
                  <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
                    Run detection with Isolation Forest, Ensemble, or DistilBERT to generate explanation data.
                  </div>
                )}
              </div>

              {/* Per-Event SHAP Explanations */}
              {shapEvents.length > 0 && (
                <div style={{ ...card('#dc2626'), marginBottom: 20 }}>
                  {sectionHead('', `Per-Event ${explainabilityLabel} (${shapEvents.length})`, explainabilityType === 'context_heuristic'
                    ? 'Context fallback explanations show which features pushed the event toward anomalous behavior while DistilBERT inference is not yet active.'
                    : 'For each top anomaly, SHAP shows which features pushed the event toward or away from being anomalous. Red bars = anomalous direction, green = normal direction.')}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {shapPageItems.map((ev, i) => {
                      const isOpen = expandedShap === ev.tl_event_id;
                      const maxShap = ev.feature_contributions?.length > 0
                        ? Math.max(...ev.feature_contributions.map(f => Math.abs(f.shap_value)))
                        : 1;
                      return (
                        <div key={ev.tl_event_id} style={{
                          borderRadius: 12, border: '1px solid var(--border-color)',
                          background: isOpen ? 'rgba(248,113,113,0.03)' : 'var(--bg-card)',
                          overflow: 'hidden', transition: 'all 0.3s',
                        }}>
                          {/* Event header */}
                          <div onClick={() => setExpandedShap(isOpen ? null : ev.tl_event_id)} style={{
                            display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
                            cursor: 'pointer',
                          }}>
                            <span style={{ ...mono, fontSize: 14, fontWeight: 800, color: '#dc2626', width: 50, textAlign: 'right' }}>
                              {ev.anomaly_score.toFixed(3)}
                            </span>
                            <span style={{ width: 6, height: 6, borderRadius: '50%', background: SRC[ev.source_type]?.color || '#666' }} />
                            <span style={{ fontSize: 11, fontWeight: 700, color: SRC[ev.source_type]?.color }}>{ev.source_type}</span>
                            <span style={{ fontSize: 12, fontWeight: 600 }}>{ev.action}</span>
                            <span style={{ color: '#0ea5e9', fontWeight: 600, fontSize: 11 }}>{ev.actor}</span>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>→ {ev.target}</span>
                            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
                              <Tip text={`Top driver: ${ev.top_driver_desc}`}>
                                <span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 9, fontWeight: 700, background: 'rgba(248,113,113,0.1)', color: '#dc2626' }}>
                                  {ev.top_driver?.replace(/_/g, ' ')}
                                </span>
                              </Tip>
                              <span style={{ fontSize: 12, transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}>▼</span>
                            </div>
                          </div>

                          {/* SHAP Waterfall */}
                          {isOpen && ev.feature_contributions && (
                            <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--border-color)' }}>
                              <div style={{ padding: '12px 0 8px', fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', display: 'flex', justifyContent: 'space-between' }}>
                                <span>Feature Contributions (SHAP Waterfall)</span>
                                <span style={{ display: 'flex', gap: 12 }}>
                                  <span style={{ color: '#dc2626' }}>■ Pushes anomalous</span>
                                  <span style={{ color: '#059669' }}>■ Pushes normal</span>
                                </span>
                              </div>
                              {ev.feature_contributions.map(fc => (
                                <ShapBar key={fc.feature} value={fc.shap_value} maxVal={maxShap}
                                  label={fc.feature.replace(/_/g, ' ')} desc={fc.description} />
                              ))}
                              <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8, background: 'rgba(129,140,248,0.06)', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                                <strong style={{ color: '#2563eb' }}>Interpretation:</strong> The top driver for this anomaly is <strong style={{ color: '#dc2626' }}>{ev.top_driver?.replace(/_/g, ' ')}</strong>.
                                {' '}{ev.top_driver_desc}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  {renderPager(shapPage, shapPages, setShapPage)}
                </div>
              )}
            </>
          )}

          {/* ═════ TAB: SCORED EVENTS ═════ */}
          {tab === 'events' && results.length > 0 && (
            <div className="glass-card-static" style={{ overflowX: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                {sectionHead('', `Scored Events (${results.length})`, 'All events with their anomaly scores. Click "Anomalies Only" to filter.')}
                <button onClick={() => setAnomOnly(!anomOnly)} style={{
                  padding: '5px 12px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
                  background: anomOnly ? 'rgba(248,113,113,0.15)' : 'transparent',
                  border: `1px solid ${anomOnly ? '#dc2626' : 'var(--border-color)'}`,
                  color: anomOnly ? '#dc2626' : 'var(--text-muted)', transition: 'all 0.2s',
                }}>Anomalies Only</button>
              </div>
              <table className="data-table">
                <thead><tr>
                  <th><Tip text="Anomaly score from 0 (normal) to 1 (highly anomalous)">Score ⓘ</Tip></th>
                  <th><Tip text="Whether the event exceeds the anomaly threshold">Flag ⓘ</Tip></th>
                  <th>Timestamp</th><th>Source</th><th>Actor</th><th>Action</th><th>Target</th>
                  <th><Tip text="Severity classification: HIGH, MEDIUM, or INFO">Sev ⓘ</Tip></th>
                </tr></thead>
                <tbody>
                  {results.slice(0, 300).map(ev => (
                    <tr key={ev.score_id} style={{ background: ev.is_anomaly ? 'rgba(248,113,113,0.03)' : 'transparent' }}>
                      <td>
                        <Tip text={`Raw score: ${ev.anomaly_score.toFixed(6)}`}>
                          <span style={{ ...mono, fontSize: 12, fontWeight: 800,
                            color: ev.anomaly_score > 0.8 ? '#dc2626' : ev.anomaly_score > 0.5 ? '#d97706' : '#94a3b8',
                          }}>{ev.anomaly_score.toFixed(3)}</span>
                        </Tip>
                      </td>
                      <td>{ev.is_anomaly ? <span style={{ color: '#dc2626', fontSize: 10, fontWeight: 700 }}>ALERT</span> : <span style={{ color: '#475569' }}>—</span>}</td>
                      <td style={{ ...mono, fontSize: 11, whiteSpace: 'nowrap' }}>{new Date(ev.normalised_ts).toLocaleString()}</td>
                      <td><span style={{ fontWeight: 700, fontSize: 11, color: SRC[ev.source_type]?.color }}>{ev.source_type}</span></td>
                      <td style={{ color: '#0ea5e9', fontWeight: 600, fontSize: 12 }}>{ev.actor}</td>
                      <td style={{ fontWeight: 600, fontSize: 12 }}>{ev.action}</td>
                      <td style={{ fontSize: 11, color: 'var(--text-secondary)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.target}</td>
                      <td><span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700, background: SEV[ev.severity]?.bg, color: SEV[ev.severity]?.color }}>{ev.severity}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {results.length > 300 && <div style={{ padding: '10px 16px', fontSize: 11, color: 'var(--text-muted)', ...mono }}>Showing 300 of {results.length}</div>}
            </div>
          )}

          {/* ═════ TAB: HISTORY ═════ */}
          {tab === 'history' && runs.length > 0 && (
            <div style={{ ...card('#94a3b8') }}>
              {sectionHead('', 'Detection Run History', 'All previous anomaly detection runs. Each run records model parameters, results, and SHAP explanations.')}
              <table className="data-table">
                <thead><tr>
                  <th>Run ID</th><th>Model</th>
                  <th><Tip text="Proportion of data expected to be anomalous">Contam. ⓘ</Tip></th>
                  <th>Events</th><th>Anomalies</th><th>Status</th><th>Started</th>
                </tr></thead>
                <tbody>
                  {runs.map(run => (
                    <tr key={run.run_id}>
                      <td style={{ ...mono, fontSize: 10 }}>{run.run_id?.slice(0, 8)}…</td>
                      <td style={{ fontWeight: 600, fontSize: 12 }}>{run.model_type}</td>
                      <td style={{ ...mono, fontSize: 12 }}>{((run.contamination || 0) * 100).toFixed(0)}%</td>
                      <td style={{ ...mono }}>{run.total_events}</td>
                      <td style={{ color: '#dc2626', fontWeight: 700, ...mono }}>{run.anomaly_count || '—'}</td>
                      <td><span style={{
                        padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700,
                        background: run.status === 'COMPLETED' ? 'rgba(52,211,153,0.15)' : run.status === 'FAILED' ? 'rgba(248,113,113,0.15)' : 'rgba(251,191,36,0.15)',
                        color: run.status === 'COMPLETED' ? '#059669' : run.status === 'FAILED' ? '#dc2626' : '#d97706',
                      }}>{run.status}</span></td>
                      <td style={{ ...mono, fontSize: 10 }}>{run.started_at ? new Date(run.started_at).toLocaleString() : ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Empty State */}
      {!loading && !summary && results.length === 0 && (
        <div className="glass-card-static empty-state" style={{ padding: 48 }}>
          <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.5 }}>AD</div>
          <h3 style={{ fontSize: 20 }}>No Anomaly Detection Results</h3>
          <p>Configure model parameters above and click <strong>{modelType === 'DistilBERT' ? '"Run Anomaly Detection + Context Explainability"' : '"Run Anomaly Detection + SHAP"'}</strong> to start the pipeline.</p>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
            The pipeline will: load timeline data → extract 10 features → train the selected model → compute explanation data → store results → update chain of custody.
          </p>
        </div>
      )}
    </div>
  );
}


