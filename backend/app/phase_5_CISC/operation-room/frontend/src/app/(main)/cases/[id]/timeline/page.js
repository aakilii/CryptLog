'use client';

import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@operation-room/lib/api';
import { useFilterState } from '@operation-room/context/FilterStateProvider';
import { AdvancedFilterBuilder } from '@operation-room/components/common/AdvancedFilterBuilder';
import dynamic from 'next/dynamic';

/* ── Lazy-load chart wrapper (single bundle, SSR-safe) ──── */
const Charts = dynamic(() => import('@operation-room/components/TimelineCharts').then(m => ({
  default: () => null, // not used as default
  ActivityChart: m.ActivityChart,
  HourlyChart: m.HourlyChart,
  SourcePie: m.SourcePie,
  ActorBar: m.ActorBar,
  SeverityPie: m.SeverityPie,
  ThreatRadar: m.ThreatRadar,
})), { ssr: false });

// Import individually for proper rendering
const ActivityChart = dynamic(() => import('@operation-room/components/TimelineCharts').then(m => m.ActivityChart), { ssr: false });
const HourlyChart   = dynamic(() => import('@operation-room/components/TimelineCharts').then(m => m.HourlyChart),  { ssr: false });
const SourcePie     = dynamic(() => import('@operation-room/components/TimelineCharts').then(m => m.SourcePie),    { ssr: false });
const ActorBar      = dynamic(() => import('@operation-room/components/TimelineCharts').then(m => m.ActorBar),     { ssr: false });
const SeverityPie   = dynamic(() => import('@operation-room/components/TimelineCharts').then(m => m.SeverityPie),  { ssr: false });
const ThreatRadar   = dynamic(() => import('@operation-room/components/TimelineCharts').then(m => m.ThreatRadar),  { ssr: false });

/* ═══════════════════════════════════════════════════════════════
   Constants
   ═══════════════════════════════════════════════════════════════ */
const VIEWS = [
  { id: 'command',  icon: 'CC', label: 'Command Center' },
  { id: 'table',    icon: 'DT', label: 'Data Table' },
  { id: 'timeline', icon: 'TL', label: 'Timeline Flow' },
  { id: 'graphs',   icon: 'AN', label: 'Analytics' },
  { id: 'heatmap',  icon: 'HM', label: 'Heatmap' },
  { id: 'lanes',    icon: 'SL', label: 'Swim Lanes' },
];

const SRC = {
  AUTH: { color: '#2563eb', bg: 'rgba(37,99,235,0.06)', icon: 'AU' },
  VPN:  { color: '#0ea5e9', bg: 'rgba(34,211,238,0.12)',  icon: 'VN' },
  FW:   { color: '#fb7185', bg: 'rgba(251,113,133,0.12)', icon: 'FW' },
  DB:   { color: '#d97706', bg: 'rgba(251,191,36,0.12)',  icon: 'DB' },
  APP:  { color: '#059669', bg: 'rgba(52,211,153,0.12)',  icon: 'AP' },
  EPP:  { color: '#7c3aed', bg: 'rgba(192,132,252,0.12)', icon: 'EP' },
  FILE: { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)', icon: 'FI' },
};

const ACTOR_COLORS = ['#2563eb','#0ea5e9','#d97706','#059669','#fb7185','#7c3aed','#db2777'];
const CHART_COLORS = ['#2563eb','#0ea5e9','#fb7185','#d97706','#059669','#7c3aed','#94a3b8'];
const SEV = {
  HIGH:   { bg: 'rgba(248,113,113,0.15)', color: '#dc2626', ring: 'rgba(248,113,113,0.3)' },
  MEDIUM: { bg: 'rgba(251,191,36,0.15)',  color: '#d97706', ring: 'rgba(251,191,36,0.3)' },
  INFO:   { bg: 'rgba(129,140,248,0.10)', color: '#3b82f6', ring: 'rgba(129,140,248,0.2)' },
};

/* ═══════════════════════════════════════════════════════════════
   Insights Engine — auto-generates forensic observations
   ═══════════════════════════════════════════════════════════════ */
function generateInsights(events, stats) {
  if (!events.length || !stats) return [];
  const insights = [];

  // 1. After-hours activity
  const afterHours = events.filter(e => {
    const h = new Date(e.normalised_ts).getHours();
    return h >= 20 || h <= 5;
  });
  if (afterHours.length > 10) {
    const actors = [...new Set(afterHours.map(e => e.actor))];
    insights.push({
      severity: 'HIGH', icon: 'AH',
      title: 'Significant After-Hours Activity',
      text: `${afterHours.length} events detected between 20:00-05:00, involving ${actors.join(', ')}. Typical insider threat indicator.`,
    });
  }

  // 2. Bulk data access
  const dbExports = events.filter(e => e.source_type === 'DB' && (e.action === 'EXPORT' || e.action === 'SELECT'));
  if (dbExports.length > 5) {
    insights.push({
      severity: 'HIGH', icon: 'DB',
      title: 'Bulk Database Access Detected',
      text: `${dbExports.length} database queries/exports found. Check for sensitive table access (customers, PII, financials).`,
    });
  }

  // 3. EPP alerts
  const eppAlerts = events.filter(e => e.source_type === 'EPP');
  if (eppAlerts.length > 0) {
    insights.push({
      severity: 'HIGH', icon: 'EP',
      title: 'Endpoint Protection Alerts',
      text: `${eppAlerts.length} EPP events: ${[...new Set(eppAlerts.map(e => e.action))].join(', ')}. Investigate for malware or suspicious tooling.`,
    });
  }

  // 4. Firewall denials
  const fwDenies = events.filter(e => e.source_type === 'FW' && (e.action === 'DENY' || e.action === 'DROP'));
  if (fwDenies.length > 3) {
    insights.push({
      severity: 'MEDIUM', icon: 'FW',
      title: 'Firewall Blocks Detected',
      text: `${fwDenies.length} DENY/DROP events. Possible blocked exfiltration or lateral movement attempts.`,
    });
  }

  // 5. Failed logins
  const failedLogins = events.filter(e => e.action === 'LOGIN_FAILED');
  if (failedLogins.length > 2) {
    const actors = [...new Set(failedLogins.map(e => e.actor))];
    insights.push({
      severity: 'MEDIUM', icon: 'LG',
      title: 'Multiple Failed Authentication',
      text: `${failedLogins.length} failed logins by ${actors.join(', ')}. May indicate credential stuffing or brute force.`,
    });
  }

  // 6. File exfiltration pattern
  const fileCopies = events.filter(e => e.source_type === 'FILE' && (e.action === 'FILE_COPY' || e.action === 'FILE_WRITE'));
  if (fileCopies.length > 3) {
    insights.push({
      severity: 'HIGH', icon: 'EX',
      title: 'Data Staging / Exfiltration Pattern',
      text: `${fileCopies.length} file copy/write operations. Check destinations for USB or external staging locations.`,
    });
  }

  // 7. VPN from unusual IPs
  const vpnEvents = events.filter(e => e.source_type === 'VPN');
  if (vpnEvents.length > 5) {
    insights.push({
      severity: 'MEDIUM', icon: 'VP',
      title: 'VPN Session Patterns',
      text: `${vpnEvents.length} VPN events detected. Review for unusual source IPs or after-hours connections.`,
    });
  }

  // 8. Top actor dominance
  const actorEntries = Object.entries(stats.actors || {});
  if (actorEntries.length > 1) {
    const sorted = actorEntries.sort((a, b) => b[1] - a[1]);
    const topPct = ((sorted[0][1] / stats.total_events) * 100).toFixed(0);
    if (parseInt(topPct) > 40) {
      insights.push({
        severity: 'MEDIUM', icon: 'AC',
        title: `"${sorted[0][0]}" Dominates Activity`,
        text: `${sorted[0][0]} accounts for ${topPct}% of all events (${sorted[0][1]}/${stats.total_events}). Disproportionate activity suggests focused investigation target.`,
      });
    }
  }

  return insights.slice(0, 6);
}

/* ═══════════════════════════════════════════════════════════════
   Threat Score Calculator
   ═══════════════════════════════════════════════════════════════ */
function calcThreatScore(events, stats) {
  if (!events.length) return { score: 0, label: 'N/A', color: '#475569' };
  let score = 0;
  const highCount = events.filter(e => e.severity === 'HIGH').length;
  const medCount  = events.filter(e => e.severity === 'MEDIUM').length;
  const eppCount  = events.filter(e => e.source_type === 'EPP').length;
  const afterHrs  = events.filter(e => { const h = new Date(e.normalised_ts).getHours(); return h >= 20 || h <= 5; }).length;
  const fwBlocks  = events.filter(e => e.action === 'DENY' || e.action === 'DROP').length;
  const dbExports = events.filter(e => e.source_type === 'DB' && (e.action === 'EXPORT' || e.action === 'SELECT')).length;
  const fileCopies= events.filter(e => e.source_type === 'FILE' && e.action === 'FILE_COPY').length;

  score += Math.min(25, highCount * 2);
  score += Math.min(10, medCount);
  score += Math.min(20, eppCount * 7);
  score += Math.min(15, Math.floor(afterHrs / 2) * 3);
  score += Math.min(10, fwBlocks * 3);
  score += Math.min(10, dbExports * 2);
  score += Math.min(10, fileCopies * 4);
  score += Math.min(5, Object.keys(stats?.sources || {}).length);
  score = Math.min(100, score);

  if (score >= 70) return { score, label: 'CRITICAL', color: '#ef4444' };
  if (score >= 45) return { score, label: 'HIGH', color: '#f59e0b' };
  if (score >= 20) return { score, label: 'ELEVATED', color: '#2563eb' };
  return { score, label: 'LOW', color: '#059669' };
}

/* ═══════════════════════════════════════════════════════════════
   Attack Phase Detection
   ═══════════════════════════════════════════════════════════════ */
function detectPhases(events) {
  if (!events.length) return [];
  const sorted = [...events].sort((a, b) => new Date(a.normalised_ts) - new Date(b.normalised_ts));
  const total = sorted.length;
  const third = Math.floor(total / 3);

  return [
    {
      id: 'recon', label: 'Reconnaissance', color: '#2563eb',
      start: sorted[0]?.normalised_ts, end: sorted[third]?.normalised_ts,
      count: third,
      desc: 'Initial probing, failed logins, VPN connections from unusual IPs',
    },
    {
      id: 'access', label: 'Access & Escalation', color: '#d97706',
      start: sorted[third]?.normalised_ts, end: sorted[third * 2]?.normalised_ts,
      count: third,
      desc: 'Database queries, sensitive table access, credential use',
    },
    {
      id: 'exfil', label: 'Exfiltration', color: '#dc2626',
      start: sorted[third * 2]?.normalised_ts, end: sorted[total - 1]?.normalised_ts,
      count: total - third * 2,
      desc: 'File copies, large outbound transfers, EPP alerts',
    },
  ];
}

/* ═══════════════════════════════════════════════════════════════
   Component
   ═══════════════════════════════════════════════════════════════ */
export default function TimelinePage() {
  const { id } = useParams();
    const searchParams = useSearchParams();

    const [events, setEvents]   = useState([]);
    const [stats, setStats]     = useState(null);
    const [initialLoading, setInitialLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [building, setBuilding] = useState(false);
    const [built, setBuilt]     = useState(false);
    const [buildResult, setBuildResult] = useState(null);
    const [anomalyHybrid, setAnomalyHybrid] = useState({
      status: 'idle',
      sequenceAnomalyCount: 0,
      sequenceGroupCount: 0,
      runId: null,
    });

    const [view, setView] = useState(searchParams.get('card') ? 'timeline' : 'command');
    const [fActor, setFActor]       = useState('');
    const [fSource, setFSource]     = useState('');
    const [fSeverity, setFSeverity] = useState('');
    const [fKeyword, setFKeyword]   = useState('');
    const [fAnchors, setFAnchors]   = useState(false);
    const [expanded, setExpanded]   = useState(null);

    const [evidenceCards, setEvidenceCards] = useState([]);
    const [activeCardId, setActiveCardId]   = useState(searchParams.get('card') || null);
    const displayedEvents = useMemo(() => {
      if (!activeCardId) return events;
      const card = evidenceCards.find(c => c.id === activeCardId);
      if (!card || !card.evidence_ref || !card.evidence_ref.pointers) return events;
      return events.filter(e => card.evidence_ref.pointers.includes(e.tl_event_id));
    }, [events, activeCardId, evidenceCards]);

  const debounceRef = useRef(null);
  const hybridPollRef = useRef(null);

  /* ── Filter State ──────────────────────────────── */
  const { getMergedFilters, state, setLocalFilters } = useFilterState();
  const mergedFilters = getMergedFilters('timeline');

  const handleChartClick = useCallback((field, value) => {
    if (field === 'hour') {
      // Hour click gives "14:00". We might want to filter, but let's keep it simple for now and skip hour or add 'contains'
      return;
    }
    const currentFilters = state.localFilters['timeline'] || { logic: 'AND', conditions: [] };
    const exists = currentFilters.conditions.some(c => c.field === field && c.value === value);
    if (!exists) {
      setLocalFilters('timeline', {
        ...currentFilters,
        conditions: [...currentFilters.conditions, { field, op: 'eq', value }]
      });
    }
  }, [state.localFilters, setLocalFilters]);

  /* ── Data Loading ────────────────────────────────── */
  const loadData = useCallback(async (isInitial = false) => {
    if (isInitial) setInitialLoading(true); else setRefreshing(true);
    try {
      const params = { limit: 2000 };
      if (fActor) params.actor = fActor;
      if (fSource) params.source_type = fSource;
      if (fSeverity) params.severity = fSeverity;
      if (fKeyword) params.keyword = fKeyword;
      if (fAnchors) params.anchors_only = 'true';
      
      const payload = getMergedFilters('timeline');
      const [ev, st] = await Promise.all([
        api.searchTimeline(id, payload, params),
        api.searchTimelineStats(id, payload, params)
      ]);
      setEvents(ev); setStats(st); setBuilt(st.total_events > 0);
    } catch {} finally { setInitialLoading(false); setRefreshing(false); }
  }, [id, fActor, fSource, fSeverity, fKeyword, fAnchors, getMergedFilters]);

  const loadAnomalyHybrid = useCallback(async () => {
    if (!id) return;
    try {
      const summary = await api.getAnomalySummary(id).catch(() => null);
      if (!summary || summary.error) {
        setAnomalyHybrid({ status: 'idle', sequenceAnomalyCount: 0, sequenceGroupCount: 0, runId: null });
        return;
      }

      setAnomalyHybrid({
        status: summary.context_engine_status || 'idle',
        sequenceAnomalyCount: summary.sequence_anomaly_count ?? 0,
        sequenceGroupCount: summary.sequence_group_count ?? summary.sequence_groups ?? 0,
        runId: summary.run_id || null,
      });
    } catch {
      setAnomalyHybrid({ status: 'idle', sequenceAnomalyCount: 0, sequenceGroupCount: 0, runId: null });
    }
  }, [id]);

  useEffect(() => {
    loadData(true);
    loadEvidenceCards();
    loadAnomalyHybrid();
  }, [id]);

  useEffect(() => {
    if (hybridPollRef.current) {
      clearInterval(hybridPollRef.current);
      hybridPollRef.current = null;
    }

    if (anomalyHybrid.status === 'started') {
      hybridPollRef.current = setInterval(() => {
        loadAnomalyHybrid();
      }, 2500);
    }

    return () => {
      if (hybridPollRef.current) {
        clearInterval(hybridPollRef.current);
        hybridPollRef.current = null;
      }
    };
  }, [anomalyHybrid.status, loadAnomalyHybrid]);

  const loadEvidenceCards = async () => {
    try {
      const cards = await api.getEvidenceCards(id);
      setEvidenceCards(cards);
    } catch (err) {
      console.error("Failed to load evidence cards", err);
    }
  };

  useEffect(() => {
    if (initialLoading) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => loadData(false), 150);
    return () => clearTimeout(debounceRef.current);
  }, [fActor, fSource, fSeverity, fKeyword, fAnchors, mergedFilters]);

  /* ── Actions ─────────────────────────────────────── */
  const handleBuild = async (force = false) => {
    setBuilding(true);
    try { const r = await api.buildTimeline(id, { force_rebuild: force }); setBuildResult(r); setBuilt(true); await loadData(false); }
    catch (err) { setBuildResult({ message: `Error: ${err.message}` }); }
    finally { setBuilding(false); }
  };

  const handleToggleAnchor = async (ev, e) => {
    if (e) e.stopPropagation();
    setEvents(prev => prev.map(item =>
      item.tl_event_id === ev.tl_event_id
        ? { ...item, is_anchor: !item.is_anchor, anchor_label: item.is_anchor ? null : `Manual: ${item.action}` }
        : item
    ));
    try {
      await api.toggleAnchor(id, { tl_event_id: ev.tl_event_id, label: ev.is_anchor ? '' : `Manual: ${ev.action}`, is_anchor: !ev.is_anchor });
      await loadData(false);
    } catch { loadData(false); }
  };

  const handleSaveGlobalVault = async () => {
    const anchoredEvents = events.filter(e => e.is_anchor);
    if (anchoredEvents.length === 0) {
      alert("No anchored events to save.");
      return;
    }
    
    const title = window.prompt(`Enter a title for this sequence (${anchoredEvents.length} events):`, "Ransomware Analysis");
    if (!title) return;
    
    const desc = window.prompt("Enter an optional description for this sequence:");
    
    try {
      const payload = {
        title,
        description: desc || undefined,
        evidence_ref: {
          case_id: id,
          table: "unified_timeline",
          pointers: anchoredEvents.map(e => e.tl_event_id),
          rowHashes: anchoredEvents.map(() => "sha256:unknown")
        }
      };
      await api.addEvidenceCard(id, payload);
      alert("Successfully saved pinned sequence to Evidence Vault!");
      loadEvidenceCards(); // Refresh cards list
    } catch (err) {
      alert(`Failed to save sequence: ${err.message}`);
    }
  };

  /* ── Computed Data ───────────────────────────────── */
  const insights = useMemo(() => generateInsights(events, stats), [events, stats]);
  const threat   = useMemo(() => calcThreatScore(events, stats), [events, stats]);
  const phases   = useMemo(() => detectPhases(events), [events]);

  const activityByDay = useMemo(() => {
    const map = {};
    events.forEach(ev => {
      const d = new Date(ev.normalised_ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      if (!map[d]) map[d] = { date: d, HIGH: 0, MEDIUM: 0, INFO: 0 };
      map[d][ev.severity]++;
    });
    return Object.values(map);
  }, [events]);

  const hourlyData = useMemo(() => {
    const map = {};
    events.forEach(ev => { const h = new Date(ev.normalised_ts).getHours(); map[h] = (map[h] || 0) + 1; });
    return Array.from({ length: 24 }, (_, h) => ({ hour: `${String(h).padStart(2, '0')}:00`, count: map[h] || 0 }));
  }, [events]);

  const sourceData = useMemo(() => Object.entries(stats?.sources || {}).map(([name, value]) => ({ name, value })), [stats]);
  const actorData  = useMemo(() => Object.entries(stats?.actors || {}).map(([name, value]) => ({ name, value })), [stats]);
  const sevData    = useMemo(() => {
    const m = { HIGH: 0, MEDIUM: 0, INFO: 0 };
    events.forEach(e => m[e.severity]++);
    return Object.entries(m).map(([name, value]) => ({ name, value }));
  }, [events]);

  const radarData = useMemo(() => {
    if (!events.length) return [];
    const afterHrs = events.filter(e => { const h = new Date(e.normalised_ts).getHours(); return h >= 20 || h <= 5; }).length;
    const highSev = events.filter(e => e.severity === 'HIGH').length;
    const sources = Object.keys(stats?.sources || {}).length;
    const actors = Object.keys(stats?.actors || {}).length;
    const anchors = stats?.total_anchors || 0;
    const max = Math.max(afterHrs, highSev, sources * 10, actors * 10, anchors * 5, 1);
    return [
      { axis: 'After-Hours', value: afterHrs, baseline: max * 0.3 },
      { axis: 'High Severity', value: highSev, baseline: max * 0.2 },
      { axis: 'Source Diversity', value: sources * 10, baseline: max * 0.4 },
      { axis: 'Actor Count', value: actors * 10, baseline: max * 0.3 },
      { axis: 'Anchor Events', value: anchors * 5, baseline: max * 0.25 },
      { axis: 'Total Volume', value: Math.min(events.length, max), baseline: max * 0.5 },
    ];
  }, [events, stats]);

  const hybridBadge = useMemo(() => {
    if (anomalyHybrid.status === 'completed') {
      return {
        text: `Context Ready (${anomalyHybrid.sequenceAnomalyCount})`,
        color: '#059669',
      };
    }
    if (anomalyHybrid.status === 'started') {
      return {
        text: `Context Running (${anomalyHybrid.sequenceGroupCount})`,
        color: '#2563eb',
      };
    }
    if (anomalyHybrid.status === 'failed') {
      return { text: 'Context Failed', color: '#dc2626' };
    }
    return { text: 'Context Idle', color: '#64748b' };
  }, [anomalyHybrid]);

  const hasFilters = fActor || fSource || fSeverity || fKeyword || fAnchors || activeCardId;
  const clearFilters = () => { setFActor(''); setFSource(''); setFSeverity(''); setFKeyword(''); setFAnchors(false); setActiveCardId(null); };

  /* ── Heatmap / Lane helpers ──────────────────────── */
  const heatmap = useMemo(() => {
    const sources = Object.keys(SRC);
    const grid = {}; sources.forEach(s => grid[s] = new Array(24).fill(0));
    events.forEach(ev => { const h = new Date(ev.normalised_ts).getHours(); if (grid[ev.source_type]) grid[ev.source_type][h]++; });
    const maxVal = Math.max(1, ...sources.flatMap(s => grid[s]));
    return { grid, maxVal, sources: sources.filter(s => grid[s].some(v => v > 0)) };
  }, [events]);

  const laneData = useMemo(() => {
    if (!displayedEvents.length) return { lanes: {}, minTs: 0, maxTs: 1 };
    const ts = displayedEvents.map(e => new Date(e.normalised_ts).getTime());
    const minTs = Math.min(...ts), maxTs = Math.max(...ts);
    const lanes = {};
    displayedEvents.forEach(ev => { if (!lanes[ev.source_type]) lanes[ev.source_type] = []; lanes[ev.source_type].push(ev); });
    return { lanes, minTs, maxTs };
  }, [displayedEvents]);

  /* ═════════════════════════════════════════════════════
     RENDER
     ═════════════════════════════════════════════════════ */
  const mono = { fontFamily: "'JetBrains Mono', monospace" };
  const cardStyle = (accent) => ({
    padding: '20px 24px', background: 'var(--bg-card)', border: '1px solid var(--border-color)',
    borderRadius: 14, borderTop: `3px solid ${accent}`,
  });
  const sectionTitle = (icon, text) => (
    <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 16,
      textTransform: 'uppercase', letterSpacing: '0.1em', display: 'flex', alignItems: 'center', gap: 8 }}>
      {icon ? <span>{icon}</span> : null}
      {text}
    </h3>
  );

  if (initialLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 16 }}>
        <div className="spinner" style={{ width: 36, height: 36 }} />
        <span style={{ color: 'var(--text-muted)', fontSize: 13, ...mono }}>Initializing timeline…</span>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1440, margin: '0 auto' }}>
      <style dangerouslySetInnerHTML={{ __html: `
        /* ── Custom Timeline Reconstruction CSS ── */
        .tl-view-tabs { display: flex; gap: 8px; align-items: center; background: #fff; padding: 6px; border-radius: 99px; border: 1px solid var(--border-color); width: fit-content; margin: 0 auto; box-shadow: 0 2px 8px rgba(0,0,0,0.02); }
        .tl-view-tab { padding: 8px 20px; border-radius: 99px; font-size: 13px; font-weight: 700; color: var(--text-muted); border: none; background: transparent; cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; gap: 8px; }
        .tl-view-tab:hover { color: #1e293b; background: rgba(15,23,42,0.03); }
        .tl-view-tab.active { background: #2563eb; color: #fff; box-shadow: 0 4px 12px rgba(37,99,235,0.25); }

        .tl-heatmap-grid { display: grid; grid-template-columns: 80px repeat(24, 1fr); gap: 2px; margin-top: 16px; overflow-x: auto; padding-bottom: 8px; }
        .tl-hm-header { font-size: 10px; font-weight: 800; text-align: center; color: var(--text-muted); padding-bottom: 4px; border-bottom: 1px solid var(--border-color); font-family: 'JetBrains Mono', monospace; }
        .tl-hm-label { font-size: 11px; font-weight: 800; display: flex; align-items: center; justify-content: flex-end; padding-right: 12px; }
        .tl-hm-cell { height: 28px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 800; cursor: crosshair; transition: transform 0.1s; font-family: 'JetBrains Mono', monospace; }
        .tl-hm-cell:hover { transform: scale(1.15); z-index: 10; box-shadow: 0 4px 12px rgba(0,0,0,0.15); border: 1px solid rgba(255,255,255,0.3); }

        .tl-vertical { position: relative; padding-left: 32px; margin-top: 20px; }
        .tl-vertical::before { content: ''; position: absolute; left: 11px; top: 0; bottom: 0; width: 2px; background: var(--border-color); }
        .tl-v-event { position: relative; padding: 12px 16px; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.02); transition: all 0.2s ease; cursor: pointer; }
        .tl-v-event:hover { transform: translateX(4px); border-color: #94a3b8; }
        .tl-v-event.is-anchor { border-left: 4px solid #d97706; background: linear-gradient(to right, rgba(217,119,6,0.05), transparent); }
        .tl-v-node { position: absolute; left: -27px; top: 18px; width: 14px; height: 14px; border-radius: 50%; border: 3px solid #fff; z-index: 2; box-shadow: 0 0 0 1px var(--border-color); transition: all 0.2s; }
        .tl-v-event:hover .tl-v-node { transform: scale(1.2); }
        .tl-v-node.anchor-node.pulse { box-shadow: 0 0 0 4px rgba(217,119,6,0.2), 0 0 0 1px #d97706; }
        .tl-v-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px; }
        .tl-v-ts { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--text-muted); margin-left: auto; font-weight: 600; }
        .tl-v-body { display: flex; align-items: center; gap: 8px; background: rgba(15,23,42,0.03); padding: 8px 12px; border-radius: 8px; flex-wrap: wrap; }
        .tl-v-target { font-family: 'JetBrains Mono', monospace; font-size: 11.5px; word-break: break-all; color: #334155; font-weight: 500; }

        .tl-lanes { display: flex; flex-direction: column; gap: 14px; margin-top: 20px; overflow-x: auto; padding-bottom: 12px; }
        .tl-lane { display: flex; align-items: center; gap: 16px; min-width: 800px; }
        .tl-lane-label { width: 80px; text-align: right; font-size: 11px; font-weight: 800; flex-shrink: 0; }
        .tl-lane-track { position: relative; flex: 1; height: 32px; background: repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(148,163,184,0.1) 40px); border-radius: 16px; background-color: rgba(248,250,252,0.8); border: 1px solid var(--border-color); }
        .tl-lane-dot { position: absolute; top: 50%; transform: translate(-50%, -50%); width: 10px; height: 10px; border-radius: 50%; box-shadow: 0 0 4px rgba(0,0,0,0.2); transition: transform 0.2s, z-index 0s; border: 1.5px solid #fff; z-index: 1; cursor: pointer; }
        .tl-lane-dot:hover { transform: translate(-50%, -50%) scale(2.5); z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }

        .tl-detail-drawer { background: rgba(248,250,252,0.8); border: 1px solid var(--border-color); padding: 16px; margin: 8px 0 12px; border-radius: 8px; box-shadow: inset 0 2px 8px rgba(0,0,0,0.02); }
        .tl-detail-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
        .tl-detail-label { font-size: 10px; font-weight: 800; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px; letter-spacing: 0.05em; }
        .tl-detail-value { font-family: 'JetBrains Mono', monospace; font-size: 11.5px; color: #1e293b; font-weight: 600; }
        
        .empty-state { text-align: center; color: var(--text-muted); display: flex; flex-direction: column; align-items: center; justify-content: center; }
        .empty-state h3 { font-size: 18px; font-weight: 700; color: #1e293b; margin-bottom: 8px; }
      `}} />
      {/* ── Header ────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24, paddingBottom: 20, borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em',
            color: '#1e293b' }}>
            Timeline Reconstruction
          </h1>
          <div style={{ ...mono, fontSize: 12, marginTop: 6, color: 'var(--text-muted)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <span>{stats?.total_events?.toLocaleString()} events</span><span style={{ opacity: 0.3 }}>|</span>
            <span>{stats?.total_anchors} anchors</span><span style={{ opacity: 0.3 }}>|</span>
            <span>{Object.keys(stats?.sources || {}).length} sources</span><span style={{ opacity: 0.3 }}>|</span>
            <span>{Object.keys(stats?.actors || {}).length} actors</span>
            {refreshing && <span style={{ color: '#0ea5e9' }}>Refreshing...</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {built && (
            <div style={{
              padding: '8px 14px', borderRadius: 999, fontSize: 11, fontWeight: 800,
              background: `${hybridBadge.color}18`, border: `1.5px solid ${hybridBadge.color}40`,
              color: hybridBadge.color, letterSpacing: '0.04em',
            }}>
              ANOMALY: {hybridBadge.text}
            </div>
          )}
          {/* Threat Badge */}
          {built && (
            <div style={{
              padding: '8px 16px', borderRadius: 999, fontSize: 12, fontWeight: 800,
              background: `${threat.color}18`, border: `1.5px solid ${threat.color}40`,
              color: threat.color, letterSpacing: '0.06em',
              boxShadow: `0 0 20px ${threat.color}15`,
            }}>
              THREAT: {threat.label} ({threat.score}/100)
            </div>
          )}
          {built && <button className="btn btn-secondary" onClick={() => handleBuild(true)} disabled={building}>
            {building ? 'Rebuilding...' : 'Rebuild'}
          </button>}
          <Link href={`/cases/${id}`} className="btn btn-ghost">← Case</Link>
        </div>
      </div>

      {/* ── Build CTA ─────────────────────────────── */}
      {!built && (
        <div className="glass-card-static empty-state" style={{ marginBottom: 24, padding: 48 }}>
          <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.5 }}>TL</div>
          <h3 style={{ fontSize: 20 }}>Build Unified Timeline</h3>
          <p>Normalise and analyse all imported evidence logs.</p>
          <button className="btn btn-primary btn-lg" onClick={() => handleBuild(false)} disabled={building}>
            {building ? 'Building...' : 'Build Timeline'}
          </button>
        </div>
      )}

      {buildResult && (
        <div style={{ marginBottom: 14, padding: '10px 18px', borderRadius: 10, background: 'rgba(52,211,153,0.06)', border: '1px solid rgba(52,211,153,0.2)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: '#059669', fontWeight: 600, fontSize: 13 }}>{buildResult.message}</span>
          {buildResult.hash_value && <span className="hash-value" style={{ fontSize: 10 }}>{buildResult.hash_value.slice(0, 20)}…</span>}
        </div>
      )}

      {built && (
        <>
          <AdvancedFilterBuilder moduleName="timeline" />
          {/* ── Source + Actor Row (unified) ────────── */}
          <div style={{ display: 'flex', gap: 16, marginBottom: 14, padding: '12px 16px', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Sources</span>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {Object.entries(stats?.sources || {}).map(([src, count]) => {
                const s = SRC[src] || {}; const active = fSource === src;
                return (
                  <button key={src} onClick={() => setFSource(active ? '' : src)} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', borderRadius: 999,
                    fontSize: 10.5, fontWeight: 700, background: active ? s.color : s.bg,
                    color: active ? '#fff' : s.color, border: `1px solid ${active ? s.color : 'transparent'}`,
                    cursor: 'pointer', transition: 'all 0.2s', boxShadow: active ? `0 0 10px ${s.color}30` : 'none',
                  }}>
                    <span style={{ width: 5, height: 5, borderRadius: '50%', background: active ? '#fff' : s.color }} />
                    <span style={{ ...mono, fontSize: 8, fontWeight: 800 }}>{s.icon || 'NA'}</span>
                    {src}
                    <span style={{ padding: '0 4px', borderRadius: 999, fontSize: 8.5, fontWeight: 800, background: 'rgba(255,255,255,0.08)' }}>{count}</span>
                  </button>
                );
              })}
            </div>
            <div style={{ width: 1, height: 20, background: 'var(--border-color)' }} />
            <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Actors</span>
            <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
              {Object.entries(stats?.actors || {}).map(([actor, count], i) => {
                const active = fActor === actor; const c = ACTOR_COLORS[i % ACTOR_COLORS.length];
                return (
                  <button key={actor} onClick={() => setFActor(active ? '' : actor)} style={{
                    display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px',
                    background: active ? `${c}15` : 'transparent', border: `1px solid ${active ? c : 'var(--border-color)'}`,
                    borderRadius: 8, cursor: 'pointer', transition: 'all 0.2s', fontSize: 11, fontWeight: 600,
                    color: active ? c : 'var(--text-secondary)',
                  }}>
                    <div style={{ width: 18, height: 18, borderRadius: '50%', background: c, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 8, fontWeight: 800, color: '#fff' }}>
                      {actor.slice(0, 2).toUpperCase()}
                    </div>
                    {actor} <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>{count}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '8px 14px', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 12, marginBottom: 14 }}>
            <select className="form-select" value={fSeverity} onChange={e => setFSeverity(e.target.value)} style={{ width: 120, flex: 'none', padding: '6px 10px', fontSize: 11.5 }}>
              <option value="">All Severity</option>
              <option value="HIGH"> HIGH</option>
              <option value="MEDIUM"> MEDIUM</option>
              <option value="INFO"> INFO</option>
            </select>
            <input className="form-input" placeholder=" Search actions, targets, details…" style={{ flex: 1, minWidth: 160, padding: '6px 12px', fontSize: 11.5 }}
              value={fKeyword} onChange={e => setFKeyword(e.target.value)} />
            <button onClick={() => setFAnchors(!fAnchors)} style={{
              display: 'flex', alignItems: 'center', gap: 5, padding: '6px 10px',
              background: fAnchors ? 'rgba(251,191,36,0.15)' : 'transparent',
              border: `1px solid ${fAnchors ? '#d97706' : 'var(--border-color)'}`,
              borderRadius: 8, cursor: 'pointer', fontSize: 11.5, fontWeight: 600,
              color: fAnchors ? '#d97706' : 'var(--text-muted)', transition: 'all 0.2s',
            }}>Anchors</button>
            <button onClick={handleSaveGlobalVault} style={{
              display: 'flex', alignItems: 'center', gap: 5, padding: '6px 10px',
              background: 'transparent', border: '1px solid #3b82f6', borderRadius: 8,
              cursor: 'pointer', fontSize: 11.5, fontWeight: 600, color: '#3b82f6',
            }}>Save Pinned to Vault</button>
            {hasFilters && <button className="btn btn-ghost btn-sm" onClick={clearFilters} style={{ fontSize: 10 }}>Clear filters</button>}
            <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto', ...mono }}>{displayedEvents.length} results</span>
          </div>

          {/* ── Saved Clusters / Evidence Cards ── */}
          {evidenceCards.length > 0 && (
            <div style={{ display: 'flex', gap: 8, padding: '0 14px 14px 14px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', paddingTop: 5 }}>Saved Clusters:</span>
              {evidenceCards.map(card => (
                <button
                  key={card.id}
                  onClick={() => setActiveCardId(activeCardId === card.id ? null : card.id)}
                  style={{
                    padding: '4px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600, cursor: 'pointer',
                    background: activeCardId === card.id ? '#3b82f6' : 'rgba(59,130,246,0.1)',
                    color: activeCardId === card.id ? '#fff' : '#2563eb',
                    border: `1px solid ${activeCardId === card.id ? '#2563eb' : 'rgba(59,130,246,0.2)'}`,
                    transition: 'all 0.2s'
                  }}
                  title={card.description}
                >
                  {card.title} ({card.evidence_ref?.pointers?.length || 0})
                </button>
              ))}
            </div>
          )}

          {/* ── View Tabs ──────────────────────────── */}
          <div className="tl-view-tabs" style={{ marginBottom: 18 }}>
            {VIEWS.map(v => (
              <button key={v.id} className={`tl-view-tab ${view === v.id ? 'active' : ''}`} onClick={() => setView(v.id)}>
                {v.icon ? <span className="tab-icon">{v.icon}</span> : null}
                {v.label}
              </button>
            ))}
          </div>

          {/* ═════════════════════════════════════════════
              VIEW: COMMAND CENTER
              ═════════════════════════════════════════════ */}
          {view === 'command' && events.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 16 }}>
              {/* Left: Activity + Insights */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {/* Stats row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                  {[
                    { icon: 'EV', val: stats?.total_events?.toLocaleString(), lbl: 'Events', c: '#2563eb' },
                    { icon: 'AN', val: stats?.total_anchors, lbl: 'Anchors', c: '#d97706' },
                    { icon: 'SR', val: Object.keys(stats?.sources || {}).length, lbl: 'Sources', c: '#0ea5e9' },
                    { icon: 'AC', val: Object.keys(stats?.actors || {}).length, lbl: 'Actors', c: '#059669' },
                  ].map((c, i) => (
                    <div key={i} style={cardStyle(c.c)}>
                      {c.icon ? <div style={{ fontSize: 18 }}>{c.icon}</div> : null}
                      <div style={{ fontSize: 24, fontWeight: 800, color: c.c, ...mono }}>{c.val}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600 }}>{c.lbl}</div>
                    </div>
                  ))}
                </div>

                {/* Activity chart */}
                <div style={cardStyle('#2563eb')}>
                  {sectionTitle('', 'Activity Timeline — Severity by Day')}
                  <ActivityChart data={activityByDay} />
                </div>

                {/* Attack Phases */}
                <div style={cardStyle('#d97706')}>
                  {sectionTitle('', 'Attack Phase Analysis')}
                  <div style={{ display: 'flex', gap: 0 }}>
                    {phases.map((p, i) => (
                      <div key={p.id} style={{
                        flex: p.count, padding: '14px 16px', background: `${p.color}10`,
                        borderLeft: i > 0 ? `2px solid ${p.color}30` : 'none',
                        borderBottom: `3px solid ${p.color}`,
                      }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: p.color, marginBottom: 4 }}>{p.label}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>{p.desc}</div>
                        <div style={{ display: 'flex', gap: 12, fontSize: 10, ...mono, color: 'var(--text-secondary)' }}>
                          <span>{p.count} events</span>
                          <span>{new Date(p.start).toLocaleDateString()}</span>
                          <span>→ {new Date(p.end).toLocaleDateString()}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Hourly + Source charts */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                  <div style={cardStyle('#2563eb')}>
                    {sectionTitle('', 'Hourly Distribution')}
                    <HourlyChart data={hourlyData} />
                  </div>
                  <div style={cardStyle('#0ea5e9')}>
                    {sectionTitle('', 'Source Distribution')}
                    <SourcePie data={sourceData} colors={sourceData.map(d => SRC[d.name]?.color || '#666')} onChartClick={handleChartClick} />
                  </div>
                </div>
              </div>

              {/* Right sidebar: Threat + Insights */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Threat Score Gauge */}
                <div style={{
                  ...cardStyle(threat.color), textAlign: 'center',
                  background: `radial-gradient(circle at 50% 80%, ${threat.color}08 0%, var(--bg-card) 70%)`,
                }}>
                  {sectionTitle('', 'Threat Level')}
                  <div style={{ position: 'relative', width: 120, height: 120, margin: '0 auto 12px' }}>
                    <svg viewBox="0 0 120 120" style={{ width: 120, height: 120 }}>
                      <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(148,163,184,0.1)" strokeWidth="8" />
                      <circle cx="60" cy="60" r="50" fill="none" stroke={threat.color} strokeWidth="8"
                        strokeDasharray={`${threat.score * 3.14} ${314 - threat.score * 3.14}`}
                        strokeDashoffset="78.5" strokeLinecap="round"
                        style={{ filter: `drop-shadow(0 0 6px ${threat.color}40)`, transition: 'stroke-dasharray 1s ease' }} />
                    </svg>
                    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                      <span style={{ fontSize: 28, fontWeight: 800, color: threat.color, ...mono }}>{threat.score}</span>
                      <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)' }}>/100</span>
                    </div>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 800, color: threat.color, letterSpacing: '0.08em' }}>{threat.label}</div>
                </div>

                {/* Threat Radar */}
                <div style={cardStyle('#2563eb')}>
                  {sectionTitle('', 'Threat Radar')}
                  <ThreatRadar data={radarData} />
                </div>

                {/* Insights */}
                <div style={cardStyle('#fb7185')}>
                  {sectionTitle('', `Investigation Insights (${insights.length})`)}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {insights.map((ins, i) => (
                      <div key={i} style={{
                        padding: '10px 14px', borderRadius: 10,
                        background: SEV[ins.severity]?.bg || 'rgba(37,99,235,0.03)',
                        borderLeft: `3px solid ${SEV[ins.severity]?.color || '#666'}`,
                      }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: SEV[ins.severity]?.color, marginBottom: 3 }}>
                            {ins.icon ? `${ins.icon} ` : ''}{ins.title}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{ins.text}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ═════════════════════════════════════════════
              VIEW: DATA TABLE
              ═════════════════════════════════════════════ */}
          {view === 'table' && events.length > 0 && (
            <div className="glass-card-static" style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead><tr>
                  <th style={{ width: 36 }}></th><th>Timestamp</th><th>Source</th>
                  <th>Actor</th><th>Action</th><th>Target</th><th>Severity</th><th>System</th>
                </tr></thead>
                <tbody>
                  {displayedEvents.map(ev => (
                    <React.Fragment key={ev.tl_event_id}>
                      <tr className={ev.is_anchor ? 'tl-row-anchor' : ''} onClick={() => setExpanded(expanded === ev.tl_event_id ? null : ev.tl_event_id)} style={{ cursor: 'pointer' }}>
                        <td><button onClick={(e) => handleToggleAnchor(ev, e)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 10, fontWeight: 700, padding: 0 }}>{ev.is_anchor ? 'PIN' : 'ADD'}</button></td>
                        <td style={{ ...mono, fontSize: 11, whiteSpace: 'nowrap', color: '#1e293b' }}>{new Date(ev.normalised_ts).toLocaleString()}</td>
                        <td><span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 700, fontSize: 11, color: SRC[ev.source_type]?.color }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: SRC[ev.source_type]?.color }} /><span style={{ ...mono, fontSize: 9 }}>{SRC[ev.source_type]?.icon || 'NA'}</span>{ev.source_type}</span></td>
                        <td style={{ color: '#0ea5e9', fontWeight: 600, fontSize: 12 }}>{ev.actor}</td>
                        <td style={{ fontWeight: 600, fontSize: 12 }}>{ev.action}</td>
                        <td style={{ fontSize: 11.5, color: 'var(--text-secondary)', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.target}</td>
                        <td><span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700, background: SEV[ev.severity]?.bg, color: SEV[ev.severity]?.color }}>{ev.severity}</span></td>
                        <td style={{ fontSize: 11, color: 'var(--text-muted)', ...mono }}>{ev.source_system}</td>
                      </tr>
                      {expanded === ev.tl_event_id && (
                        <tr><td colSpan={8} style={{ padding: 0 }}>
                          <div className="tl-detail-drawer">
                            <div className="tl-detail-grid">
                              <div><div className="tl-detail-label">Event ID</div><div className="tl-detail-value">{ev.tl_event_id}</div></div>
                              <div><div className="tl-detail-label">Original ID</div><div className="tl-detail-value">{ev.original_event_id}</div></div>
                              <div><div className="tl-detail-label">UTC Offset</div><div className="tl-detail-value">{ev.utc_offset}</div></div>
                              <div><div className="tl-detail-label">System</div><div className="tl-detail-value">{ev.source_system}</div></div>
                              {ev.anchor_label && <div><div className="tl-detail-label">Anchor</div><div className="tl-detail-value" style={{ color: '#d97706' }}>{ev.anchor_label}</div></div>}
                              {ev.detail && <div style={{ gridColumn: '1/-1' }}><div className="tl-detail-label">Raw Detail</div><div className="tl-detail-value" style={{ wordBreak: 'break-all', fontSize: 10, lineHeight: 1.5 }}>{ev.detail}</div></div>}
                            </div>
                          </div>
                        </td></tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
              <div style={{ padding: '10px 16px', fontSize: 10, color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)', ...mono }}>
                {events.length} events · click row to expand · click ○ to pin
              </div>
            </div>
          )}

          {/* ═════════════════════════════════════════════
              VIEW: TIMELINE FLOW
              ═════════════════════════════════════════════ */}
          {view === 'timeline' && events.length > 0 && (
            <div className="tl-vertical">
              {displayedEvents.slice(0, 200).map(ev => (
                <div key={ev.tl_event_id}>
                  <div className={`tl-v-event ${ev.is_anchor ? 'is-anchor' : ''}`}
                    onClick={() => setExpanded(expanded === ev.tl_event_id ? null : ev.tl_event_id)}>
                    <div className={`tl-v-node ${ev.is_anchor ? 'anchor-node pulse' : ''}`}
                      style={{ background: ev.is_anchor ? '#d97706' : (SRC[ev.source_type]?.color || '#666') }} />
                    <div className="tl-v-header">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ width: 6, height: 6, borderRadius: '50%', background: SRC[ev.source_type]?.color }} />
                        <span style={{ ...mono, fontSize: 9, fontWeight: 800, color: SRC[ev.source_type]?.color }}>{SRC[ev.source_type]?.icon || 'NA'}</span>
                        <span style={{ fontWeight: 700, fontSize: 11, color: SRC[ev.source_type]?.color }}>{ev.source_type}</span>
                        <span style={{ fontWeight: 700, fontSize: 12.5 }}>{ev.action}</span>
                        <span style={{ padding: '1px 7px', borderRadius: 999, fontSize: 9, fontWeight: 700, background: SEV[ev.severity]?.bg, color: SEV[ev.severity]?.color }}>{ev.severity}</span>
                        {ev.is_anchor && <span style={{ padding: '1px 6px', borderRadius: 999, fontSize: 9, fontWeight: 700, background: 'rgba(251,191,36,0.2)', color: '#d97706' }}>ANCHOR</span>}
                        <button onClick={(e) => handleToggleAnchor(ev, e)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 10, fontWeight: 700, padding: 0, color: 'var(--text-muted)' }}>{ev.is_anchor ? 'PIN' : 'ADD'}</button>
                      </div>
                      <span className="tl-v-ts">{new Date(ev.normalised_ts).toLocaleString()}</span>
                    </div>
                    <div className="tl-v-body">
                      <span style={{ color: '#0ea5e9', fontWeight: 600, fontSize: 12 }}>{ev.actor}</span>
                      <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>→</span>
                      <span className="tl-v-target">{ev.target}</span>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto', ...mono }}>{ev.source_system}</span>
                    </div>
                  </div>
                  {expanded === ev.tl_event_id && (
                    <div className="tl-detail-drawer">
                      <div className="tl-detail-grid">
                        <div><div className="tl-detail-label">Event ID</div><div className="tl-detail-value">{ev.tl_event_id}</div></div>
                        <div><div className="tl-detail-label">Original ID</div><div className="tl-detail-value">{ev.original_event_id}</div></div>
                        {ev.detail && <div style={{ gridColumn: '1/-1' }}><div className="tl-detail-label">Raw Detail</div><div className="tl-detail-value" style={{ wordBreak: 'break-all', fontSize: 10 }}>{ev.detail}</div></div>}
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {events.length > 200 && <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: 12 }}>Showing 200 of {events.length}. Filter to narrow.</div>}
            </div>
          )}

          {/* ═════════════════════════════════════════════
              VIEW: ANALYTICS
              ═════════════════════════════════════════════ */}
          {view === 'graphs' && events.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div style={{ ...cardStyle('#2563eb'), gridColumn: '1 / -1' }}>
                {sectionTitle('', 'Activity Timeline — Stacked by Severity')}
                <ActivityChart data={activityByDay} />
              </div>
              <div style={cardStyle('#2563eb')}>
                {sectionTitle('', 'Hourly Distribution')}
                <HourlyChart data={hourlyData} />
              </div>
              <div style={cardStyle('#0ea5e9')}>
                {sectionTitle('', 'Source Distribution')}
                <SourcePie data={sourceData} colors={sourceData.map(d => SRC[d.name]?.color || '#666')} onChartClick={handleChartClick} />
              </div>
              <div style={cardStyle('#059669')}>
                {sectionTitle('', 'Actor Activity')}
                <ActorBar data={actorData} colors={ACTOR_COLORS} onChartClick={handleChartClick} />
              </div>
              <div style={cardStyle('#dc2626')}>
                {sectionTitle('', 'Severity Breakdown')}
                <SeverityPie data={sevData} onChartClick={handleChartClick} />
              </div>
            </div>
          )}

          {/* ═════════════════════════════════════════════
              VIEW: HEATMAP
              ═════════════════════════════════════════════ */}
          {view === 'heatmap' && events.length > 0 && (
            <div className="glass-card-static tl-heatmap">
              {sectionTitle('', 'Event Density — Source × Hour of Day')}
              <div className="tl-heatmap-grid">
                <div />
                {Array.from({ length: 24 }, (_, h) => <div key={h} className="tl-hm-header">{String(h).padStart(2, '0')}</div>)}
                {heatmap.sources.map(src => (
                  <React.Fragment key={src}>
                    <div className="tl-hm-label" style={{ color: SRC[src]?.color }}>{src}</div>
                    {heatmap.grid[src].map((val, h) => {
                      const intensity = val / heatmap.maxVal;
                      const color = SRC[src]?.color || '#2563eb';
                      return (
                        <div key={`${src}-${h}`} className="tl-hm-cell"
                          style={{ background: val > 0 ? `color-mix(in srgb, ${color} ${Math.max(15, intensity * 100)}%, transparent)` : 'rgba(255,255,255,0.015)', color: val > 0 ? '#fff' : 'transparent' }}
                          title={`${src} @ ${h}:00 — ${val} events`}>{val > 0 ? val : ''}</div>
                      );
                    })}
                  </React.Fragment>
                ))}
              </div>
              <div style={{ marginTop: 14, display: 'flex', gap: 16, fontSize: 10, color: 'var(--text-muted)', ...mono }}>
                <span>darker = more events</span><span>max = {heatmap.maxVal}/cell</span><span>total = {events.length}</span>
              </div>
            </div>
          )}

          {/* ═════════════════════════════════════════════
              VIEW: SWIM LANES
              ═════════════════════════════════════════════ */}
          {view === 'lanes' && events.length > 0 && (() => {
            const { lanes, minTs, maxTs } = laneData;
            const span = maxTs - minTs || 1;
            return (
              <div className="glass-card-static">
                {sectionTitle('', 'Source Swim Lanes')}
                <div className="tl-lanes">
                  {Object.entries(lanes).map(([src, srcEvts]) => (
                    <div key={src} className="tl-lane">
                      <div className="tl-lane-label" style={{ color: SRC[src]?.color }}>{src}</div>
                      <div className="tl-lane-track">
                        {srcEvts.map(ev => {
                          const pct = ((new Date(ev.normalised_ts).getTime() - minTs) / span) * 100;
                          return <div key={ev.tl_event_id} className={`tl-lane-dot ${ev.is_anchor ? 'dot-anchor pulse' : ''}`}
                            style={{ left: `${Math.max(0.5, Math.min(99, pct))}%`, background: ev.is_anchor ? '#d97706' : (SRC[src]?.color || '#666'), color: SRC[src]?.color }}
                            title={`${ev.actor} | ${ev.action} | ${new Date(ev.normalised_ts).toLocaleString()}`} />;
                        })}
                      </div>
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, fontSize: 10, color: 'var(--text-muted)', ...mono }}>
                  <span>{new Date(minTs).toLocaleString()}</span>
                  <span>{events.length} events across {Object.keys(lanes).length} sources</span>
                  <span>{new Date(maxTs).toLocaleString()}</span>
                </div>
              </div>
            );
          })()}

          {/* ── No results ────────────────────────────── */}
          {!refreshing && events.length === 0 && (
            <div className="glass-card-static empty-state" style={{ padding: 40 }}>
              <div style={{ fontSize: 48, opacity: 0.4, marginBottom: 12 }}>TL</div>
              <h3>No Events Match</h3>
              <p>Try clearing filters or rebuilding with new data.</p>
              <button className="btn btn-ghost" onClick={clearFilters}>Clear all filters</button>
            </div>
          )}
        </>
      )}
    </div>
  );
}


