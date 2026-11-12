'use client'

import { Node, mergeAttributes } from '@tiptap/core'
import { ReactNodeViewRenderer, NodeViewWrapper, NodeViewProps } from '@tiptap/react'
import React, { useState, useCallback } from 'react'
import { 
  Clock, AlertTriangle, Network, Database, BarChart3, 
  Trash2, Settings, GripVertical, Maximize2, Minimize2,
  FileText, ExternalLink, Hash, Info, Activity, Crosshair, Grid, List, Filter, Check
} from 'lucide-react'
import { Button } from '@operation-room/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@operation-room/components/ui/dropdown-menu'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@operation-room/components/ui/popover'
import { cn } from '@operation-room/lib/utils'

// Import premium chart components
import { ShapFeatureImportance, ShapWaterfall } from '@operation-room/components/charts/ShapCharts'
import { TimelineVerticalChart, TimelineSwimlane, TimelineSummary } from '@operation-room/components/charts/TimelineCharts'
import { ActivityChart, HourlyChart, SourcePie, ActorBar, ThreatRadar } from '@operation-room/components/TimelineCharts'
import { NetworkFlowTable, NetworkTopology, NetworkStats } from '@operation-room/components/charts/NetworkCharts'
import { CorrelationGraph, CausalChainView, CorrelationSummary } from '@operation-room/components/charts/CorrelationCharts'
import { 
  ScatterChart, Scatter, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, ZAxis 
} from 'recharts'

// ═══════════════════════════════════════════════════════════════════════════
// Types for Evidence Block Data
// ═══════════════════════════════════════════════════════════════════════════

export type EvidenceType = 
  | 'chart' 
  | 'table' 
  | 'metric' 
  | 'finding' 
  | 'timeline-event' 
  | 'anomaly' 
  | 'network-flow'
  | 'shap-explanation'
  | 'correlation-graph'

export type ModuleSource = 
  | 'timeline' 
  | 'anomaly' 
  | 'correlation' 
  | 'crud' 
  | 'network' 
  | 'depth' 
  | 'case'

export interface EvidenceBlockAttrs {
  id: string
  type: EvidenceType
  source: ModuleSource
  title: string
  caption?: string
  figureNumber?: number
  data: any
  filters?: Record<string, string[]>
  metadata?: {
    hash?: string              // SHA-256 of data payload
    timestamp?: string         // When inserted into the report
    runId?: string             // Module run that generated the data
    pageRef?: string           // Which page this block lives on
    verified?: boolean         // Investigator has verified this evidence
    // Provenance fields (forensic lineage)
    citationId?: string        // Auto-generated key e.g. "[EVD-TIMELINE-a3f2]"
    insertionActor?: string    // Who inserted (investigator ID)
    configHash?: string        // Hash of chart config at insertion time
    sourceQuery?: string       // The filter/query that produced this data
    sourceVersion?: number     // Version of the source data when captured
  }
  displayMode?: 'full' | 'compact' | 'inline'
}

// ═══════════════════════════════════════════════════════════════════════════
// Module Icon Mapping
// ═══════════════════════════════════════════════════════════════════════════

const ModuleIcon: Record<ModuleSource, React.FC<{ className?: string }>> = {
  timeline: Clock,
  anomaly: AlertTriangle,
  correlation: Network,
  crud: Database,
  network: Network,
  depth: BarChart3,
  case: FileText,
}

const ModuleColor: Record<ModuleSource, string> = {
  timeline: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
  anomaly: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  correlation: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
  crud: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
  network: 'bg-cyan-500/10 text-cyan-600 border-cyan-500/20',
  depth: 'bg-rose-500/10 text-rose-600 border-rose-500/20',
  case: 'bg-slate-500/10 text-slate-600 border-slate-500/20',
}

const TypeLabels: Record<EvidenceType, string> = {
  'chart': 'Chart',
  'table': 'Data Table',
  'metric': 'Metric',
  'finding': 'Finding',
  'timeline-event': 'Timeline Event',
  'anomaly': 'Anomaly',
  'network-flow': 'Network Flow',
  'shap-explanation': 'SHAP Explanation',
  'correlation-graph': 'Correlation Graph',
}

// ═══════════════════════════════════════════════════════════════════════════
// Evidence Content Renderers
// ═══════════════════════════════════════════════════════════════════════════

interface ContentProps {
  type: EvidenceType
  data: any
  displayMode: 'full' | 'compact' | 'inline'
  filters?: Record<string, any>
  dimensions?: { width: number; height: number }
}

export function EvidenceContent({ type, data, displayMode, filters, dimensions }: ContentProps) {
  switch (type) {
    case 'metric':
      return <MetricContent data={data} displayMode={displayMode} />
    case 'finding':
      return <FindingContent data={data} displayMode={displayMode} />
    case 'table':
      return <TableContent data={data} displayMode={displayMode} />
    case 'chart':
      return <ChartContent data={data} displayMode={displayMode} filters={filters} />
    case 'anomaly':
      return <AnomalyContent data={data} displayMode={displayMode} />
    case 'timeline-event':
      return <TimelineEventContent data={data} displayMode={displayMode} />
    case 'shap-explanation':
      return <ShapContent data={data} displayMode={displayMode} filters={filters} dimensions={dimensions} />
    case 'network-flow':
      return <NetworkFlowContent data={data} displayMode={displayMode} filters={filters} dimensions={dimensions} />
    case 'correlation-graph':
      return <CorrelationContent data={data} displayMode={displayMode} />
    default:
      return (
        <div className="p-4 text-sm text-muted-foreground">
          Unknown evidence type: {type}
        </div>
      )
  }
}

function MetricContent({ data, displayMode }: { data: any; displayMode: string }) {
  const { value, unit, trend, description } = data
  
  if (displayMode === 'inline') {
    return (
      <span className="inline-flex items-center gap-1 font-mono text-sm">
        <span className="font-semibold">{value}</span>
        {unit && <span className="text-muted-foreground">{unit}</span>}
      </span>
    )
  }
  
  return (
    <div className="flex items-center gap-4 p-4">
      <div>
        <p className="text-3xl font-bold tracking-tight">
          {value}
          {unit && <span className="text-lg text-muted-foreground ml-1">{unit}</span>}
        </p>
        {trend && (
          <p className={cn(
            "text-sm font-medium",
            trend > 0 ? "text-red-600" : "text-green-600"
          )}>
            {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
          </p>
        )}
      </div>
      {description && displayMode === 'full' && (
        <p className="text-sm text-muted-foreground">{description}</p>
      )}
    </div>
  )
}

function FindingContent({ data, displayMode }: { data: any; displayMode: string }) {
  const { severity, summary, details, evidence_ids } = data
  
  const severityColors: Record<string, string> = {
    critical: 'bg-red-100 text-red-800 border-red-200',
    high: 'bg-orange-100 text-orange-800 border-orange-200',
    medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    low: 'bg-green-100 text-green-800 border-green-200',
    info: 'bg-blue-100 text-blue-800 border-blue-200',
  }
  
  return (
    <div className="p-4 space-y-2">
      <div className="flex items-start gap-2">
        <span className={cn(
          "px-2 py-0.5 text-xs font-medium rounded border shrink-0",
          severityColors[severity] || severityColors.info
        )}>
          {severity?.toUpperCase() || 'INFO'}
        </span>
        <p className="text-sm font-medium">{summary}</p>
      </div>
      {displayMode === 'full' && details && (
        <p className="text-sm text-muted-foreground pl-4 border-l-2 border-muted">
          {details}
        </p>
      )}
      {evidence_ids?.length > 0 && (
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <Hash className="h-3 w-3" />
          <span>{evidence_ids.length} linked evidence items</span>
        </div>
      )}
    </div>
  )
}

function TableContent({ data, displayMode }: { data: any; displayMode: string }) {
  const { columns, rows, summary } = data
  const displayRows = displayMode === 'compact' ? rows?.slice(0, 3) : rows
  
  if (!columns || !rows) {
    return <div className="p-4 text-sm text-muted-foreground">No table data</div>
  }
  
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-muted/50 border-b">
          <tr>
            {columns.map((col: string, i: number) => (
              <th key={i} className="px-3 py-2 text-left font-medium text-muted-foreground">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayRows?.map((row: any[], rowIdx: number) => (
            <tr key={rowIdx} className="border-b last:border-0 hover:bg-muted/30">
              {row.map((cell, cellIdx) => (
                <td key={cellIdx} className="px-3 py-2 font-mono text-xs">
                  {typeof cell === 'object' ? JSON.stringify(cell) : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {displayMode === 'compact' && rows.length > 3 && (
        <div className="px-3 py-2 text-xs text-muted-foreground text-center border-t">
          + {rows.length - 3} more rows
        </div>
      )}
      {summary && displayMode === 'full' && (
        <div className="px-3 py-2 text-xs text-muted-foreground bg-muted/30 border-t">
          {summary}
        </div>
      )}
    </div>
  )
}

function TimelineHeatmapContent({ events }: { events: any[] }) {
  const heatmap = React.useMemo(() => {
    const grid: Record<string, number[]> = {}
    let maxVal = 0

    events.forEach(e => {
      const src = e.source_type || e.source || 'SYS'
      if (!grid[src]) grid[src] = Array(24).fill(0)
      const d = e.normalised_ts ? new Date(e.normalised_ts) : new Date(e.timestamp)
      const h = isNaN(d.getTime()) ? 0 : d.getHours()
      grid[src][h]++
      if (grid[src][h] > maxVal) maxVal = grid[src][h]
    })
    
    // Sort sources
    const sources = Object.keys(grid).sort((a, b) => {
      const sumA = grid[a].reduce((x, y) => x + y, 0)
      const sumB = grid[b].reduce((x, y) => x + y, 0)
      return sumB - sumA
    })

    return { grid, sources: sources.slice(0, 10), maxVal: maxVal || 1 }
  }, [events])

  if (events.length === 0) {
    return (
      <div className="p-8 text-center bg-slate-50 border rounded-lg border-dashed my-2 shadow-sm flex flex-col items-center justify-center text-muted-foreground min-h-[160px]">
        <Grid className="h-8 w-8 mb-2 opacity-50 text-cyan-500" />
        <p className="text-sm font-medium">No heatmap data.</p>
      </div>
    )
  }



  const SRC: Record<string, string> = {
    AUTH: '#8b5cf6', VPN: '#eab308', DB: '#06b6d4', FW: '#ef4444', FILE: '#10b981', EPP: '#f97316'
  }

  return (
    <div className="p-4 bg-slate-50 border rounded-lg overflow-x-auto shadow-inner my-2">
      <h4 className="text-xs font-bold text-slate-500 mb-4 tracking-wider uppercase">Event Density Heatmap</h4>
      <div style={{ display: 'grid', gridTemplateColumns: '80px repeat(24, 1fr)', gap: '2px', minWidth: '800px' }}>
        <div />
        {Array.from({ length: 24 }, (_, h) => (
          <div key={h} className="text-center text-[10px] font-mono text-slate-400 pb-1 border-b border-slate-200">
            {String(h).padStart(2, '0')}
          </div>
        ))}
        {heatmap.sources.map(src => (
          <React.Fragment key={src}>
            <div className="text-[11px] font-bold flex items-center justify-end pr-2" style={{ color: SRC[src] || '#64748b' }}>
              {src}
            </div>
            {heatmap.grid[src].map((val, h) => {
              const intensity = val / heatmap.maxVal
              const color = SRC[src] || '#64748b'
              return (
                <div key={`${src}-${h}`} 
                     className="h-7 rounded flex items-center justify-center text-[10px] font-bold font-mono transition-transform hover:scale-110"
                     style={{ 
                       background: val > 0 ? `color-mix(in srgb, ${color} ${Math.max(15, intensity * 100)}%, transparent)` : 'rgba(0,0,0,0.03)',
                       color: val > 0 ? '#fff' : 'transparent',
                       cursor: val > 0 ? 'crosshair' : 'default'
                     }}
                     title={`${src} @ ${h}:00 — ${val} events`}>
                  {val > 0 ? val : ''}
                </div>
              )
            })}
          </React.Fragment>
        ))}
      </div>
      <div className="mt-4 flex gap-4 text-[10px] text-slate-400 font-mono">
        <span>darker = more events</span>
        <span>max = {heatmap.maxVal}/cell</span>
        <span>total = {events.length}</span>
      </div>
    </div>
  )
}

function TimelineStatsContent({ events }: { events: any[] }) {
  const stats = React.useMemo(() => {
    const sources = new Set()
    const actors = new Set()
    let anchors = 0
    events.forEach(e => {
      if (e.source_type || e.source) sources.add(e.source_type || e.source)
      if (e.actor) actors.add(e.actor)
      if (e.is_anchor) anchors++
    })
    return { sources: sources.size, actors: actors.size, anchors }
  }, [events])

  return (
    <div className="grid grid-cols-4 gap-4 my-2">
      {[
        { label: 'Total Events', val: events.length.toLocaleString(), c: '#2563eb' },
        { label: 'Anchors', val: stats.anchors, c: '#d97706' },
        { label: 'Sources', val: stats.sources, c: '#0ea5e9' },
        { label: 'Actors', val: stats.actors, c: '#059669' },
      ].map((card, idx) => (
        <div key={idx} className="p-4 bg-white border rounded-xl border-t-4 shadow-sm" style={{ borderTopColor: card.c }}>
           <div className="text-2xl font-bold font-mono" style={{ color: card.c }}>{card.val}</div>
           <div className="text-[10px] font-bold text-slate-500 uppercase mt-1 tracking-wider">{card.label}</div>
        </div>
      ))}
    </div>
  )
}

export function ChartContent({ data, displayMode, filters }: { data: any; displayMode?: string; filters?: Record<string, string[]> }) {
  if (!data) return <div className="p-4 text-xs text-slate-400 text-center border-dashed border-2 rounded">No chart data available</div>
  const { chartType, events, swimlanes, summary, timeline } = data
  let allEvents = events || timeline || summary?.events || swimlanes || []
  
  if (filters && Object.keys(filters).length > 0) {
    allEvents = allEvents.filter((ev: any) => {
      let isMatch = true
      if (filters.severity?.length > 0) {
        isMatch = isMatch && filters.severity.includes(ev.severity?.toUpperCase() || 'INFO')
      }
      if (filters.actor?.length > 0) {
        isMatch = isMatch && filters.actor.includes(ev.actor || 'System')
      }
      if (filters.source?.length > 0) {
        isMatch = isMatch && filters.source.includes(ev.source_type || ev.source || 'SYS')
      }
      if (filters.minRisk !== undefined) {
        const rScore = Number(ev.risk_score || ev.score || 0)
        isMatch = isMatch && rScore >= Number(filters.minRisk)
      }
      if (filters.excludeInfo) {
        const sev = (ev.severity || '').toUpperCase()
        isMatch = isMatch && sev !== 'INFO' && sev !== 'LOW'
      }
      return isMatch
    })
  }
  
  // Area Chart (Activity Chart)
  if (chartType === 'timeline-area-chart') {
    if (allEvents.length === 0) {
      return (
        <div className="p-8 text-center bg-card rounded-lg border border-dashed my-2 shadow-sm flex flex-col items-center justify-center text-muted-foreground min-h-[160px]">
          <Activity className="h-8 w-8 mb-2 opacity-50 text-cyan-500" />
          <p className="text-sm font-medium">No timeline events available.</p>
          <p className="text-xs opacity-70 mt-1">Populate the timeline to visualize event density.</p>
        </div>
      )
    }

    const activityData = allEvents.reduce((acc: Record<string, any>, ev: any) => {
      const d = ev.normalised_ts ? new Date(ev.normalised_ts) : new Date(ev.timestamp)
      const dateStr = isNaN(d.getTime()) ? 'Unknown' : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
      if (!acc[dateStr]) acc[dateStr] = { date: dateStr, HIGH: 0, MEDIUM: 0, INFO: 0 }
      
      const rawSev = ev.severity || 'INFO'
      const sev = rawSev.toUpperCase()
      if (['HIGH', 'MEDIUM', 'INFO'].includes(sev)) {
         acc[dateStr][sev]++
      } else if (sev === 'CRITICAL') {
         acc[dateStr]['HIGH']++
      } else {
         acc[dateStr]['INFO']++
      }
      return acc
    }, {})
    
    return (
      <div className="p-2 bg-card rounded-lg border my-2 shadow-sm">
         <h4 className="text-xs font-medium text-muted-foreground mb-2 pl-2 pt-2 uppercase tracking-wider">Event Activity Density</h4>
         <ActivityChart data={Object.values(activityData)} onTimeRangeBrush={(range: any) => window.dispatchEvent(new CustomEvent('globalTimeSlice', { detail: range }))} />
      </div>
    )
  }

  // Hourly Chart
  if (chartType === 'timeline-hourly-chart') {
    if (allEvents.length === 0) {
      return (
        <div className="p-8 text-center bg-card rounded-lg border border-dashed my-2 shadow-sm flex flex-col items-center justify-center text-muted-foreground min-h-[160px]">
          <BarChart3 className="h-8 w-8 mb-2 opacity-50 text-indigo-500" />
          <p className="text-sm font-medium">No events for hourly distribution.</p>
        </div>
      )
    }

    const hourlyMap = allEvents.reduce((acc: Record<string, number>, ev: any) => {
      const d = ev.normalised_ts ? new Date(ev.normalised_ts) : new Date(ev.timestamp)
      const h = isNaN(d.getTime()) ? 0 : d.getHours()
      acc[h] = (acc[h] || 0) + 1
      return acc
    }, {})
    const hourlyData = Array.from({ length: 24 }, (_, h) => ({
      hour: `${String(h).padStart(2, '0')}:00`,
      count: hourlyMap[h] || 0
    }))
    return (
      <div className="p-2 bg-card rounded-lg border my-2 shadow-sm">
         <h4 className="text-xs font-medium text-muted-foreground mb-2 pl-2 pt-2 uppercase tracking-wider">Hourly Distribution</h4>
         <HourlyChart data={hourlyData} onChartClick={() => {}} />
      </div>
    )
  }

  // Source Chart
  if (chartType === 'timeline-source-chart') {
    if (allEvents.length === 0) {
      return (
        <div className="p-8 text-center bg-card rounded-lg border border-dashed my-2 shadow-sm flex flex-col items-center justify-center text-muted-foreground min-h-[160px]">
          <PieChart className="h-8 w-8 mb-2 opacity-50 text-amber-500" />
          <p className="text-sm font-medium">No sources to distribute.</p>
        </div>
      )
    }

    const sourceMap = allEvents.reduce((acc: Record<string, number>, ev: any) => {
      const src = ev.source_type || ev.source || 'Unknown'
      acc[src] = (acc[src] || 0) + 1
      return acc
    }, {})
    const sourceData = Object.entries(sourceMap).map(([name, value]) => ({ name, value }))
    return (
      <div className="p-2 bg-card rounded-lg border my-2 shadow-sm">
         <h4 className="text-xs font-medium text-muted-foreground mb-2 pl-2 pt-2 uppercase tracking-wider">Events by Source</h4>
         <SourcePie data={sourceData} colors={['#6366f1', '#eab308', '#ef4444', '#10b981', '#f97316']} onChartClick={() => {}} />
      </div>
    )
  }

  // Actor Chart
  if (chartType === 'timeline-actor-chart') {
    if (allEvents.length === 0) {
      return (
        <div className="p-8 text-center bg-card rounded-lg border border-dashed my-2 shadow-sm flex flex-col items-center justify-center text-muted-foreground min-h-[160px]">
          <BarChart3 className="h-8 w-8 mb-2 opacity-50 text-fuchsia-500" />
          <p className="text-sm font-medium">No actor data available.</p>
        </div>
      )
    }

    const actorMap = allEvents.reduce((acc: Record<string, number>, ev: any) => {
      const act = ev.actor || 'System'
      acc[act] = (acc[act] || 0) + 1
      return acc
    }, {})
    const actorData = Object.entries(actorMap)
      .map(([actor, count]) => ({ actor, count: count as number }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5) // top 5 actors
    return (
      <div className="p-2 bg-card rounded-lg border my-2 shadow-sm">
         <h4 className="text-xs font-medium text-muted-foreground mb-2 pl-2 pt-2 uppercase tracking-wider">Top Actors</h4>
         <ActorBar data={actorData} colors={['#8b5cf6', '#a855f7', '#d946ef', '#f43f5e']} onChartClick={() => {}} />
      </div>
    )
  }

  // Command Center Stats
  if (chartType === 'timeline-command-center') {
    return <TimelineStatsContent events={allEvents} />
  }

  // Event Density Heatmap
  if (chartType === 'timeline-heatmap') {
    return <TimelineHeatmapContent events={allEvents} />
  }

  // Threat Metrics Radar
  if (chartType === 'timeline-radar') {
    if (allEvents.length === 0) {
      return (
        <div className="p-8 text-center bg-card rounded-lg border border-dashed my-2 shadow-sm flex flex-col items-center justify-center text-muted-foreground min-h-[160px]">
          <Crosshair className="h-8 w-8 mb-2 opacity-50 text-rose-500" />
          <p className="text-sm font-medium">Insufficient data for Threat Radar.</p>
        </div>
      )
    }

    const hourlyMap = allEvents.reduce((acc: Record<string, number>, ev: any) => {
      const d = ev.normalised_ts ? new Date(ev.normalised_ts) : new Date(ev.timestamp)
      const h = isNaN(d.getTime()) ? 0 : d.getHours()
      acc[h] = (acc[h] || 0) + 1
      return acc
    }, {})
    
    const pacingCount = Object.values(hourlyMap).reduce((acc: number, val: unknown) => {
      return acc + ((val as number) > (allEvents.length / 24) * 2 ? 1 : 0)
    }, 0)

    const uniqueSources = new Set(allEvents.map((e: any) => e.source_type || e.source)).size
    const uniqueActors = new Set(allEvents.map((e: any) => e.actor)).size

    const radarData = [
      { metric: 'Volume', value: Math.max(0, Math.min(100, Math.log10(allEvents.length) * 20)) },
      { metric: 'Gravity', value: Math.max(0, Math.min(100, (allEvents.filter((e: any) => e.severity?.toUpperCase() === 'HIGH').length / (allEvents.length || 1)) * 100)) },
      { metric: 'Spread', value: Math.max(0, Math.min(100, uniqueSources * 15)) },
      { metric: 'Actors', value: Math.max(0, Math.min(100, uniqueActors * 10)) },
      { metric: 'Pacing', value: Math.max(0, Math.min(100, pacingCount * 10)) }
    ]
    return (
      <div className="p-2 bg-card rounded-lg border my-2 shadow-sm">
         <h4 className="text-xs font-medium text-muted-foreground mb-2 pl-2 pt-2 uppercase tracking-wider">Threat Geometry</h4>
         <ThreatRadar data={radarData} />
      </div>
    )
  }

  // Timeline vertical chart fallback
  if (chartType === 'timeline' || chartType === 'timeline-vertical-list' || (!chartType && events)) {
    const timelineEvents = allEvents
    if (timelineEvents.length === 0) {
      return (
        <div className="p-4">
          <div className="p-8 text-center bg-card rounded-lg border border-dashed my-2 flex flex-col items-center justify-center text-muted-foreground min-h-[160px]">
            <List className="h-8 w-8 mb-2 opacity-50 text-slate-500" />
            <p className="text-sm font-medium">No chronological flow data.</p>
          </div>
        </div>
      )
    }
    return (
      <div className="p-4">
        <TimelineVerticalChart 
          events={timelineEvents.slice(0, displayMode === 'compact' ? 5 : 20)}
          highlightAnchor={true}
          className={displayMode === 'compact' ? 'max-h-48' : 'max-h-96'}
        />
        {displayMode === 'compact' && timelineEvents.length > 5 && (
          <p className="text-xs text-muted-foreground text-center mt-2">
            + {timelineEvents.length - 5} more events
          </p>
        )}
      </div>
    )
  }
  
  // Swimlane view
  if (chartType === 'swimlane' || swimlanes) {
    const swimlaneEvents = swimlanes || events || []
    return (
      <div className="p-4">
        <TimelineSwimlane 
          events={swimlaneEvents}
          groupBy="actor"
          className={displayMode === 'compact' ? 'h-40' : 'h-64'}
        />
      </div>
    )
  }
  
  // Timeline summary
  if (chartType === 'timeline-summary' || summary) {
    const summaryEvents = summary?.events || events || timeline || []
    return (
      <div className="p-4">
        <TimelineSummary 
          events={summaryEvents}
          className={displayMode === 'compact' ? '' : 'py-2'}
        />
      </div>
    )
  }

  // ── Anomaly Component Renderers ─────────────────────────────────────────

  if (chartType === 'anomaly-score-timeline') {
    const topAnomalies = data.summary?.top_anomalies || []
    // Map to scatter data format
    const scatterData = topAnomalies.map((a: any) => ({
      time: new Date(a.timestamp).getTime(),
      score: a.score * 100,
      action: a.action || 'Unknown',
      actor: a.actor || 'System'
    })).sort((a: any, b: any) => a.time - b.time)
    
    // Normalize time to a relative index for the X axis, or just use raw times formatted
    const start = scatterData.length > 0 ? scatterData[0].time : 0
    const normalizedData = scatterData.map((d: any) => ({
      ...d,
      relativeHrs: ((d.time - start) / (1000 * 60 * 60)).toFixed(1),
      displayTime: new Date(d.time).toLocaleTimeString()
    }))

    return (
      <div className="p-4 border rounded-lg bg-card my-2 shadow-sm">
        <h4 className="text-sm font-semibold mb-4">Anomaly Score Timeline</h4>
        <div className={displayMode === 'compact' ? 'h-48' : 'h-72'}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.2} stroke="#8b5cf6" />
              <XAxis dataKey="displayTime" name="Time" tick={{fontSize: 10}} tickMargin={10} />
              <YAxis dataKey="score" name="Score" domain={[0, 100]} tick={{fontSize: 10}} />
              <ZAxis range={[50, 200]} />
              <RechartsTooltip 
                cursor={{ strokeDasharray: '3 3' }}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload
                    return (
                      <div className="bg-slate-900 border-slate-700 p-2 border rounded shadow-lg text-white text-xs">
                        <p className="font-bold text-amber-500">{data.score.toFixed(1)}% Anomaly</p>
                        <p>{data.displayTime}</p>
                        <p>Action: {data.action}</p>
                        <p>Actor: {data.actor}</p>
                      </div>
                    )
                  }
                  return null
                }}
              />
              <Scatter name="Anomalies" data={normalizedData} fill="#f43f5e" />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>
    )
  }

  if (chartType === 'anomaly-source-dist') {
    const bySource = data.summary?.by_source || {}
    const pieData = Object.entries(bySource).map(([name, stats]: [string, any]) => ({
      name,
      value: stats.anomalies,
      total: stats.total
    })).filter(d => d.value > 0)
    
    const COLORS = ['#f43f5e', '#ec4899', '#d946ef', '#a855f7', '#8b5cf6', '#6366f1']

    return (
      <div className="p-4 border rounded-lg bg-card my-2 shadow-sm">
        <h4 className="text-sm font-semibold mb-4">Anomalous Activity by Source</h4>
        <div className={displayMode === 'compact' ? 'h-48' : 'h-64'}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={displayMode === 'compact' ? 40 : 60}
                outerRadius={displayMode === 'compact' ? 70 : 100}
                paddingAngle={2}
                dataKey="value"
              >
                {pieData.map((_, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <RechartsTooltip 
                formatter={(value: any, name: any, props: any) => [
                  `${value} anomalies (${props.payload.total} total events)`, 
                  name || 'Unknown'
                ]}
                contentStyle={{ borderRadius: '8px', fontSize: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    )
  }

  // Default chart placeholder
  return (
    <div className={cn(
      "flex items-center justify-center bg-muted/20 border rounded m-4",
      displayMode === 'compact' ? 'h-32' : 'h-64'
    )}>
      <div className="text-center text-muted-foreground">
        <BarChart3 className="h-8 w-8 mx-auto mb-2" />
        <p className="text-sm font-medium">{chartType || 'Chart'} Visualization</p>
        <p className="text-xs">Interactive chart renders here</p>
      </div>
    </div>
  )
}

function AnomalyContent({ data, displayMode }: { data: any; displayMode: string }) {
  const { score, actor, action, features, timestamp } = data
  
  const scoreColor = score > 0.8 ? 'text-red-600' : 
                     score > 0.5 ? 'text-orange-600' : 
                     score > 0.3 ? 'text-yellow-600' : 'text-green-600'
  
  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className={cn("h-5 w-5", scoreColor)} />
          <span className={cn("text-2xl font-bold", scoreColor)}>
            {(score * 100).toFixed(1)}%
          </span>
          <span className="text-sm text-muted-foreground">anomaly score</span>
        </div>
        {timestamp && (
          <span className="text-xs text-muted-foreground font-mono">{timestamp}</span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        {actor && (
          <div>
            <span className="text-muted-foreground">Actor:</span>
            <span className="ml-2 font-mono">{actor}</span>
          </div>
        )}
        {action && (
          <div>
            <span className="text-muted-foreground">Action:</span>
            <span className="ml-2 font-mono">{action}</span>
          </div>
        )}
      </div>
      {displayMode === 'full' && features && features.length > 0 && (
        <div className="mt-3 pt-3 border-t">
          <p className="text-xs text-muted-foreground mb-2">Contributing Features:</p>
          <div className="flex flex-wrap gap-1">
            {features.slice(0, 5).map((f: any, i: number) => (
              <span key={i} className="px-2 py-0.5 bg-muted rounded text-xs font-mono">
                {f.name}: {f.value?.toFixed(2)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TimelineEventContent({ data, displayMode }: { data: any; displayMode: string }) {
  const { timestamp, event_type, source, message, severity, events } = data
  const clusters = data.clusters || []
  
  if (clusters && clusters.length > 0) {
    return (
      <div className="p-4">
        <TimelineVerticalChart
          events={clusters.map((c: any) => ({
            id: String(c.cluster_id || Math.random()),
            timestamp: c.start || "N/A",
            event_type: "Density Cluster",
            severity: c.cluster_id === 'outliers' ? 'high' : 'info',
            source: "DBSCAN",
            actor: `Count: ${c.event_count || 0}`,
          }))}
          highlightAnchor={true}
          className={displayMode === 'compact' ? 'max-h-48' : 'max-h-80'}
        />
        {displayMode === 'compact' && clusters.length > 5 && (
          <p className="text-xs text-muted-foreground text-center mt-2">
            + {clusters.length - 5} more clusters
          </p>
        )}
      </div>
    )
  }

  
  // If we have multiple events, use the vertical chart
  if (events && events.length > 0) {
    return (
      <div className="p-4">
        <TimelineVerticalChart 
          events={events.slice(0, displayMode === 'compact' ? 5 : 10)}
          highlightAnchor={true}
          className={displayMode === 'compact' ? 'max-h-48' : 'max-h-80'}
        />
        {displayMode === 'compact' && events.length > 5 && (
          <p className="text-xs text-muted-foreground text-center mt-2">
            + {events.length - 5} more events
          </p>
        )}
      </div>
    )
  }
  
  // Single event display
  const severityColors: Record<string, string> = {
    critical: 'bg-red-100 text-red-800',
    high: 'bg-orange-100 text-orange-800',
    medium: 'bg-yellow-100 text-yellow-800',
    low: 'bg-green-100 text-green-800',
    info: 'bg-blue-100 text-blue-800',
  }
  
  return (
    <div className="p-4">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-20 text-right">
          <span className="text-xs font-mono text-muted-foreground">
            {timestamp?.split('T')[1]?.substring(0, 8) || timestamp}
          </span>
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className={cn(
              "px-2 py-0.5 text-xs font-medium rounded",
              severityColors[severity] || severityColors.info
            )}>
              {event_type}
            </span>
            {source && (
              <span className="text-xs text-muted-foreground">{source}</span>
            )}
          </div>
          {message && (
            <p className="mt-1 text-sm">{message}</p>
          )}
        </div>
      </div>
    </div>
  )
}

function ShapContent({ data, displayMode, filters, dimensions }: { data: any; displayMode: string; filters?: Record<string, any>; dimensions?: { width: number; height: number } }) {
  const { features, base_value, prediction, chartType } = data
  
  // Convert features to the format expected by chart components
  let chartFeatures = features?.map((f: any) => ({
    feature: f.name || f.feature || 'Unknown',
    contribution: f.contribution || f.importance || f.value || 0,
    value: f.rawValue || f.value || 0,
    baseValue: f.baseValue || base_value,
  })) || []
  
  // WIDGET SPILL PREVENTION & FILTERING
  if (Array.isArray(filters?.excludedFeatures) && filters.excludedFeatures.length > 0) {
     chartFeatures = chartFeatures.filter((f: any) => !filters.excludedFeatures.includes(f.feature));
  }

  
    if (filters?.labelOverrides) {
      chartFeatures = chartFeatures.map((f: any) => ({ ...f, feature: filters.labelOverrides[f.feature] || f.feature }))
    }
    let renderLimit = chartFeatures.length; // Default to full length of surviving features
  if (displayMode === 'compact') {
     renderLimit = 5;
  }
  
  if (filters?.topN) {
     renderLimit = Number(filters.topN)
  } else if (dimensions?.height) {
       // A typical SHAP row is ~45px + 145px for header overhead.
       // Auto-slice dataset rigorously to prevent SVG overlap outside bounded canvas box.
       const spaceAllocatedLimit = Math.max(1, Math.floor((dimensions.height - 145) / 45))
  }
  
  chartFeatures = chartFeatures.slice(0, renderLimit)
  
  // Use actual chart components based on chartType or displayMode
  if (displayMode === 'compact') {
    return (
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium">{filters?.titleOverride || 'SHAP Feature Importance'}</span>
          {prediction !== undefined && (
            <span className="px-2 py-0.5 bg-muted rounded text-xs">
              Prediction: {typeof prediction === 'number' ? prediction.toFixed(3) : prediction}
            </span>
          )}
        </div>
        <ShapFeatureImportance 
          features={chartFeatures}
          maxFeatures={5}
          className="h-auto"
          colors={filters?.colors}
        />
      </div>
    )
  }

  // Full mode - show waterfall chart
  if (chartType === 'waterfall') {
    return (
      <div className="p-4">
        <ShapWaterfall 
          features={chartFeatures}
          baseValue={base_value || 0.5}
          outputValue={prediction || 0.8}
          className="h-auto"
          colors={filters?.colors}
        />
      </div>
    )
  }

  // Default: Feature importance with more features
  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium">{filters?.titleOverride || 'SHAP Feature Importance'}</span>
        {prediction !== undefined && (
          <span className="px-2 py-0.5 bg-muted rounded text-xs">
            Prediction: {typeof prediction === 'number' ? prediction.toFixed(3) : prediction}
          </span>
        )}
      </div>
      <ShapFeatureImportance 
        features={chartFeatures}
        maxFeatures={renderLimit}
        className="h-auto"
        colors={filters?.colors}
      />
    </div>
  )
}

export function NetworkFlowContent({ data, displayMode, filters, dimensions }: { data: any; displayMode?: string; filters?: Record<string, any>; dimensions?: { width: number; height: number } }) {
  const { src_ip, dst_ip, bytes, packets, protocol, direction, nodes, stats, chartType } = data
  let { flows } = data
  
  if (filters && Object.keys(filters).length > 0 && flows?.length) {
    flows = flows.filter((f: any) => {
      let isMatch = true
      if (filters.severity?.length > 0) {
        isMatch = isMatch && filters.severity.includes(String(f.risk_score > 80 ? 'HIGH' : f.risk_score > 40 ? 'MEDIUM' : 'INFO'))
      }
      if (filters.actor?.length > 0) {
        isMatch = isMatch && filters.actor.includes(f.protocol || 'TCP')
      }
      return isMatch
    })
  }
  
  if (chartType === 'network-flow-density' || chartType === 'network-activity-volume') {
    const series = stats?.time_series || []
    const chartData = series.map((s: any) => ({
      time: new Date(s.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
      connections: s.connections || s.count || 0,
      bytes: s.bytes || 0
    }))

    return (
      <div className="p-4 border rounded-lg bg-card my-2 shadow-sm">
        <h4 className="text-sm font-semibold mb-4">Network Flow/Activity Density</h4>
        <div className={displayMode === 'compact' ? 'h-48' : 'h-72'}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorConns" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis dataKey="time" tick={{fontSize: 10}} tickMargin={10} />
              <YAxis tick={{fontSize: 10}} />
              <CartesianGrid strokeDasharray="3 3" opacity={0.1} vertical={false} />
              <RechartsTooltip 
                contentStyle={{ borderRadius: '8px', fontSize: '12px', border: '1px solid #e2e8f0' }}
              />
              <Area 
                type="monotone" 
                dataKey="connections" 
                stroke="#0ea5e9" 
                strokeWidth={2}
                fillOpacity={1} 
                fill="url(#colorConns)" 
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    )
  }

  // If we have multiple flows, use the table component
  if (flows && flows.length > 0) {
    return (
      <div className="p-4">
        <NetworkFlowTable 
          flows={flows}
          maxRows={displayMode === 'compact' ? 5 : 20}
          className="h-auto"
        />
        {displayMode === 'compact' && flows.length > 5 && (
          <p className="text-xs text-muted-foreground text-center mt-2">
            + {flows.length - 5} more flows
          </p>
        )}
      </div>
    )
  }
  
  // If we have topology data, show the network graph
  if (nodes && nodes.length > 0) {
    return (
      <div className="p-4">
        <NetworkTopology 
          nodes={nodes}
          flows={flows || []}
          className={displayMode === 'compact' ? 'h-40' : 'h-64'}
        />
      </div>
    )
  }
  
  // If we have stats, show network stats
  if (stats) {
    return (
      <div className="p-4">
        <NetworkStats 
          flows={stats.flows || []}
        />
      </div>
    )
  }
  
  // Single flow display (legacy format)
  return (
    <div className="p-4">
      <div className="flex items-center gap-3">
        <div className="font-mono text-sm">
          <span className="text-muted-foreground">From:</span>
          <span className="ml-2">{src_ip}</span>
        </div>
        <span className="text-lg text-muted-foreground">
          {direction === 'outbound' ? '→' : '←'}
        </span>
        <div className="font-mono text-sm">
          <span className="text-muted-foreground">To:</span>
          <span className="ml-2">{dst_ip}</span>
        </div>
      </div>
      <div className="flex gap-4 mt-2 text-xs text-muted-foreground">
        {protocol && <span>Protocol: {protocol}</span>}
        {bytes && <span>Bytes: {bytes.toLocaleString()}</span>}
        {packets && <span>Packets: {packets.toLocaleString()}</span>}
      </div>
    </div>
  )
}

function CorrelationContent({ data, displayMode }: { data: any; displayMode: string }) {
  const { nodes, edges, central_entity, causal_chain, clusters, summary } = data
  
  // If we have a causal chain, show it
  if (causal_chain) {
    return (
      <div className="p-4">
        <CausalChainView 
          chain={causal_chain}
          className="h-auto"
        />
      </div>
    )
  }
  
  // If we have summary stats, show correlation summary
  if (summary && summary.nodes) {
    return (
      <div className="p-4">
        <CorrelationSummary 
          nodes={summary.nodes || nodes || []}
          edges={summary.edges || edges || []}
          clusters={summary.clusters || clusters}
        />
      </div>
    )
  }
  
  // If we have nodes and edges, show the graph
  if (nodes && nodes.length > 0) {
    return (
      <div className="p-4">
        <CorrelationGraph 
          nodes={nodes}
          edges={edges || []}
          clusters={clusters}
          className={displayMode === 'compact' ? 'h-40' : 'h-64'}
        />
      </div>
    )
  }
  
  // Fallback placeholder
  return (
    <div className={cn(
      "flex items-center justify-center bg-muted/20 border rounded m-4",
      displayMode === 'compact' ? 'h-32' : 'h-64'
    )}>
      <div className="text-center text-muted-foreground">
        <Network className="h-8 w-8 mx-auto mb-2" />
        <p className="text-sm font-medium">Correlation Graph</p>
        <p className="text-xs">
          {nodes?.length || 0} nodes, {edges?.length || 0} edges
        </p>
        {central_entity && (
          <p className="text-xs mt-1">Central: {central_entity}</p>
        )}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Evidence Block Node View Component
// ═══════════════════════════════════════════════════════════════════════════

function EvidenceBlockComponent({ node, updateAttributes, deleteNode, selected }: NodeViewProps) {
  const attrs = node.attrs as EvidenceBlockAttrs
  const [isExpanded, setIsExpanded] = useState(attrs.displayMode !== 'compact')
  const [showMetadata, setShowMetadata] = useState(false)
  
  const filterOptions = React.useMemo(() => {
    const events = attrs.data?.events || attrs.data?.timeline || attrs.data?.summary?.events || attrs.data?.swimlanes || attrs.data?.flows || []
    if (!Array.isArray(events) || events.length === 0) return null
    
    const severities = new Set<string>()
    const actors = new Set<string>()
    const sources = new Set<string>()
    
    events.forEach(ev => {
      const sev = ev.severity?.toUpperCase() || (ev.risk_score > 80 ? 'HIGH' : ev.risk_score > 40 ? 'MEDIUM' : 'INFO')
      if (sev) severities.add(String(sev))
      
      const actor = ev.actor || ev.protocol || 'System'
      if (actor) actors.add(String(actor))
        
      const src = ev.source_type || ev.source || 'SYS'
      if (src) sources.add(String(src))
    })
    
    return {
      severity: Array.from(severities),
      actor: Array.from(actors),
      source: Array.from(sources)
    }
  }, [attrs.data])
  
  const Icon = ModuleIcon[attrs.source] || FileText
  const colorClass = ModuleColor[attrs.source] || ModuleColor.case
  
  const handleToggleExpand = useCallback(() => {
    const newMode = isExpanded ? 'compact' : 'full'
    setIsExpanded(!isExpanded)
    updateAttributes({ displayMode: newMode })
  }, [isExpanded, updateAttributes])
  
  const handleOpenSource = useCallback(() => {
    window.dispatchEvent(new CustomEvent('evidence:navigate', {
      detail: { source: attrs.source, id: attrs.id, data: attrs.data }
    }))
  }, [attrs])
  
  return (
    <NodeViewWrapper 
      className={cn(
        "evidence-block my-4 rounded-lg border transition-all",
        selected && "ring-2 ring-blue-500 ring-offset-2",
        colorClass
      )}
      data-evidence-id={attrs.id}
      data-evidence-type={attrs.type}
      data-evidence-source={attrs.source}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b bg-white/50">
        <div className="flex items-center gap-2">
          <div 
            className="cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground"
            contentEditable={false}
          >
            <GripVertical className="h-4 w-4" />
          </div>
          
          <Icon className="h-4 w-4" />
          <span className="text-xs font-medium uppercase tracking-wide">
            {attrs.source}
          </span>
          <span className="text-xs text-muted-foreground">•</span>
          <span className="text-xs px-1.5 py-0.5 bg-white/50 border rounded">
            {TypeLabels[attrs.type]}
          </span>
          
          {attrs.figureNumber && (
            <span className="text-xs font-medium text-muted-foreground">
              Fig. {attrs.figureNumber}
            </span>
          )}

          {attrs.metadata?.citationId && (
            <button
              className="text-[10px] font-geist-mono px-1.5 py-0.5 bg-sky-50 text-sky-700 border border-sky-200 rounded cursor-pointer hover:bg-sky-100 transition-colors"
              onClick={() => navigator.clipboard.writeText(attrs.metadata?.citationId || '')}
              title="Click to copy citation key"
              contentEditable={false}
            >
              {attrs.metadata.citationId}
            </button>
          )}
        </div>
        
        <div className="flex items-center gap-1">
          {attrs.metadata?.verified !== undefined && (
            <span className={cn(
              "text-xs px-1.5 py-0.5 rounded",
              attrs.metadata.verified 
                ? "bg-green-100 text-green-800" 
                : "bg-red-100 text-red-800"
            )}>
              {attrs.metadata.verified ? 'Verified' : 'Unverified'}
            </span>
          )}
          
          <Button 
            variant="ghost" 
            size="icon" 
            className="h-6 w-6"
            onClick={() => setShowMetadata(!showMetadata)}
            title="View metadata"
          >
            <Info className="h-3 w-3" />
          </Button>

          <Button 
            variant="ghost" 
            size="icon" 
            className="h-6 w-6"
            onClick={handleToggleExpand}
          >
            {isExpanded ? 
              <Minimize2 className="h-3 w-3" /> : 
              <Maximize2 className="h-3 w-3" />
            }
          </Button>
          
          {filterOptions && (() => {
            const activeCount = attrs.filters
              ? Object.values(attrs.filters).reduce((sum, arr) => sum + (arr?.length || 0), 0)
              : 0
            const categoryIcons: Record<string, React.ReactNode> = {
              severity: <AlertTriangle className="h-3 w-3 text-amber-500" />,
              actor: <GripVertical className="h-3 w-3 text-cyan-500" />,
              source: <Database className="h-3 w-3 text-emerald-500" />,
            }
            const categoryColors: Record<string, string> = {
              severity: 'border-l-amber-400',
              actor: 'border-l-cyan-400',
              source: 'border-l-emerald-400',
            }
            return (
            <Popover>
              <PopoverTrigger asChild>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className={cn(
                    "h-6 w-6 relative transition-all duration-200",
                    activeCount > 0
                      ? "text-indigo-600 bg-indigo-50 hover:bg-indigo-100 shadow-[0_0_8px_rgba(99,102,241,0.25)]"
                      : "hover:text-indigo-500"
                  )}
                  title="Filter Data"
                >
                  <Filter className="h-3 w-3" />
                  {activeCount > 0 && (
                    <span className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-indigo-600 text-white text-[8px] font-bold flex items-center justify-center ring-2 ring-white animate-in zoom-in-50">
                      {activeCount}
                    </span>
                  )}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-72 p-0 overflow-hidden" align="end" sideOffset={8}>
                {/* Header */}
                <div className="px-4 py-3 bg-gradient-to-r from-indigo-50 to-violet-50 dark:from-indigo-950/30 dark:to-violet-950/20 border-b">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-md bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center">
                        <Filter className="h-3 w-3 text-indigo-600" />
                      </div>
                      <div>
                        <h4 className="font-semibold text-xs text-foreground">Data Filters</h4>
                        <p className="text-[10px] text-muted-foreground">Slice component data</p>
                      </div>
                    </div>
                    {activeCount > 0 && (
                      <span className="px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 text-[10px] font-bold">
                        {activeCount} active
                      </span>
                    )}
                  </div>
                </div>
                
                {/* Filter Categories */}
                <div className="p-3 space-y-3 max-h-[320px] overflow-y-auto">
                  {Object.entries(filterOptions).map(([category, options]) => options.length > 0 && (
                    <div key={category} className={cn("rounded-lg border bg-card p-2.5 border-l-[3px]", categoryColors[category] || 'border-l-slate-300')}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-1.5">
                          {categoryIcons[category] || <Filter className="h-3 w-3 text-slate-400" />}
                          <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">{category}</span>
                        </div>
                        <span className="text-[9px] text-muted-foreground/60">{options.length} options</span>
                      </div>
                      <div className="space-y-0.5 max-h-32 overflow-y-auto">
                        {options.map(opt => {
                          const isActive = (attrs.filters?.[category] || []).includes(opt)
                          return (
                            <div 
                              key={opt} 
                              className={cn(
                                "flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-all duration-150",
                                isActive
                                  ? "bg-indigo-50 dark:bg-indigo-900/20"
                                  : "hover:bg-muted/50"
                              )}
                              onClick={(e) => {
                                e.stopPropagation();
                                const current = attrs.filters?.[category] || []
                                const next = isActive ? current.filter(c => c !== opt) : [...current, opt]
                                updateAttributes({ 
                                  filters: { ...(attrs.filters || {}), [category]: next }
                                })
                              }}
                            >
                              <div className={cn(
                                "w-4 h-4 border-2 rounded flex items-center justify-center flex-shrink-0 transition-all duration-200",
                                isActive
                                  ? "bg-indigo-600 border-indigo-600 text-white scale-110"
                                  : "border-slate-300 bg-white hover:border-indigo-400"
                              )}>
                                {isActive && <Check className="h-2.5 w-2.5" strokeWidth={3} />}
                              </div>
                              <span className={cn(
                                "truncate flex-1 text-xs transition-colors",
                                isActive ? "font-medium text-indigo-700 dark:text-indigo-300" : "text-foreground/80"
                              )} title={opt}>{opt}</span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  ))}
                </div>
                
                {/* Footer */}
                {activeCount > 0 && (
                  <div className="px-3 py-2.5 border-t bg-muted/30">
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="w-full text-xs h-7 text-rose-600 hover:text-rose-700 hover:bg-rose-50 gap-1.5 font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        updateAttributes({ filters: {} });
                      }}
                    >
                      <Trash2 className="h-3 w-3" />
                      Clear All Filters
                    </Button>
                  </div>
                )}
              </PopoverContent>
            </Popover>
            )
          })()}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-6 w-6">
                <Settings className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleOpenSource}>
                <ExternalLink className="h-4 w-4 mr-2" />
                Open in Module
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => {
                navigator.clipboard.writeText(`[EVD-${attrs.source.toUpperCase()}-${attrs.id.slice(0, 8)}]`)
              }}>
                <Hash className="h-4 w-4 mr-2" />
                Copy Citation
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => deleteNode()} className="text-red-600">
                <Trash2 className="h-4 w-4 mr-2" />
                Remove Block
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      
      {/* Metadata Inspector Drawer */}
      {showMetadata && (
        <div className="px-4 py-3 border-b bg-gradient-to-r from-slate-50 to-blue-50/30 dark:from-slate-900/50 dark:to-blue-950/20" contentEditable={false}>
          <div className="flex items-center gap-2 mb-2">
            <Info className="h-3.5 w-3.5 text-sky-500" />
            <span className="text-xs font-semibold text-sky-700 dark:text-sky-400 uppercase tracking-wider">Evidence Metadata</span>
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-[11px]">
            <div>
              <span className="text-muted-foreground">Block ID</span>
              <div className="font-mono text-foreground truncate">{attrs.id}</div>
            </div>
            <div>
              <span className="text-muted-foreground">Type</span>
              <div className="font-medium text-foreground">{attrs.type}</div>
            </div>
            <div>
              <span className="text-muted-foreground">Module Source</span>
              <div className="font-medium text-foreground uppercase">{attrs.source}</div>
            </div>
            <div>
              <span className="text-muted-foreground">Display Mode</span>
              <div className="font-medium text-foreground">{attrs.displayMode || 'full'}</div>
            </div>
            {attrs.metadata?.hash && (
              <div className="col-span-2">
                <span className="text-muted-foreground">Integrity Hash (SHA-256)</span>
                <div className="font-mono text-foreground text-[10px] break-all">{attrs.metadata.hash}</div>
              </div>
            )}
            {attrs.metadata?.timestamp && (
              <div>
                <span className="text-muted-foreground">Captured At</span>
                <div className="font-mono text-foreground">{new Date(attrs.metadata.timestamp).toLocaleString()}</div>
              </div>
            )}
            {attrs.metadata?.citationId && (
              <div>
                <span className="text-muted-foreground">Citation Key</span>
                <div className="font-mono text-sky-600 dark:text-sky-400">{attrs.metadata.citationId}</div>
              </div>
            )}
            {attrs.data?.chartType && (
              <div>
                <span className="text-muted-foreground">Chart Engine</span>
                <div className="font-medium text-foreground">{attrs.data.chartType}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {attrs.title && (
        <div className="px-4 pt-3">
          <h4 className="text-sm font-semibold">{attrs.title}</h4>
        </div>
      )}
      
      {/* Active Filter Badges Strip */}
      {attrs.filters && Object.entries(attrs.filters).some(([, v]) => v?.length > 0) && (
        <div className="px-4 py-2 border-b bg-gradient-to-r from-indigo-50/60 to-violet-50/40 dark:from-indigo-950/20 dark:to-violet-950/10 flex items-center gap-2 flex-wrap" contentEditable={false}>
          <Filter className="h-3 w-3 text-indigo-500 flex-shrink-0" />
          <span className="text-[10px] font-semibold text-indigo-600/80 uppercase tracking-wider mr-1">Active:</span>
          {Object.entries(attrs.filters).flatMap(([cat, values]) =>
            (values || []).map(val => (
              <span
                key={`${cat}-${val}`}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300 border border-indigo-200/60 cursor-pointer hover:bg-rose-100 hover:text-rose-700 hover:border-rose-200 transition-colors group"
                onClick={() => {
                  const current = attrs.filters?.[cat] || []
                  const next = current.filter(c => c !== val)
                  updateAttributes({ filters: { ...(attrs.filters || {}), [cat]: next } })
                }}
                title={`Click to remove ${cat}: ${val}`}
              >
                <span className="opacity-60 group-hover:hidden">{cat[0].toUpperCase()}:</span>
                <span className="hidden group-hover:inline text-rose-500">✕</span>
                {val}
              </span>
            ))
          )}
          <button
            className="ml-auto text-[10px] text-indigo-500 hover:text-rose-600 transition-colors font-medium"
            onClick={() => updateAttributes({ filters: {} })}
          >
            Clear all
          </button>
        </div>
      )}
      
      <div className="relative" contentEditable={false}>
        <EvidenceContent 
          type={attrs.type} 
          data={attrs.data} 
          displayMode={isExpanded ? 'full' : 'compact'}
          filters={attrs.filters}
        />
      </div>
      
      {attrs.caption && (
        <div className="px-4 py-2 border-t bg-muted/30">
          <p className="text-xs text-muted-foreground italic">
            {attrs.figureNumber && <span className="font-medium">Figure {attrs.figureNumber}:</span>}{' '}
            {attrs.caption}
          </p>
        </div>
      )}
      
      {(attrs.metadata?.hash || attrs.metadata?.timestamp) && (
        <div className="px-4 py-1.5 border-t bg-muted/20 flex items-center gap-4 text-[10px] text-muted-foreground font-mono">
          {attrs.metadata.hash && (
            <span title={attrs.metadata.hash}>
              SHA256: {attrs.metadata.hash.slice(0, 12)}...
            </span>
          )}
          {attrs.metadata.timestamp && (
            <span>Captured: {new Date(attrs.metadata.timestamp).toLocaleString()}</span>
          )}
        </div>
      )}

      {/* Resize handle */}
      <div
        className="h-2 cursor-ns-resize flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity bg-gradient-to-b from-transparent to-muted/30 rounded-b-lg group"
        contentEditable={false}
        title="Drag to resize"
      >
        <div className="w-8 h-0.5 rounded-full bg-muted-foreground/30 group-hover:bg-muted-foreground/50" />
      </div>
    </NodeViewWrapper>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// TipTap Node Extension
// ═══════════════════════════════════════════════════════════════════════════

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    evidenceBlock: {
      insertEvidenceBlock: (attrs: Partial<EvidenceBlockAttrs>) => ReturnType
      updateEvidenceBlock: (id: string, attrs: Partial<EvidenceBlockAttrs>) => ReturnType
    }
  }
}

export const EvidenceBlockNode = Node.create({
  name: 'evidenceBlock',
  
  group: 'block',
  
  atom: true,
  
  draggable: true,
  
  addAttributes() {
    return {
      id: {
        default: null,
        parseHTML: element => element.getAttribute('data-evidence-id'),
        renderHTML: attrs => ({ 'data-evidence-id': attrs.id }),
      },
      type: {
        default: 'finding' as EvidenceType,
        parseHTML: element => element.getAttribute('data-evidence-type') as EvidenceType,
        renderHTML: attrs => ({ 'data-evidence-type': attrs.type }),
      },
      source: {
        default: 'case' as ModuleSource,
        parseHTML: element => element.getAttribute('data-evidence-source') as ModuleSource,
        renderHTML: attrs => ({ 'data-evidence-source': attrs.source }),
      },
      title: { default: '' },
      caption: { default: '' },
      figureNumber: { default: null },
      data: { default: {} },
      filters: { default: {} },
      metadata: { default: {} },
      displayMode: { default: 'full' as 'full' | 'compact' | 'inline' },
    }
  },
  
  parseHTML() {
    return [{ tag: 'div[data-evidence-block]' }]
  },
  
  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(HTMLAttributes, { 'data-evidence-block': '' }), 0]
  },
  
  addNodeView() {
    return ReactNodeViewRenderer(EvidenceBlockComponent)
  },
  
  addCommands() {
    return {
      insertEvidenceBlock: (attrs) => ({ commands }) => {
        return commands.insertContent({
          type: this.name,
          attrs: {
            id: attrs.id || `evd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            ...attrs,
          },
        })
      },
      
      updateEvidenceBlock: (id, attrs) => ({ tr, state }) => {
        const { doc } = state
        let updated = false
        
        doc.descendants((node, pos) => {
          if (node.type.name === this.name && node.attrs.id === id) {
            tr.setNodeMarkup(pos, undefined, { ...node.attrs, ...attrs })
            updated = true
            return false
          }
        })
        
        return updated
      },
    }
  },
})

export default EvidenceBlockNode





