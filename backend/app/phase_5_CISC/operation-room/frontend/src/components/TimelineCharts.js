'use client';

/**
 * TimelineCharts — Recharts wrapper for forensic timeline analytics.
 * 
 * Imported as a single lazy-loaded component to avoid the per-component
 * dynamic() import issue that strips props (colors, fills, strokes).
 */

import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, Brush
} from 'recharts';

const TOOLTIP_STYLE = {
  contentStyle: {
    background: 'rgba(8,11,20,0.95)', border: '1px solid rgba(129,140,248,0.25)',
    borderRadius: 10, fontSize: 12, backdropFilter: 'blur(12px)',
    boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
  },
  itemStyle: { color: '#e2e8f0', fontSize: 12 },
  labelStyle: { color: '#94a3b8', fontWeight: 600, marginBottom: 4 },
};

/* ── Activity Over Time (Stacked Area) ────────────────────── */
export function ActivityChart({ data, onTimeRangeBrush }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 25, left: 0 }}>
        <defs>
          <linearGradient id="gHigh" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#f87171" stopOpacity={0.35} />
            <stop offset="95%" stopColor="#f87171" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gMed" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#fbbf24" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gInfo" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#818cf8" stopOpacity={0.25} />
            <stop offset="95%" stopColor="#818cf8" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" />
        <XAxis dataKey="date" stroke="#475569" fontSize={10} tickLine={false} />
        <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
        <Tooltip {...TOOLTIP_STYLE} />
        
        {/* Phase 1: Global Sync Brush Handler */}
        <Brush 
          dataKey="date" 
          height={20} 
          stroke="#6366f1" 
          fill="rgba(15,23,42,0.9)"
          tickFormatter={(tick) => ''} 
          onChange={(idx) => {
             if (onTimeRangeBrush && idx?.startIndex !== undefined && idx?.endIndex !== undefined) {
                onTimeRangeBrush(data[idx.startIndex].date, data[idx.endIndex].date)
             }
          }}
        />

        <Area type="monotone" dataKey="HIGH" stackId="1" stroke="#f87171" fill="url(#gHigh)" strokeWidth={2} />
        <Area type="monotone" dataKey="MEDIUM" stackId="1" stroke="#fbbf24" fill="url(#gMed)" strokeWidth={1.5} />
        <Area type="monotone" dataKey="INFO" stackId="1" stroke="#818cf8" fill="url(#gInfo)" strokeWidth={1.5} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* ── Hourly Distribution (Gradient Bar) ───────────────────── */
export function HourlyChart({ data, onChartClick }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
        <defs>
          <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#818cf8" stopOpacity={0.9} />
            <stop offset="100%" stopColor="#6366f1" stopOpacity={0.4} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" />
        <XAxis dataKey="hour" stroke="#475569" fontSize={9} interval={2} tickLine={false} />
        <YAxis stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
        <Tooltip {...TOOLTIP_STYLE} />
        <Bar dataKey="count" fill="url(#barGrad)" radius={[4, 4, 0, 0]} name="Events" onClick={(e) => onChartClick && e && onChartClick('hour', e.hour)} cursor={onChartClick ? "pointer" : "default"} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── Source Distribution (Donut) ──────────────────────────── */
export function SourcePie({ data, colors, onChartClick }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie data={data} cx="50%" cy="50%" innerRadius={55} outerRadius={82}
          paddingAngle={3} dataKey="value" stroke="none"
          label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
          labelLine={{ stroke: '#475569' }} fontSize={10}
          onClick={(e) => onChartClick && e && onChartClick('source_type', e.name)}
          cursor={onChartClick ? "pointer" : "default"}>
          {data.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
        </Pie>
        <Tooltip {...TOOLTIP_STYLE} />
      </PieChart>
    </ResponsiveContainer>
  );
}

/* ── Actor Activity (Horizontal Bar) ─────────────────────── */
export function ActorBar({ data, colors, onChartClick }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 55 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.06)" />
        <XAxis type="number" stroke="#475569" fontSize={10} tickLine={false} axisLine={false} />
        <YAxis type="category" dataKey="name" stroke="#94a3b8" fontSize={11} width={55} tickLine={false} axisLine={false} />
        <Tooltip {...TOOLTIP_STYLE} />
        <Bar dataKey="value" radius={[0, 6, 6, 0]} name="Events" onClick={(e) => onChartClick && e && onChartClick('actor', e.name)} cursor={onChartClick ? "pointer" : "default"}>
          {data.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} fillOpacity={0.8} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── Severity Donut ──────────────────────────────────────── */
export function SeverityPie({ data, onChartClick }) {
  const colors = { HIGH: '#f87171', MEDIUM: '#fbbf24', INFO: '#818cf8' };
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie data={data} cx="50%" cy="50%" innerRadius={50} outerRadius={75}
          paddingAngle={4} dataKey="value" stroke="none"
          label={({ name, value }) => `${name}: ${value}`} fontSize={11}
          onClick={(e) => onChartClick && e && onChartClick('severity', e.name)}
          cursor={onChartClick ? "pointer" : "default"}>
          {data.map((entry, i) => <Cell key={i} fill={colors[entry.name] || '#666'} />)}
        </Pie>
        <Tooltip {...TOOLTIP_STYLE} />
      </PieChart>
    </ResponsiveContainer>
  );
}

/* ── Threat Radar ────────────────────────────────────────── */
export function ThreatRadar({ data }) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius={70}>
        <PolarGrid stroke="rgba(148,163,184,0.12)" />
        <PolarAngleAxis dataKey="axis" stroke="#94a3b8" fontSize={10} />
        <PolarRadiusAxis stroke="#475569" fontSize={9} />
        <Radar dataKey="value" stroke="#818cf8" fill="#818cf8" fillOpacity={0.2} strokeWidth={2} />
        <Radar dataKey="baseline" stroke="#475569" fill="none" strokeDasharray="4 4" strokeWidth={1} />
        <Tooltip {...TOOLTIP_STYLE} />
      </RadarChart>
    </ResponsiveContainer>
  );
}
