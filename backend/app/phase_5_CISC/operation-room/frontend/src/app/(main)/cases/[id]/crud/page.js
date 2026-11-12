'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@operation-room/lib/api';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RTooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
  AreaChart, Area, ScatterChart, Scatter, ZAxis,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from 'recharts';

/* ── Constants ────────────────────────────────────── */
const CRUD_COLORS = { CREATE: '#059669', READ: '#2563eb', UPDATE: '#d97706', DELETE: '#dc2626' };
const CRUD_ICONS  = { CREATE: 'C', READ: 'R', UPDATE: 'U', DELETE: 'D' };
const SENS_COLORS = { LOW: '#94a3b8', MEDIUM: '#d97706', HIGH: '#ea580c', CRITICAL: '#dc2626' };
const SENS_ORDER  = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];
const mono = { fontFamily: "'JetBrains Mono', monospace" };

/* ── Tooltip ────────────────────────────────────── */
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
          borderRadius: 8, fontSize: 11, color: '#1e293b', whiteSpace: 'normal', width: 260,
          zIndex: 999, marginBottom: 6, lineHeight: 1.5, boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
        }}>{text}</div>
      )}
    </span>
  );
}

const card = (accent) => ({
  padding: '20px 24px', background: 'var(--bg-card)', border: '1px solid var(--border-color)',
  borderRadius: 14, borderTop: `3px solid ${accent}`,
});

function SensChip({ level }) {
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 999, fontSize: 9, fontWeight: 700,
      background: `${SENS_COLORS[level] || '#94a3b8'}15`,
      color: SENS_COLORS[level] || '#94a3b8',
      border: `1px solid ${SENS_COLORS[level] || '#94a3b8'}30`,
    }}>{level}</span>
  );
}

function CrudChip({ type }) {
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700,
      background: `${CRUD_COLORS[type] || '#2563eb'}18`,
      color: CRUD_COLORS[type] || '#2563eb',
    }}>{CRUD_ICONS[type]} {type}</span>
  );
}

/* ── Custom Recharts Tooltip ──────────────────────── */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10,
      padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
    }}>
      {label && <div style={{ fontSize: 11, fontWeight: 700, color: '#1e293b', marginBottom: 4 }}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i} style={{ fontSize: 11, color: p.color || '#3b82f6', display: 'flex', gap: 8 }}>
          <span style={{ fontWeight: 600 }}>{p.name}:</span>
          <span style={{ ...mono, fontWeight: 700 }}>{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}</span>
        </div>
      ))}
    </div>
  );
}

/* ── Donut Center Label ──────────────────────────── */
function DonutCenter({ cx, cy, value, label }) {
  return (
    <>
      <text x={cx} y={cy - 6} textAnchor="middle" fill="#1e293b" style={{ fontSize: 22, fontWeight: 800, fontFamily: 'JetBrains Mono, monospace' }}>{value}</text>
      <text x={cx} y={cy + 14} textAnchor="middle" fill="#94a3b8" style={{ fontSize: 10, fontWeight: 600 }}>{label}</text>
    </>
  );
}

/* ═══════════════════════════════════════════════════ */
export default function CrudPage() {
  const { id } = useParams();

  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [events, setEvents] = useState([]);
  const [summary, setSummary] = useState([]);
  const [runs, setRuns] = useState([]);
  const [tab, setTab] = useState('overview');

  const [filterCrud, setFilterCrud] = useState('all');
  const [filterSens, setFilterSens] = useState('all');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filterCrud !== 'all') params.crud_type = filterCrud;
      if (filterSens !== 'all') params.sensitivity = filterSens;
      const [ev, sum, rs] = await Promise.all([
        api.getCrudEvents(id, params).catch(() => []),
        api.getCrudSummary(id).catch(() => []),
        api.getCrudRuns(id).catch(() => []),
      ]);
      setEvents(Array.isArray(ev) ? ev : []);
      setSummary(Array.isArray(sum) ? sum : []);
      setRuns(Array.isArray(rs) ? rs : []);
    } catch {} finally { setLoading(false); }
  }, [id, filterCrud, filterSens]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRun = async () => {
    setRunning(true);
    try { await api.runCrud(id, {}); await loadData(); }
    catch (err) { alert('CRUD analysis failed: ' + err.message); }
    finally { setRunning(false); }
  };

  /* ── Computed Chart Data ──────────────────────── */

  const stats = useMemo(() => {
    const total = events.length;
    const highRisk = events.filter(e => e.is_high_risk).length;
    const byType = {}; events.forEach(e => { byType[e.crud_type] = (byType[e.crud_type] || 0) + 1; });
    const bySens = {}; events.forEach(e => { bySens[e.sensitivity] = (bySens[e.sensitivity] || 0) + 1; });
    return { total, highRisk, byType, bySens };
  }, [events]);

  // Donut chart data
  const donutData = useMemo(() =>
    ['CREATE', 'READ', 'UPDATE', 'DELETE']
      .filter(t => stats.byType[t] > 0)
      .map(t => ({ name: t, value: stats.byType[t] || 0 })),
  [stats]);

  // Sensitivity donut data
  const sensDonutData = useMemo(() =>
    SENS_ORDER.filter(s => stats.bySens[s] > 0).map(s => ({ name: s, value: stats.bySens[s] || 0 })),
  [stats]);

  // Temporal activity (events per hour)
  const temporalData = useMemo(() => {
    const hours = Array.from({ length: 24 }, (_, i) => ({
      hour: `${String(i).padStart(2, '0')}:00`,
      CREATE: 0, READ: 0, UPDATE: 0, DELETE: 0, total: 0, risk: 0,
    }));
    events.forEach(ev => {
      try {
        const h = new Date(ev.normalised_ts).getUTCHours();
        if (hours[h]) {
          hours[h][ev.crud_type] = (hours[h][ev.crud_type] || 0) + 1;
          hours[h].total++;
          if (ev.is_high_risk) hours[h].risk++;
        }
      } catch {}
    });
    return hours;
  }, [events]);

  // Actor risk radar data
  const actorData = useMemo(() => {
    const actors = {};
    events.forEach(e => {
      if (!actors[e.actor]) actors[e.actor] = { name: e.actor, count: 0, risk: 0, CREATE: 0, READ: 0, UPDATE: 0, DELETE: 0, anomaly: 0 };
      actors[e.actor].count++;
      actors[e.actor][e.crud_type]++;
      actors[e.actor].anomaly += (e.anomaly_score || 0);
      if (e.is_high_risk) actors[e.actor].risk++;
    });
    return Object.values(actors).sort((a, b) => b.count - a.count).slice(0, 10).map(a => ({
      ...a, avgAnomaly: a.count > 0 ? (a.anomaly / a.count) : 0,
    }));
  }, [events]);

  // Target heatmap data (scatter)
  const targetScatter = useMemo(() => {
    const targets = {};
    events.forEach(e => {
      const t = e.target_object || '(none)';
      if (!targets[t]) targets[t] = { name: t, count: 0, risk: 0, avgAnomaly: 0, sens: 'LOW' };
      targets[t].count++;
      targets[t].avgAnomaly += (e.anomaly_score || 0);
      if (e.is_high_risk) targets[t].risk++;
      const sw = { LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };
      if ((sw[e.sensitivity] || 0) > (sw[targets[t].sens] || 0)) targets[t].sens = e.sensitivity;
    });
    return Object.values(targets).map(t => ({
      ...t, avgAnomaly: t.count > 0 ? +(t.avgAnomaly / t.count).toFixed(3) : 0,
    })).sort((a, b) => b.count - a.count).slice(0, 20);
  }, [events]);

  // Radar data for top actors
  const radarData = useMemo(() => {
    return actorData.slice(0, 5).map(a => ({
      actor: a.name,
      Creates: a.CREATE, Reads: a.READ, Updates: a.UPDATE, Deletes: a.DELETE,
      'Risk Events': a.risk, 'Avg Anomaly': +(a.avgAnomaly * 100).toFixed(0),
    }));
  }, [actorData]);

  const TABS = [
    { id: 'overview',   icon: 'OV', label: 'Overview' },
    { id: 'temporal',   icon: 'TM', label: 'Temporal' },
    { id: 'actors',     icon: 'AC', label: 'Actors' },
    { id: 'matrix',     icon: 'MX', label: 'Matrix' },
    { id: 'events',     icon: 'EV', label: 'Events' },
    { id: 'high_risk',  icon: 'HR', label: `High-Risk (${stats.highRisk})` },
    { id: 'history',    icon: 'RN', label: 'Runs' },
  ];

  return (
    <div style={{ maxWidth: 1500, margin: '0 auto' }}>
      {/* ── Header ─────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, paddingBottom: 16, borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.04em',
            color: '#1e293b' }}>
             CRUD & Data-Access Analysis
          </h1>
          <div style={{ ...mono, fontSize: 11, marginTop: 4, color: 'var(--text-muted)' }}>
            <Tip text="5-node pipeline: LoadAndClassify → ComputeMetrics → DetectPatterns → BuildMatrix → StoreAndAudit">LangGraph 5-Node Pipeline</Tip>
            <span style={{ opacity: 0.3, margin: '0 8px' }}>·</span>
            <Tip text="Classifies each event as Create/Read/Update/Delete with sensitivity scoring (LOW→CRITICAL)">Sensitivity Classification</Tip>
            <span style={{ opacity: 0.3, margin: '0 8px' }}>·</span>
            <Tip text="Detects suspicious patterns: off-hours bulk reads, audit trail modification, burst activity">Pattern Detection</Tip>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link href={`/cases/${id}/correlation`} className="btn btn-ghost"> Correlation</Link>
          <Link href={`/cases/${id}/anomalies`} className="btn btn-ghost"> Anomalies</Link>
          <Link href={`/cases/${id}`} className="btn btn-ghost">← Case</Link>
        </div>
      </div>

      {/* ── Run Button ──────────────────────────── */}
      <div style={{ ...card('#059669'), marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>
              <Tip text="Reuses unified_timeline + anomaly_scores from upstream modules. Classifies 30+ action types into CRUD, applies 11 sensitivity rules, and runs 6 heuristic pattern detectors.">Analysis Engine ⓘ</Tip>
            </div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Classifies CRUD operations, detects suspicious patterns, and generates user×object×operation matrices.
            </span>
          </div>
          <button className="btn btn-primary" onClick={handleRun} disabled={running} style={{ padding: '10px 22px', fontSize: 13, fontWeight: 700, flexShrink: 0 }}>
            {running ? 'Analyzing...' : 'Run CRUD Analysis'}
          </button>
        </div>
      </div>

      {/* ── Stats Cards ──────────────────────────── */}
      {stats.total > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginBottom: 16 }}>
          {[
            { label: 'Total Events', value: stats.total, color: '#2563eb', tip: 'Total CRUD-classified events' },
            { label: 'High-Risk', value: stats.highRisk, color: '#dc2626', tip: 'Events flagged by heuristic detectors' },
            { label: 'Creates', value: stats.byType.CREATE || 0, color: CRUD_COLORS.CREATE },
            { label: 'Reads', value: stats.byType.READ || 0, color: CRUD_COLORS.READ },
            { label: 'Updates', value: stats.byType.UPDATE || 0, color: CRUD_COLORS.UPDATE },
            { label: 'Deletes', value: stats.byType.DELETE || 0, color: CRUD_COLORS.DELETE },
          ].map(s => (
            <Tip key={s.label} text={s.tip || s.label}>
              <div style={{ ...card(s.color), textAlign: 'center', cursor: 'help' }}>
                <div style={{ ...mono, fontSize: 22, fontWeight: 800, color: s.color }}>{s.value}</div>
                <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', marginTop: 2 }}>{s.label}</div>
              </div>
            </Tip>
          ))}
        </div>
      )}

      {/* ── Tabs ─────────────────────────────── */}
      <div className="tl-view-tabs" style={{ marginBottom: 16 }}>
        {TABS.map(t => (
          <button key={t.id} className={`tl-view-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            <span className="tab-icon">{t.icon}</span>{t.label}
          </button>
        ))}
      </div>

      {/* ═══ TAB: OVERVIEW — Charts Dashboard ═══ */}
      {tab === 'overview' && stats.total > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          {/* CRUD Type Donut */}
          <div style={card('#2563eb')}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              <Tip text="Distribution of Create/Read/Update/Delete operations across all events">CRUD Type Distribution ⓘ</Tip>
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={donutData} cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                  paddingAngle={3} dataKey="value" stroke="none" animationDuration={800}>
                  {donutData.map(d => <Cell key={d.name} fill={CRUD_COLORS[d.name]} />)}
                </Pie>
                <RTooltip content={<ChartTooltip />} />
                <text x="50%" y="46%" textAnchor="middle" fill="#1e293b" style={{ fontSize: 22, fontWeight: 800, fontFamily: 'JetBrains Mono, monospace' }}>{stats.total}</text>
                <text x="50%" y="56%" textAnchor="middle" fill="#94a3b8" style={{ fontSize: 10, fontWeight: 600 }}>TOTAL</text>
              </PieChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 16 }}>
              {donutData.map(d => (
                <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: CRUD_COLORS[d.name] }} />
                  <span style={{ fontSize: 10, fontWeight: 600, color: CRUD_COLORS[d.name] }}>{d.name}</span>
                  <span style={{ ...mono, fontSize: 9, color: 'var(--text-muted)' }}>({d.value})</span>
                </div>
              ))}
            </div>
          </div>

          {/* Sensitivity Donut */}
          <div style={card('#d97706')}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              <Tip text="How many events touch LOW/MEDIUM/HIGH/CRITICAL sensitivity data. CRITICAL = payroll, passwords, audit trails.">Data Sensitivity Breakdown ⓘ</Tip>
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={sensDonutData} cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                  paddingAngle={3} dataKey="value" stroke="none" animationDuration={800}>
                  {sensDonutData.map(d => <Cell key={d.name} fill={SENS_COLORS[d.name]} />)}
                </Pie>
                <RTooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 14 }}>
              {sensDonutData.map(d => (
                <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: SENS_COLORS[d.name] }} />
                  <span style={{ fontSize: 10, fontWeight: 600, color: SENS_COLORS[d.name] }}>{d.name}</span>
                  <span style={{ ...mono, fontSize: 9, color: 'var(--text-muted)' }}>({d.value})</span>
                </div>
              ))}
            </div>
          </div>

          {/* Actor Horizontal Bar (full width) */}
          <div style={{ ...card('#0ea5e9'), gridColumn: '1 / -1' }}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              <Tip text="Top actors by CRUD operation count, split by type. Red = high-risk event count.">Top Actors — CRUD Breakdown ⓘ</Tip>
            </h3>
            <ResponsiveContainer width="100%" height={Math.max(200, actorData.length * 32)}>
              <BarChart data={actorData} layout="vertical" margin={{ left: 60, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#1e293b', fontSize: 11, fontWeight: 600 }} width={60} />
                <RTooltip content={<ChartTooltip />} />
                <Bar dataKey="CREATE" stackId="a" fill={CRUD_COLORS.CREATE} radius={[0, 0, 0, 0]} name="Create" />
                <Bar dataKey="READ" stackId="a" fill={CRUD_COLORS.READ} name="Read" />
                <Bar dataKey="UPDATE" stackId="a" fill={CRUD_COLORS.UPDATE} name="Update" />
                <Bar dataKey="DELETE" stackId="a" fill={CRUD_COLORS.DELETE} radius={[0, 4, 4, 0]} name="Delete" />
                <Legend wrapperStyle={{ fontSize: 10, color: '#94a3b8' }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ═══ TAB: TEMPORAL — Activity Over Time ═══ */}
      {tab === 'temporal' && stats.total > 0 && (
        <div style={{ display: 'grid', gap: 14 }}>
          {/* Stacked Area Chart: CRUD over time of day */}
          <div style={card('#2563eb')}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              <Tip text="CRUD activity by hour of day (UTC). Peaks outside 07:00–20:00 suggest off-hours activity — a classic insider threat indicator.">
                 Hourly CRUD Activity ⓘ
              </Tip>
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={temporalData} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
                <defs>
                  {['CREATE', 'READ', 'UPDATE', 'DELETE'].map(t => (
                    <linearGradient key={t} id={`grad-${t}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CRUD_COLORS[t]} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={CRUD_COLORS[t]} stopOpacity={0.02} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                <XAxis dataKey="hour" tick={{ fill: '#94a3b8', fontSize: 9 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <RTooltip content={<ChartTooltip />} />
                {['CREATE', 'READ', 'UPDATE', 'DELETE'].map(t => (
                  <Area key={t} type="monotone" dataKey={t} stackId="1"
                    stroke={CRUD_COLORS[t]} fill={`url(#grad-${t})`}
                    strokeWidth={2} name={t} animationDuration={800} />
                ))}
                <Legend wrapperStyle={{ fontSize: 10 }} />
              </AreaChart>
            </ResponsiveContainer>
            {/* Off-hours markers */}
            <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8 }}>
              <span style={{ fontSize: 10, color: '#dc2626', fontWeight: 600 }}>Off-hours: 00:00-06:59, 21:00-23:59</span>
              <span style={{ fontSize: 10, color: '#059669', fontWeight: 600 }}>Business hours: 07:00-20:00</span>
            </div>
          </div>

          {/* Risk Events per Hour */}
          <div style={card('#dc2626')}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              <Tip text="High-risk events by hour. Spikes here correlate with suspicious pattern detection (bulk reads, audit modifications, etc.)">
                 Risk Events by Hour ⓘ
              </Tip>
            </h3>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={temporalData} margin={{ top: 5, right: 20, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                <XAxis dataKey="hour" tick={{ fill: '#94a3b8', fontSize: 9 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <RTooltip content={<ChartTooltip />} />
                <Bar dataKey="risk" fill="#dc2626" radius={[4, 4, 0, 0]} name="High-Risk Events" animationDuration={600}>
                  {temporalData.map((entry, i) => (
                    <Cell key={i} fill={entry.risk > 0 ? '#dc2626' : 'rgba(248,113,113,0.15)'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ═══ TAB: ACTORS — Actor Analysis ═══ */}
      {tab === 'actors' && stats.total > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          {/* Actor Radar */}
          {radarData.length > 0 && (
            <div style={{ ...card('#7c3aed'), gridColumn: '1 / -1' }}>
              <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
                <Tip text="Radar profile of top 5 actors: CRUD activity mix + risk events + anomaly score. Wider profiles = more diverse (and potentially suspicious) activity.">
                   Actor Behaviour Radar ⓘ
                </Tip>
              </h3>
              <ResponsiveContainer width="100%" height={320}>
                <RadarChart data={[
                  { metric: 'Creates', ...Object.fromEntries(radarData.map(r => [r.actor, r.Creates])) },
                  { metric: 'Reads', ...Object.fromEntries(radarData.map(r => [r.actor, r.Reads])) },
                  { metric: 'Updates', ...Object.fromEntries(radarData.map(r => [r.actor, r.Updates])) },
                  { metric: 'Deletes', ...Object.fromEntries(radarData.map(r => [r.actor, r.Deletes])) },
                  { metric: 'Risk Events', ...Object.fromEntries(radarData.map(r => [r.actor, r['Risk Events']])) },
                ]}>
                  <PolarGrid stroke="rgba(148,163,184,0.15)" />
                  <PolarAngleAxis dataKey="metric" tick={{ fill: '#1e293b', fontSize: 10 }} />
                  <PolarRadiusAxis tick={{ fill: '#94a3b8', fontSize: 9 }} />
                  {radarData.map((r, i) => (
                    <Radar key={r.actor} name={r.actor} dataKey={r.actor}
                      stroke={['#2563eb', '#dc2626', '#059669', '#d97706', '#0ea5e9'][i]}
                      fill={['#2563eb', '#dc2626', '#059669', '#d97706', '#0ea5e9'][i]}
                      fillOpacity={0.1} strokeWidth={2} animationDuration={800} />
                  ))}
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                  <RTooltip content={<ChartTooltip />} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Target Scatter Plot: count vs anomaly */}
          <div style={{ ...card('#059669'), gridColumn: '1 / -1' }}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              <Tip text="Each bubble = a data target (table/file/API). X = access count, Y = average anomaly score, size = risk events. Targets in the top-right are high-volume and highly anomalous — investigate first.">
                 Target Risk Bubble Chart ⓘ
              </Tip>
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                <XAxis type="number" dataKey="count" name="Access Count" tick={{ fill: '#94a3b8', fontSize: 10 }}
                  label={{ value: 'Access Count', position: 'bottom', fill: '#94a3b8', fontSize: 10, offset: -5 }} />
                <YAxis type="number" dataKey="avgAnomaly" name="Avg Anomaly" tick={{ fill: '#94a3b8', fontSize: 10 }}
                  label={{ value: 'Avg Anomaly', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 }} />
                <ZAxis type="number" dataKey="risk" range={[40, 400]} name="Risk Events" />
                <RTooltip content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#1e293b', marginBottom: 4 }}>{d.name}</div>
                      <div style={{ fontSize: 10, color: '#3b82f6' }}>Accesses: <strong>{d.count}</strong></div>
                      <div style={{ fontSize: 10, color: '#3b82f6' }}>Avg Anomaly: <strong>{d.avgAnomaly}</strong></div>
                      <div style={{ fontSize: 10, color: '#dc2626' }}>Risk Events: <strong>{d.risk}</strong></div>
                      <div style={{ fontSize: 10, color: SENS_COLORS[d.sens] }}>Sensitivity: <strong>{d.sens}</strong></div>
                    </div>
                  );
                }} />
                <Scatter data={targetScatter} animationDuration={800}>
                  {targetScatter.map((d, i) => (
                    <Cell key={i} fill={SENS_COLORS[d.sens] || '#2563eb'} fillOpacity={0.7} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 6 }}>
              {SENS_ORDER.map(s => (
                <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: SENS_COLORS[s] }} />
                  <span style={{ fontSize: 9, fontWeight: 600, color: SENS_COLORS[s] }}>{s}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ═══ TAB: MATRIX ═══ */}
      {tab === 'matrix' && (
        <div style={card('#0ea5e9')}>
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 14 }}>
            <Tip text="Aggregated view: each row is a unique user × object × CRUD type combination"> User × Object × Operation Matrix ⓘ</Tip>
          </h3>
          {summary.length > 0 ? (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead><tr>
                  <th>Actor</th><th>Target Object</th><th>Type</th><th>Events</th><th>Bytes</th><th>Sensitivity</th><th>Avg Anomaly</th><th>High-Risk</th><th>First Seen</th><th>Last Seen</th>
                </tr></thead>
                <tbody>
                  {summary.slice(0, 50).map(s => (
                    <tr key={s.summary_id} style={{ background: s.high_risk_count > 0 ? 'rgba(248,113,113,0.04)' : undefined }}>
                      <td style={{ fontWeight: 600, fontSize: 11 }}>{s.actor}</td>
                      <td style={{ ...mono, fontSize: 10, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.target_object}</td>
                      <td><CrudChip type={s.crud_type} /></td>
                      <td style={{ ...mono, fontWeight: 700 }}>{s.event_count}</td>
                      <td style={{ ...mono, fontSize: 10 }}>{(s.total_bytes / 1024).toFixed(1)} KB</td>
                      <td><SensChip level={s.max_sensitivity} /></td>
                      <td style={{ ...mono, fontSize: 10, color: s.avg_anomaly > 0.5 ? '#dc2626' : '#059669' }}>{s.avg_anomaly?.toFixed(3)}</td>
                      <td>{s.high_risk_count > 0 ? <span style={{ ...mono, color: '#dc2626', fontWeight: 700 }}>{s.high_risk_count}</span> : '-'}</td>
                      <td style={{ ...mono, fontSize: 9 }}>{s.first_seen?.slice(0, 19)}</td>
                      <td style={{ ...mono, fontSize: 9 }}>{s.last_seen?.slice(0, 19)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Run CRUD analysis to build the matrix</p>}
        </div>
      )}

      {/* ═══ TAB: EVENTS ═══ */}
      {tab === 'events' && (
        <div style={card('#2563eb')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
               Classified Events ({events.length})
            </h3>
            <div style={{ display: 'flex', gap: 6 }}>
              {['all', 'CREATE', 'READ', 'UPDATE', 'DELETE'].map(t => (
                <button key={t} onClick={() => setFilterCrud(t)} style={{
                  padding: '3px 8px', borderRadius: 6, fontSize: 9, fontWeight: 700, cursor: 'pointer',
                  background: filterCrud === t ? (t === 'all' ? 'rgba(255,255,255,0.1)' : `${CRUD_COLORS[t]}18`) : 'transparent',
                  border: `1px solid ${filterCrud === t ? (t === 'all' ? '#fff' : CRUD_COLORS[t]) : 'transparent'}`,
                  color: t === 'all' ? '#fff' : CRUD_COLORS[t],
                }}>{t === 'all' ? 'All' : `${CRUD_ICONS[t] ? `${CRUD_ICONS[t]} ` : ''}${t}`}</button>
              ))}
              <span style={{ opacity: 0.2 }}>|</span>
              {['all', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(s => (
                <button key={s} onClick={() => setFilterSens(s)} style={{
                  padding: '3px 8px', borderRadius: 999, fontSize: 9, fontWeight: 700, cursor: 'pointer',
                  background: filterSens === s ? `${SENS_COLORS[s] || '#fff'}15` : 'transparent',
                  border: `1px solid ${filterSens === s ? (SENS_COLORS[s] || '#fff') : 'transparent'}`,
                  color: SENS_COLORS[s] || '#fff',
                }}>{s}</button>
              ))}
            </div>
          </div>
          <div style={{ overflowX: 'auto', maxHeight: 500, overflowY: 'auto' }}>
            <table className="data-table">
              <thead><tr><th>Time</th><th>Actor</th><th>Type</th><th>Target</th><th>Sensitivity</th><th>Anomaly</th><th>Risk</th></tr></thead>
              <tbody>
                {events.slice(0, 100).map(ev => (
                  <tr key={ev.crud_event_id} style={{ background: ev.is_high_risk ? 'rgba(248,113,113,0.04)' : undefined }}>
                    <td style={{ ...mono, fontSize: 10 }}>{ev.normalised_ts?.slice(0, 19)}</td>
                    <td style={{ fontWeight: 600, fontSize: 11 }}>{ev.actor}</td>
                    <td><CrudChip type={ev.crud_type} /></td>
                    <td style={{ ...mono, fontSize: 10, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis' }}>{ev.target_object}</td>
                    <td><SensChip level={ev.sensitivity} /></td>
                    <td style={{ ...mono, fontSize: 10, color: ev.anomaly_score > 0.5 ? '#dc2626' : '#059669' }}>{ev.anomaly_score?.toFixed(3)}</td>
                    <td>{ev.is_high_risk ? <Tip text={ev.risk_reason}><span style={{ ...mono, color: '#dc2626', fontWeight: 700, fontSize: 10 }}>RISK</span></Tip> : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══ TAB: HIGH RISK ═══ */}
      {tab === 'high_risk' && (
        <div style={card('#dc2626')}>
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 14 }}>
            <Tip text="Events flagged by heuristic rules: off-hours bulk reads, audit trail modifications, high-anomaly writes, burst activity">High-Risk Events ⓘ</Tip>
          </h3>
          {events.filter(e => e.is_high_risk).length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {events.filter(e => e.is_high_risk).slice(0, 30).map(ev => (
                <div key={ev.crud_event_id} style={{ padding: '12px 16px', borderRadius: 10, border: '1px solid rgba(248,113,113,0.2)', background: 'rgba(248,113,113,0.04)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CrudChip type={ev.crud_type} />
                      <span style={{ fontWeight: 700, fontSize: 12 }}>{ev.actor}</span>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>→ {ev.target_object}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <SensChip level={ev.sensitivity} />
                      <span style={{ ...mono, fontSize: 10, color: '#dc2626' }}>score: {ev.anomaly_score?.toFixed(3)}</span>
                    </div>
                  </div>
                  <div style={{ padding: '6px 10px', borderRadius: 6, background: 'rgba(248,113,113,0.08)', fontSize: 11, color: '#fca5a5' }}>{ev.risk_reason}</div>
                  <div style={{ ...mono, fontSize: 9, color: 'var(--text-muted)', marginTop: 6 }}>{ev.normalised_ts?.slice(0, 19)} | Source: {ev.source_type}</div>
                </div>
              ))}
            </div>
          ) : <p style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', padding: 24 }}>No high-risk events detected.</p>}
        </div>
      )}

      {/* ═══ TAB: HISTORY ═══ */}
      {tab === 'history' && (
        <div style={card('#94a3b8')}>
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 14 }}>CRUD Analysis Runs</h3>
          {runs.length > 0 ? (
            <table className="data-table">
              <thead><tr><th>Run ID</th><th>Events</th><th>C</th><th>R</th><th>U</th><th>D</th><th>High-Risk</th><th>Status</th><th>Started</th></tr></thead>
              <tbody>
                {runs.map(run => {
                  const c = run.crud_counts || {};
                  return (
                    <tr key={run.run_id}>
                      <td style={{ ...mono, fontSize: 10 }}>{run.run_id?.slice(0, 8)}…</td>
                      <td style={{ ...mono, fontWeight: 700 }}>{run.total_events}</td>
                      <td style={{ ...mono, color: CRUD_COLORS.CREATE }}>{c.CREATE || 0}</td>
                      <td style={{ ...mono, color: CRUD_COLORS.READ }}>{c.READ || 0}</td>
                      <td style={{ ...mono, color: CRUD_COLORS.UPDATE }}>{c.UPDATE || 0}</td>
                      <td style={{ ...mono, color: CRUD_COLORS.DELETE }}>{c.DELETE || 0}</td>
                      <td>{run.high_risk_count > 0 ? <span style={{ ...mono, color: '#dc2626', fontWeight: 700 }}>{run.high_risk_count}</span> : '-'}</td>
                      <td><span style={{
                        padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700,
                        background: run.status === 'COMPLETED' ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)',
                        color: run.status === 'COMPLETED' ? '#059669' : '#dc2626',
                      }}>{run.status}</span></td>
                      <td style={{ ...mono, fontSize: 10 }}>{run.started_at ? new Date(run.started_at).toLocaleString() : ''}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>No runs yet</p>}
        </div>
      )}

      {/* Empty state */}
      {!loading && events.length === 0 && tab !== 'history' && (
        <div className="glass-card-static empty-state" style={{ padding: 48, marginTop: 16 }}>
          <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.4 }}>CR</div>
          <h3 style={{ fontSize: 20 }}>No CRUD Data</h3>
          <p>Click <strong>&quot;Run CRUD Analysis&quot;</strong> to classify data-access events, compute sensitivity, and detect suspicious patterns.</p>
        </div>
      )}
    </div>
  );
}


