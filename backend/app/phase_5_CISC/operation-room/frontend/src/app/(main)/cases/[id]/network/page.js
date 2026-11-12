'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@operation-room/lib/api';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid,
  ResponsiveContainer, Tooltip as RTooltip, Legend,
} from 'recharts';

/* ── Constants ────────────────────────────────────── */
const DIR_STYLE = {
  OUTBOUND: { color: '#dc2626', icon: 'OUT', bg: 'rgba(248,113,113,0.08)' },
  INBOUND:  { color: '#0ea5e9', icon: 'IN', bg: 'rgba(34,211,238,0.08)' },
  INTERNAL: { color: '#94a3b8', icon: 'INT', bg: 'rgba(148,163,184,0.08)' },
};
const PROTO_COLOR = { TCP: '#2563eb', UDP: '#d97706', HTTP: '#059669', HTTPS: '#0ea5e9', DNS: '#7c3aed', VPN: '#ea580c' };
const mono = { fontFamily: "'JetBrains Mono', monospace" };

/* ── Tip component ────────────────────────────────── */
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
        }}>{text}
          <div style={{ position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)',
            width: 0, height: 0, borderLeft: '6px solid transparent', borderRight: '6px solid transparent',
            borderTop: '6px solid rgba(37,99,235,0.12)' }} />
        </div>
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

function formatBytes(b) {
  if (!b) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let v = b;
  while (v >= 1024 && i < 3) { v /= 1024; i++; }
  return `${v.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

/* ═══════════════════════════════════════════════════════════ */
export default function NetworkPage() {
  const { id } = useParams();

  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [flows, setFlows] = useState([]);
  const [exfil, setExfil] = useState([]);
  const [destinations, setDestinations] = useState([]);
  const [runs, setRuns] = useState([]);
  const [tab, setTab] = useState('overview');
  const [dirFilter, setDirFilter] = useState('all');
  const [protoFilter, setProtoFilter] = useState('all');
  const [suspiciousOnly, setSuspiciousOnly] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [f, e, d, r] = await Promise.all([
        api.getNetworkFlows(id).catch(() => []),
        api.getExfilCandidates(id).catch(() => []),
        api.getDestinations(id).catch(() => []),
        api.getNetworkRuns(id).catch(() => []),
      ]);
      setFlows(f);
      setExfil(e);
      setDestinations(d);
      setRuns(r);
    } catch {} finally { setLoading(false); }
  }, [id]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleRun = async () => {
    setRunning(true);
    try {
      await api.runNetwork(id, {});
      await loadData();
    } catch (err) { alert('Network analysis failed: ' + err.message); }
    finally { setRunning(false); }
  };

  /* ── Computed data ── */
  const stats = useMemo(() => {
    const total = flows.length;
    const suspicious = flows.filter(f => f.is_suspicious).length;
    const outbound = flows.filter(f => f.direction === 'OUTBOUND').length;
    const totalOut = flows.reduce((s, f) => s + (f.direction === 'OUTBOUND' ? (f.bytes_sent || 0) : 0), 0);
    const knownBad = destinations.filter(d => d.is_known_bad).length;
    return { total, suspicious, outbound, totalOut, exfil: exfil.length, knownBad };
  }, [flows, exfil, destinations]);

  const filteredFlows = useMemo(() => {
    return flows.filter(f => {
      if (dirFilter !== 'all' && f.direction !== dirFilter) return false;
      if (protoFilter !== 'all' && f.protocol !== protoFilter) return false;
      if (suspiciousOnly && !f.is_suspicious) return false;
      return true;
    });
  }, [flows, dirFilter, protoFilter, suspiciousOnly]);

  // Protocol donut data
  const protoData = useMemo(() => {
    const counts = {};
    flows.forEach(f => { counts[f.protocol] = (counts[f.protocol] || 0) + 1; });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [flows]);

  // Volume timeline (hourly buckets)
  const volumeTimeline = useMemo(() => {
    const buckets = {};
    flows.forEach(f => {
      if (!f.normalised_ts) return;
      const h = f.normalised_ts.substr(0, 13); // YYYY-MM-DDTHH
      if (!buckets[h]) buckets[h] = { time: h, outbound: 0, inbound: 0, internal: 0, suspicious: 0 };
      const b = f.bytes_sent || 0;
      if (f.direction === 'OUTBOUND') buckets[h].outbound += b;
      else if (f.direction === 'INBOUND') buckets[h].inbound += b;
      else buckets[h].internal += b;
      if (f.is_suspicious) buckets[h].suspicious += b;
    });
    return Object.values(buckets).sort((a, b) => a.time.localeCompare(b.time));
  }, [flows]);

  // Direction donut
  const dirData = useMemo(() => {
    const counts = {};
    flows.forEach(f => { counts[f.direction] = (counts[f.direction] || 0) + 1; });
    return Object.entries(counts).map(([name, value]) => ({ name, value }));
  }, [flows]);

  // Destination scatter
  const dstScatter = useMemo(() => {
    return destinations.map(d => ({
      name: d.dst_ip,
      flows: d.total_flows,
      threat: d.max_threat_score || 0,
      bytes: d.total_bytes_out || 0,
      bad: d.is_known_bad,
      actors: d.unique_actors || 0,
    }));
  }, [destinations]);

  const TABS = [
    { id: 'overview',     icon: 'OV', label: 'Overview' },
    { id: 'flows',        icon: 'FL', label: 'Flows' },
    { id: 'destinations', icon: 'DS', label: 'Destinations' },
    { id: 'exfiltration', icon: 'EX', label: 'Exfiltration' },
    { id: 'threatintel',  icon: 'TI', label: 'Threat Intel' },
    { id: 'runs',         icon: 'RN', label: 'Runs' },
  ];

  return (
    <div style={{ maxWidth: 1500, margin: '0 auto' }}>
      {/* ── Header ─────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, paddingBottom: 16, borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.04em',
            color: '#1e293b' }}>
             Network & Exfiltration Analysis
          </h1>
          <div style={{ ...mono, fontSize: 11, marginTop: 4, color: 'var(--text-muted)' }}>
            <Tip text="6-node pipeline: ParseFlows → ExtractFeatures → DetectExfiltration → EnrichThreatIntel → CorrelateWithCRUD → StoreAndAudit">
              LangGraph 6-Node Pipeline
            </Tip>
            <span style={{ opacity: 0.3, margin: '0 8px' }}>·</span>
            <Tip text="Analyses FW, VPN, PROXY, DNS logs for suspicious outbound transfers">
              Network Flow Analysis
            </Tip>
            <span style={{ opacity: 0.3, margin: '0 8px' }}>·</span>
            <Tip text="Cross-references outbound flows with CRUD data reads to confirm exfiltration">
              CRUD Correlation
            </Tip>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Link href={`/cases/${id}/crud`} className="btn btn-ghost">CRUD</Link>
          <Link href={`/cases/${id}/correlation`} className="btn btn-ghost">Correlation</Link>
          <Link href={`/cases/${id}`} className="btn btn-ghost">← Case</Link>
          <button className="btn btn-primary" onClick={handleRun} disabled={running} style={{ padding: '10px 22px', fontSize: 13, fontWeight: 700 }}>
            {running ? 'Analyzing network...' : 'Run Network Analysis'}
          </button>
        </div>
      </div>

      {/* ── Tabs ─────────────────────────────── */}
      <div className="tl-view-tabs" style={{ marginBottom: 16 }}>
        {TABS.map(t => (
          <button key={t.id} className={`tl-view-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            <span className="tab-icon">{t.icon}</span>{t.label}
            {t.id === 'exfiltration' && exfil.length > 0 && (
              <span style={{ marginLeft: 6, padding: '1px 6px', borderRadius: 999, fontSize: 9, fontWeight: 800, background: 'rgba(248,113,113,0.2)', color: '#dc2626' }}>{exfil.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* ═══ TAB: OVERVIEW ═══ */}
      {tab === 'overview' && (
        <>
          {/* Stats */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 20 }}>
            {[
              { icon: 'FL', val: stats.total.toLocaleString(), lbl: 'Total Flows', c: '#2563eb', tip: 'Total network flow records parsed from FW/VPN/PROXY/DNS logs' },
              { icon: 'OUT', val: stats.outbound.toLocaleString(), lbl: 'Outbound', c: '#dc2626', tip: 'Flows where internal host sends to external IP' },
              { icon: 'SP', val: stats.suspicious, lbl: 'Suspicious', c: '#d97706', tip: 'Flows flagged by heuristic rules (large transfer, beaconing, off-hours, etc.)' },
              { icon: 'EX', val: stats.exfil, lbl: 'Exfil Candidates', c: '#dc2626', tip: 'Suspicious outbound flows correlated with prior CRUD data reads' },
              { icon: 'BO', val: formatBytes(stats.totalOut), lbl: 'Total Bytes Out', c: '#0ea5e9', tip: 'Total bytes sent outbound across all flows' },
              { icon: 'TI', val: stats.knownBad, lbl: 'Known-Bad IPs', c: '#ea580c', tip: 'Destination IPs matching known threat intelligence indicators' },
            ].map((c, i) => (
              <Tip key={i} text={c.tip}>
                <div style={card(c.c)}>
                  <div style={{ fontSize: 18 }}>{c.icon}</div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: c.c, ...mono }}>{c.val}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600 }}>{c.lbl}</div>
                </div>
              </Tip>
            ))}
          </div>

          {/* Volume Timeline + Protocol Donut */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14, marginBottom: 20 }}>
            <div style={card('#2563eb')}>
              {sectionHead('', 'Outbound Volume Timeline', 'Bytes transferred per hour, stacked by direction. Red spikes indicate potential exfiltration bursts.')}
              {volumeTimeline.length > 0 ? (
                <ResponsiveContainer width="100%" height={240}>
                  <AreaChart data={volumeTimeline} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                    <XAxis dataKey="time" tick={{ fill: '#94a3b8', fontSize: 9 }}
                      tickFormatter={v => { try { return v.split('T')[1] + ':00'; } catch { return v; } }} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickFormatter={v => formatBytes(v)} />
                    <RTooltip content={({ active, payload, label }) => {
                      if (!active || !payload?.length) return null;
                      return (
                        <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                          <div style={{ fontSize: 11, fontWeight: 700, color: '#1e293b', marginBottom: 4 }}>{label}</div>
                          {payload.map(p => (
                            <div key={p.name} style={{ fontSize: 10, color: p.color }}>
                              {p.name}: <strong>{formatBytes(p.value)}</strong>
                            </div>
                          ))}
                        </div>
                      );
                    }} />
                    <Area type="monotone" dataKey="outbound" stackId="1" stroke="#dc2626" fill="#dc2626" fillOpacity={0.3} name="Outbound" />
                    <Area type="monotone" dataKey="suspicious" stackId="2" stroke="#d97706" fill="#d97706" fillOpacity={0.4} name="Suspicious" />
                    <Area type="monotone" dataKey="inbound" stackId="1" stroke="#0ea5e9" fill="#0ea5e9" fillOpacity={0.15} name="Inbound" />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>Run analysis to see volume timeline</div>}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Protocol Donut */}
              <div style={card('#7c3aed')}>
                {sectionHead('', 'Protocol Mix', 'Proportion of network protocols. High DNS might indicate tunnelling.')}
                {protoData.length > 0 ? (
                  <>
                    <ResponsiveContainer width="100%" height={160}>
                      <PieChart>
                        <Pie data={protoData} cx="50%" cy="50%" innerRadius={35} outerRadius={60}
                          paddingAngle={3} dataKey="value" stroke="none" animationDuration={800}>
                          {protoData.map(d => <Cell key={d.name} fill={PROTO_COLOR[d.name] || '#666'} />)}
                        </Pie>
                        <RTooltip content={({ active, payload }) => {
                          if (!active || !payload?.length) return null;
                          const d = payload[0].payload;
                          return (
                            <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                              <div style={{ fontSize: 12, fontWeight: 700, color: PROTO_COLOR[d.name] || '#fff' }}>{d.name}</div>
                              <div style={{ fontSize: 10, color: '#3b82f6' }}>{d.value} flows</div>
                            </div>
                          );
                        }} />
                      </PieChart>
                    </ResponsiveContainer>
                    <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
                      {protoData.map(d => (
                        <span key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 9, color: PROTO_COLOR[d.name] || '#aaa' }}>
                          <span style={{ width: 6, height: 6, borderRadius: '50%', background: PROTO_COLOR[d.name] || '#666' }} />
                          {d.name}
                        </span>
                      ))}
                    </div>
                  </>
                ) : null}
              </div>

              {/* Direction Donut */}
              <div style={card('#0ea5e9')}>
                {sectionHead('', 'Flow Direction', 'Outbound vs Inbound vs Internal flow counts.')}
                {dirData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={120}>
                    <PieChart>
                      <Pie data={dirData} cx="50%" cy="50%" innerRadius={25} outerRadius={45}
                        paddingAngle={4} dataKey="value" stroke="none" animationDuration={600}>
                        {dirData.map(d => <Cell key={d.name} fill={DIR_STYLE[d.name]?.color || '#666'} />)}
                      </Pie>
                      <RTooltip content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const d = payload[0].payload;
                        return (
                          <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '8px 12px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                            <div style={{ fontSize: 11, fontWeight: 700, color: DIR_STYLE[d.name]?.color }}>{DIR_STYLE[d.name]?.icon} {d.name}: {d.value}</div>
                          </div>
                        );
                      }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : null}
              </div>
            </div>
          </div>
        </>
      )}

      {/* ═══ TAB: FLOWS ═══ */}
      {tab === 'flows' && (
        <div style={card('#2563eb')}>
          {/* Filters */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>DIRECTION:</span>
            {['all', 'OUTBOUND', 'INBOUND', 'INTERNAL'].map(d => (
              <button key={d} onClick={() => setDirFilter(d)} style={{
                padding: '3px 10px', borderRadius: 999, fontSize: 9, fontWeight: 700, cursor: 'pointer',
                background: dirFilter === d ? (DIR_STYLE[d]?.bg || 'rgba(255,255,255,0.1)') : 'transparent',
                border: `1px solid ${dirFilter === d ? (DIR_STYLE[d]?.color || '#fff') : 'transparent'}`,
                color: DIR_STYLE[d]?.color || '#fff',
              }}>{d === 'all' ? 'All' : `${DIR_STYLE[d]?.icon} ${d}`}</button>
            ))}
            <span style={{ opacity: 0.2 }}>|</span>
            <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>PROTOCOL:</span>
            {['all', 'TCP', 'UDP', 'HTTP', 'DNS', 'VPN'].map(p => (
              <button key={p} onClick={() => setProtoFilter(p)} style={{
                padding: '3px 8px', borderRadius: 999, fontSize: 9, fontWeight: 700, cursor: 'pointer',
                background: protoFilter === p ? `${PROTO_COLOR[p] || '#fff'}15` : 'transparent',
                border: `1px solid ${protoFilter === p ? (PROTO_COLOR[p] || '#fff') : 'transparent'}`,
                color: PROTO_COLOR[p] || '#fff',
              }}>{p}</button>
            ))}
            <span style={{ opacity: 0.2 }}>|</span>
            <label style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <input type="checkbox" checked={suspiciousOnly} onChange={e => setSuspiciousOnly(e.target.checked)}
                style={{ accentColor: '#dc2626' }} />
              Suspicious Only
            </label>
            <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>
              {filteredFlows.length} / {flows.length} flows
            </span>
          </div>

          {filteredFlows.length > 0 ? (
            <div style={{ maxHeight: 500, overflowY: 'auto' }}>
              <table className="data-table">
                <thead><tr>
                  <th>Time</th><th>Dir</th><th>Src IP</th><th>Port</th>
                  <th>Dst IP</th><th>Port</th><th>Proto</th>
                  <th>Sent</th><th>Recv</th><th>Actor</th><th>Flag</th>
                </tr></thead>
                <tbody>
                  {filteredFlows.slice(0, 200).map(f => (
                    <tr key={f.flow_id} style={{
                      background: f.is_suspicious ? 'rgba(248,113,113,0.04)' : undefined,
                      borderLeft: f.is_suspicious ? '3px solid #dc2626' : undefined,
                    }}>
                      <td style={{ ...mono, fontSize: 10 }}>{f.normalised_ts?.slice(11, 19)}</td>
                      <td><span style={{ color: DIR_STYLE[f.direction]?.color, fontSize: 10, fontWeight: 700 }}>{DIR_STYLE[f.direction]?.icon}</span></td>
                      <td style={{ ...mono, fontSize: 10, color: _is_internal_ip(f.src_ip) ? '#94a3b8' : '#dc2626' }}>{f.src_ip}</td>
                      <td style={{ ...mono, fontSize: 10 }}>{f.src_port || ''}</td>
                      <td style={{ ...mono, fontSize: 10, color: _is_internal_ip(f.dst_ip) ? '#94a3b8' : '#dc2626' }}>{f.dst_ip}</td>
                      <td style={{ ...mono, fontSize: 10 }}>{f.dst_port || ''}</td>
                      <td><span style={{ color: PROTO_COLOR[f.protocol] || '#aaa', fontSize: 10, fontWeight: 700 }}>{f.protocol}</span></td>
                      <td style={{ ...mono, fontSize: 10, color: f.bytes_sent > 100000 ? '#dc2626' : '#1e293b' }}>{formatBytes(f.bytes_sent)}</td>
                      <td style={{ ...mono, fontSize: 10 }}>{formatBytes(f.bytes_received)}</td>
                      <td style={{ fontSize: 10, fontWeight: 600, color: '#0ea5e9' }}>{f.actor}</td>
                      <td>
                        {f.is_suspicious && (
                          <Tip text={f.suspicion_reason}>
                            <span style={{ padding: '2px 6px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: 'rgba(248,113,113,0.15)', color: '#dc2626' }}>SUSP</span>
                          </Tip>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No flows match filters</p>}
        </div>
      )}

      {/* ═══ TAB: DESTINATIONS ═══ */}
      {tab === 'destinations' && (
        <>
          {/* Scatter */}
          {dstScatter.length > 0 && (
            <div style={{ ...card('#dc2626'), marginBottom: 14 }}>
              {sectionHead('', 'Destination Risk Scatter', 'Each dot = one external destination. X = flow count, Y = threat score, size = bytes transferred. Red = known-bad IP.')}
              <ResponsiveContainer width="100%" height={280}>
                <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                  <XAxis type="number" dataKey="flows" name="Flows" tick={{ fill: '#94a3b8', fontSize: 10 }}
                    label={{ value: 'Flow Count', position: 'bottom', fill: '#94a3b8', fontSize: 10, offset: -5 }} />
                  <YAxis type="number" dataKey="threat" name="Threat" domain={[0, 1]} tick={{ fill: '#94a3b8', fontSize: 10 }}
                    label={{ value: 'Threat Score', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 }} />
                  <ZAxis type="number" dataKey="bytes" range={[40, 400]} name="Bytes" />
                  <RTooltip content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload;
                    return (
                      <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: d.bad ? '#dc2626' : '#1e293b' }}>{d.bad ? 'BAD ' : ''}{d.name}</div>
                        <div style={{ fontSize: 10, color: '#3b82f6' }}>Flows: <strong>{d.flows}</strong></div>
                        <div style={{ fontSize: 10, color: '#3b82f6' }}>Threat: <strong>{d.threat.toFixed(2)}</strong></div>
                        <div style={{ fontSize: 10, color: '#3b82f6' }}>Bytes Out: <strong>{formatBytes(d.bytes)}</strong></div>
                        <div style={{ fontSize: 10, color: '#3b82f6' }}>Actors: <strong>{d.actors}</strong></div>
                      </div>
                    );
                  }} />
                  <Scatter data={dstScatter} animationDuration={600}>
                    {dstScatter.map((d, i) => (
                      <Cell key={i} fill={d.bad ? '#dc2626' : d.threat > 0.4 ? '#d97706' : '#059669'} fillOpacity={0.8} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
              <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 6 }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10 }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#dc2626' }} /> Known-Bad</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#d97706' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#d97706' }} /> Medium Threat</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 10, color: '#059669' }}><span style={{ width: 8, height: 8, borderRadius: '50%', background: '#059669' }} /> Low Threat</span>
              </div>
            </div>
          )}

          {/* Destination table */}
          <div style={card('#0ea5e9')}>
            {sectionHead('', 'Destination Summary', 'Aggregated view of all external destinations with threat-intel enrichment.')}
            {destinations.length > 0 ? (
              <table className="data-table">
                <thead><tr><th>IP</th><th>Flows</th><th>Bytes Out</th><th>Actors</th><th>Protocols</th><th>Threat</th><th>Country</th><th>ASN</th><th>Status</th></tr></thead>
                <tbody>
                  {destinations.map(d => {
                    const ti = d.threat_intel || {};
                    return (
                      <tr key={d.summary_id} style={{ background: d.is_known_bad ? 'rgba(248,113,113,0.04)' : undefined }}>
                        <td style={{ ...mono, fontSize: 11, fontWeight: 700, color: d.is_known_bad ? '#dc2626' : '#1e293b' }}>{d.dst_ip}</td>
                        <td style={{ ...mono }}>{d.total_flows}</td>
                        <td style={{ ...mono, color: d.total_bytes_out > 1000000 ? '#dc2626' : '#1e293b' }}>{formatBytes(d.total_bytes_out)}</td>
                        <td style={{ ...mono }}>{d.unique_actors}</td>
                        <td style={{ fontSize: 10 }}>{(d.protocols || []).map(p => (
                          <span key={p} style={{ padding: '1px 5px', borderRadius: 4, fontSize: 8, fontWeight: 700, background: `${PROTO_COLOR[p] || '#666'}20`, color: PROTO_COLOR[p] || '#aaa', marginRight: 3 }}>{p}</span>
                        ))}</td>
                        <td><span style={{ ...mono, fontSize: 11, fontWeight: 800, color: d.max_threat_score > 0.6 ? '#dc2626' : d.max_threat_score > 0.3 ? '#d97706' : '#059669' }}>{(d.max_threat_score || 0).toFixed(2)}</span></td>
                        <td style={{ fontSize: 11, fontWeight: 600 }}>{ti.country || '?'}</td>
                        <td style={{ ...mono, fontSize: 10, color: 'var(--text-muted)' }}>{ti.asn || '?'}</td>
                        <td>{d.is_known_bad ? <span style={{ padding: '2px 6px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: 'rgba(248,113,113,0.15)', color: '#dc2626' }}>BAD</span> : <span style={{ fontSize: 8, color: '#059669' }}>OK</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>Run analysis to see destinations</p>}
          </div>
        </>
      )}

      {/* ═══ TAB: EXFILTRATION ═══ */}
      {tab === 'exfiltration' && (
        <div style={card('#dc2626')}>
          {sectionHead('', 'Exfiltration Candidates', 'Flows correlated with prior CRUD reads — actor read data then sent it outbound. Higher confidence = stronger evidence.')}
          {exfil.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {exfil.map(e => (
                <div key={e.exfil_id} style={{
                  padding: '16px 20px', borderRadius: 12,
                  background: e.confidence > 0.5 ? 'rgba(248,113,113,0.06)' : 'rgba(0,0,0,0.015)',
                  border: `1px solid ${e.confidence > 0.5 ? 'rgba(248,113,113,0.2)' : 'var(--border-color)'}`,
                  borderLeft: `4px solid ${e.confidence > 0.7 ? '#dc2626' : e.confidence > 0.4 ? '#d97706' : '#059669'}`,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <Tip text={`Confidence: ${(e.confidence * 100).toFixed(1)}% — combination of volume match, time proximity, anomaly score, and threat intel`}>
                        <span style={{ ...mono, fontSize: 18, fontWeight: 800, color: e.confidence > 0.7 ? '#dc2626' : e.confidence > 0.4 ? '#d97706' : '#059669' }}>
                          {(e.confidence * 100).toFixed(0)}%
                        </span>
                      </Tip>
                      <span style={{ fontSize: 13, fontWeight: 700, color: '#0ea5e9' }}>{e.actor}</span>
                    </div>
                    <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)' }}>{e.normalised_ts?.slice(0, 19)}</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 8 }}>
                    {e.evidence_summary}
                  </div>
                  <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                     CRUD Read: <strong style={{ color: '#2563eb' }}>{formatBytes(e.bytes_crud)}</strong>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                     Network Out: <strong style={{ color: '#dc2626' }}>{formatBytes(e.bytes_network)}</strong>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                     Delta: <strong style={{ color: '#d97706' }}>{Math.round(e.time_delta_secs)}s</strong>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                     Target: <strong>{e.data_target}</strong>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                     Dst: <strong style={{ color: '#dc2626' }}>{e.dst_ip}</strong>
                    </div>
                  </div>
                  {/* Confidence bar */}
                  <div style={{ marginTop: 8, height: 4, background: 'rgba(255,255,255,0.04)', borderRadius: 999, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', width: `${Math.min(100, e.confidence * 100)}%`, borderRadius: 999, transition: 'width 0.5s',
                      background: e.confidence > 0.7 ? '#dc2626' : e.confidence > 0.4 ? '#d97706' : '#059669',
                    }} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>EX</div>
              <p>No exfiltration candidates found. Run network analysis to correlate with CRUD events.</p>
            </div>
          )}
        </div>
      )}

      {/* ═══ TAB: THREAT INTEL ═══ */}
      {tab === 'threatintel' && (
        <div style={card('#ea580c')}>
          {sectionHead('', 'Threat Intelligence', 'IP reputation, ASN, and geolocation enrichment for all external destinations. In production, integrates with AbuseIPDB, VirusTotal, MaxMind.')}
          {destinations.length > 0 ? (
            <table className="data-table">
              <thead><tr><th>IP</th><th>Threat Score</th><th>Country</th><th>ASN</th><th>Organisation</th><th>Known Bad</th><th>Flows</th><th>Bytes</th><th>Source</th></tr></thead>
              <tbody>
                {destinations.map(d => {
                  const ti = d.threat_intel || {};
                  return (
                    <tr key={d.summary_id} style={{ background: d.is_known_bad ? 'rgba(248,113,113,0.04)' : undefined }}>
                      <td style={{ ...mono, fontSize: 11, fontWeight: 700, color: d.is_known_bad ? '#dc2626' : '#1e293b' }}>{d.dst_ip}</td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ width: 60, height: 4, background: 'rgba(255,255,255,0.04)', borderRadius: 999, overflow: 'hidden' }}>
                            <div style={{ height: '100%', width: `${(d.max_threat_score || 0) * 100}%`, borderRadius: 999,
                              background: d.max_threat_score > 0.6 ? '#dc2626' : d.max_threat_score > 0.3 ? '#d97706' : '#059669' }} />
                          </div>
                          <span style={{ ...mono, fontSize: 11, fontWeight: 800, color: d.max_threat_score > 0.6 ? '#dc2626' : '#1e293b' }}>{(d.max_threat_score || 0).toFixed(2)}</span>
                        </div>
                      </td>
                      <td style={{ fontSize: 11, fontWeight: 600 }}>{ti.country || 'UNKNOWN'}</td>
                      <td style={{ ...mono, fontSize: 10 }}>{ti.asn || '?'}</td>
                      <td style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{ti.org || '?'}</td>
                      <td>{d.is_known_bad ? <span style={{ color: '#dc2626', fontWeight: 800 }}>YES</span> : <span style={{ color: '#059669' }}>NO</span>}</td>
                      <td style={{ ...mono }}>{d.total_flows}</td>
                      <td style={{ ...mono, fontSize: 10 }}>{formatBytes(d.total_bytes_out)}</td>
                      <td style={{ fontSize: 9, color: 'var(--text-muted)' }}>{ti.source || 'demo'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>Run analysis to see threat intel</p>}
        </div>
      )}

      {/* ═══ TAB: RUNS ═══ */}
      {tab === 'runs' && (
        <div style={card('#94a3b8')}>
          {sectionHead('', 'Analysis History', 'Past network analysis runs with result counts and hashes.')}
          {runs.length > 0 ? (
            <table className="data-table">
              <thead><tr><th>Run ID</th><th>Flows</th><th>Suspicious</th><th>Exfil</th><th>Bytes Out</th><th>Status</th><th>Started</th></tr></thead>
              <tbody>
                {runs.map(run => (
                  <tr key={run.run_id}>
                    <td style={{ ...mono, fontSize: 10 }}>{run.run_id?.slice(0, 8)}…</td>
                    <td style={{ ...mono }}>{run.total_flows}</td>
                    <td style={{ ...mono, color: '#d97706' }}>{run.suspicious_count}</td>
                    <td style={{ ...mono, color: '#dc2626', fontWeight: 700 }}>{run.exfil_candidates}</td>
                    <td style={{ ...mono, fontSize: 10 }}>{formatBytes(run.total_bytes_out)}</td>
                    <td><span style={{
                      padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700,
                      background: run.status === 'COMPLETED' ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)',
                      color: run.status === 'COMPLETED' ? '#059669' : '#dc2626',
                    }}>{run.status}</span></td>
                    <td style={{ ...mono, fontSize: 10 }}>{run.started_at ? new Date(run.started_at).toLocaleString() : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No runs yet</p>}
        </div>
      )}

      {/* Empty state */}
      {!loading && flows.length === 0 && tab === 'overview' && (
        <div className="glass-card-static empty-state" style={{ padding: 48, marginTop: 16 }}>
          <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.4 }}>NW</div>
          <h3 style={{ fontSize: 20 }}>No Network Data</h3>
          <p>Click <strong>"Run Network Analysis"</strong> to parse FW/VPN/PROXY/DNS logs and detect suspicious outbound transfers.</p>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
            Pipeline: Parse flows → Extract features → Detect exfiltration → Enrich threat intel → Correlate with CRUD → Store + CoC
          </p>
        </div>
      )}
    </div>
  );
}

/* Helper: check if IP looks internal (client-side) */
function _is_internal_ip(ip) {
  if (!ip) return true;
  return ip.startsWith('10.') || ip.startsWith('172.16.') || ip.startsWith('172.17.') ||
    ip.startsWith('172.18.') || ip.startsWith('192.168.') || ip.startsWith('127.');
}


