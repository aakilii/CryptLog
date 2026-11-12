'use client';

import React, { useEffect, useState, useCallback, useRef, useMemo, Suspense } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@operation-room/lib/api';
import dynamic from 'next/dynamic';
import {
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RTooltip,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
  ScatterChart, Scatter, ZAxis,
} from 'recharts';

/* ── Lazy load heavy graph libs ─────────────────────────── */
const ForceGraph3D = dynamic(() => import('react-force-graph-3d'), { ssr: false });

/* ── Constants ────────────────────────────────────── */
const ENTITY_STYLE = {
  USER:        { color: '#2563eb', icon: 'US', shape: 'dot', size: 18 },
  IP:          { color: '#0ea5e9', icon: 'IP', shape: 'diamond', size: 14 },
  HOST:        { color: '#fb7185', icon: 'HO', shape: 'square', size: 16 },
  SESSION:     { color: '#d97706', icon: 'SE', shape: 'triangle', size: 12 },
  DATA_OBJECT: { color: '#059669', icon: 'DO', shape: 'star', size: 14 },
  PROCESS:     { color: '#7c3aed', icon: 'PR', shape: 'dot', size: 12 },
};
const REL_COLORS = {
  PERFORMED: '#2563eb20', AUTHENTICATED_FROM: '#0ea5e940', CONNECTED_TO: '#fb718540',
  USED_SESSION: '#d9770640', ACCESSED: '#05966940', EXECUTED_ON: '#7c3aed40',
};
const mono = { fontFamily: "'JetBrains Mono', monospace" };

const formatGraphEngineLabel = (engine) => {
  const raw = (engine || '').toLowerCase();
  if (!raw) return 'legacy fallback';
  if (raw.includes('neo4j')) return 'Neo4j primary engine';
  if (raw.includes('networkx')) return 'NetworkX fallback';
  if (raw.includes('duckdb')) return 'DuckDB stored graph';
  if (raw.includes('fallback')) return 'Fallback graph path';
  return engine.replace(/_/g, ' ');
};

const formatLayoutLabel = (layout, layoutLabel) => {
  if (layoutLabel) return layoutLabel;
  const raw = (layout || '').toLowerCase();
  if (!raw) return 'browser physics fallback';
  if (raw === 'tree') return 'backend tree layout';
  if (raw === 'force-directed') return 'backend force-directed fallback';
  if (raw === 'grid-fallback') return 'backend grid fallback';
  if (raw === 'empty') return 'empty graph';
  if (raw === 'browser-physics-fallback') return 'browser physics fallback';
  return layout.replace(/_/g, ' ');
};

const formatGraphSourceLabel = (graphData) => graphData?.graph_source_label || 'DuckDB correlation graph';

const toTitle = (value) => (value || '').toString().toUpperCase();

const getGenerationSteps = (engine, graphData) => {
  const selected = (engine || 'duckdb').toLowerCase();
  const status = (graphData?.generation_status || (graphData?.nodes?.length ? 'generated' : 'pending')).toLowerCase();

  if (selected === 'neo4j') {
    return [
      { label: 'Check Neo4j service', state: status === 'generated' ? 'done' : (status === 'error' || status === 'unavailable' ? 'failed' : 'running') },
      { label: 'Retrieve graph subgraph', state: status === 'generated' ? 'done' : (status === 'error' || status === 'unavailable' ? 'failed' : 'pending') },
      { label: 'Apply correlation layout', state: status === 'generated' ? 'done' : 'pending' },
    ];
  }

  if (selected === 'networkx') {
    return [
      { label: 'Load nodes and edges from run', state: status === 'generated' ? 'done' : (status === 'error' ? 'failed' : 'running') },
      { label: 'Build NetworkX graph in memory', state: status === 'generated' ? 'done' : (status === 'error' ? 'failed' : 'pending') },
      { label: 'Apply correlation layout', state: status === 'generated' ? 'done' : 'pending' },
    ];
  }

  return [
    { label: 'Load DuckDB stored graph', state: status === 'generated' ? 'done' : (status === 'error' ? 'failed' : 'running') },
    { label: 'Apply correlation layout', state: status === 'generated' ? 'done' : 'pending' },
  ];
};

const getEdgeSource = (edge) => edge?.source_node_id || edge?.source_id || null;
const getEdgeTarget = (edge) => edge?.target_node_id || edge?.target_id || null;

/* ── Tip ────────────────────────────────────────── */
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

/* ── 2D vis-network Graph ─────────────────────────── */
function VisGraph({ nodes, edges, onSelectNode, compactMode, riskFocusThreshold, graphSource }) {
  const containerRef = useRef(null);
  const networkRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return;

    import('vis-network/standalone').then(({ Network, DataSet }) => {
      const hasPresetLayout = nodes.some(n => Number.isFinite(n.x) && Number.isFinite(n.y));
      const isNetworkxView = (graphSource || '').toLowerCase() === 'networkx';

      const visNodes = new DataSet(nodes.map(n => ({
        ...(function () {
          const severity = Number(n.severity_score || 0);
          const isHighRisk = severity >= riskFocusThreshold;
          return {
            id: n.node_id,
            // Compact mode intentionally suppresses low-risk labels to keep analyst focus on threat hubs.
            label: compactMode && !isHighRisk ? '' : `${n.entity_value || ''}`.slice(0, compactMode ? 20 : 28),
            group: n.entity_type,
            value: Math.max(5, severity * (compactMode ? 52 : 40)),
            x: Number.isFinite(n.x) ? n.x : undefined,
            y: Number.isFinite(n.y) ? n.y : undefined,
            fixed: hasPresetLayout ? { x: true, y: true } : false,
            title: `[${n.entity_type}] ${n.entity_value}\nSeverity: ${severity.toFixed(3)}\nEvents: ${n.event_count}`,
            color: {
              background: ENTITY_STYLE[n.entity_type]?.color || '#666',
              border: isHighRisk ? '#ef4444' : `${ENTITY_STYLE[n.entity_type]?.color || '#666'}`,
              highlight: { background: '#fff', border: isHighRisk ? '#ef4444' : ENTITY_STYLE[n.entity_type]?.color },
            },
            font: {
              color: isHighRisk ? '#fca5a5' : '#1e293b',
              size: isHighRisk ? 12 : 11,
              face: 'JetBrains Mono, monospace',
            },
            borderWidth: isHighRisk ? 5 : (compactMode ? 1 : 2),
            shadow: isHighRisk
              ? { enabled: true, color: 'rgba(239,68,68,0.55)', size: compactMode ? 18 : 14 }
              : false,
          };
        })(),
      })));

      const visEdges = new DataSet(edges.map(e => ({
        from: getEdgeSource(e),
        to: getEdgeTarget(e),
        title: `${e.relationship} (weight: ${e.weight})`,
        value: e.weight,
        color: { color: REL_COLORS[e.relationship] || '#ffffff10', opacity: isNetworkxView ? 0.78 : 0.58 },
        font: { color: '#94a3b8', size: 8, face: 'JetBrains Mono, monospace' },
        arrows: 'to',
        smooth: { type: isNetworkxView ? 'dynamic' : 'curvedCW', roundness: isNetworkxView ? 0.36 : 0.2 },
      })));

      const physicsPreset = isNetworkxView
        ? {
            forceAtlas2Based: { gravitationalConstant: -65, centralGravity: 0.02, springLength: 160 },
            solver: 'forceAtlas2Based',
            stabilization: { iterations: 120 },
            enabled: !hasPresetLayout,
          }
        : {
            forceAtlas2Based: { gravitationalConstant: -80, centralGravity: 0.01, springLength: 190 },
            solver: 'forceAtlas2Based',
            stabilization: { iterations: 100 },
            enabled: !hasPresetLayout,
          };

      const options = {
        physics: physicsPreset,
        nodes: { shape: 'dot', scaling: { min: 9, max: 34 } },
        edges: { width: 0.8, selectionWidth: 3 },
        interaction: { hover: true, tooltipDelay: 200, dragView: true, zoomView: true },
        layout: { improvedLayout: !hasPresetLayout },
      };

      if (networkRef.current) networkRef.current.destroy();
      const net = new Network(containerRef.current, { nodes: visNodes, edges: visEdges }, options);
      networkRef.current = net;

      net.on('click', (e) => {
        if (e.nodes.length > 0) {
          const node = nodes.find(n => n.node_id === e.nodes[0]);
          if (node) onSelectNode(node);
        }
      });
    });

    return () => { if (networkRef.current) networkRef.current.destroy(); };
  }, [nodes, edges, onSelectNode, compactMode, riskFocusThreshold, graphSource]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%', background: '#0a0b1a', borderRadius: 12 }} />;
}

/* ── 3D Force Graph ────────────────────────────────── */
function Graph3D({ nodes, edges, onSelectNode, compactMode, riskFocusThreshold, graphSource }) {
  const graphData = useMemo(() => ({
    nodes: nodes.map(n => ({
      id: n.node_id, name: n.entity_value, group: n.entity_type,
      val: Math.max(1, n.severity_score * 8),
      color: ENTITY_STYLE[n.entity_type]?.color || '#666',
      severity: Number(n.severity_score || 0),
    })),
    links: edges.map(e => ({
      source: getEdgeSource(e), target: getEdgeTarget(e),
      name: e.relationship, value: e.weight,
      color: REL_COLORS[e.relationship] || '#ffffff08',
    })),
  }), [nodes, edges]);

  const isNetworkxView = (graphSource || '').toLowerCase() === 'networkx';

  return (
    <div style={{ width: '100%', height: '100%', borderRadius: 12, overflow: 'hidden', background: '#0a0b1a' }}>
      <Suspense fallback={<div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:'var(--text-muted)'}}>Loading 3D…</div>}>
        <ForceGraph3D
          graphData={graphData}
          nodeLabel={n => {
            const highRisk = Number(n.severity || 0) >= riskFocusThreshold;
            if (compactMode && !highRisk) return '';
            return `[${n.group}] ${n.name}`;
          }}
          nodeColor={n => n.color}
          nodeVal={n => {
            const highRisk = Number(n.severity || 0) >= riskFocusThreshold;
            return highRisk ? n.val * 1.35 : n.val;
          }}
          linkLabel={l => l.name}
          linkColor={l => l.color}
          linkWidth={l => Math.max(0.3, l.value * (isNetworkxView ? 0.45 : 0.3))}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          linkOpacity={isNetworkxView ? 0.56 : 0.4}
          backgroundColor="#0a0b1a"
          onNodeClick={n => {
            const node = nodes.find(nd => nd.node_id === n.id);
            if (node) onSelectNode(node);
          }}
        />
      </Suspense>
    </div>
  );
}

/* ═══════════════════════════════════════════════════ */
export default function CorrelationPage() {
  const { id } = useParams();

  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [narrative, setNarrative] = useState(null);
  const [runs, setRuns] = useState([]);
  const [rules, setRules] = useState([]);
  const [providers, setProviders] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [llmProvider, setLlmProvider] = useState('ollama');
  const [viewMode, setViewMode] = useState('2d');
  const [tab, setTab] = useState('graph');
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [filterType, setFilterType] = useState('all');
  const [filterMinSeverity, setFilterMinSeverity] = useState(0);
  const [narrativeMode, setNarrativeMode] = useState('base');
  const [activeRunId, setActiveRunId] = useState('');
  const [graphEngineView, setGraphEngineView] = useState('duckdb');
  const [engineNotice, setEngineNotice] = useState('');
  const [graphProgressTick, setGraphProgressTick] = useState(0);
  const [neo4jAttempt, setNeo4jAttempt] = useState(0);
  const [compactInvestigatorMode, setCompactInvestigatorMode] = useState(true);
  const [edgeSimplification, setEdgeSimplification] = useState(35);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const selectedRunId = activeRunId || undefined;
      const [g, n, rs, rl, pv] = await Promise.all([
        api.getCorrelationGraph(id, selectedRunId, graphEngineView).catch(() => ({ nodes: [], edges: [] })),
        api.getCorrelationNarrative(id, selectedRunId).catch(() => null),
        api.getCorrelationRuns(id).catch(() => []),
        api.getCorrelationRules(id).catch(() => []),
        api.getCorrelationProviders(id).catch(() => []),
      ]);
      setGraphData(g);
      if (n && !n.error) setNarrative(n);
      setRuns(rs);
      setRules(rl);
      setProviders(pv);

      if (g?.graph_pending) {
        setEngineNotice(g?.progress_message || `Loading ${graphEngineView.toUpperCase()} graph...`);
      } else if (g?.error && !g?.nodes?.length) {
        setEngineNotice(g.error);
      } else {
        setEngineNotice('');
      }
    } catch {} finally { setLoading(false); }
  }, [id, activeRunId, graphEngineView]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (!narrative) return;
    if (narrative.graphrag_narrative) {
      setNarrativeMode('graphrag');
    } else {
      setNarrativeMode('base');
    }
  }, [narrative]);

  useEffect(() => {
    if (!graphData?.graph_pending) return;
    const timer = setInterval(() => {
      setGraphProgressTick(prev => (prev + 1) % 3);
    }, 500);
    return () => clearInterval(timer);
  }, [graphData?.graph_pending]);

  useEffect(() => {
    if (!graphData?.graph_pending) return;
    if (graphEngineView !== 'neo4j') return;
    if (!graphData?.retry_after_ms || graphData.retry_after_ms <= 0) return;

    const retryAfterMs = Math.max(1200, graphData?.retry_after_ms || 3000);
    const timer = setTimeout(() => {
      setNeo4jAttempt(prev => prev + 1);
      loadData();
    }, retryAfterMs);
    return () => clearTimeout(timer);
  }, [graphData?.graph_pending, graphData?.retry_after_ms, graphEngineView, loadData]);

  useEffect(() => {
    if (graphEngineView !== 'neo4j') {
      setNeo4jAttempt(0);
    }
  }, [graphEngineView]);

  const providerOptions = useMemo(() => {
    if (providers?.length > 0) {
      return providers.map(p => ({
        id: p.id,
        label: p.id === 'ollama' ? ' Qwen3 (Local)' : ` ${p.name || p.id}`,
        desc: p.description || 'LLM provider',
        configured: p.configured !== false,
      }));
    }

    return [
      { id: 'ollama', label: ' Qwen3 (Local)', desc: 'Fast, private, no API key', configured: true },
      { id: 'gemini', label: ' Gemini', desc: 'Requires API key in .env', configured: true },
    ];
  }, [providers]);

  const activeRun = useMemo(
    () => runs.find(r => r.run_id === activeRunId) || runs[0] || null,
    [runs, activeRunId]
  );

  const normalizeEngine = useCallback((run) => {
    const raw = (run?.graph_engine_used || '').toLowerCase();
    if (raw.includes('neo4j')) return 'neo4j';
    if (raw.includes('networkx')) return 'networkx';
    return 'other';
  }, []);

  const displayedNarrative = useMemo(() => {
    if (!narrative) return '';
    if (narrativeMode === 'graphrag' && narrative.graphrag_narrative) {
      return narrative.graphrag_narrative;
    }
    return narrative.narrative || '';
  }, [narrative, narrativeMode]);

  useEffect(() => {
    const selected = providerOptions.find(p => p.id === llmProvider);
    if (selected?.configured) return;

    const fallback = providerOptions.find(p => p.configured);
    if (fallback && fallback.id !== llmProvider) {
      setLlmProvider(fallback.id);
    }
  }, [providerOptions, llmProvider]);

  useEffect(() => {
    if (!runs.length) {
      if (activeRunId) setActiveRunId('');
      return;
    }

    const valid = runs.some(r => r.run_id === activeRunId);
    if (!activeRunId || !valid) {
      setActiveRunId(runs[0].run_id);
    }
  }, [runs, activeRunId]);

  const quickPrompts = [
    'What is the most likely entry point?',
    'Show the top 3 risky entities and why',
    'Summarize lateral movement in this run',
    'What should we contain immediately?',
  ];

  const handleEngineSwitch = (engineId) => {
    if (engineId === graphEngineView) return;
    setGraphEngineView(engineId);
    setTab('graph');
    setSelectedNode(null);
    setEngineNotice(engineId === 'neo4j' ? 'Checking Neo4j service...' : `Loading ${engineId.toUpperCase()} graph...`);
    setGraphData({
      nodes: [],
      edges: [],
      graph_source: engineId,
      graph_source_label: engineId === 'duckdb' ? 'DuckDB correlation graph' : engineId === 'neo4j' ? 'Neo4j correlation graph' : 'NetworkX correlation graph',
      graph_pending: true,
      progress_message: engineId === 'neo4j' ? 'Neo4j is starting. Waiting for service readiness...' : `Loading ${engineId.toUpperCase()} graph...`,
      retry_after_ms: engineId === 'neo4j' ? 3000 : 0,
    });
  };

  const handleRun = async () => {
    setRunning(true);
    try {
      await api.runCorrelation(id, { llm_provider: llmProvider });
      await loadData();
    } catch (err) { alert('Correlation failed: ' + err.message); }
    finally { setRunning(false); }
  };

  const handleChat = async () => {
    if (!chatInput.trim()) return;
    const q = chatInput.trim();
    setChatMessages(prev => [...prev, { role: 'user', text: q }]);
    setChatInput('');
    setChatLoading(true);
    try {
      const res = await api.correlationChat(id, { query: q, llm_provider: llmProvider });
      setChatMessages(prev => [...prev, { role: 'agent', text: res.response, provider: res.llm_provider }]);
    } catch (e) {
      setChatMessages(prev => [...prev, { role: 'agent', text: `Error: ${e.message}` }]);
    } finally { setChatLoading(false); }
  };

  const handleToggleRule = async (ruleId, enabled) => {
    await api.toggleCorrelationRule(id, ruleId, { enabled });
    setRules(prev => prev.map(r => r.rule_id === ruleId ? { ...r, enabled } : r));
  };

  // Filtered nodes/edges
  const filteredNodes = useMemo(() => {
    return graphData.nodes?.filter(n => {
      if (filterType !== 'all' && n.entity_type !== filterType) return false;
      if (n.severity_score < filterMinSeverity) return false;
      return true;
    }) || [];
  }, [graphData.nodes, filterType, filterMinSeverity]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map(n => n.node_id)), [filteredNodes]);
  const filteredEdges = useMemo(() => {
    return (graphData.edges || []).filter(e => {
      const source = getEdgeSource(e);
      const target = getEdgeTarget(e);
      return source && target && filteredNodeIds.has(source) && filteredNodeIds.has(target);
    });
  }, [graphData.edges, filteredNodeIds]);

  const riskFocusThreshold = compactInvestigatorMode ? 0.6 : 0.75;

  const simplifiedEdges = useMemo(() => {
    const baseEdges = filteredEdges || [];
    if (!baseEdges.length) return [];

    const simplifyFactor = Math.max(0, Math.min(0.85, edgeSimplification / 100));
    if (simplifyFactor <= 0.01) return baseEdges;

    const highRiskNodeIds = new Set(
      (filteredNodes || [])
        .filter(n => Number(n.severity_score || 0) >= riskFocusThreshold)
        .map(n => n.node_id)
    );

    const ranked = baseEdges
      .map(e => {
        const source = getEdgeSource(e);
        const target = getEdgeTarget(e);
        const touchesHighRisk = highRiskNodeIds.has(source) || highRiskNodeIds.has(target);
        return {
          ...e,
          __score: Number(e.weight || 0) + (touchesHighRisk ? 0.35 : 0),
        };
      })
      .sort((a, b) => b.__score - a.__score);

    const baseKeepRatio = 1 - simplifyFactor * 0.75;
    const keepCount = Math.max(Math.min(baseEdges.length, 24), Math.round(baseEdges.length * baseKeepRatio));
    const kept = ranked.slice(0, keepCount);

    const covered = new Set();
    kept.forEach(e => {
      covered.add(getEdgeSource(e));
      covered.add(getEdgeTarget(e));
    });

    if (highRiskNodeIds.size > 0) {
      highRiskNodeIds.forEach(nodeId => {
        if (covered.has(nodeId)) return;
        const supporting = ranked.find(e => getEdgeSource(e) === nodeId || getEdgeTarget(e) === nodeId);
        if (supporting) kept.push(supporting);
      });
    }

    const dedup = new Map();
    kept.forEach(e => {
      const key = `${e.edge_id || ''}:${getEdgeSource(e) || ''}:${getEdgeTarget(e) || ''}:${e.relationship || ''}`;
      if (!dedup.has(key)) {
        const { __score, ...rest } = e;
        dedup.set(key, rest);
      }
    });

    return Array.from(dedup.values());
  }, [filteredEdges, filteredNodes, edgeSimplification, riskFocusThreshold]);

  const renderedNodes = useMemo(() => {
    if (!compactInvestigatorMode) return filteredNodes;
    const connected = new Set();
    (simplifiedEdges || []).forEach(e => {
      connected.add(getEdgeSource(e));
      connected.add(getEdgeTarget(e));
    });
    return (filteredNodes || []).filter(n => connected.has(n.node_id) || Number(n.severity_score || 0) >= riskFocusThreshold);
  }, [compactInvestigatorMode, filteredNodes, simplifiedEdges, riskFocusThreshold]);

  const TABS = [
    { id: 'graph',     icon: 'GR', label: 'Entity Graph' },
    { id: 'analytics', icon: 'AN', label: 'Analytics' },
    { id: 'narrative', icon: 'AI', label: 'AI Narrative' },
    { id: 'chat',      icon: 'CH', label: 'Ask AI' },
    { id: 'rules',     icon: 'RL', label: 'Rules' },
    { id: 'history',   icon: 'RN', label: 'Runs' },
  ];

  // Chart data computations
  const entityTypeData = useMemo(() => {
    const counts = {};
    (graphData.nodes || []).forEach(n => { counts[n.entity_type] = (counts[n.entity_type] || 0) + 1; });
    return Object.entries(counts).map(([type, value]) => ({ name: type, value }));
  }, [graphData.nodes]);

  const severityBuckets = useMemo(() => {
    const buckets = [
      { range: '0.0-0.2', min: 0, max: 0.2, count: 0, color: '#059669' },
      { range: '0.2-0.4', min: 0.2, max: 0.4, count: 0, color: '#0ea5e9' },
      { range: '0.4-0.6', min: 0.4, max: 0.6, count: 0, color: '#d97706' },
      { range: '0.6-0.8', min: 0.6, max: 0.8, count: 0, color: '#ea580c' },
      { range: '0.8-1.0', min: 0.8, max: 1.0, count: 0, color: '#dc2626' },
    ];
    (graphData.nodes || []).forEach(n => {
      const s = n.severity_score || 0;
      const b = buckets.find(b => s >= b.min && s < b.max) || buckets[buckets.length - 1];
      b.count++;
    });
    return buckets;
  }, [graphData.nodes]);

  const topEntities = useMemo(() => {
    return [...(graphData.nodes || [])]
      .sort((a, b) => (b.severity_score || 0) - (a.severity_score || 0))
      .slice(0, 12)
      .map(n => ({
        name: `${ENTITY_STYLE[n.entity_type]?.icon || ''} ${n.entity_value}`,
        severity: +(n.severity_score || 0).toFixed(3),
        events: n.event_count || 0,
        type: n.entity_type,
      }));
  }, [graphData.nodes]);

  const entityScatterData = useMemo(() => {
    return (graphData.nodes || []).map(n => ({
      name: n.entity_value,
      type: n.entity_type,
      events: n.event_count || 0,
      severity: +(n.severity_score || 0).toFixed(3),
      anomaly: +(n.anomaly_score || 0).toFixed(3),
    }));
  }, [graphData.nodes]);

  const graphEngineLabel = formatGraphEngineLabel(graphData.graph_engine_used || narrative?.graph_engine_used || activeRun?.graph_engine_used);
  const graphLayoutLabel = formatLayoutLabel(graphData.layout, graphData.layout_label);
  const graphSourceLabel = formatGraphSourceLabel(graphData);
  const loadingDots = '.'.repeat(graphProgressTick + 1);
  const selectedSource = (graphEngineView || 'duckdb').toLowerCase();
  const actualSource = (graphData?.graph_source || '').toLowerCase();
  const sourceMismatch = Boolean(actualSource) && selectedSource !== actualSource;
  const generationStatus = (graphData?.generation_status || (graphData?.graph_pending ? 'pending' : (filteredNodes.length > 0 ? 'generated' : 'error'))).toLowerCase();
  
  // Safety override: If valid nodes exist for the requested engine (or fallback), always unblock the graph UI.
  const hasNodes = Array.isArray(graphData?.nodes) && graphData.nodes.length > 0;
  const isErrorState = generationStatus === 'error' || graphData?.error;
  const forceShowGraph = hasNodes && !sourceMismatch;
  const resolveProcessState = forceShowGraph ? false : (sourceMismatch || generationStatus === 'pending' || graphData?.graph_pending);
  const showProcessState = resolveProcessState && (!isErrorState || sourceMismatch);
  
  const effectiveGenerationStatus = sourceMismatch ? 'error' : generationStatus;
  const generationSteps = getGenerationSteps(selectedSource, { ...graphData, generation_status: effectiveGenerationStatus });
  const generationMessage =
    graphData?.generation_message ||
    graphData?.progress_message ||
    (sourceMismatch
      ? `Requested ${toTitle(selectedSource)} graph; received ${toTitle(actualSource)}.`
      : `Generating ${toTitle(selectedSource)} graph${loadingDots}`);
  const sourceVisualProfile = selectedSource === 'networkx'
    ? 'NetworkX focused threat channels'
    : selectedSource === 'neo4j'
      ? 'Neo4j live relationship graph'
      : 'DuckDB full correlation graph';
  const neo4jDiagnostics = graphData?.neo4j_diagnostics || null;
  const neo4jCommands = Array.isArray(neo4jDiagnostics?.start_command_candidates)
    ? neo4jDiagnostics.start_command_candidates
    : [];

  return (
    <div style={{ maxWidth: 1500, margin: '0 auto' }}>
      {/* ── Header ─────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, paddingBottom: 16, borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.04em',
            color: '#1e293b' }}>
             Correlation & Root-Cause Analysis
          </h1>
          <div style={{ ...mono, fontSize: 11, marginTop: 4, color: 'var(--text-muted)' }}>
            <Tip text="6-node pipeline: LoadEnrichedData → ExtractEntities → BuildGraph → ScoreEntities → GenerateNarrative → StoreAndAudit">
              LangGraph 6-Node Pipeline
            </Tip>
            <span style={{ opacity: 0.3, margin: '0 8px' }}>·</span>
            <Tip text="Entity graph with users, IPs, hosts, sessions, data objects — linked by join rules">
              Entity Graph
            </Tip>
            <span style={{ opacity: 0.3, margin: '0 8px' }}>·</span>
            <Tip text="AI generates structured root-cause narrative with MITRE ATT&CK tactic mapping">
              MITRE ATT&CK Mapping
            </Tip>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link href={`/cases/${id}/anomalies`} className="btn btn-ghost"> Anomalies</Link>
          <Link href={`/cases/${id}/timeline`} className="btn btn-ghost"> Timeline</Link>
          <Link href={`/cases/${id}`} className="btn btn-ghost">← Case</Link>
        </div>
      </div>

      {/* ── Config Panel ──────────────────────── */}
      <div style={{ ...card('#2563eb'), marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <label style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
              <Tip text="Switch between local Ollama (Qwen3) and Google Gemini API">LLM Provider ⓘ</Tip>
            </label>
            <div style={{ display: 'flex', gap: 6 }}>
              {providerOptions.map(p => (
                <button key={p.id} onClick={() => setLlmProvider(p.id)} disabled={!p.configured} style={{
                  padding: '6px 14px', borderRadius: 8, fontSize: 11, fontWeight: 700, cursor: 'pointer',
                  background: llmProvider === p.id ? 'rgba(37,99,235,0.06)' : 'transparent',
                  border: `1px solid ${llmProvider === p.id ? '#2563eb' : 'var(--border-color)'}`,
                  color: llmProvider === p.id ? '#2563eb' : 'var(--text-muted)',
                  opacity: p.configured ? 1 : 0.45,
                  transition: 'all 0.2s',
                }}>
                  <Tip text={p.desc}>{p.label}</Tip>
                </button>
              ))}
            </div>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <button className="btn btn-primary" onClick={handleRun} disabled={running} style={{ padding: '10px 22px', fontSize: 13, fontWeight: 700 }}>
              {running ? 'Building graph and narrative...' : 'Run Correlation Analysis'}
            </button>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, marginTop: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ ...mono, fontSize: 10, color: 'var(--text-muted)' }}>Active Run</label>
          <select
            value={activeRunId}
            onChange={e => setActiveRunId(e.target.value)}
            className="form-input"
            style={{ minWidth: 260, fontSize: 11, padding: '8px 10px' }}
          >
            {(runs || []).map(run => (
              <option key={run.run_id} value={run.run_id}>
                {run.run_id?.slice(0, 8)} • {run.status} • {run.llm_provider || 'ollama'}
              </option>
            ))}
          </select>
          {activeRun && (
            <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)' }}>
              Nodes: {activeRun.total_nodes ?? '—'} | Edges: {activeRun.total_edges ?? '—'} | Started: {activeRun.started_at ? new Date(activeRun.started_at).toLocaleString() : '—'}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ ...mono, fontSize: 10, color: 'var(--text-muted)' }}>Graph Source</label>
          {[
            { id: 'duckdb', label: 'DuckDB' },
            { id: 'neo4j', label: 'Neo4j' },
            { id: 'networkx', label: 'NetworkX' },
          ].map(opt => (
            <button
              key={opt.id}
              onClick={() => handleEngineSwitch(opt.id)}
              style={{
                padding: '4px 10px', borderRadius: 6, fontSize: 10, fontWeight: 700, cursor: 'pointer',
                background: graphEngineView === opt.id ? 'rgba(37,99,235,0.08)' : 'transparent',
                border: `1px solid ${graphEngineView === opt.id ? '#2563eb' : 'var(--border-color)'}`,
                color: graphEngineView === opt.id ? '#2563eb' : 'var(--text-muted)',
              }}
            >
              {opt.label}
            </button>
          ))}
          {engineNotice && (
            <span style={{ ...mono, fontSize: 10, color: '#b45309' }}>{engineNotice}</span>
          )}
        </div>
      </div>

      {/* ── Tabs ─────────────────────────────── */}
      <div className="tl-view-tabs" style={{ marginBottom: 16 }}>
        {TABS.map(t => (
          <button key={t.id} className={`tl-view-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
            <span className="tab-icon">{t.icon}</span>{t.label}
          </button>
        ))}
      </div>

      {/* ═══ TAB: GRAPH ═══ */}
      {tab === 'graph' && (
        <div style={{ display: 'grid', gridTemplateColumns: selectedNode ? '1fr 320px' : '1fr', gap: 14 }}>
          <div>
            {/* Toolbar */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <Tip text="Switch between 2D force-directed (vis-network) and 3D WebGL (react-force-graph)"><span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>VIEW ⓘ</span></Tip>
              {[{ id: '2d', label: '2D Graph' }, { id: '3d', label: '3D Graph' }].map(v => (
                <button key={v.id} onClick={() => setViewMode(v.id)} style={{
                  padding: '4px 10px', borderRadius: 6, fontSize: 10, fontWeight: 700, cursor: 'pointer',
                  background: viewMode === v.id ? 'rgba(37,99,235,0.06)' : 'transparent',
                  border: `1px solid ${viewMode === v.id ? '#2563eb' : 'var(--border-color)'}`,
                  color: viewMode === v.id ? '#2563eb' : 'var(--text-muted)',
                }}>{v.label}</button>
              ))}
              <span style={{ opacity: 0.2 }}>|</span>
              <Tip text="Filter graph to show only specific entity types"><span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>FILTER ⓘ</span></Tip>
              {['all', ...Object.keys(ENTITY_STYLE)].map(t => (
                <button key={t} onClick={() => setFilterType(t)} style={{
                  padding: '3px 8px', borderRadius: 999, fontSize: 9, fontWeight: 700, cursor: 'pointer',
                  background: filterType === t ? (t === 'all' ? 'rgba(255,255,255,0.1)' : `${ENTITY_STYLE[t]?.color}20`) : 'transparent',
                  border: `1px solid ${filterType === t ? (t === 'all' ? '#fff' : ENTITY_STYLE[t]?.color) : 'transparent'}`,
                  color: t === 'all' ? '#fff' : ENTITY_STYLE[t]?.color,
                }}>{t === 'all' ? 'All' : `${ENTITY_STYLE[t]?.icon} ${t}`}</button>
              ))}
              <span style={{ opacity: 0.2 }}>|</span>
              <Tip text="Hide low-severity nodes">
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>Min Severity:</span>
              </Tip>
              <input type="range" min="0" max="1" step="0.05" value={filterMinSeverity}
                onChange={e => setFilterMinSeverity(parseFloat(e.target.value))}
                style={{ width: 80, accentColor: '#2563eb' }} />
              <span style={{ ...mono, fontSize: 10, color: '#2563eb' }}>{filterMinSeverity.toFixed(2)}</span>
              <span style={{ opacity: 0.2 }}>|</span>
              <button
                onClick={() => setCompactInvestigatorMode(prev => !prev)}
                style={{
                  padding: '4px 10px', borderRadius: 6, fontSize: 10, fontWeight: 700, cursor: 'pointer',
                  background: compactInvestigatorMode ? 'rgba(220,38,38,0.1)' : 'transparent',
                  border: `1px solid ${compactInvestigatorMode ? '#dc2626' : 'var(--border-color)'}`,
                  color: compactInvestigatorMode ? '#b91c1c' : 'var(--text-muted)',
                }}
              >
                Compact Investigator: {compactInvestigatorMode ? 'ON' : 'OFF'}
              </button>
              <Tip text="Reduce edge noise while preserving high-risk paths.">
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>Edge Simplification:</span>
              </Tip>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={edgeSimplification}
                onChange={e => setEdgeSimplification(parseInt(e.target.value, 10))}
                style={{ width: 90, accentColor: '#dc2626' }}
              />
              <span style={{ ...mono, fontSize: 10, color: '#dc2626' }}>{edgeSimplification}%</span>
              <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>{renderedNodes.length} nodes · {simplifiedEdges.length} edges</span>
            </div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
              <span style={{ ...mono, fontSize: 10, padding: '3px 8px', borderRadius: 999, background: 'rgba(37,99,235,0.08)', color: '#1d4ed8', border: '1px solid rgba(37,99,235,0.25)' }}>
                Source: {graphSourceLabel}
              </span>
              <span style={{ ...mono, fontSize: 10, padding: '3px 8px', borderRadius: 999, background: 'rgba(14,165,233,0.08)', color: '#0369a1', border: '1px solid rgba(14,165,233,0.25)' }}>
                Layout: {graphLayoutLabel}
              </span>
              <span style={{ ...mono, fontSize: 10, padding: '3px 8px', borderRadius: 999, background: 'rgba(5,150,105,0.08)', color: '#065f46', border: '1px solid rgba(5,150,105,0.25)' }}>
                Path Nodes: {graphData.path_count || 0}
              </span>
              <span style={{ ...mono, fontSize: 10, padding: '3px 8px', borderRadius: 999, background: 'rgba(37,99,235,0.08)', color: '#1d4ed8', border: '1px solid rgba(37,99,235,0.25)' }}>
                Engine: {graphEngineLabel}
              </span>
              <span style={{ ...mono, fontSize: 10, padding: '3px 8px', borderRadius: 999, background: 'rgba(220,38,38,0.08)', color: '#b91c1c', border: '1px solid rgba(220,38,38,0.25)' }}>
                Profile: {sourceVisualProfile}
              </span>
            </div>
            {graphData.graph_fallback_reason && (
              <div style={{ ...mono, fontSize: 10, color: '#b45309', marginBottom: 8 }}>
                {graphData.graph_fallback_reason}
              </div>
            )}
            {graphData.graph_pending && (
              <div style={{ ...mono, fontSize: 10, color: '#0369a1', marginBottom: 8 }}>
                {(graphData.progress_message || 'Preparing graph') + loadingDots}
              </div>
            )}
            {graphData.graph_source_requested_label && graphData.graph_source_requested_label !== graphSourceLabel && (
              <div style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', marginBottom: 8 }}>
                Requested: {graphData.graph_source_requested_label}
              </div>
            )}
            {/* Graph */}
            <div style={{ height: 520, borderRadius: 12, overflow: 'hidden', border: '1px solid var(--border-color)' }}>
              {showProcessState ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#cbd5e1', background: '#0a0b1a' }}>
                  <div style={{ textAlign: 'center', maxWidth: 520, padding: '0 20px' }}>
                    <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>
                      {generationMessage}
                    </div>
                    <div style={{ ...mono, fontSize: 11, color: '#94a3b8', marginBottom: 10 }}>
                      {sourceMismatch
                        ? 'Fallback graph display is blocked. Neo4j or strict-source backend support is not active on the running server.'
                        : 'Showing source generation process until graph is ready.'}
                    </div>
                    {graphEngineView === 'neo4j' && (
                      <div style={{ ...mono, fontSize: 10, color: '#93c5fd', marginBottom: 10 }}>
                        Live Neo4j refresh attempts: {neo4jAttempt}
                      </div>
                    )}
                    {graphEngineView === 'neo4j' && neo4jDiagnostics && (
                      <div style={{ textAlign: 'left', margin: '0 auto 10px', maxWidth: 440, background: 'rgba(2,6,23,0.55)', border: '1px solid rgba(148,163,184,0.2)', borderRadius: 10, padding: 10 }}>
                        <div style={{ ...mono, fontSize: 10, color: '#93c5fd', marginBottom: 6 }}>
                          Neo4j diagnostics: {neo4jDiagnostics.host || 'localhost'}:{neo4jDiagnostics.port || 7687}
                        </div>
                        <div style={{ ...mono, fontSize: 10, color: '#cbd5e1' }}>
                          Bolt port open: {neo4jDiagnostics.bolt_port_open ? 'yes' : 'no'}
                        </div>
                        <div style={{ ...mono, fontSize: 10, color: '#cbd5e1' }}>
                          Python neo4j driver: {neo4jDiagnostics.neo4j_python_driver_installed ? 'installed' : 'missing'}
                        </div>
                        <div style={{ ...mono, fontSize: 10, color: '#cbd5e1' }}>
                          Local startup paths found: {neo4jCommands.length}
                        </div>
                        {neo4jCommands.length > 0 && (
                          <div style={{ ...mono, fontSize: 10, color: '#94a3b8', marginTop: 4 }}>
                            First command: {neo4jCommands[0]}
                          </div>
                        )}
                        {neo4jDiagnostics.last_error && (
                          <div style={{ ...mono, fontSize: 10, color: '#fca5a5', marginTop: 4 }}>
                            Last error: {neo4jDiagnostics.last_error}
                          </div>
                        )}
                      </div>
                    )}
                    <div style={{ textAlign: 'left', margin: '0 auto', maxWidth: 440, background: 'rgba(15,23,42,0.55)', border: '1px solid rgba(148,163,184,0.2)', borderRadius: 10, padding: 12 }}>
                      {generationSteps.map((step) => (
                        <div key={step.label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                          <span style={{ width: 8, height: 8, borderRadius: '50%', background: step.state === 'done' ? '#10b981' : step.state === 'failed' ? '#ef4444' : step.state === 'running' ? '#3b82f6' : '#64748b' }} />
                          <span style={{ ...mono, fontSize: 11, color: '#cbd5e1' }}>{step.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ) : filteredNodes.length > 0 ? (
                viewMode === '2d'
                  ? <VisGraph
                      nodes={renderedNodes}
                      edges={simplifiedEdges}
                      onSelectNode={setSelectedNode}
                      compactMode={compactInvestigatorMode}
                      riskFocusThreshold={riskFocusThreshold}
                      graphSource={selectedSource}
                    />
                  : <Graph3D
                      nodes={renderedNodes}
                      edges={simplifiedEdges}
                      onSelectNode={setSelectedNode}
                      compactMode={compactInvestigatorMode}
                      riskFocusThreshold={riskFocusThreshold}
                      graphSource={selectedSource}
                    />
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', background: '#0a0b1a' }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>GR</div>
                    <p>{graphData?.error || 'Run correlation analysis to build the entity graph'}</p>
                  </div>
                </div>
              )}
            </div>
            {/* Legend */}
            <div style={{ display: 'flex', gap: 16, marginTop: 10, flexWrap: 'wrap' }}>
              {Object.entries(ENTITY_STYLE).map(([type, s]) => (
                <Tip key={type} text={`${type}: ${s.icon} entities in the graph`}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: s.color }} />
                    <span style={{ fontSize: 10, fontWeight: 600, color: s.color }}>{type}</span>
                  </div>
                </Tip>
              ))}
            </div>
          </div>

          {/* Node Detail Panel */}
          {selectedNode && (
            <div style={{ ...card('#2563eb'), height: 'fit-content', maxHeight: 560, overflowY: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Entity Details</h4>
                <button onClick={() => setSelectedNode(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 12 }}>Close</button>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
                <span style={{ fontSize: 28 }}>{ENTITY_STYLE[selectedNode.entity_type]?.icon}</span>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: ENTITY_STYLE[selectedNode.entity_type]?.color }}>{selectedNode.entity_value}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{selectedNode.entity_type}</div>
                </div>
              </div>
              {[
                { label: 'Severity', value: selectedNode.severity_score?.toFixed(4), color: selectedNode.severity_score > 0.5 ? '#dc2626' : '#059669' },
                { label: 'Anomaly Score', value: selectedNode.anomaly_score?.toFixed(4), color: '#d97706' },
                { label: 'Event Count', value: selectedNode.event_count, color: '#2563eb' },
                { label: 'First Seen', value: selectedNode.first_seen?.slice(0, 19) },
                { label: 'Last Seen', value: selectedNode.last_seen?.slice(0, 19) },
              ].map(item => (
                <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid rgba(148,163,184,0.06)' }}>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.label}</span>
                  <span style={{ ...mono, fontSize: 11, fontWeight: 700, color: item.color || 'var(--text-primary)' }}>{item.value || '—'}</span>
                </div>
              ))}
              {selectedNode.metadata?.actions && (
                <div style={{ marginTop: 10 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>Actions</div>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {selectedNode.metadata.actions.map(a => (
                      <span key={a} style={{ padding: '2px 6px', borderRadius: 4, fontSize: 9, fontWeight: 600, background: 'rgba(129,140,248,0.1)', color: '#2563eb' }}>{a}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ═══ TAB: ANALYTICS ═══ */}
      {tab === 'analytics' && graphData.nodes?.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          {/* Entity Type Donut */}
          <div style={card('#2563eb')}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              <Tip text="Distribution of entity types in the correlation graph. Imbalances may indicate incomplete log coverage.">Entity Type Distribution ⓘ</Tip>
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={entityTypeData} cx="50%" cy="50%" innerRadius={50} outerRadius={80}
                  paddingAngle={3} dataKey="value" stroke="none" animationDuration={800}>
                  {entityTypeData.map(d => <Cell key={d.name} fill={ENTITY_STYLE[d.name]?.color || '#666'} />)}
                </Pie>
                <RTooltip content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: ENTITY_STYLE[d.name]?.color }}>{ENTITY_STYLE[d.name]?.icon} {d.name}</div>
                      <div style={{ fontSize: 10, color: '#3b82f6' }}>{d.value} entities</div>
                    </div>
                  );
                }} />
                <text x="50%" y="46%" textAnchor="middle" fill="#1e293b" style={{ fontSize: 20, fontWeight: 800, fontFamily: 'JetBrains Mono' }}>{graphData.nodes?.length || 0}</text>
                <text x="50%" y="56%" textAnchor="middle" fill="#94a3b8" style={{ fontSize: 9, fontWeight: 600 }}>ENTITIES</text>
              </PieChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
              {entityTypeData.map(d => (
                <span key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9, color: ENTITY_STYLE[d.name]?.color }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: ENTITY_STYLE[d.name]?.color }} />
                  {d.name} ({d.value})
                </span>
              ))}
            </div>
          </div>

          {/* Severity Distribution Histogram */}
          <div style={card('#dc2626')}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              <Tip text="How entities distribute across severity ranges. High-severity entities (0.6+) require immediate attention.">Severity Distribution ⓘ</Tip>
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={severityBuckets} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                <XAxis dataKey="range" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <RTooltip content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: d.color }}>Severity {d.range}</div>
                      <div style={{ fontSize: 10, color: '#3b82f6' }}>{d.count} entities</div>
                    </div>
                  );
                }} />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} animationDuration={600} name="Entities">
                  {severityBuckets.map((b, i) => <Cell key={i} fill={b.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Top Entities by Severity (horizontal bar) */}
          <div style={{ ...card('#0ea5e9'), gridColumn: '1 / -1' }}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              <Tip text="The most severe entities in the graph. Investigate these first — they're connected to the most suspicious activity.">Top Entities by Severity ⓘ</Tip>
            </h3>
            <ResponsiveContainer width="100%" height={Math.max(200, topEntities.length * 28)}>
              <BarChart data={topEntities} layout="vertical" margin={{ left: 120, right: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                <XAxis type="number" domain={[0, 1]} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#1e293b', fontSize: 10, fontWeight: 600 }} width={120} />
                <RTooltip content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: ENTITY_STYLE[d.type]?.color }}>{d.name}</div>
                      <div style={{ fontSize: 10, color: '#3b82f6' }}>Severity: <strong>{d.severity}</strong></div>
                      <div style={{ fontSize: 10, color: '#3b82f6' }}>Events: <strong>{d.events}</strong></div>
                    </div>
                  );
                }} />
                <Bar dataKey="severity" radius={[0, 6, 6, 0]} animationDuration={800} name="Severity">
                  {topEntities.map((d, i) => <Cell key={i} fill={ENTITY_STYLE[d.type]?.color || '#2563eb'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Entity Scatter: Events vs Severity */}
          <div style={{ ...card('#059669'), gridColumn: '1 / -1' }}>
            <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 8 }}>
              <Tip text="Each dot is one entity. X = event count, Y = severity. Top-right = high-activity + high-severity entities. Size = anomaly score.">Entity Risk Scatter ⓘ</Tip>
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                <XAxis type="number" dataKey="events" name="Events" tick={{ fill: '#94a3b8', fontSize: 10 }}
                  label={{ value: 'Event Count', position: 'bottom', fill: '#94a3b8', fontSize: 10, offset: -5 }} />
                <YAxis type="number" dataKey="severity" name="Severity" domain={[0, 1]} tick={{ fill: '#94a3b8', fontSize: 10 }}
                  label={{ value: 'Severity', angle: -90, position: 'insideLeft', fill: '#94a3b8', fontSize: 10 }} />
                <ZAxis type="number" dataKey="anomaly" range={[30, 300]} name="Anomaly" />
                <RTooltip content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload;
                  return (
                    <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: ENTITY_STYLE[d.type]?.color }}>{ENTITY_STYLE[d.type]?.icon} {d.name}</div>
                      <div style={{ fontSize: 10, color: '#3b82f6' }}>Type: {d.type}</div>
                      <div style={{ fontSize: 10, color: '#3b82f6' }}>Events: <strong>{d.events}</strong></div>
                      <div style={{ fontSize: 10, color: '#3b82f6' }}>Severity: <strong>{d.severity}</strong></div>
                      <div style={{ fontSize: 10, color: '#3b82f6' }}>Anomaly: <strong>{d.anomaly}</strong></div>
                    </div>
                  );
                }} />
                <Scatter data={entityScatterData} animationDuration={600}>
                  {entityScatterData.map((d, i) => (
                    <Cell key={i} fill={ENTITY_STYLE[d.type]?.color || '#2563eb'} fillOpacity={0.7} />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 6 }}>
              {Object.entries(ENTITY_STYLE).map(([type, s]) => (
                <span key={type} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 9 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: s.color }} />
                  <span style={{ color: s.color }}>{type}</span>
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ═══ TAB: NARRATIVE ═══ */}
      {tab === 'narrative' && (
        <div style={card('#0ea5e9')}>
          {narrative ? (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <h3 style={{ fontSize: 14, fontWeight: 800, color: '#1e293b' }}>Root-Cause Analysis Narrative</h3>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ ...mono, fontSize: 10, padding: '2px 8px', borderRadius: 6, background: 'rgba(129,140,248,0.1)', color: '#2563eb' }}>
                    {narrative.llm_provider || 'ollama'}
                  </span>
                  <span style={{ ...mono, fontSize: 10, padding: '2px 8px', borderRadius: 6, background: 'rgba(5,150,105,0.08)', color: '#065f46' }}>
                    {formatGraphEngineLabel(narrative.graph_engine_used || graphData.graph_engine_used || activeRun?.graph_engine_used)}
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, gap: 12, flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    onClick={() => setNarrativeMode('graphrag')}
                    disabled={!narrative.graphrag_narrative}
                    style={{
                      padding: '5px 10px', borderRadius: 8, fontSize: 10, fontWeight: 700, cursor: 'pointer',
                      background: narrativeMode === 'graphrag' ? 'rgba(14,165,233,0.12)' : 'transparent',
                      border: `1px solid ${narrativeMode === 'graphrag' ? '#0284c7' : 'var(--border-color)'}`,
                      color: narrativeMode === 'graphrag' ? '#0369a1' : 'var(--text-muted)',
                      opacity: narrative.graphrag_narrative ? 1 : 0.45,
                    }}
                  >
                    GraphRAG Narrative
                  </button>
                  <button
                    onClick={() => setNarrativeMode('base')}
                    style={{
                      padding: '5px 10px', borderRadius: 8, fontSize: 10, fontWeight: 700, cursor: 'pointer',
                      background: narrativeMode === 'base' ? 'rgba(37,99,235,0.12)' : 'transparent',
                      border: `1px solid ${narrativeMode === 'base' ? '#1d4ed8' : 'var(--border-color)'}`,
                      color: narrativeMode === 'base' ? '#1d4ed8' : 'var(--text-muted)',
                    }}
                  >
                    Base Narrative
                  </button>
                </div>
                <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)' }}>
                  Computed: {narrative.last_computed_at ? new Date(narrative.last_computed_at).toLocaleString() : '—'}
                </span>
              </div>
              {/* MITRE Tactics chips */}
              {narrative.mitre_tactics?.length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>MITRE ATT&CK Tactics</div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {narrative.mitre_tactics.map(t => (
                      <Tip key={t} text={`MITRE ATT&CK tactic detected in event actions`}>
                        <span style={{ padding: '3px 10px', borderRadius: 999, fontSize: 10, fontWeight: 700, background: 'rgba(248,113,113,0.1)', color: '#dc2626', border: '1px solid rgba(248,113,113,0.2)' }}>{t}</span>
                      </Tip>
                    ))}
                  </div>
                </div>
              )}
              {/* Narrative text */}
              <div style={{ padding: '16px 20px', borderRadius: 10, background: 'rgba(0,0,0,0.015)', border: '1px solid var(--border-color)', fontSize: 13, lineHeight: 1.8, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap' }}>
                {displayedNarrative}
              </div>
              {/* Recommendations */}
              {narrative.recommendations?.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 8, textTransform: 'uppercase' }}>Recommendations</div>
                  {narrative.recommendations.map((r, i) => (
                    <div key={i} style={{ display: 'flex', gap: 8, padding: '8px 12px', marginBottom: 6, borderRadius: 8, background: 'rgba(52,211,153,0.04)', borderLeft: '3px solid #059669' }}>
                      <span style={{ color: '#059669', fontWeight: 700, fontSize: 12 }}>{i + 1}.</span>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{r}</span>
                    </div>
                  ))}
                </div>
              )}
              <div style={{ marginTop: 12, ...mono, fontSize: 10, color: 'var(--text-muted)' }}>
                Hash: {narrative.hash_value?.slice(0, 16)}… | Generated: {narrative.created_at ? new Date(narrative.created_at).toLocaleString() : '—'}
              </div>
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 48, marginBottom: 12, opacity: 0.3 }}>AI</div>
              <p>Run correlation analysis to generate the AI narrative</p>
            </div>
          )}
        </div>
      )}

      {/* ═══ TAB: CHAT ═══ */}
      {tab === 'chat' && (
        <div style={card('#059669')}>
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>Ask the AI Agent</h3>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 14 }}>
            Ask questions about the case: &quot;Why is user X flagged?&quot;, &quot;What happened after 14:05?&quot;, &quot;Show lateral movement&quot;
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 400, overflowY: 'auto', marginBottom: 14, paddingRight: 4 }}>
            {chatMessages.length === 0 && (
              <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)', opacity: 0.5, fontSize: 12 }}>
                Start a conversation with the forensic AI agent
              </div>
            )}
            {chatMessages.map((m, i) => (
              <div key={i} style={{
                padding: '10px 14px', borderRadius: 10, maxWidth: '80%', fontSize: 12, lineHeight: 1.6, whiteSpace: 'pre-wrap',
                ...(m.role === 'user'
                  ? { alignSelf: 'flex-end', background: 'rgba(37,99,235,0.06)', color: '#1e293b', borderBottomRightRadius: 2 }
                  : { alignSelf: 'flex-start', background: 'rgba(52,211,153,0.06)', color: 'var(--text-secondary)', borderBottomLeftRadius: 2, border: '1px solid rgba(52,211,153,0.1)' }),
              }}>
                {m.role === 'agent' && <span style={{ fontSize: 9, fontWeight: 700, color: '#059669', display: 'block', marginBottom: 4 }}>{m.provider || 'AI'}</span>}
                {m.text}
              </div>
            ))}
            {chatLoading && <div style={{ padding: 10, fontSize: 12, color: '#2563eb' }}>⟳ Thinking…</div>}
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
            {quickPrompts.map(prompt => (
              <button
                key={prompt}
                className="btn btn-ghost"
                onClick={() => setChatInput(prompt)}
                style={{ fontSize: 10, padding: '5px 8px' }}
              >
                {prompt}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <input value={chatInput} onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleChat()}
              placeholder="Ask about the case…" className="form-input"
              style={{ flex: 1, padding: '10px 14px', fontSize: 12 }} />
            <button className="btn btn-primary" onClick={handleChat} disabled={chatLoading} style={{ padding: '10px 18px' }}>
              Send
            </button>
          </div>
        </div>
      )}

      {/* ═══ TAB: RULES ═══ */}
      {tab === 'rules' && (
        <div style={card('#d97706')}>
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 14 }}>
            <Tip text="Pluggable join rules determine how entities are linked. Enable/disable rules to change what connections appear in the graph."> Correlation Rules ⓘ</Tip>
          </h3>
          {rules.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {rules.map(r => (
                <div key={r.rule_id} style={{
                  display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderRadius: 10,
                  background: r.enabled ? 'rgba(251,191,36,0.04)' : 'rgba(0,0,0,0.015)',
                  border: `1px solid ${r.enabled ? 'rgba(251,191,36,0.15)' : 'var(--border-color)'}`,
                }}>
                  <button onClick={() => handleToggleRule(r.rule_id, !r.enabled)} style={{
                    width: 36, height: 20, borderRadius: 10, border: 'none', cursor: 'pointer', position: 'relative',
                    background: r.enabled ? '#059669' : '#475569', transition: 'background 0.2s',
                  }}>
                    <span style={{
                      position: 'absolute', top: 2, left: r.enabled ? 18 : 2,
                      width: 16, height: 16, borderRadius: '50%', background: '#fff',
                      transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                    }} />
                  </button>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: r.enabled ? 'var(--text-primary)' : 'var(--text-muted)' }}>{r.name}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{r.description}</div>
                  </div>
                  <Tip text={`Joins on: ${r.join_field}, window: ${r.window_seconds}s, priority: ${r.priority}`}>
                    <span style={{ ...mono, fontSize: 10, color: '#d97706' }}>{r.join_field}</span>
                  </Tip>
                  <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)' }}>{r.window_seconds}s</span>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: 12 }}>Run correlation to initialize default rules</p>
          )}
        </div>
      )}

      {/* ═══ TAB: HISTORY ═══ */}
      {tab === 'history' && runs.length > 0 && (
        <div style={card('#94a3b8')}>
          <h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 14 }}>Correlation Run History</h3>
          <table className="data-table">
            <thead><tr>
              <th>Run ID</th><th>Engine</th><th>LLM</th><th>Nodes</th><th>Edges</th><th>Status</th><th>Started</th>
            </tr></thead>
            <tbody>
              {runs.map(run => (
                <tr key={run.run_id} onClick={() => { setActiveRunId(run.run_id); setTab('graph'); }} style={{ cursor: 'pointer' }}>
                  <td style={{ ...mono, fontSize: 10 }}>{run.run_id?.slice(0, 8)}…</td>
                  <td style={{ fontSize: 11, fontWeight: 600, color: '#2563eb' }}>{run.graph_engine_used || '—'}</td>
                  <td style={{ fontWeight: 600, fontSize: 11 }}>{run.llm_provider}</td>
                  <td style={{ ...mono }}>{run.total_nodes}</td>
                  <td style={{ ...mono }}>{run.total_edges}</td>
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
        </div>
      )}

      {/* Empty state */}
      {!loading && graphData.nodes?.length === 0 && tab === 'graph' && (
        <div className="glass-card-static empty-state" style={{ padding: 48, marginTop: 16 }}>
          <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.4 }}>CR</div>
          <h3 style={{ fontSize: 20 }}>No Correlation Data</h3>
          <p>Click <strong>"Run Correlation Analysis"</strong> to build the entity graph and generate the AI root-cause narrative.</p>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
            Pipeline: Load enriched timeline+anomaly data → Extract entities (Users, IPs, Hosts, Sessions) → Build graph via join rules → Score severity → LLM narrative → Store + CoC
          </p>
        </div>
      )}
    </div>
  );
}


