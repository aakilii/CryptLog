'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@operation-room/lib/api';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, ResponsiveContainer,
  Tooltip as RTooltip, Legend,
} from 'recharts';

/* ── Constants ────────────────────────────────────── */
const DIM_COLORS = {
  ACCOUNT: '#2563eb', SYSTEM: '#0ea5e9', DATA: '#dc2626', CONTROL: '#d97706',
};
const SEV_COLORS = { CRITICAL: '#dc2626', HIGH: '#ea580c', MEDIUM: '#d97706', LOW: '#059669' };
const mono = { fontFamily: "'JetBrains Mono', monospace" };

/* ── Tip ──────────────────────────────────────────── */
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

const sectionHead = (icon, title, tip) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
    <span style={{ fontSize: 18 }}>{icon}</span>
    <Tip text={tip}><h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', cursor: 'help' }}>{title} ⓘ</h3></Tip>
  </div>
);

/* ── Gauge ─────────────────────────────────────────── */
function DepthGauge({ label, value, max = 10, color, tip }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <Tip text={tip}>
      <div style={card(color)}>
        <div style={{ fontSize: 28, fontWeight: 800, color, ...mono }}>{value.toFixed(1)}<span style={{ fontSize: 14, color: 'var(--text-muted)' }}>/{max}</span></div>
        <div style={{ height: 6, background: 'rgba(255,255,255,0.04)', borderRadius: 999, overflow: 'hidden', margin: '8px 0 6px' }}>
          <div style={{ height: '100%', width: `${pct}%`, borderRadius: 999, background: `linear-gradient(90deg, ${color}40, ${color})`, transition: 'width 0.8s ease' }} />
        </div>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{label}</div>
      </div>
    </Tip>
  );
}

/* ── Metric card ───────────────────────────────────── */
function MetricRow({ name, value, max, evidence }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const label = name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  return (
    <div style={{ padding: '10px 14px', borderRadius: 10, background: 'rgba(0,0,0,0.015)', marginBottom: 6, border: '1px solid var(--border-color)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#1e293b' }}>{label}</span>
        <span style={{ ...mono, fontSize: 12, fontWeight: 800, color: pct > 60 ? '#dc2626' : pct > 30 ? '#d97706' : '#059669' }}>
          {typeof value === 'number' && value > 1000 ? value.toLocaleString() : value}
          <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400 }}> / {typeof max === 'number' && max > 1000 ? max.toLocaleString() : max}</span>
        </span>
      </div>
      <div style={{ height: 4, background: 'rgba(255,255,255,0.04)', borderRadius: 999, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, borderRadius: 999, background: pct > 60 ? '#dc2626' : pct > 30 ? '#d97706' : '#059669', transition: 'width 0.6s' }} />
      </div>
      {evidence && typeof evidence === 'object' && (
        <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 4, ...mono }}>
          {Array.isArray(evidence) ? evidence.slice(0, 8).join(', ') : JSON.stringify(evidence).slice(0, 120)}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════ */
export default function DepthPage() {
  const { id } = useParams();

  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [generatingNarrative, setGeneratingNarrative] = useState(false);
  const [results, setResults] = useState(null);
  const [details, setDetails] = useState([]);
  const [narrative, setNarrative] = useState(null);
  const [runs, setRuns] = useState([]);
  const [tab, setTab] = useState('overview');

  // Weight sliders
  const [weights, setWeights] = useState({ account: 0.25, system: 0.25, data: 0.30, control: 0.20 });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [r, d, n, ru] = await Promise.all([
        api.getDepthResults(id).catch(() => null),
        api.getDepthDetails(id).catch(() => []),
        api.getDepthNarrative(id).catch(() => null),
        api.getDepthRuns(id).catch(() => []),
      ]);
      setResults(r?.error ? null : r);
      setDetails(Array.isArray(d) ? d : []);
      setNarrative(n?.error ? null : n);
      setRuns(ru);
    } catch {} finally { setLoading(false); }
  }, [id]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRun = async () => {
    setRunning(true);
    try {
      await api.runDepth(id, { weights });
      await loadData();
    } catch (err) { alert('Depth analysis failed: ' + err.message); }
    finally { setRunning(false); }
  };

  const handleNarrative = async () => {
    setGeneratingNarrative(true);
    try {
      const n = await api.genDepthNarrative(id, { llm_provider: 'ollama' });
      setNarrative(n);
    } catch (err) { alert('Narrative failed: ' + err.message); }
    finally { setGeneratingNarrative(false); }
  };

  /* ── Computed ── */
  const radarData = useMemo(() => {
    if (!results) return [];
    return [
      { dim: 'Account', value: results.account_depth || 0, fullMark: 10 },
      { dim: 'System', value: results.system_depth || 0, fullMark: 10 },
      { dim: 'Data', value: results.data_depth || 0, fullMark: 10 },
      { dim: 'Control', value: results.control_depth || 0, fullMark: 10 },
    ];
  }, [results]);

  const dimDetails = (dim) => details.filter(d => d.dimension === dim);

  const liveScore = useMemo(() => {
    if (!results) return 0;
    return (
      (weights.account * (results.account_depth || 0)) +
      (weights.system * (results.system_depth || 0)) +
      (weights.data * (results.data_depth || 0)) +
      (weights.control * (results.control_depth || 0))
    ).toFixed(2);
  }, [results, weights]);

  const barData = useMemo(() => {
    if (!results) return [];
    return [
      { dim: 'Account', depth: results.account_depth || 0, fill: DIM_COLORS.ACCOUNT },
      { dim: 'System', depth: results.system_depth || 0, fill: DIM_COLORS.SYSTEM },
      { dim: 'Data', depth: results.data_depth || 0, fill: DIM_COLORS.DATA },
      { dim: 'Control', depth: results.control_depth || 0, fill: DIM_COLORS.CONTROL },
    ];
  }, [results]);

  const TABS = [
    { id: 'overview',  icon: 'OV', label: 'Overview' },
    { id: 'account',   icon: 'AC', label: 'Account' },
    { id: 'system',    icon: 'SY', label: 'System' },
    { id: 'data',      icon: 'DT', label: 'Data' },
    { id: 'control',   icon: 'CT', label: 'Control' },
    { id: 'weights',   icon: 'WG', label: 'Weights' },
    { id: 'narrative', icon: 'AI', label: 'Narrative' },
    { id: 'runs',      icon: 'RN', label: 'Runs' },
  ];

  return (
    <div style={{ maxWidth: 1500, margin: '0 auto' }}>
      {/* ── Header ─────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, paddingBottom: 16, borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.04em',
            color: '#1e293b' }}>
             Depth &amp; Impact Assessment
          </h1>
          <div style={{ ...mono, fontSize: 11, marginTop: 4, color: 'var(--text-muted)' }}>
            <Tip text="7-node pipeline: LoadAllData → AccountDepth → SystemDepth → DataDepth → ControlDepth → ScoreImpact → StoreAndAudit">
              LangGraph 7-Node Pipeline
            </Tip>
            <span style={{ opacity: 0.3, margin: '0 8px' }}>·</span>
            <Tip text="Integrates all 6 modules: Timeline, Anomaly, Correlation, CRUD, Network, Exfiltration">
              All-Module Integration
            </Tip>
            <span style={{ opacity: 0.3, margin: '0 8px' }}>·</span>
            <Tip text="Configurable weights for each dimension. Adjust and recompute severity in real time.">
              Interactive Scoring
            </Tip>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Link href={`/cases/${id}/network`} className="btn btn-ghost">Network</Link>
          <Link href={`/cases/${id}/correlation`} className="btn btn-ghost">Correlation</Link>
          <Link href={`/cases/${id}`} className="btn btn-ghost">← Case</Link>
          <button className="btn btn-primary" onClick={handleRun} disabled={running} style={{ padding: '10px 22px', fontSize: 13, fontWeight: 700 }}>
            {running ? 'Computing depth...' : 'Run Depth Analysis'}
          </button>
        </div>
      </div>

      {/* ── Tabs ──────────────────────── */}
      <div className="tl-view-tabs" style={{ marginBottom: 16 }}>
        {TABS.map(t => (
          <button key={t.id} className={`tl-view-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            <span className="tab-icon">{t.icon}</span>{t.label}
          </button>
        ))}
      </div>

      {/* ═══ OVERVIEW ═══ */}
      {tab === 'overview' && results && (
        <>
          {/* Severity banner */}
          <div style={{
            ...card(SEV_COLORS[results.severity_label] || '#94a3b8'), marginBottom: 16,
            background: `linear-gradient(135deg, ${SEV_COLORS[results.severity_label]}08, transparent)`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>Overall Severity</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
                  <span style={{ fontSize: 44, fontWeight: 800, color: SEV_COLORS[results.severity_label], ...mono }}>{results.overall_severity?.toFixed(1)}</span>
                  <span style={{ fontSize: 16, fontWeight: 300, color: 'var(--text-muted)' }}>/10</span>
                  <span style={{
                    padding: '4px 14px', borderRadius: 999, fontSize: 12, fontWeight: 800, letterSpacing: 1,
                    background: `${SEV_COLORS[results.severity_label]}20`,
                    color: SEV_COLORS[results.severity_label],
                  }}>{results.severity_label}</span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 16 }}>
                {results.business_impact && Object.entries(results.business_impact).filter(([k]) => !k.includes('_')).map(([k, v]) => (
                  <Tip key={k} text={`${k} impact assessment based on depth scores and data sensitivity`}>
                    <div style={{ textAlign: 'center', padding: '6px 12px', borderRadius: 8, background: 'rgba(0,0,0,0.015)' }}>
                      <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{k}</div>
                      <div style={{ fontSize: 14, fontWeight: 800, color: SEV_COLORS[v] || '#94a3b8' }}>{v}</div>
                    </div>
                  </Tip>
                ))}
              </div>
            </div>
          </div>

          {/* 4 Gauges */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
            <DepthGauge label="Account Depth" value={results.account_depth || 0} color={DIM_COLORS.ACCOUNT} tip="How many accounts were compromised, privilege levels used, MFA bypassed" />
            <DepthGauge label="System Depth" value={results.system_depth || 0} color={DIM_COLORS.SYSTEM} tip="How many infrastructure tiers, hosts, subnets were penetrated" />
            <DepthGauge label="Data Depth" value={results.data_depth || 0} color={DIM_COLORS.DATA} tip="Volume and sensitivity of data accessed, modified, or exfiltrated" />
            <DepthGauge label="Control Depth" value={results.control_depth || 0} color={DIM_COLORS.CONTROL} tip="Security control weaknesses exploited: missing MFA, weak passwords, etc." />
          </div>

          {/* Radar + Bar */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div style={card('#2563eb')}>
              {sectionHead('', 'Depth Profile Radar', 'Shape indicates penetration profile. Larger area = deeper overall penetration. Spikes reveal the most compromised dimension.')}
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                  <PolarGrid stroke="rgba(148,163,184,0.1)" />
                  <PolarAngleAxis dataKey="dim" tick={{ fill: '#1e293b', fontSize: 12, fontWeight: 600 }} />
                  <PolarRadiusAxis angle={90} domain={[0, 10]} tick={{ fill: '#94a3b8', fontSize: 9 }} />
                  <Radar dataKey="value" stroke="#2563eb" fill="#2563eb" fillOpacity={0.25} strokeWidth={2} dot={{ fill: '#2563eb', r: 4 }} animationDuration={600} />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            <div style={card('#0ea5e9')}>
              {sectionHead('', 'Dimension Comparison', 'Side-by-side comparison of all 4 depth dimensions on a 0–10 scale.')}
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={barData} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                  <XAxis dataKey="dim" tick={{ fill: '#1e293b', fontSize: 12, fontWeight: 600 }} />
                  <YAxis domain={[0, 10]} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                  <RTooltip content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload;
                    return (
                      <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: d.fill }}>{d.dim}: {d.depth.toFixed(1)}/10</div>
                      </div>
                    );
                  }} />
                  <Bar dataKey="depth" radius={[6, 6, 0, 0]} animationDuration={800}>
                    {barData.map((d, i) => <Cell key={i} fill={d.fill} fillOpacity={0.8} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}

      {/* ═══ ACCOUNT ═══ */}
      {tab === 'account' && (
        <div style={card(DIM_COLORS.ACCOUNT)}>
          {sectionHead('', 'Account Depth Breakdown', 'Measures how many accounts were compromised, privilege levels used, MFA bypassed, and credential compromise indicators.')}
          {results && <div style={{ fontSize: 22, fontWeight: 800, color: DIM_COLORS.ACCOUNT, ...mono, marginBottom: 14 }}>{results.account_depth?.toFixed(1)}/10</div>}
          {dimDetails('ACCOUNT').map(d => <MetricRow key={d.detail_id} name={d.metric_name} value={d.metric_value} max={d.max_value} evidence={d.evidence} />)}
          {dimDetails('ACCOUNT').length === 0 && <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>Run depth analysis to see account metrics</p>}
        </div>
      )}

      {/* ═══ SYSTEM ═══ */}
      {tab === 'system' && (
        <div style={card(DIM_COLORS.SYSTEM)}>
          {sectionHead('', 'System Depth Breakdown', 'Measures infrastructure tiers breached, subnets traversed, hosts accessed, lateral movement, and dwell time.')}
          {results && <div style={{ fontSize: 22, fontWeight: 800, color: DIM_COLORS.SYSTEM, ...mono, marginBottom: 14 }}>{results.system_depth?.toFixed(1)}/10</div>}
          {dimDetails('SYSTEM').length > 0 && (
            <>
              {/* Tier heat map */}
              {(() => {
                const tierD = dimDetails('SYSTEM').find(d => d.metric_name === 'infrastructure_tiers');
                const tiersReached = tierD?.evidence || [];
                const ALL = ['web', 'application', 'database', 'storage', 'identity', 'network', 'endpoint', 'monitoring'];
                return (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>Infrastructure Tiers Heat Map</div>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {ALL.map(t => {
                        const reached = Array.isArray(tiersReached) && tiersReached.includes(t);
                        return (
                          <div key={t} style={{
                            padding: '6px 14px', borderRadius: 8, fontSize: 11, fontWeight: 700, textTransform: 'uppercase',
                            background: reached ? 'rgba(248,113,113,0.15)' : 'rgba(37,99,235,0.03)',
                            color: reached ? '#dc2626' : '#64748b',
                            border: `1px solid ${reached ? 'rgba(248,113,113,0.3)' : 'var(--border-color)'}`,
                          }}>{reached ? ' ' : ' '}{t}</div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
              {dimDetails('SYSTEM').map(d => <MetricRow key={d.detail_id} name={d.metric_name} value={d.metric_value} max={d.max_value} evidence={d.evidence} />)}
            </>
          )}
          {dimDetails('SYSTEM').length === 0 && <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>Run depth analysis to see system metrics</p>}
        </div>
      )}

      {/* ═══ DATA ═══ */}
      {tab === 'data' && (
        <div style={card(DIM_COLORS.DATA)}>
          {sectionHead('', 'Data Depth Breakdown', 'Measures sensitive data accessed, volume read/modified/deleted, high-risk CRUD events, and confirmed exfiltration.')}
          {results && <div style={{ fontSize: 22, fontWeight: 800, color: DIM_COLORS.DATA, ...mono, marginBottom: 14 }}>{results.data_depth?.toFixed(1)}/10</div>}
          {dimDetails('DATA').length > 0 && (
            <>
              {/* Sensitivity donut */}
              {(() => {
                const sensDist = dimDetails('DATA').find(d => d.metric_name === 'sensitivity_distribution');
                const dist = sensDist?.evidence;
                if (!dist || typeof dist !== 'object' || Array.isArray(dist)) return null;
                const senData = Object.entries(dist).map(([name, value]) => ({ name, value }));
                const sensColor = { CRITICAL: '#dc2626', HIGH: '#ea580c', MEDIUM: '#d97706', LOW: '#059669' };
                return (
                  <div style={{ marginBottom: 14 }}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>Data Sensitivity Distribution</div>
                    <ResponsiveContainer width="100%" height={140}>
                      <PieChart>
                        <Pie data={senData} cx="50%" cy="50%" innerRadius={30} outerRadius={55} paddingAngle={3} dataKey="value" stroke="none" animationDuration={600}>
                          {senData.map(d => <Cell key={d.name} fill={sensColor[d.name] || '#666'} />)}
                        </Pie>
                        <RTooltip content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const d = payload[0].payload;
                          return (
                            <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '8px 12px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                              <div style={{ fontSize: 11, fontWeight: 700, color: sensColor[d.name] }}>{d.name}: {d.value}</div>
                            </div>
                          );
                        }} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
                      {senData.map(d => (
                        <span key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 9, color: sensColor[d.name] }}>
                          <span style={{ width: 6, height: 6, borderRadius: '50%', background: sensColor[d.name] }} />{d.name}: {d.value}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })()}
              {dimDetails('DATA').map(d => <MetricRow key={d.detail_id} name={d.metric_name} value={d.metric_value} max={d.max_value} evidence={d.evidence} />)}
            </>
          )}
          {dimDetails('DATA').length === 0 && <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>Run depth analysis to see data metrics</p>}
        </div>
      )}

      {/* ═══ CONTROL ═══ */}
      {tab === 'control' && (
        <div style={card(DIM_COLORS.CONTROL)}>
          {sectionHead('', 'Control Depth Breakdown', 'Measures security control gaps: missing MFA, weak credentials, unblocked anomalies, suspicious outbound traffic, off-hours admin access.')}
          {results && <div style={{ fontSize: 22, fontWeight: 800, color: DIM_COLORS.CONTROL, ...mono, marginBottom: 14 }}>{results.control_depth?.toFixed(1)}/10</div>}
          {dimDetails('CONTROL').length > 0 && (
            <>
              {/* Control gap checklist */}
              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>Control Gap Assessment</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
                  {dimDetails('CONTROL').map(d => {
                    const pct = d.max_value > 0 ? d.metric_value / d.max_value : 0;
                    const isGap = pct > 0.3;
                    return (
                      <div key={d.detail_id} style={{
                        padding: '8px 12px', borderRadius: 8, display: 'flex', alignItems: 'center', gap: 8,
                        background: isGap ? 'rgba(248,113,113,0.06)' : 'rgba(52,211,153,0.06)',
                        border: `1px solid ${isGap ? 'rgba(248,113,113,0.2)' : 'rgba(52,211,153,0.2)'}`,
                      }}>
                        <span style={{ fontSize: 10, fontWeight: 800, color: isGap ? '#dc2626' : '#059669', ...mono }}>{isGap ? 'GAP' : 'OK'}</span>
                        <div>
                          <div style={{ fontSize: 11, fontWeight: 600, color: isGap ? '#dc2626' : '#059669' }}>
                            {d.metric_name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                          </div>
                          <div style={{ ...mono, fontSize: 10, color: 'var(--text-muted)' }}>{d.metric_value} / {d.max_value}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
          {dimDetails('CONTROL').length === 0 && <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>Run depth analysis to see control metrics</p>}
        </div>
      )}

      {/* ═══ WEIGHTS ═══ */}
      {tab === 'weights' && (
        <div style={card('#7c3aed')}>
          {sectionHead('', 'Weight Configuration', 'Adjust the relative importance of each dimension. Severity score recalculates live as you drag the sliders.')}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
            <div>
              {[
                { key: 'account', label: 'Account Depth', color: DIM_COLORS.ACCOUNT, icon: 'AC' },
                { key: 'system',  label: 'System Depth',  color: DIM_COLORS.SYSTEM,  icon: 'SY' },
                { key: 'data',    label: 'Data Depth',    color: DIM_COLORS.DATA,    icon: 'DT' },
                { key: 'control', label: 'Control Depth', color: DIM_COLORS.CONTROL, icon: 'CT' },
              ].map(w => (
                <div key={w.key} style={{ marginBottom: 20, padding: '12px 16px', borderRadius: 10, background: 'rgba(0,0,0,0.015)', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: w.color }}>{w.icon ? `${w.icon} ` : ''}{w.label}</span>
                    <span style={{ ...mono, fontSize: 14, fontWeight: 800, color: w.color }}>{(weights[w.key] * 100).toFixed(0)}%</span>
                  </div>
                  <input type="range" min="0" max="100" step="5"
                    value={weights[w.key] * 100}
                    onChange={e => {
                      const v = parseInt(e.target.value) / 100;
                      setWeights(prev => ({ ...prev, [w.key]: v }));
                    }}
                    style={{ width: '100%', accentColor: w.color }}
                  />
                </div>
              ))}
              <div style={{ padding: '12px 16px', borderRadius: 10, background: 'rgba(37,99,235,0.03)', border: '1px solid var(--border-color)', textAlign: 'center' }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>TOTAL WEIGHT</div>
                <div style={{ ...mono, fontSize: 18, fontWeight: 800, color: Math.abs(Object.values(weights).reduce((s, v) => s + v, 0) - 1) < 0.01 ? '#059669' : '#dc2626' }}>
                  {(Object.values(weights).reduce((s, v) => s + v, 0) * 100).toFixed(0)}%
                </div>
              </div>
              <button className="btn btn-primary" onClick={handleRun} disabled={running} style={{ width: '100%', marginTop: 12, padding: '12px', fontSize: 13, fontWeight: 700 }}>
                {running ? 'Recomputing...' : 'Save & Recompute'}
              </button>
            </div>

            {/* Live preview */}
            <div style={{ padding: '20px 24px', borderRadius: 14, background: 'rgba(0,0,0,0.015)', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>Live Severity Preview</div>
              <div style={{ fontSize: 48, fontWeight: 800, textAlign: 'center', ...mono,
                color: liveScore >= 7 ? '#dc2626' : liveScore >= 5 ? '#ea580c' : liveScore >= 3 ? '#d97706' : '#059669',
              }}>{liveScore}</div>
              <div style={{ textAlign: 'center', fontSize: 14, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 16 }}>/10</div>
              {results && (
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                  <div>Account: <strong style={{ color: DIM_COLORS.ACCOUNT }}>{results.account_depth?.toFixed(1)}</strong> x {(weights.account * 100).toFixed(0)}% = <strong>{(results.account_depth * weights.account).toFixed(2)}</strong></div>
                  <div>System: <strong style={{ color: DIM_COLORS.SYSTEM }}>{results.system_depth?.toFixed(1)}</strong> x {(weights.system * 100).toFixed(0)}% = <strong>{(results.system_depth * weights.system).toFixed(2)}</strong></div>
                  <div>Data: <strong style={{ color: DIM_COLORS.DATA }}>{results.data_depth?.toFixed(1)}</strong> x {(weights.data * 100).toFixed(0)}% = <strong>{(results.data_depth * weights.data).toFixed(2)}</strong></div>
                  <div>Control: <strong style={{ color: DIM_COLORS.CONTROL }}>{results.control_depth?.toFixed(1)}</strong> x {(weights.control * 100).toFixed(0)}% = <strong>{(results.control_depth * weights.control).toFixed(2)}</strong></div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══ NARRATIVE ═══ */}
      {tab === 'narrative' && (
        <div style={card('#ea580c')}>
          {sectionHead('', 'AI Impact Narrative', 'LLM-generated plain-language summary of depth findings, business impact, and prioritised remediation actions.')}
          {!narrative && (
            <div style={{ textAlign: 'center', padding: 32 }}>
              <button className="btn btn-primary" onClick={handleNarrative} disabled={generatingNarrative} style={{ padding: '12px 28px', fontSize: 14, fontWeight: 700 }}>
                {generatingNarrative ? 'Generating narrative...' : 'Generate Impact Narrative'}
              </button>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8 }}>Uses Ollama/Gemini to summarise depth findings</p>
            </div>
          )}
          {narrative && (
            <div>
              {narrative.executive_summary && (
                <div style={{ padding: '14px 18px', borderRadius: 10, background: 'rgba(251,146,60,0.06)', border: '1px solid rgba(251,146,60,0.2)', marginBottom: 16 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: '#ea580c', textTransform: 'uppercase', marginBottom: 4 }}>Executive Summary</div>
                  <div style={{ fontSize: 13, color: '#1e293b', lineHeight: 1.6 }}>{narrative.executive_summary}</div>
                </div>
              )}
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
                {narrative.narrative}
              </div>
              {narrative.remediation && narrative.remediation.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>Remediation Priorities</div>
                  {narrative.remediation.map((r, i) => (
                    <div key={i} style={{
                      padding: '8px 14px', borderRadius: 8, marginBottom: 4,
                      background: r.priority === 'CRITICAL' ? 'rgba(248,113,113,0.06)' : r.priority === 'HIGH' ? 'rgba(251,146,60,0.06)' : 'rgba(0,0,0,0.015)',
                      borderLeft: `3px solid ${r.priority === 'CRITICAL' ? '#dc2626' : r.priority === 'HIGH' ? '#ea580c' : '#d97706'}`,
                      display: 'flex', alignItems: 'center', gap: 10,
                    }}>
                      <span style={{ padding: '1px 6px', borderRadius: 4, fontSize: 8, fontWeight: 800,
                        background: `${r.priority === 'CRITICAL' ? '#dc2626' : r.priority === 'HIGH' ? '#ea580c' : '#d97706'}20`,
                        color: r.priority === 'CRITICAL' ? '#dc2626' : r.priority === 'HIGH' ? '#ea580c' : '#d97706',
                      }}>{r.priority}</span>
                      <span style={{ fontSize: 12, color: '#1e293b' }}>{r.action}</span>
                    </div>
                  ))}
                </div>
              )}
              <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
                <button className="btn btn-ghost" onClick={handleNarrative} disabled={generatingNarrative}>
                  {generatingNarrative ? 'Generating...' : 'Regenerate'}
                </button>
                <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', alignSelf: 'center' }}>
                  Provider: {narrative.llm_provider}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══ RUNS ═══ */}
      {tab === 'runs' && (
        <div style={card('#94a3b8')}>
          {sectionHead('', 'Analysis History', 'Past depth analysis runs with dimension scores.')}
          {runs.length > 0 ? (
            <table className="data-table">
              <thead><tr><th>Run ID</th><th>Acct</th><th>System</th><th>Data</th><th>Control</th><th>Overall</th><th>Label</th><th>Status</th><th>Started</th></tr></thead>
              <tbody>
                {runs.map(r => (
                  <tr key={r.run_id}>
                    <td style={{ ...mono, fontSize: 10 }}>{r.run_id?.slice(0, 8)}…</td>
                    <td style={{ ...mono, color: DIM_COLORS.ACCOUNT }}>{r.account_depth?.toFixed(1)}</td>
                    <td style={{ ...mono, color: DIM_COLORS.SYSTEM }}>{r.system_depth?.toFixed(1)}</td>
                    <td style={{ ...mono, color: DIM_COLORS.DATA }}>{r.data_depth?.toFixed(1)}</td>
                    <td style={{ ...mono, color: DIM_COLORS.CONTROL }}>{r.control_depth?.toFixed(1)}</td>
                    <td style={{ ...mono, fontSize: 14, fontWeight: 800, color: SEV_COLORS[r.severity_label] }}>{r.overall_severity?.toFixed(1)}</td>
                    <td><span style={{
                      padding: '2px 8px', borderRadius: 999, fontSize: 9, fontWeight: 700,
                      background: `${SEV_COLORS[r.severity_label] || '#94a3b8'}20`,
                      color: SEV_COLORS[r.severity_label] || '#94a3b8',
                    }}>{r.severity_label}</span></td>
                    <td><span style={{
                      padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700,
                      background: r.status === 'COMPLETED' ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)',
                      color: r.status === 'COMPLETED' ? '#059669' : '#dc2626',
                    }}>{r.status}</span></td>
                    <td style={{ ...mono, fontSize: 10 }}>{r.started_at ? new Date(r.started_at).toLocaleString() : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No runs yet</p>}
        </div>
      )}

      {/* Empty state */}
      {!loading && !results && tab === 'overview' && (
        <div className="glass-card-static empty-state" style={{ padding: 48, marginTop: 16 }}>
          <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.4 }}>DP</div>
          <h3 style={{ fontSize: 20 }}>No Depth Assessment Data</h3>
          <p>Click <strong>"Run Depth Analysis"</strong> to compute how deeply the attacker penetrated across 4 dimensions.</p>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
            Pipeline: Load all → Account depth → System depth → Data depth → Control depth → Score impact → Store + CoC
          </p>
        </div>
      )}
    </div>
  );
}


