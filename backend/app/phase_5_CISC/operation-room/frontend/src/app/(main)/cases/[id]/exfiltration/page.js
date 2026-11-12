'use client';

import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { api } from '@operation-room/lib/api';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid,
  ResponsiveContainer, Tooltip as RTooltip, Legend,
} from 'recharts';

/* ── Constants ────────────────────────────────────── */
const RISK_STYLE = {
  CRITICAL: { color: '#dc2626', bg: 'rgba(248,113,113,0.1)', label: 'CRITICAL' },
  HIGH:     { color: '#ea580c', bg: 'rgba(234,88,12,0.08)',  label: 'HIGH' },
  MEDIUM:   { color: '#d97706', bg: 'rgba(217,119,6,0.08)',  label: 'MEDIUM' },
  LOW:      { color: '#059669', bg: 'rgba(5,150,105,0.08)',   label: 'LOW' },
};
const CHANNEL_COLOR = { USB: '#dc2626', EMAIL: '#3b82f6', CLOUD: '#8b5cf6', WEB: '#059669', BLUETOOTH: '#d97706', INFERRED: '#94a3b8', UNKNOWN: '#64748b' };
const NODE_COLOR = { USER: '#3b82f6', FILE: '#8b5cf6', DEVICE: '#d97706', IP: '#dc2626', APPLICATION: '#059669' };
const EDGE_COLOR = { READ: '#3b82f6', WRITE: '#059669', CONNECT: '#d97706', SEND: '#dc2626', USED: '#94a3b8', AUTHENTICATED_FROM: '#8b5cf6', INTERACT: '#64748b' };
const mono = { fontFamily: "'JetBrains Mono', monospace" };

const ENGINE_NAMES = [
  'Normalisation', 'Behaviour Graph', 'Data Flow Detection',
  'Channel Correlation', 'Intent Detection', 'Ghost Transfer',
  'Staging Detection', 'Scoring', 'Explainable AI',
];

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
          borderRadius: 8, fontSize: 11, color: '#1e293b', whiteSpace: 'normal', width: 280,
          zIndex: 999, marginBottom: 6, lineHeight: 1.5, boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
        }}>{text}<div style={{ position: 'absolute', top: '100%', left: '50%', transform: 'translateX(-50%)', width: 0, height: 0, borderLeft: '6px solid transparent', borderRight: '6px solid transparent', borderTop: '6px solid rgba(37,99,235,0.12)' }} /></div>
      )}
    </span>
  );
}

const card = (accent) => ({
  padding: '20px 24px', background: 'var(--bg-card)', border: '1px solid var(--border-color)',
  borderRadius: 14, borderTop: `3px solid ${accent}`,
});

const sectionHead = (title, tip) => (
  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
    <Tip text={tip}><h3 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', cursor: 'help' }}>{title} &#9432;</h3></Tip>
  </div>
);

function formatBytes(b) {
  if (!b) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0; let v = b;
  while (v >= 1024 && i < 3) { v /= 1024; i++; }
  return `${v.toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

function parseJsonField(val) {
  if (Array.isArray(val)) return val;
  if (!val) return [];
  try { return JSON.parse(val); } catch { return []; }
}

/* ── Pipeline Stepper ───────────────────────────────── */
function PipelineStepper({ engines, onComplete, onError }) {
  const [steps, setSteps] = useState(() =>
    ENGINE_NAMES.map((name, i) => ({ name, status: 'pending', detail: '' }))
  );
  const [complete, setComplete] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(Date.now());

  useEffect(() => {
    const timer = setInterval(() => {
      if (!complete && !error) setElapsed(((Date.now() - startRef.current) / 1000).toFixed(1));
    }, 100);
    return () => clearInterval(timer);
  }, [complete, error]);

  useEffect(() => {
    if (!engines) return;
    const url = engines;
    const es = new EventSource(url);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'engine') {
          setSteps(prev => prev.map((s, i) => {
            if (i === data.index) {
              return { ...s, status: data.status, detail: data.detail || '' };
            }
            return s;
          }));
        } else if (data.type === 'complete') {
          setComplete(true);
          setResult(data);
          es.close();
          if (onComplete) onComplete(data);
        } else if (data.type === 'error') {
          setError(data.message);
          es.close();
          if (onError) onError(data.message);
        }
      } catch {}
    };

    es.onerror = () => {
      if (!complete) {
        setError('Connection lost — analysis may still be running');
        es.close();
      }
    };

    return () => es.close();
  }, [engines]);

  const doneCount = steps.filter(s => s.status === 'done').length;
  const progress = (doneCount / steps.length) * 100;

  return (
    <div style={{
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
      borderRadius: 16, padding: '28px 32px', color: '#fff',
      border: '1px solid rgba(59,130,246,0.3)',
      boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 800, letterSpacing: '-0.03em' }}>
            {complete ? 'Analysis Complete' : error ? 'Analysis Error' : 'Running 9-Engine Pipeline...'}
          </h2>
          <p style={{ ...mono, fontSize: 11, color: 'rgba(148,163,184,0.8)', marginTop: 4 }}>
            {elapsed}s elapsed · {doneCount}/{steps.length} engines
          </p>
        </div>
        {complete && result && (
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ ...mono, fontSize: 24, fontWeight: 800, color: '#f87171' }}>{result.total_incidents}</div>
              <div style={{ fontSize: 9, color: '#94a3b8' }}>INCIDENTS</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ ...mono, fontSize: 24, fontWeight: 800, color: '#fbbf24' }}>{result.ghost_transfers}</div>
              <div style={{ fontSize: 9, color: '#94a3b8' }}>GHOSTS</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ ...mono, fontSize: 24, fontWeight: 800, color: RISK_STYLE[result.overall_risk]?.color || '#059669' }}>
                {result.overall_risk}
              </div>
              <div style={{ fontSize: 9, color: '#94a3b8' }}>RISK</div>
            </div>
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div style={{ height: 6, background: 'rgba(255,255,255,0.1)', borderRadius: 99, overflow: 'hidden', marginBottom: 20 }}>
        <div style={{
          height: '100%', borderRadius: 99,
          background: error ? '#ef4444' : complete ? '#22c55e' : 'linear-gradient(90deg, #3b82f6, #8b5cf6)',
          width: `${progress}%`, transition: 'width 0.4s ease',
        }} />
      </div>

      {/* Engine steps */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
        {steps.map((step, i) => {
          const isRunning = step.status === 'running';
          const isDone = step.status === 'done';
          return (
            <div key={i} style={{
              padding: '10px 14px', borderRadius: 10,
              background: isDone ? 'rgba(34,197,94,0.12)' : isRunning ? 'rgba(59,130,246,0.15)' : 'rgba(255,255,255,0.04)',
              border: `1px solid ${isDone ? 'rgba(34,197,94,0.3)' : isRunning ? 'rgba(59,130,246,0.4)' : 'rgba(255,255,255,0.06)'}`,
              transition: 'all 0.3s ease',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  ...mono, fontSize: 10, fontWeight: 700,
                  color: isDone ? '#22c55e' : isRunning ? '#60a5fa' : '#475569',
                  width: 18,
                }}>
                  {isDone ? '\u2713' : isRunning ? '\u25CF' : (i + 1)}
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 600,
                  color: isDone ? '#86efac' : isRunning ? '#93c5fd' : '#64748b',
                }}>
                  {step.name}
                </span>
                {isRunning && (
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%', background: '#3b82f6',
                    animation: 'pulse 1s infinite',
                    marginLeft: 'auto',
                  }} />
                )}
              </div>
              {step.detail && (
                <div style={{ ...mono, fontSize: 9, color: '#94a3b8', marginTop: 4, paddingLeft: 26 }}>
                  {step.detail}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {error && (
        <div style={{ marginTop: 16, padding: '12px 16px', background: 'rgba(239,68,68,0.15)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.3)' }}>
          <span style={{ fontSize: 12, color: '#fca5a5' }}>{error}</span>
        </div>
      )}

      <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.4; transform: scale(0.7); }
        }
      `}</style>
    </div>
  );
}

/* ── Force-Directed Interactive Graph ───────────────────────── */
function ForceGraph({ nodes, links, nodeMap, selectedNode, setSelectedNode }) {
  const canvasRef = useRef(null);
  const simRef = useRef({ nodes: [], links: [] });
  const dragRef = useRef(null);
  const hoverRef = useRef(null);
  const panRef = useRef({ x: 0, y: 0, scale: 1, dragging: false, sx: 0, sy: 0, ox: 0, oy: 0 });
  const frameRef = useRef(null);
  const drawFnRef = useRef(null);
  const selRef = useRef(selectedNode);
  const filtRef = useRef('all');
  const [hoverNode, setHoverNode] = useState(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });
  const [filterType, setFilterType] = useState('all');

  selRef.current = selectedNode;
  filtRef.current = filterType;

  useEffect(() => {
    if (!nodes.length) return;
    const W = 900, H = 640;
    const cx = W / 2, cy = H / 2;

    const byType = {};
    nodes.forEach(n => {
      if (!byType[n.type]) byType[n.type] = [];
      byType[n.type].push(n);
    });

    const simNodes = nodes.map((n, i) => {
      const typeGroup = byType[n.type] || [];
      const gi = typeGroup.indexOf(n);
      const typeIdx = ['USER', 'DEVICE', 'IP', 'FILE', 'APPLICATION'].indexOf(n.type);
      const sectorAngle = (2 * Math.PI / 5) * typeIdx;
      const spreadAngle = sectorAngle + (gi / Math.max(typeGroup.length, 1)) * (Math.PI / 3) - Math.PI / 6;
      const dist = n.type === 'USER' ? 40 : n.type === 'FILE' ? 240 + gi * 3 : 150 + gi * 5;
      return {
        ...n, idx: i,
        x: cx + dist * Math.cos(spreadAngle) + (Math.random() - 0.5) * 30,
        y: cy + dist * Math.sin(spreadAngle) + (Math.random() - 0.5) * 30,
        vx: 0, vy: 0,
        r: Math.max(8, Math.min(28, 6 + (n.event_count || 1) * 1.8)),
        pinned: false,
      };
    });

    const idxMap = {};
    simNodes.forEach((n, i) => { idxMap[n.id] = i; });

    const simLinks = links.filter(l => idxMap[l.source] !== undefined && idxMap[l.target] !== undefined)
      .map(l => ({ ...l, si: idxMap[l.source], ti: idxMap[l.target] }));

    simRef.current = { nodes: simNodes, links: simLinks, idxMap };

    for (let step = 0; step < 80; step++) {
      const ns = simRef.current.nodes;
      const ls = simRef.current.links;
      for (let i = 0; i < ns.length; i++) {
        for (let j = i + 1; j < ns.length; j++) {
          let dx = ns[j].x - ns[i].x, dy = ns[j].y - ns[i].y;
          let d = Math.sqrt(dx * dx + dy * dy) || 1;
          let f = 500 / (d * d);
          ns[i].vx -= (dx / d) * f; ns[i].vy -= (dy / d) * f;
          ns[j].vx += (dx / d) * f; ns[j].vy += (dy / d) * f;
        }
      }
      for (const l of ls) {
        const s = ns[l.si], t = ns[l.ti];
        if (!s || !t) continue;
        let dx = t.x - s.x, dy = t.y - s.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
        let f = (d - 70) * 0.003;
        s.vx += (dx / d) * f; s.vy += (dy / d) * f;
        t.vx -= (dx / d) * f; t.vy -= (dy / d) * f;
      }
      for (const n of ns) {
        n.vx += (cx - n.x) * 0.0005; n.vy += (cy - n.y) * 0.0005;
        n.vx *= 0.35; n.vy *= 0.35;
        n.x += n.vx; n.y += n.vy;
        n.x = Math.max(n.r + 10, Math.min(W - n.r - 10, n.x));
        n.y = Math.max(n.r + 10, Math.min(H - n.r - 10, n.y));
      }
    }

    const targetPos = simRef.current.nodes.map(n => ({ x: n.x, y: n.y }));
    simRef.current.nodes.forEach((n, i) => {
      n.x = cx + (Math.random() - 0.5) * 100;
      n.y = cy + (Math.random() - 0.5) * 100;
    });

    let frame = 0;
    const totalFrames = 60;

    function animate() {
      frame++;
      const t = Math.min(1, frame / totalFrames);
      const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      simRef.current.nodes.forEach((n, i) => {
        n.x = n.x + (targetPos[i].x - n.x) * (ease < 0.99 ? 0.08 + ease * 0.12 : 1);
        n.y = n.y + (targetPos[i].y - n.y) * (ease < 0.99 ? 0.08 + ease * 0.12 : 1);
      });
      draw();
      if (frame < totalFrames) {
        frameRef.current = requestAnimationFrame(animate);
      }
    }

    function draw() {
      const cvs = canvasRef.current;
      if (!cvs) return;
      const ctx = cvs.getContext('2d');
      const dpr = window.devicePixelRatio || 1;
      if (cvs.width !== W * dpr || cvs.height !== H * dpr) {
        cvs.width = W * dpr; cvs.height = H * dpr;
        ctx.scale(dpr, dpr);
      }
      const p = panRef.current;
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.scale(p.scale, p.scale);

      ctx.fillStyle = '#0a0e1a';
      ctx.fillRect(-p.x / p.scale, -p.y / p.scale, W / p.scale, H / p.scale);

      const gridSize = 40;
      ctx.strokeStyle = 'rgba(59,130,246,0.04)';
      ctx.lineWidth = 0.5;
      for (let gx = 0; gx < W; gx += gridSize) {
        ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, H); ctx.stroke();
      }
      for (let gy = 0; gy < H; gy += gridSize) {
        ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(W, gy); ctx.stroke();
      }

      const ns = simRef.current.nodes;
      const ls = simRef.current.links;
      const hov = hoverRef.current;
      const filt = filtRef.current;
      const sel = selRef.current;

      for (const l of ls) {
        const s = ns[l.si], t = ns[l.ti];
        if (!s || !t) continue;
        const dimmed = filt !== 'all' && s.type !== filt && t.type !== filt;
        const highlighted = hov && (s.id === hov || t.id === hov);
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(t.x, t.y);
        ctx.strokeStyle = highlighted
          ? (EDGE_COLOR[l.relationship] || '#94a3b8')
          : dimmed ? 'rgba(100,116,139,0.04)' : (EDGE_COLOR[l.relationship] || 'rgba(100,116,139,0.12)');
        ctx.lineWidth = highlighted ? 2 : 0.6;
        ctx.globalAlpha = highlighted ? 0.9 : dimmed ? 0.1 : 0.25;
        ctx.stroke();

        if (highlighted) {
          const angle = Math.atan2(t.y - s.y, t.x - s.x);
          const arrowLen = 8;
          const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2;
          ctx.beginPath();
          ctx.moveTo(mx + arrowLen * Math.cos(angle), my + arrowLen * Math.sin(angle));
          ctx.lineTo(mx + arrowLen * Math.cos(angle + 2.5), my + arrowLen * Math.sin(angle + 2.5));
          ctx.lineTo(mx + arrowLen * Math.cos(angle - 2.5), my + arrowLen * Math.sin(angle - 2.5));
          ctx.closePath();
          ctx.fillStyle = EDGE_COLOR[l.relationship] || '#94a3b8';
          ctx.globalAlpha = 0.8;
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;

      for (const n of ns) {
        const col = NODE_COLOR[n.type] || '#94a3b8';
        const isHov = n.id === hov;
        const isSel = n.id === sel;
        const dimmed = filt !== 'all' && n.type !== filt;

        if (dimmed && !isHov && !isSel) {
          ctx.globalAlpha = 0.15;
        }

        if (isHov || isSel) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.r + 12, 0, Math.PI * 2);
          ctx.fillStyle = col;
          ctx.globalAlpha = 0.08;
          ctx.fill();
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.r + 6, 0, Math.PI * 2);
          ctx.fillStyle = col;
          ctx.globalAlpha = 0.15;
          ctx.fill();
        }

        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        const grad = ctx.createRadialGradient(n.x - n.r * 0.3, n.y - n.r * 0.3, n.r * 0.1, n.x, n.y, n.r);
        grad.addColorStop(0, col + 'ee');
        grad.addColorStop(1, col + '88');
        ctx.fillStyle = grad;
        ctx.globalAlpha = dimmed ? 0.2 : 1;
        ctx.fill();

        if (isSel) {
          ctx.strokeStyle = '#ffffff';
          ctx.lineWidth = 2.5;
          ctx.globalAlpha = 0.9;
          ctx.stroke();
        }

        ctx.globalAlpha = dimmed ? 0.15 : (isHov ? 1 : 0.75);
        ctx.fillStyle = '#e2e8f0';
        ctx.font = `${isHov ? 'bold 11px' : '9px'} 'JetBrains Mono', monospace`;
        ctx.textAlign = 'center';
        const label = n.value?.length > 18 ? n.value.slice(0, 16) + '\u2026' : n.value;
        ctx.fillText(label, n.x, n.y + n.r + 14);

        ctx.globalAlpha = 1;
      }

      ctx.restore();
    }

    drawFnRef.current = draw;
    animate();
    return () => { if (frameRef.current) cancelAnimationFrame(frameRef.current); };
  }, [nodes, links]);

  useEffect(() => {
    if (drawFnRef.current) drawFnRef.current();
  }, [selectedNode, filterType]);

  useEffect(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    const rect = () => cvs.getBoundingClientRect();
    const toWorld = (clientX, clientY) => {
      const r = rect();
      const p = panRef.current;
      const dpr = window.devicePixelRatio || 1;
      const sx = (clientX - r.left) * (cvs.width / dpr / r.width);
      const sy = (clientY - r.top) * (cvs.height / dpr / r.height);
      return { x: (sx - p.x) / p.scale, y: (sy - p.y) / p.scale };
    };
    const hitTest = (wx, wy) => {
      return simRef.current.nodes.find(n => {
        const dx = n.x - wx, dy = n.y - wy;
        return dx * dx + dy * dy <= (n.r + 4) * (n.r + 4);
      });
    };

    const onMouseMove = (e) => {
      const p = panRef.current;
      if (p.dragging && !dragRef.current) {
        p.x = e.clientX - p.sx + p.ox;
        p.y = e.clientY - p.sy + p.oy;
        drawFrame();
        return;
      }
      if (dragRef.current) {
        const w = toWorld(e.clientX, e.clientY);
        dragRef.current.x = w.x;
        dragRef.current.y = w.y;
        drawFrame();
        return;
      }
      const w = toWorld(e.clientX, e.clientY);
      const hit = hitTest(w.x, w.y);
      hoverRef.current = hit ? hit.id : null;
      setHoverNode(hit || null);
      if (hit) {
        const r = rect();
        setHoverPos({ x: e.clientX - r.left, y: e.clientY - r.top });
      }
      drawFrame();
    };
    const onMouseDown = (e) => {
      const w = toWorld(e.clientX, e.clientY);
      const hit = hitTest(w.x, w.y);
      if (hit) {
        dragRef.current = hit;
        hit.pinned = true;
        e.preventDefault();
      } else {
        panRef.current.dragging = true;
        panRef.current.sx = e.clientX;
        panRef.current.sy = e.clientY;
        panRef.current.ox = panRef.current.x;
        panRef.current.oy = panRef.current.y;
      }
    };
    const onMouseUp = () => {
      if (dragRef.current) {
        dragRef.current.pinned = false;
        dragRef.current = null;
      }
      panRef.current.dragging = false;
    };
    const onClick = (e) => {
      const w = toWorld(e.clientX, e.clientY);
      const hit = hitTest(w.x, w.y);
      setSelectedNode(hit ? (hit.id === selRef.current ? null : hit.id) : null);
    };
    const onWheel = (e) => {
      e.preventDefault();
      const p = panRef.current;
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      const newScale = Math.max(0.3, Math.min(3, p.scale * factor));
      const r = rect();
      const dpr = window.devicePixelRatio || 1;
      const mx = (e.clientX - r.left) * (cvs.width / dpr / r.width);
      const my = (e.clientY - r.top) * (cvs.height / dpr / r.height);
      p.x = mx - ((mx - p.x) / p.scale) * newScale;
      p.y = my - ((my - p.y) / p.scale) * newScale;
      p.scale = newScale;
      drawFrame();
    };

    function drawFrame() {
      const ctx = cvs.getContext('2d');
      const W = 900, H = 640;
      const dpr = window.devicePixelRatio || 1;
      if (cvs.width !== W * dpr || cvs.height !== H * dpr) {
        cvs.width = W * dpr; cvs.height = H * dpr;
        ctx.scale(dpr, dpr);
      }
      const p = panRef.current;
      ctx.clearRect(0, 0, W, H);
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.scale(p.scale, p.scale);

      ctx.fillStyle = '#0a0e1a';
      ctx.fillRect(-p.x / p.scale, -p.y / p.scale, W / p.scale, H / p.scale);

      const gridSize = 40;
      ctx.strokeStyle = 'rgba(59,130,246,0.04)';
      ctx.lineWidth = 0.5;
      for (let gx = 0; gx < W; gx += gridSize) {
        ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, H); ctx.stroke();
      }
      for (let gy = 0; gy < H; gy += gridSize) {
        ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(W, gy); ctx.stroke();
      }

      const ns = simRef.current.nodes;
      const ls = simRef.current.links;
      const hov = hoverRef.current;
      const filt = filtRef.current;
      const sel = selRef.current;

      for (const l of ls) {
        const s = ns[l.si], t = ns[l.ti];
        if (!s || !t) continue;
        const dimmed = filt !== 'all' && s.type !== filt && t.type !== filt;
        const highlighted = hov && (s.id === hov || t.id === hov);
        ctx.beginPath();
        ctx.moveTo(s.x, s.y); ctx.lineTo(t.x, t.y);
        ctx.strokeStyle = highlighted ? (EDGE_COLOR[l.relationship] || '#94a3b8') : dimmed ? 'rgba(100,116,139,0.04)' : (EDGE_COLOR[l.relationship] || 'rgba(100,116,139,0.12)');
        ctx.lineWidth = highlighted ? 2 : 0.6;
        ctx.globalAlpha = highlighted ? 0.9 : dimmed ? 0.1 : 0.25;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      for (const n of ns) {
        const col = NODE_COLOR[n.type] || '#94a3b8';
        const isHov = n.id === hov;
        const isSel = n.id === sel;
        const dimmed = filt !== 'all' && n.type !== filt;
        if (dimmed && !isHov && !isSel) ctx.globalAlpha = 0.15;

        if (isHov || isSel) {
          ctx.beginPath(); ctx.arc(n.x, n.y, n.r + 10, 0, Math.PI * 2);
          ctx.fillStyle = col; ctx.globalAlpha = 0.1; ctx.fill();
        }
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        const grad = ctx.createRadialGradient(n.x - n.r * 0.3, n.y - n.r * 0.3, n.r * 0.1, n.x, n.y, n.r);
        grad.addColorStop(0, col + 'ee'); grad.addColorStop(1, col + '88');
        ctx.fillStyle = grad; ctx.globalAlpha = dimmed ? 0.2 : 1; ctx.fill();
        if (isSel) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 2.5; ctx.globalAlpha = 0.9; ctx.stroke(); }

        ctx.globalAlpha = dimmed ? 0.15 : (isHov ? 1 : 0.7);
        ctx.fillStyle = '#e2e8f0';
        ctx.font = `${isHov ? 'bold 11px' : '9px'} 'JetBrains Mono', monospace`;
        ctx.textAlign = 'center';
        ctx.fillText(n.value?.length > 18 ? n.value.slice(0, 16) + '\u2026' : n.value, n.x, n.y + n.r + 14);
        ctx.globalAlpha = 1;
      }
      ctx.restore();
    }

    cvs.addEventListener('mousemove', onMouseMove);
    cvs.addEventListener('mousedown', onMouseDown);
    cvs.addEventListener('mouseup', onMouseUp);
    cvs.addEventListener('click', onClick);
    cvs.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('mouseup', onMouseUp);

    return () => {
      cvs.removeEventListener('mousemove', onMouseMove);
      cvs.removeEventListener('mousedown', onMouseDown);
      cvs.removeEventListener('mouseup', onMouseUp);
      cvs.removeEventListener('click', onClick);
      cvs.removeEventListener('wheel', onWheel);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  const selNodeData = selectedNode ? (nodeMap[selectedNode] || null) : null;
  const selEdgeCount = selectedNode ? links.filter(l => l.source === selectedNode || l.target === selectedNode).length : 0;

  if (!nodes.length) return <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>Run analysis to build the behaviour graph</div>;

  return (
    <div style={{
      background: 'linear-gradient(135deg, #0a0e1a 0%, #111827 100%)',
      borderRadius: 16, overflow: 'hidden', border: '1px solid rgba(59,130,246,0.2)',
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
    }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '12px 20px', borderBottom: '1px solid rgba(59,130,246,0.1)',
        background: 'rgba(15,23,42,0.8)',
      }}>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ ...mono, fontSize: 11, color: '#94a3b8', marginRight: 8 }}>FILTER:</span>
          {['all', 'USER', 'FILE', 'DEVICE', 'IP'].map(t => (
            <button key={t} onClick={() => setFilterType(t)} style={{
              padding: '4px 10px', borderRadius: 6, fontSize: 10, fontWeight: 700, cursor: 'pointer',
              background: filterType === t ? (NODE_COLOR[t] || 'rgba(59,130,246,0.3)') + '25' : 'transparent',
              border: `1px solid ${filterType === t ? (NODE_COLOR[t] || '#3b82f6') : 'rgba(100,116,139,0.2)'}`,
              color: filterType === t ? (NODE_COLOR[t] || '#3b82f6') : '#64748b',
            }}>{t === 'all' ? 'ALL' : t}</button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
          <span style={{ ...mono, fontSize: 10, color: '#64748b' }}>{nodes.length} nodes</span>
          <span style={{ ...mono, fontSize: 10, color: '#64748b' }}>{links.length} edges</span>
          <span style={{ ...mono, fontSize: 9, color: '#475569' }}>Scroll to zoom &middot; Drag to pan &middot; Drag nodes to move</span>
        </div>
      </div>

      {/* Canvas */}
      <div style={{ position: 'relative' }}>
        <canvas ref={canvasRef} style={{ width: '100%', height: 640, display: 'block', cursor: 'grab' }} />

        {/* Hover tooltip */}
        {hoverNode && (
          <div style={{
            position: 'absolute', left: Math.min(hoverPos.x + 16, 700), top: Math.max(hoverPos.y - 10, 10),
            padding: '12px 16px', borderRadius: 12,
            background: 'rgba(15,23,42,0.95)', border: `1px solid ${NODE_COLOR[hoverNode.type] || '#3b82f6'}44`,
            backdropFilter: 'blur(12px)', boxShadow: `0 8px 24px rgba(0,0,0,0.4), 0 0 20px ${NODE_COLOR[hoverNode.type] || '#3b82f6'}15`,
            pointerEvents: 'none', zIndex: 10, maxWidth: 280,
          }}>
            <div style={{ fontSize: 12, fontWeight: 800, color: NODE_COLOR[hoverNode.type] || '#e2e8f0' }}>
              {hoverNode.type}
            </div>
            <div style={{ ...mono, fontSize: 11, color: '#e2e8f0', marginTop: 2, wordBreak: 'break-all' }}>
              {hoverNode.value}
            </div>
            <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
              <div><span style={{ fontSize: 9, color: '#64748b' }}>Events</span><div style={{ ...mono, fontSize: 14, fontWeight: 800, color: '#e2e8f0' }}>{hoverNode.event_count}</div></div>
              <div><span style={{ fontSize: 9, color: '#64748b' }}>First</span><div style={{ ...mono, fontSize: 10, color: '#94a3b8' }}>{hoverNode.first_seen?.slice(0, 10)}</div></div>
              <div><span style={{ fontSize: 9, color: '#64748b' }}>Last</span><div style={{ ...mono, fontSize: 10, color: '#94a3b8' }}>{hoverNode.last_seen?.slice(0, 10)}</div></div>
            </div>
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 16, justifyContent: 'center', padding: '10px 20px', borderTop: '1px solid rgba(59,130,246,0.1)', background: 'rgba(15,23,42,0.6)' }}>
        {Object.entries(NODE_COLOR).map(([type, col]) => (
          <span key={type} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: col }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: col, boxShadow: `0 0 8px ${col}66` }} />{type}
          </span>
        ))}
        <span style={{ width: 1, height: 16, background: 'rgba(100,116,139,0.3)' }} />
        {Object.entries(EDGE_COLOR).filter(([k]) => ['READ', 'WRITE', 'SEND', 'CONNECT'].includes(k)).map(([rel, col]) => (
          <span key={rel} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 10, color: col }}>
            <span style={{ width: 14, height: 2, background: col, borderRadius: 1 }} />{rel}
          </span>
        ))}
      </div>

      {/* Selected node detail panel */}
      {selNodeData && (
        <div style={{
          padding: '16px 20px', borderTop: '1px solid rgba(59,130,246,0.15)',
          background: 'rgba(15,23,42,0.8)',
        }}>
          <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
            <div style={{ width: 40, height: 40, borderRadius: '50%', background: NODE_COLOR[selNodeData.type] || '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: `0 0 16px ${NODE_COLOR[selNodeData.type] || '#3b82f6'}44` }}>
              <span style={{ color: '#fff', fontSize: 14, fontWeight: 800 }}>{selNodeData.type?.[0]}</span>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 800, color: NODE_COLOR[selNodeData.type] || '#e2e8f0' }}>{selNodeData.type}: {selNodeData.value}</div>
              <div style={{ ...mono, fontSize: 10, color: '#94a3b8', marginTop: 2 }}>
                {selNodeData.event_count} events &middot; {selEdgeCount} connections &middot; First: {selNodeData.first_seen?.slice(0, 19)} &middot; Last: {selNodeData.last_seen?.slice(0, 19)}
              </div>
            </div>
            <button onClick={() => setSelectedNode(null)} style={{ background: 'rgba(100,116,139,0.2)', border: 'none', borderRadius: 6, padding: '4px 10px', color: '#94a3b8', cursor: 'pointer', fontSize: 10 }}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Cinematic Timeline ──────────────────────────────────── */
function CinematicTimeline({ incidents, summary, actorChannels = {} }) {
  const [expandedId, setExpandedId] = useState(null);

  if (!incidents.length) return (
    <div style={{ padding: '20px 24px', background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: 14, borderTop: '3px solid #3b82f6', textAlign: 'center', color: 'var(--text-muted)', paddingTop: 40, paddingBottom: 40 }}>
      <p>No incidents yet — run analysis first</p>
    </div>
  );

  const sorted = [...incidents].sort((a, b) => String(a.normalised_ts || '').localeCompare(String(b.normalised_ts || '')));

  const dayGroups = {};
  sorted.forEach(inc => {
    const date = String(inc.normalised_ts || '').slice(0, 10) || 'Unknown';
    if (!dayGroups[date]) dayGroups[date] = [];
    dayGroups[date].push(inc);
  });
  const days = Object.keys(dayGroups).sort();

  const firstTs = sorted[0]?.normalised_ts ? String(sorted[0].normalised_ts).slice(0, 10) : '';
  const lastTs = sorted[sorted.length - 1]?.normalised_ts ? String(sorted[sorted.length - 1].normalised_ts).slice(0, 10) : '';

  const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const fmtDateLong = (d) => {
    try {
      const dt = new Date(d + 'T00:00:00');
      return `${dayNames[dt.getDay()]}, ${monthNames[dt.getMonth()]} ${dt.getDate()}, ${dt.getFullYear()}`;
    } catch { return d; }
  };

  return (
    <div style={{
      padding: '24px 28px', background: 'var(--bg-card)', border: '1px solid var(--border-color)',
      borderRadius: 14, borderTop: '3px solid #3b82f6',
    }}>
      {/* Header with case period */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <h3 style={{ fontSize: 14, fontWeight: 800, color: '#1e293b' }}>Correlated Event Timeline</h3>
          <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>
            {incidents.length} events across {days.length} days
          </span>
        </div>
        {/* Case period bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', background: 'rgba(59,130,246,0.04)', borderRadius: 10, border: '1px solid rgba(59,130,246,0.1)' }}>
          <div style={{ ...mono, fontSize: 11, fontWeight: 700, color: '#3b82f6' }}>{firstTs}</div>
          <div style={{ flex: 1, height: 2, background: 'linear-gradient(90deg, #3b82f6, #8b5cf6, #dc2626)', borderRadius: 99, position: 'relative' }}>
            {days.map((day, di) => {
              const pct = days.length > 1 ? (di / (days.length - 1)) * 100 : 50;
              const count = dayGroups[day].length;
              return (
                <div key={day} style={{ position: 'absolute', left: `${pct}%`, top: -4, transform: 'translateX(-50%)' }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: count > 2 ? '#dc2626' : count > 1 ? '#d97706' : '#3b82f6', border: '2px solid var(--bg-card)' }} />
                </div>
              );
            })}
          </div>
          <div style={{ ...mono, fontSize: 11, fontWeight: 700, color: '#dc2626' }}>{lastTs}</div>
        </div>
        {summary && (
          <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Run: <strong style={{ ...mono }}>{summary.run_id?.slice(0, 8)}</strong></span>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Risk: <strong style={{ color: RISK_STYLE[summary.overall_risk]?.color || '#059669' }}>{summary.overall_risk}</strong></span>
            <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Actors: <strong>{summary.affected_actors}</strong></span>
          </div>
        )}
      </div>

      {/* Day-grouped timeline */}
      {days.map((day, dayIdx) => {
        const dayIncs = dayGroups[day];
        const targets = [...new Set(dayIncs.map(i => i.data_target))];
        const dayRisk = dayIncs.some(i => i.risk_category === 'CRITICAL') ? 'CRITICAL' : dayIncs.some(i => i.risk_category === 'HIGH') ? 'HIGH' : 'MEDIUM';
        const dayRs = RISK_STYLE[dayRisk] || RISK_STYLE.MEDIUM;

        return (
          <div key={day} style={{ marginBottom: dayIdx < days.length - 1 ? 28 : 0 }}>
            {/* Day header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
              <div style={{
                width: 48, height: 48, borderRadius: 12, background: dayRs.bg,
                border: `1px solid ${dayRs.color}33`, display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}>
                <span style={{ ...mono, fontSize: 9, fontWeight: 700, color: dayRs.color, lineHeight: 1, textTransform: 'uppercase' }}>
                  {monthNames[parseInt(day.slice(5, 7)) - 1] || '???'}
                </span>
                <span style={{ ...mono, fontSize: 18, fontWeight: 900, color: dayRs.color, lineHeight: 1 }}>
                  {day.slice(8, 10)}
                </span>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#1e293b' }}>{fmtDateLong(day)}</div>
                <div style={{ display: 'flex', gap: 10, marginTop: 2 }}>
                  <span style={{ ...mono, fontSize: 10, color: dayRs.color, fontWeight: 700 }}>{dayIncs.length} event{dayIncs.length !== 1 ? 's' : ''}</span>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{targets.length} target{targets.length !== 1 ? 's' : ''} accessed</span>
                  <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)' }}>
                    {String(dayIncs[0].normalised_ts || '').slice(11, 19)}
                    {dayIncs.length > 1 ? ` \u2013 ${String(dayIncs[dayIncs.length - 1].normalised_ts || '').slice(11, 19)}` : ''}
                  </span>
                </div>
              </div>
              <div style={{
                padding: '4px 10px', borderRadius: 8, fontSize: 10, fontWeight: 800,
                background: dayRs.bg, color: dayRs.color, border: `1px solid ${dayRs.color}33`,
              }}>{dayRisk}</div>
            </div>

            {/* Events within day */}
            <div style={{ position: 'relative', paddingLeft: 32, marginLeft: 24, borderLeft: `2px solid ${dayRs.color}22` }}>
              {dayIncs.map((inc, incIdx) => {
                const rs = RISK_STYLE[inc.risk_category] || RISK_STYLE.LOW;
                const expanded = expandedId === inc.incident_id;
                const factors = parseJsonField(inc.contributing_factors);
                const timeline = parseJsonField(inc.timeline_json);
                const time = String(inc.normalised_ts || '').slice(11, 19);
                const sameTimePrev = incIdx > 0 && String(dayIncs[incIdx - 1].normalised_ts || '').slice(11, 19) === time;

                return (
                  <div key={inc.incident_id} style={{ position: 'relative', marginBottom: 10 }}>
                    {/* Spine connector dot */}
                    <div style={{
                      position: 'absolute', left: -39, top: 14, width: 12, height: 12,
                      borderRadius: '50%', background: rs.color, border: '2px solid var(--bg-card)',
                      boxShadow: `0 0 6px ${rs.color}44`, zIndex: 1,
                    }} />
                    {/* Horizontal connector line */}
                    <div style={{ position: 'absolute', left: -27, top: 19, width: 24, height: 1, background: `${rs.color}33` }} />

                    {/* Event card */}
                    <div
                      onClick={() => setExpandedId(expanded ? null : inc.incident_id)}
                      style={{
                        padding: '14px 18px', borderRadius: 10, cursor: 'pointer',
                        background: expanded ? rs.bg : 'rgba(0,0,0,0.01)',
                        border: `1px solid ${expanded ? rs.color + '33' : 'var(--border-color)'}`,
                        borderLeft: `3px solid ${rs.color}`,
                        transition: 'all 0.15s ease',
                      }}
                    >
                      {/* Time + confidence + badges */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        {!sameTimePrev && (
                          <span style={{
                            ...mono, fontSize: 12, fontWeight: 800, color: '#1e293b',
                            padding: '2px 8px', background: 'rgba(59,130,246,0.06)', borderRadius: 6,
                          }}>{time}</span>
                        )}
                        {sameTimePrev && <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', opacity: 0.4 }}>same time</span>}
                        <span style={{ ...mono, fontSize: 16, fontWeight: 900, color: rs.color }}>
                          {(inc.confidence * 100).toFixed(0)}%
                        </span>
                        <span style={{ fontSize: 12, fontWeight: 700, color: '#0ea5e9' }}>{inc.actor}</span>
                        <span style={{ padding: '2px 7px', borderRadius: 6, fontSize: 9, fontWeight: 800, background: rs.bg, color: rs.color }}>{inc.risk_category}</span>
                        {inc.is_ghost && <span style={{ padding: '1px 5px', borderRadius: 5, fontSize: 8, fontWeight: 700, background: 'rgba(148,163,184,0.1)', color: '#64748b' }}>GHOST</span>}
                        {inc.is_staged && <span style={{ padding: '1px 5px', borderRadius: 5, fontSize: 8, fontWeight: 700, background: 'rgba(139,92,246,0.1)', color: '#8b5cf6' }}>STAGED</span>}
                        <span style={{ padding: '1px 5px', borderRadius: 5, fontSize: 8, fontWeight: 700, background: `${CHANNEL_COLOR[inc.channel] || '#666'}12`, color: CHANNEL_COLOR[inc.channel] || '#94a3b8' }}>{inc.channel}</span>
                        {actorChannels[inc.actor]?.size > 1
                          ? <span style={{ padding: '1px 5px', borderRadius: 5, fontSize: 8, fontWeight: 700, background: 'rgba(139,92,246,0.1)', color: '#8b5cf6' }}>MULTI-CH</span>
                          : <span style={{ padding: '1px 5px', borderRadius: 5, fontSize: 8, fontWeight: 700, background: 'rgba(59,130,246,0.1)', color: '#3b82f6' }}>SINGLE-CH</span>}
                      </div>

                      {/* Target + destination in prominent row */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                        <span style={{ ...mono, fontSize: 11, color: '#1e293b', fontWeight: 600 }}>{inc.data_target}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>&rarr;</span>
                        <span style={{ ...mono, fontSize: 11, color: '#dc2626', fontWeight: 600 }}>{inc.dst_ip || 'N/A'}</span>
                      </div>

                      {/* Explanation */}
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{inc.explanation}</div>

                      {/* Stats row */}
                      <div style={{ display: 'flex', gap: 12, marginTop: 6 }}>
                        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>Read: <strong style={{ color: '#2563eb' }}>{formatBytes(inc.bytes_accessed)}</strong></span>
                        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>Sent: <strong style={{ color: '#dc2626' }}>{formatBytes(inc.bytes_exfil)}</strong></span>
                        <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>Intent: <strong style={{ color: '#d97706' }}>{(inc.intent_score || 0).toFixed(2)}</strong></span>
                      </div>

                      {/* Confidence bar */}
                      <div style={{ marginTop: 6, height: 3, background: 'rgba(0,0,0,0.04)', borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${Math.min(100, (inc.confidence || 0) * 100)}%`, borderRadius: 99, background: rs.color, transition: 'width 0.4s' }} />
                      </div>

                      {/* Expanded */}
                      {expanded && (
                        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-color)' }}>
                          {factors.length > 0 && (
                            <div style={{ marginBottom: 10 }}>
                              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Contributing Factors</div>
                              {factors.map((f, i) => (
                                <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4, paddingLeft: 10, borderLeft: `2px solid ${rs.color}55`, lineHeight: 1.6 }}>{f}</div>
                              ))}
                            </div>
                          )}
                          {timeline.length > 0 && (
                            <div>
                              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Event Chain</div>
                              <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                                {timeline.map((step, i) => (
                                  <React.Fragment key={i}>
                                    {i > 0 && <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>&rarr;</span>}
                                    <div style={{ flex: 1, padding: '6px 10px', borderRadius: 6, background: rs.bg, border: `1px solid ${rs.color}22` }}>
                                      <div style={{ ...mono, fontSize: 9, fontWeight: 700, color: rs.color }}>{step.step}</div>
                                      <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 1 }}>{step.detail}</div>
                                      {step.timestamp && <div style={{ ...mono, fontSize: 9, color: 'var(--text-muted)', marginTop: 1 }}>{String(step.timestamp).slice(0, 19)}</div>}
                                    </div>
                                  </React.Fragment>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Day correlation summary */}
            {targets.length > 1 && (
              <div style={{ marginLeft: 56, marginTop: 6, padding: '8px 14px', borderRadius: 8, background: 'rgba(59,130,246,0.04)', border: '1px solid rgba(59,130,246,0.08)' }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: '#3b82f6' }}>Correlated targets this day: </span>
                {targets.map((t, i) => (
                  <span key={i} style={{ ...mono, fontSize: 10, color: 'var(--text-secondary)' }}>
                    {i > 0 ? ', ' : ''}{t}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════ */
export default function ExfiltrationPage() {
  const { id } = useParams();

  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [streamUrl, setStreamUrl] = useState(null);
  const [summary, setSummary] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [graph, setGraph] = useState({ nodes: [], edges: [] });
  const [channels, setChannels] = useState([]);
  const [runs, setRuns] = useState([]);
  const [tab, setTab] = useState('overview');
  const [riskFilter, setRiskFilter] = useState('all');
  const [channelFilter, setChannelFilter] = useState('all');
  const [expandedIncident, setExpandedIncident] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [autoRanOnce, setAutoRanOnce] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [s, inc, g, ch, r] = await Promise.all([
        api.getExfilIntelSummary(id).catch(() => null),
        api.getExfilIntelIncidents(id).catch(() => []),
        api.getExfilIntelGraph(id).catch(() => ({ nodes: [], edges: [] })),
        api.getExfilIntelChannels(id).catch(() => []),
        api.getExfilIntelRuns(id).catch(() => []),
      ]);
      setSummary(s);
      setIncidents(Array.isArray(inc) ? inc : []);
      setGraph(g && g.nodes ? g : { nodes: [], edges: [] });
      setChannels(Array.isArray(ch) ? ch : []);
      setRuns(Array.isArray(r) ? r : []);
      return { summary: s, incidents: Array.isArray(inc) ? inc : [] };
    } catch { return { summary: null, incidents: [] }; }
    finally { setLoading(false); }
  }, [id]);

  useEffect(() => {
    loadData().then(({ summary: s, incidents: inc }) => {
      const hasData = inc && inc.length > 0;
      if (!hasData && !autoRanOnce) {
        setAutoRanOnce(true);
        handleStreamRun();
      }
    });
  }, []);

  const handleStreamRun = () => {
    setRunning(true);
    setTab('overview');
    setStreamUrl(api.streamExfilIntel(id));
  };

  const onPipelineComplete = async () => {
    await loadData();
    setRunning(false);
    setStreamUrl(null);
  };

  const onPipelineError = (msg) => {
    setRunning(false);
    alert('Pipeline error: ' + msg);
  };

  /* ── Computed ── */
  const stats = useMemo(() => {
    if (!summary) return { total: 0, high: 0, actors: 0, devices: 0, bytes: 0, risk: 'LOW' };
    return {
      total: parseInt(summary.total_incidents || 0),
      high: parseInt(summary.high_risk_count || 0),
      actors: parseInt(summary.affected_actors || 0),
      devices: parseInt(summary.affected_devices || 0),
      bytes: parseInt(summary.total_bytes_out || 0),
      risk: summary.overall_risk || 'LOW',
    };
  }, [summary]);

  const filteredIncidents = useMemo(() => {
    return incidents.filter(i => {
      if (riskFilter !== 'all' && i.risk_category !== riskFilter) return false;
      if (channelFilter !== 'all' && i.channel !== channelFilter) return false;
      return true;
    });
  }, [incidents, riskFilter, channelFilter]);

  const timelineData = useMemo(() => {
    const buckets = {};
    incidents.forEach(i => {
      if (!i.normalised_ts) return;
      const h = String(i.normalised_ts).substr(0, 13);
      if (!buckets[h]) buckets[h] = { time: h, incidents: 0, bytes: 0, highRisk: 0 };
      buckets[h].incidents += 1;
      buckets[h].bytes += (i.bytes_exfil || 0);
      if (i.risk_category === 'CRITICAL' || i.risk_category === 'HIGH') buckets[h].highRisk += 1;
    });
    return Object.values(buckets).sort((a, b) => a.time.localeCompare(b.time));
  }, [incidents]);

  const riskHeatmap = useMemo(() => {
    const map = {};
    incidents.forEach(i => {
      const key = i.actor || 'unknown';
      if (!map[key]) map[key] = { actor: key, total: 0, critical: 0, high: 0, medium: 0, low: 0, maxConf: 0 };
      map[key].total += 1;
      map[key][i.risk_category?.toLowerCase() || 'low'] += 1;
      map[key].maxConf = Math.max(map[key].maxConf, i.confidence || 0);
    });
    return Object.values(map).sort((a, b) => b.maxConf - a.maxConf);
  }, [incidents]);

  const channelPie = useMemo(() => {
    return channels.map(c => ({ name: c.channel, value: c.count, bytes: c.bytes }));
  }, [channels]);

  const uniqueChannels = useMemo(() => {
    return [...new Set(incidents.map(i => i.channel))];
  }, [incidents]);

  const noveltyStats = useMemo(() => {
    const ghosts = incidents.filter(i => i.is_ghost);
    const staged = incidents.filter(i => i.is_staged);
    const behavAnom = incidents.filter(i => i.intent_score > 0.5);

    const actorChannels = {};
    incidents.forEach(i => {
      if (!actorChannels[i.actor]) actorChannels[i.actor] = new Set();
      actorChannels[i.actor].add(i.channel);
    });
    const singleChActors = Object.entries(actorChannels).filter(([, chs]) => chs.size === 1);
    const multiChActors = Object.entries(actorChannels).filter(([, chs]) => chs.size > 1);
    const singleChIncidents = incidents.filter(i => actorChannels[i.actor]?.size === 1);
    const multiChIncidents = incidents.filter(i => actorChannels[i.actor]?.size > 1);

    return {
      ghosts: ghosts.length, staged: staged.length, behavioral: behavAnom.length,
      singleChannelActors: singleChActors.length,
      multiChannelActors: multiChActors.length,
      singleChannelIncidents: singleChIncidents.length,
      multiChannelIncidents: multiChIncidents.length,
      actorChannels,
    };
  }, [incidents]);

  const graphViz = useMemo(() => {
    if (!graph.nodes || !graph.nodes.length) return { nodes: [], links: [], nodeMap: {} };
    const nodeMap = {};
    graph.nodes.forEach(n => { nodeMap[n.id] = n; });
    const links = (graph.edges || []).filter(e => nodeMap[e.source] && nodeMap[e.target]);
    return { nodes: graph.nodes, links, nodeMap };
  }, [graph]);

  const TABS = [
    { id: 'overview',   label: 'Overview',          count: null },
    { id: 'incidents',  label: 'Incidents',         count: stats.total || null },
    { id: 'graph',      label: 'Behaviour Graph',   count: graph.nodes?.length || null },
    { id: 'timeline',   label: 'Timeline',          count: timelineData.length || null },
    { id: 'channels',   label: 'Channels',          count: channels.length || null },
    { id: 'heatmap',    label: 'Risk Heatmap',      count: riskHeatmap.length || null },
    { id: 'novelty',    label: 'Novelty Showcase',  count: null },
    { id: 'runs',       label: 'Runs',              count: runs.length || null },
  ];

  return (
    <div style={{ maxWidth: 1500, margin: '0 auto' }}>
      {/* ── Header ─────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20, paddingBottom: 16, borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-0.04em', color: '#1e293b' }}>
            Data Exfiltration Intelligence
          </h1>
          <div style={{ ...mono, fontSize: 11, marginTop: 4, color: 'var(--text-muted)' }}>
            <Tip text="9-engine pipeline: Normalise → Graph → DataFlow → Channel → Intent → Ghost → Staging → Score → Explain">9-Engine Modular Pipeline</Tip>
            <span style={{ opacity: 0.3, margin: '0 8px' }}>&middot;</span>
            <Tip text="Constructs directed interaction graphs: User→File→Device→IP with READ/WRITE/SEND edges">Behaviour Graph Analysis</Tip>
            <span style={{ opacity: 0.3, margin: '0 8px' }}>&middot;</span>
            <Tip text="Detects ghost transfers, staging activity, and multi-channel exfiltration with configurable thresholds">Intent-Aware Detection</Tip>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Link href={`/cases/${id}/network`} className="btn btn-ghost">Network</Link>
          <Link href={`/cases/${id}/crud`} className="btn btn-ghost">CRUD</Link>
          <Link href={`/cases/${id}`} className="btn btn-ghost">&larr; Case</Link>
          <button className="btn btn-primary" onClick={handleStreamRun} disabled={running}
            style={{ padding: '10px 22px', fontSize: 13, fontWeight: 700 }}>
            {running ? 'Analyzing...' : 'Run Exfiltration Analysis'}
          </button>
        </div>
      </div>

      {/* ── Live Pipeline Stepper (shown during analysis) ── */}
      {running && streamUrl && (
        <div style={{ marginBottom: 20 }}>
          <PipelineStepper
            engines={streamUrl}
            onComplete={onPipelineComplete}
            onError={onPipelineError}
          />
        </div>
      )}

      {/* ── Tabs ─────────────────────────────── */}
      {!running && (
        <>
          <div className="tl-view-tabs" style={{ marginBottom: 16 }}>
            {TABS.map(t => (
              <button key={t.id} className={`tl-view-tab ${tab === t.id ? 'active' : ''}`} onClick={() => setTab(t.id)}>
                {t.label}
                {t.count > 0 && (
                  <span style={{
                    marginLeft: 6, padding: '1px 6px', borderRadius: 999, fontSize: 9, fontWeight: 800,
                    background: t.id === 'incidents' ? 'rgba(248,113,113,0.2)' : 'rgba(59,130,246,0.15)',
                    color: t.id === 'incidents' ? '#dc2626' : '#3b82f6',
                  }}>{t.count}</span>
                )}
              </button>
            ))}
          </div>

          {/* Loading state */}
          {loading && (
            <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>
              <div style={{ ...mono, fontSize: 14 }}>Loading data...</div>
            </div>
          )}

          {/* ═══ TAB: OVERVIEW ═══ */}
          {!loading && tab === 'overview' && incidents.length > 0 && (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 20 }}>
                {[
                  { val: stats.total, lbl: 'Total Incidents', c: '#3b82f6', tip: 'Total exfiltration incidents detected across all engines' },
                  { val: stats.high, lbl: 'High/Critical', c: '#dc2626', tip: 'Incidents with confidence > 50% rated HIGH or CRITICAL' },
                  { val: stats.actors, lbl: 'Affected Users', c: '#8b5cf6', tip: 'Unique actors involved in exfiltration incidents' },
                  { val: stats.devices, lbl: 'Ext. Destinations', c: '#d97706', tip: 'Unique external IPs where data was sent' },
                  { val: formatBytes(stats.bytes), lbl: 'Bytes Exfiltrated', c: '#ea580c', tip: 'Total bytes transferred outbound in detected incidents' },
                  { val: stats.risk, lbl: 'Overall Risk', c: RISK_STYLE[stats.risk]?.color || '#059669', tip: 'Aggregate risk level based on highest-confidence incident' },
                ].map((c, i) => (
                  <Tip key={i} text={c.tip}>
                    <div style={card(c.c)}>
                      <div style={{ fontSize: 22, fontWeight: 800, color: c.c, ...mono }}>{c.val}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600 }}>{c.lbl}</div>
                    </div>
                  </Tip>
                ))}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14, marginBottom: 20 }}>
                <div style={card('#3b82f6')}>
                  {sectionHead('Exfiltration Timeline', 'Incident count and bytes per hour. Red areas indicate high-risk activity spikes.')}
                  {timelineData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={240}>
                      <AreaChart data={timelineData} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                        <XAxis dataKey="time" tick={{ fill: '#94a3b8', fontSize: 9 }}
                          tickFormatter={v => { try { return v.split('T')[1] + ':00'; } catch { return v; } }} />
                        <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                        <RTooltip content={({ active, payload, label }) => {
                          if (!active || !payload?.length) return null;
                          return (
                            <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                              <div style={{ fontSize: 11, fontWeight: 700, color: '#1e293b', marginBottom: 4 }}>{label}</div>
                              {payload.map(p => <div key={p.name} style={{ fontSize: 10, color: p.color }}>{p.name}: <strong>{p.value}</strong></div>)}
                            </div>
                          );
                        }} />
                        <Area type="monotone" dataKey="incidents" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} name="Incidents" animationDuration={1200} />
                        <Area type="monotone" dataKey="highRisk" stroke="#dc2626" fill="#dc2626" fillOpacity={0.4} name="High Risk" animationDuration={1500} />
                        <Legend wrapperStyle={{ fontSize: 10 }} />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>All incidents at same hour</div>}
                </div>

                <div style={card('#8b5cf6')}>
                  {sectionHead('Channel Distribution', 'Breakdown by exfiltration channel: USB, Email, Cloud, Web, Bluetooth, Inferred')}
                  {channelPie.length > 0 ? (
                    <>
                      <ResponsiveContainer width="100%" height={200}>
                        <PieChart>
                          <Pie data={channelPie} cx="50%" cy="50%" innerRadius={40} outerRadius={70}
                            paddingAngle={3} dataKey="value" stroke="none" animationDuration={800}>
                            {channelPie.map(d => <Cell key={d.name} fill={CHANNEL_COLOR[d.name] || '#666'} />)}
                          </Pie>
                          <RTooltip content={({ active, payload }) => {
                            if (!active || !payload?.length) return null;
                            const d = payload[0].payload;
                            return (
                              <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 10, padding: '10px 14px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
                                <div style={{ fontSize: 12, fontWeight: 700, color: CHANNEL_COLOR[d.name] || '#333' }}>{d.name}</div>
                                <div style={{ fontSize: 10 }}>{d.value} incidents &middot; {formatBytes(d.bytes)}</div>
                              </div>
                            );
                          }} />
                        </PieChart>
                      </ResponsiveContainer>
                      <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
                        {channelPie.map(d => (
                          <span key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 9, color: CHANNEL_COLOR[d.name] || '#aaa' }}>
                            <span style={{ width: 6, height: 6, borderRadius: '50%', background: CHANNEL_COLOR[d.name] || '#666' }} />{d.name}
                          </span>
                        ))}
                      </div>
                    </>
                  ) : <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-muted)' }}>No channel data</div>}
                </div>
              </div>

              {/* Quick incident preview */}
              <div style={card('#dc2626')}>
                {sectionHead('Top Incidents', 'Highest confidence detections from the latest analysis run')}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {incidents.slice(0, 5).map(inc => {
                    const rs = RISK_STYLE[inc.risk_category] || RISK_STYLE.LOW;
                    return (
                      <div key={inc.incident_id} style={{
                        padding: '12px 16px', borderRadius: 10, display: 'flex', gap: 14, alignItems: 'center',
                        background: rs.bg, border: `1px solid ${rs.color}22`,
                      }}>
                        <div style={{ ...mono, fontSize: 18, fontWeight: 800, color: rs.color, minWidth: 50, textAlign: 'center' }}>
                          {(inc.confidence * 100).toFixed(0)}%
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 2 }}>
                            <span style={{ fontSize: 12, fontWeight: 700, color: '#0ea5e9' }}>{inc.actor}</span>
                            <span style={{ padding: '1px 6px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: rs.bg, color: rs.color }}>{inc.risk_category}</span>
                            {inc.is_ghost && <span style={{ padding: '1px 5px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: 'rgba(148,163,184,0.15)', color: '#64748b' }}>GHOST</span>}
                            {inc.is_staged && <span style={{ padding: '1px 5px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: 'rgba(139,92,246,0.15)', color: '#8b5cf6' }}>STAGED</span>}
                            <span style={{ padding: '1px 5px', borderRadius: 999, fontSize: 8, background: `${CHANNEL_COLOR[inc.channel] || '#666'}20`, color: CHANNEL_COLOR[inc.channel] || '#aaa' }}>{inc.channel}</span>
                            {noveltyStats.actorChannels[inc.actor]?.size > 1
                              ? <span style={{ padding: '1px 5px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: 'rgba(139,92,246,0.1)', color: '#8b5cf6' }}>MULTI-CH</span>
                              : <span style={{ padding: '1px 5px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: 'rgba(59,130,246,0.1)', color: '#3b82f6' }}>SINGLE-CH</span>}
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{inc.explanation}</div>
                        </div>
                        <div style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', minWidth: 60, textAlign: 'right' }}>
                          {inc.dst_ip || 'N/A'}
                        </div>
                      </div>
                    );
                  })}
                </div>
                {incidents.length > 5 && (
                  <button onClick={() => setTab('incidents')} style={{
                    marginTop: 12, width: '100%', padding: '8px 0', border: 'none', background: 'rgba(59,130,246,0.08)',
                    borderRadius: 8, fontSize: 11, fontWeight: 700, color: '#3b82f6', cursor: 'pointer',
                  }}>View All {incidents.length} Incidents &rarr;</button>
                )}
              </div>
            </>
          )}

          {/* Empty state for overview */}
          {!loading && tab === 'overview' && incidents.length === 0 && (
            <div className="glass-card-static empty-state" style={{ padding: 48, marginTop: 16, textAlign: 'center' }}>
              <div style={{ fontSize: 56, marginBottom: 16, opacity: 0.4 }}>EI</div>
              <h3 style={{ fontSize: 20 }}>No Exfiltration Intelligence Data</h3>
              <p>Click <strong>&quot;Run Exfiltration Analysis&quot;</strong> to execute the 9-engine pipeline.</p>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
                Requires: Timeline must be built first. Anomaly + CRUD runs recommended for richer scoring.
              </p>
            </div>
          )}

          {/* ═══ TAB: INCIDENTS ═══ */}
          {!loading && tab === 'incidents' && (
            <div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 14, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>RISK:</span>
                {['all', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(r => (
                  <button key={r} onClick={() => setRiskFilter(r)} style={{
                    padding: '3px 10px', borderRadius: 999, fontSize: 9, fontWeight: 700, cursor: 'pointer',
                    background: riskFilter === r ? (RISK_STYLE[r]?.bg || 'rgba(255,255,255,0.1)') : 'transparent',
                    border: `1px solid ${riskFilter === r ? (RISK_STYLE[r]?.color || '#94a3b8') : 'transparent'}`,
                    color: RISK_STYLE[r]?.color || '#94a3b8',
                  }}>{r === 'all' ? 'All' : r}</button>
                ))}
                <span style={{ opacity: 0.2 }}>|</span>
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>CHANNEL:</span>
                {['all', ...uniqueChannels].map(c => (
                  <button key={c} onClick={() => setChannelFilter(c)} style={{
                    padding: '3px 8px', borderRadius: 999, fontSize: 9, fontWeight: 700, cursor: 'pointer',
                    background: channelFilter === c ? `${CHANNEL_COLOR[c] || '#fff'}15` : 'transparent',
                    border: `1px solid ${channelFilter === c ? (CHANNEL_COLOR[c] || '#fff') : 'transparent'}`,
                    color: CHANNEL_COLOR[c] || '#94a3b8',
                  }}>{c === 'all' ? 'All' : c}</button>
                ))}
                <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' }}>
                  {filteredIncidents.length} / {incidents.length} incidents
                </span>
              </div>

              {filteredIncidents.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {filteredIncidents.map(inc => {
                    const rs = RISK_STYLE[inc.risk_category] || RISK_STYLE.LOW;
                    const expanded = expandedIncident === inc.incident_id;
                    const factors = parseJsonField(inc.contributing_factors);
                    const timeline = parseJsonField(inc.timeline_json);
                    return (
                      <div key={inc.incident_id} style={{
                        padding: '16px 20px', borderRadius: 12, background: rs.bg,
                        border: `1px solid ${rs.color}22`, borderLeft: `4px solid ${rs.color}`,
                        cursor: 'pointer',
                      }} onClick={() => setExpandedIncident(expanded ? null : inc.incident_id)}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{ ...mono, fontSize: 18, fontWeight: 800, color: rs.color }}>
                              {(inc.confidence * 100).toFixed(0)}%
                            </span>
                            <span style={{ fontSize: 13, fontWeight: 700, color: '#0ea5e9' }}>{inc.actor}</span>
                            <span style={{ padding: '2px 8px', borderRadius: 999, fontSize: 9, fontWeight: 700, background: rs.bg, color: rs.color, border: `1px solid ${rs.color}44` }}>{inc.risk_category}</span>
                            {inc.is_ghost && <span style={{ padding: '2px 6px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: 'rgba(148,163,184,0.15)', color: '#64748b' }}>GHOST</span>}
                            {inc.is_staged && <span style={{ padding: '2px 6px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: 'rgba(139,92,246,0.15)', color: '#8b5cf6' }}>STAGED</span>}
                            <span style={{ padding: '2px 6px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: `${CHANNEL_COLOR[inc.channel] || '#666'}20`, color: CHANNEL_COLOR[inc.channel] || '#aaa' }}>{inc.channel}</span>
                            {noveltyStats.actorChannels[inc.actor]?.size > 1
                              ? <span style={{ padding: '2px 6px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: 'rgba(139,92,246,0.12)', color: '#8b5cf6' }}>MULTI-CH</span>
                              : <span style={{ padding: '2px 6px', borderRadius: 999, fontSize: 8, fontWeight: 700, background: 'rgba(59,130,246,0.12)', color: '#3b82f6' }}>SINGLE-CH</span>}
                          </div>
                          <span style={{ ...mono, fontSize: 10, color: 'var(--text-muted)' }}>{String(inc.normalised_ts || '').slice(0, 19)}</span>
                        </div>

                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 8 }}>{inc.explanation}</div>

                        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Target: <strong>{inc.data_target}</strong></div>
                          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Dst: <strong style={{ color: '#dc2626' }}>{inc.dst_ip}</strong></div>
                          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Read: <strong style={{ color: '#2563eb' }}>{formatBytes(inc.bytes_accessed)}</strong></div>
                          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Sent: <strong style={{ color: '#dc2626' }}>{formatBytes(inc.bytes_exfil)}</strong></div>
                          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Intent: <strong style={{ color: '#d97706' }}>{(inc.intent_score || 0).toFixed(2)}</strong></div>
                        </div>

                        <div style={{ marginTop: 8, height: 4, background: 'rgba(0,0,0,0.04)', borderRadius: 999, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${Math.min(100, (inc.confidence || 0) * 100)}%`, borderRadius: 999, transition: 'width 0.5s', background: rs.color }} />
                        </div>

                        {expanded && (
                          <div style={{ marginTop: 12, padding: '12px 16px', background: 'rgba(255,255,255,0.6)', borderRadius: 8, border: '1px solid var(--border-color)' }}>
                            <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 8, color: 'var(--text-muted)' }}>CONTRIBUTING FACTORS</div>
                            {factors.length > 0 ? factors.map((f, i) => (
                              <div key={i} style={{ fontSize: 11, color: '#1e293b', marginBottom: 4, paddingLeft: 12, borderLeft: `2px solid ${rs.color}` }}>{f}</div>
                            )) : <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>No detailed factors available</div>}
                            {timeline.length > 0 && (
                              <>
                                <div style={{ fontSize: 11, fontWeight: 700, marginTop: 12, marginBottom: 8, color: 'var(--text-muted)' }}>EVENT TIMELINE</div>
                                {timeline.map((step, i) => (
                                  <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, marginBottom: 4 }}>
                                    <span style={{ ...mono, fontSize: 10, color: rs.color, minWidth: 80 }}>{step.step}</span>
                                    <span style={{ color: '#1e293b' }}>{step.detail}</span>
                                  </div>
                                ))}
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No incidents match filters</p>}
            </div>
          )}

          {/* ═══ TAB: BEHAVIOUR GRAPH ═══ */}
          {!loading && tab === 'graph' && (
            <ForceGraph
              nodes={graphViz.nodes}
              links={graphViz.links}
              nodeMap={graphViz.nodeMap}
              selectedNode={selectedNode}
              setSelectedNode={setSelectedNode}
            />
          )}

          {/* ═══ TAB: TIMELINE ═══ */}
          {!loading && tab === 'timeline' && (
            <CinematicTimeline incidents={incidents} summary={summary} actorChannels={noveltyStats.actorChannels} />
          )}

          {/* ═══ TAB: CHANNELS ═══ */}
          {!loading && tab === 'channels' && (
            <>
              {channels.length > 0 ? (
                <>
                  {/* Single vs Multi summary strip */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                    <div style={{
                      padding: '14px 20px', borderRadius: 12, display: 'flex', alignItems: 'center', gap: 16,
                      background: 'rgba(59,130,246,0.04)', border: '1px solid rgba(59,130,246,0.15)',
                    }}>
                      <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(59,130,246,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <span style={{ fontSize: 16, fontWeight: 900, color: '#3b82f6' }}>1</span>
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 800, color: '#1e293b' }}>Single-Channel Exfiltration</div>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>Actors using exactly one channel</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ ...mono, fontSize: 22, fontWeight: 800, color: '#3b82f6' }}>{noveltyStats.singleChannelActors}</div>
                        <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>{noveltyStats.singleChannelIncidents} incidents</div>
                      </div>
                    </div>
                    <div style={{
                      padding: '14px 20px', borderRadius: 12, display: 'flex', alignItems: 'center', gap: 16,
                      background: 'rgba(139,92,246,0.04)', border: '1px solid rgba(139,92,246,0.15)',
                    }}>
                      <div style={{ width: 40, height: 40, borderRadius: 10, background: 'rgba(139,92,246,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <span style={{ fontSize: 16, fontWeight: 900, color: '#8b5cf6' }}>N</span>
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, fontWeight: 800, color: '#1e293b' }}>Multi-Channel Exfiltration</div>
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>Actors using 2+ channels</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ ...mono, fontSize: 22, fontWeight: 800, color: '#8b5cf6' }}>{noveltyStats.multiChannelActors}</div>
                        <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>{noveltyStats.multiChannelIncidents} incidents</div>
                      </div>
                    </div>
                  </div>

                  {/* Per-channel cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12, marginBottom: 20 }}>
                    {channels.map(ch => (
                      <div key={ch.channel} style={card(CHANNEL_COLOR[ch.channel] || '#666')}>
                        <div style={{ fontSize: 16, fontWeight: 800, color: CHANNEL_COLOR[ch.channel] || '#333', ...mono }}>{ch.channel}</div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 10 }}>
                          <div><div style={{ fontSize: 18, fontWeight: 800, ...mono }}>{ch.count}</div><div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Incidents</div></div>
                          <div><div style={{ fontSize: 14, fontWeight: 700, ...mono }}>{formatBytes(ch.bytes)}</div><div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Bytes</div></div>
                          <div><div style={{ fontSize: 14, fontWeight: 700, ...mono, color: '#d97706' }}>{(ch.avg_confidence * 100).toFixed(0)}%</div><div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Avg Conf.</div></div>
                          <div><div style={{ fontSize: 14, fontWeight: 700, ...mono }}>{(ch.actors || []).length}</div><div style={{ fontSize: 9, color: 'var(--text-muted)' }}>Actors</div></div>
                        </div>
                      </div>
                    ))}
                  </div>
                  {channelPie.length > 0 && (
                    <div style={card('#8b5cf6')}>
                      {sectionHead('Channel Comparison', 'Relative incident volume by exfiltration channel')}
                      <ResponsiveContainer width="100%" height={260}>
                        <BarChart data={channelPie} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                          <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                          <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                          <RTooltip />
                          <Bar dataKey="value" name="Incidents" radius={[6, 6, 0, 0]} animationDuration={600}>
                            {channelPie.map(d => <Cell key={d.name} fill={CHANNEL_COLOR[d.name] || '#666'} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </>
              ) : <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No channel data — run analysis first</p>}
            </>
          )}

          {/* ═══ TAB: RISK HEATMAP ═══ */}
          {!loading && tab === 'heatmap' && (
            <div style={card('#dc2626')}>
              {sectionHead('Risk Heatmap', 'Actors ranked by maximum confidence score. Bar segments show risk distribution.')}
              {riskHeatmap.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {riskHeatmap.map(row => {
                    const total = row.total || 1;
                    return (
                      <div key={row.actor} style={{
                        display: 'flex', alignItems: 'center', gap: 12,
                        padding: '10px 14px', background: 'rgba(0,0,0,0.02)', borderRadius: 8,
                      }}>
                        <div style={{ minWidth: 100, fontSize: 12, fontWeight: 700, color: '#0ea5e9', ...mono }}>{row.actor}</div>
                        <div style={{ flex: 1 }}>
                          <div style={{ height: 24, display: 'flex', borderRadius: 6, overflow: 'hidden' }}>
                            {row.critical > 0 && <div title={`${row.critical} CRITICAL`} style={{ width: `${(row.critical / total) * 100}%`, background: RISK_STYLE.CRITICAL.color, height: '100%' }} />}
                            {row.high > 0 && <div title={`${row.high} HIGH`} style={{ width: `${(row.high / total) * 100}%`, background: RISK_STYLE.HIGH.color, height: '100%' }} />}
                            {row.medium > 0 && <div title={`${row.medium} MEDIUM`} style={{ width: `${(row.medium / total) * 100}%`, background: RISK_STYLE.MEDIUM.color, height: '100%' }} />}
                            {row.low > 0 && <div title={`${row.low} LOW`} style={{ width: `${(row.low / total) * 100}%`, background: RISK_STYLE.LOW.color, height: '100%' }} />}
                          </div>
                          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
                            {row.critical > 0 && <span style={{ fontSize: 9, color: RISK_STYLE.CRITICAL.color }}>{row.critical} CRITICAL</span>}
                            {row.high > 0 && <span style={{ fontSize: 9, color: RISK_STYLE.HIGH.color }}>{row.high} HIGH</span>}
                            {row.medium > 0 && <span style={{ fontSize: 9, color: RISK_STYLE.MEDIUM.color }}>{row.medium} MEDIUM</span>}
                            {row.low > 0 && <span style={{ fontSize: 9, color: RISK_STYLE.LOW.color }}>{row.low} LOW</span>}
                          </div>
                        </div>
                        <div style={{ minWidth: 60, ...mono, fontSize: 14, fontWeight: 800, color: row.maxConf > 0.7 ? '#dc2626' : row.maxConf > 0.4 ? '#d97706' : '#059669', textAlign: 'right' }}>
                          {(row.maxConf * 100).toFixed(0)}%
                        </div>
                        <div style={{ ...mono, fontSize: 10, color: 'var(--text-muted)', minWidth: 50, textAlign: 'right' }}>{row.total} inc.</div>
                      </div>
                    );
                  })}
                </div>
              ) : <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No data — run analysis first</p>}
            </div>
          )}

          {/* ═══ TAB: NOVELTY SHOWCASE ═══ */}
          {!loading && tab === 'novelty' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* ── Single vs Multi Channel Breakdown ── */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <div style={card('#3b82f6')}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                    <div style={{ fontSize: 14, fontWeight: 800, color: '#3b82f6' }}>Single-Channel Exfiltration</div>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ ...mono, fontSize: 22, fontWeight: 800, color: '#3b82f6' }}>{noveltyStats.singleChannelActors}</div>
                        <div style={{ fontSize: 8, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Actors</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ ...mono, fontSize: 22, fontWeight: 800, color: '#60a5fa' }}>{noveltyStats.singleChannelIncidents}</div>
                        <div style={{ fontSize: 8, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Incidents</div>
                      </div>
                    </div>
                  </div>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>
                    Actor used exactly one exfiltration channel (e.g. only USB, only Email, only Web). Each channel is independently detected and scored.
                  </p>
                  <p style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.5, padding: '8px 10px', background: 'rgba(0,0,0,0.02)', borderRadius: 6 }}>
                    Even single-channel exfiltration is flagged with full confidence scoring. The Data Flow engine detects READ&rarr;SEND chains per channel independently: USB (removable media), EMAIL (SMTP/Exchange), CLOUD (S3/OneDrive/Dropbox), WEB (HTTP/HTTPS uploads), BLUETOOTH (OBEX/BT transfers).
                  </p>
                  {/* Per-actor breakdown */}
                  {Object.entries(noveltyStats.actorChannels).filter(([, chs]) => chs.size === 1).length > 0 && (
                    <div style={{ marginTop: 10, padding: '8px 12px', background: 'rgba(59,130,246,0.04)', borderRadius: 8, border: '1px solid rgba(59,130,246,0.1)' }}>
                      <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Single-Channel Actors</div>
                      {Object.entries(noveltyStats.actorChannels).filter(([, chs]) => chs.size === 1).map(([actor, chs]) => (
                        <div key={actor} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                          <span style={{ ...mono, fontSize: 11, fontWeight: 700, color: '#0ea5e9' }}>{actor}</span>
                          <span style={{ fontSize: 9, color: '#64748b' }}>&rarr;</span>
                          {[...chs].map(ch => (
                            <span key={ch} style={{ padding: '1px 6px', borderRadius: 5, fontSize: 9, fontWeight: 700, background: `${CHANNEL_COLOR[ch] || '#666'}15`, color: CHANNEL_COLOR[ch] || '#94a3b8' }}>{ch}</span>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div style={card('#8b5cf6')}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                    <div style={{ fontSize: 14, fontWeight: 800, color: '#8b5cf6' }}>Multi-Channel Exfiltration</div>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ ...mono, fontSize: 22, fontWeight: 800, color: '#8b5cf6' }}>{noveltyStats.multiChannelActors}</div>
                        <div style={{ fontSize: 8, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Actors</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ ...mono, fontSize: 22, fontWeight: 800, color: '#a78bfa' }}>{noveltyStats.multiChannelIncidents}</div>
                        <div style={{ fontSize: 8, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>Incidents</div>
                      </div>
                    </div>
                  </div>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>
                    Actor used multiple channels (USB + Web, Email + Cloud, etc.) to exfiltrate data, making detection harder with single-channel tools. Stronger exfiltration signal.
                  </p>
                  <p style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.5, padding: '8px 10px', background: 'rgba(0,0,0,0.02)', borderRadius: 6 }}>
                    Channel correlation engine groups events within 10-minute time windows and detects actors switching between USB, Email, Cloud, Web, and Bluetooth. Multi-channel activity elevates composite confidence.
                  </p>
                  {Object.entries(noveltyStats.actorChannels).filter(([, chs]) => chs.size > 1).length > 0 && (
                    <div style={{ marginTop: 10, padding: '8px 12px', background: 'rgba(139,92,246,0.04)', borderRadius: 8, border: '1px solid rgba(139,92,246,0.1)' }}>
                      <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Multi-Channel Actors</div>
                      {Object.entries(noveltyStats.actorChannels).filter(([, chs]) => chs.size > 1).map(([actor, chs]) => (
                        <div key={actor} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                          <span style={{ ...mono, fontSize: 11, fontWeight: 700, color: '#0ea5e9' }}>{actor}</span>
                          <span style={{ fontSize: 9, color: '#64748b' }}>&rarr;</span>
                          {[...chs].map(ch => (
                            <span key={ch} style={{ padding: '1px 6px', borderRadius: 5, fontSize: 9, fontWeight: 700, background: `${CHANNEL_COLOR[ch] || '#666'}15`, color: CHANNEL_COLOR[ch] || '#94a3b8' }}>{ch}</span>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* ── Other Novelty Cards (2x2) ── */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 14 }}>
                {[
                  { title: 'Ghost Transfer Detection', count: noveltyStats.ghosts, color: '#dc2626',
                    desc: 'File read detected with no local write, but outbound traffic observed. Inferred exfiltration without direct transfer logs.',
                    detail: 'Engine uses temporal correlation: READ event + absence of WRITE + presence of outbound network activity within configurable window.' },
                  { title: 'Staging Activity', count: noveltyStats.staged, color: '#d97706',
                    desc: 'Pre-exfiltration preparation detected: compression (.zip, .7z), encryption (.enc, .gpg), or batch file creation before transfer.',
                    detail: 'Staging engine scans for known archiver extensions and EPP quarantine events that indicate archiver tools were blocked.' },
                  { title: 'Behavioral Anomaly', count: noveltyStats.behavioral, color: '#059669',
                    desc: 'Intent scoring flagged actors with unusual behaviour patterns: bulk data access, off-hours activity, new device usage.',
                    detail: 'Intent engine computes weighted score from 4 features: bulk_access_rate, off_hours_ratio, new_device_count, staging_activity. All weights configurable.' },
                ].map(item => (
                  <div key={item.title} style={card(item.color)}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                      <div style={{ fontSize: 14, fontWeight: 800, color: item.color }}>{item.title}</div>
                      <div style={{ ...mono, fontSize: 20, fontWeight: 800, color: item.color }}>{item.count}</div>
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>{item.desc}</p>
                    <p style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.5, padding: '8px 10px', background: 'rgba(0,0,0,0.02)', borderRadius: 6 }}>{item.detail}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ═══ TAB: RUNS ═══ */}
          {!loading && tab === 'runs' && (
            <div style={card('#94a3b8')}>
              {sectionHead('Analysis History', 'Past exfiltration intelligence runs with result counts and hashes.')}
              {runs.length > 0 ? (
                <table className="data-table">
                  <thead><tr><th>Run ID</th><th>Incidents</th><th>High Risk</th><th>Actors</th><th>Bytes Out</th><th>Risk</th><th>Status</th><th>Started</th></tr></thead>
                  <tbody>
                    {runs.map(run => (
                      <tr key={run.run_id}>
                        <td style={{ ...mono, fontSize: 10 }}>{run.run_id?.slice(0, 8)}&hellip;</td>
                        <td style={{ ...mono }}>{run.total_incidents}</td>
                        <td style={{ ...mono, color: '#dc2626', fontWeight: 700 }}>{run.high_risk_count}</td>
                        <td style={{ ...mono }}>{run.affected_actors}</td>
                        <td style={{ ...mono, fontSize: 10 }}>{formatBytes(parseInt(run.total_bytes_out || 0))}</td>
                        <td><span style={{
                          padding: '2px 8px', borderRadius: 999, fontSize: 10, fontWeight: 700,
                          background: RISK_STYLE[run.overall_risk]?.bg || RISK_STYLE.LOW.bg,
                          color: RISK_STYLE[run.overall_risk]?.color || RISK_STYLE.LOW.color,
                        }}>{run.overall_risk}</span></td>
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
        </>
      )}
    </div>
  );
}
