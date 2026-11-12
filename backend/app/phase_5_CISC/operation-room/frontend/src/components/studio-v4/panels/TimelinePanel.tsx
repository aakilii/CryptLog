'use client'

import React, { useEffect, useState, useCallback } from 'react'
import {
  Clock,
  Activity,
  Users,
  Flag,
  AlertTriangle,
  TrendingUp,
  RefreshCw,
  ChevronRight,
  Plus,
  BarChart2,
  PieChart,
  Waves,
  AreaChart,
  Anchor,
  List,
  Grid,
  Crosshair,
  LayoutDashboard,
} from 'lucide-react'
import {
  ResponsiveContainer, AreaChart as RechartsAreaChart, Area, BarChart, Bar,
  XAxis, CartesianGrid, RadarChart, PolarGrid, PolarAngleAxis,
  PolarRadiusAxis, Radar
} from 'recharts'
import { cn } from '@operation-room/lib/utils'
import { api } from '@operation-room/lib/api'
import {
  PanelHeader,
  PanelContent,
  PanelLoading,
  PanelEmptyState,
  ComponentCard,
  MetricCard,
  FindingCard,
} from '../ExpandablePanel'
import { Button } from '@operation-room/components/ui/button'
import { Badge } from '@operation-room/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@operation-room/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@operation-room/components/ui/collapsible'
import { useStudioStore } from '../store/useStudioStore'

// Types
interface TimelineStats {
  total_events: number
  total_anchors: number
  sources: Record<string, number>
  actors: Record<string, number>
  time_span_start: string | null
  time_span_end: string | null
  events_by_hour: Record<string, number>
}

interface TimelineEvent {
  tl_event_id: string
  normalised_ts: string
  source_type: string
  actor?: string
  action?: string
  target?: string
  severity: 'HIGH' | 'MEDIUM' | 'INFO'
  is_anchor: boolean
  anchor_label?: string
}

interface AnchorEvent {
  anchor_id: string
  tl_event_id: string
  label: string
  auto_detected: boolean
  created_by: string
}

// Insertable timeline components
const TIMELINE_COMPONENTS = [
  {
    id: 'timeline-area-chart',
    name: 'Event Density Activity',
    description: 'Interactive area chart showing event volume over time',
    icon: AreaChart,
    type: 'area-chart' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 overflow-hidden flex flex-col justify-end">
        <ResponsiveContainer width="100%" height="90%">
          <RechartsAreaChart data={[{ v: 10 }, { v: 40 }, { v: 25 }, { v: 50 }, { v: 20 }, { v: 45 }]} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="gMockArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.6} />
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="v" stroke="#8b5cf6" fill="url(#gMockArea)" strokeWidth={2} isAnimationActive={false} />
          </RechartsAreaChart>
        </ResponsiveContainer>
      </div>
    ),
  },
  {
    id: 'timeline-heatmap',
    name: 'Density Heatmap (Grid)',
    description: 'Grid tracking event density relative to hour of day by Source',
    icon: Grid,
    type: 'heatmap' as const,
    preview: (
      <div className="w-full h-full p-3 bg-slate-900/5 flex flex-col gap-1 justify-center opacity-80 cursor-default">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex gap-1 w-full justify-center">
            {Array.from({ length: 8 }).map((_, j) => {
              const op = Math.max(0.1, Math.random() * 0.9);
              return <div key={j} className="h-3 w-4 rounded-sm" style={{ backgroundColor: `rgba(6, 182, 212, ${op})` }} />
            })}
          </div>
        ))}
      </div>
    ),
  },
  {
    id: 'timeline-vertical-list',
    name: 'Chronological Flow',
    description: 'Vertical list tracing chronological incident pathways',
    icon: List,
    type: 'timeline' as const,
    preview: (
      <div className="w-full h-full p-3 bg-slate-900/5 flex flex-col gap-2 justify-center opacity-80 cursor-default">
        {['#f43f5e', '#eab308', '#0ea5e9'].map((c, i) => (
          <div key={i} className="flex gap-2 items-center px-2">
            <div className="w-2 h-2 rounded-full" style={{ background: c }} />
            <div className="h-1.5 flex-1 rounded-full bg-slate-200" />
          </div>
        ))}
      </div>
    ),
  },
  {
    id: 'timeline-radar',
    name: 'Threat Metrics Radar',
    description: 'Multi-directional matrix of behavioral indicators',
    icon: Crosshair,
    type: 'radar' as const,
    preview: (
      <div className="w-full h-full p-1 bg-slate-900/5 overflow-hidden">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={[
            { a: 'Vol', v: 90 }, { a: 'Grav', v: 50 }, { a: 'Spr', v: 80 }, { a: 'Act', v: 40 }, { a: 'Pace', v: 70 }
          ]} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
            <PolarGrid stroke="rgba(0,0,0,0.05)" />
            <Radar dataKey="v" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.2} isAnimationActive={false} />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    ),
  },
  {
    id: 'timeline-swimlane',
    name: 'Source Swimlanes',
    description: 'Horizontal lanes grouped by source isolating attack overlaps',
    icon: Waves,
    type: 'timeline' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 flex flex-col justify-center gap-2 opacity-80 cursor-default">
        {['SYS', 'FW', 'APP'].map((lbl, i) => (
          <div key={i} className="flex gap-2 items-center">
            <div className="text-[8px] font-bold w-4 text-slate-400">{lbl}</div>
            <div className="h-3 flex-1 bg-slate-100 rounded relative">
               <div className="absolute top-0 bottom-0 bg-blue-400 rounded-sm opacity-50" style={{ left: `${Math.random()*20}%`, width: `${20 + Math.random()*20}%` }} />
               <div className="absolute top-0 bottom-0 bg-rose-400 rounded-sm opacity-50" style={{ left: `${50 + Math.random()*20}%`, width: `${10 + Math.random()*20}%` }} />
            </div>
          </div>
        ))}
      </div>
    ),
  },
  {
    id: 'timeline-command-center',
    name: 'Command Stats Dashboard',
    description: 'Four card high-level aggregate count metrics',
    icon: LayoutDashboard,
    type: 'stat-card' as const,
    preview: (
      <div className="w-full h-full p-3 bg-slate-900/5 opacity-80 flex flex-col justify-center cursor-default">
        <div className="grid grid-cols-2 gap-2 h-full">
           <div className="bg-slate-100 rounded-md border border-slate-200 border-t-2 border-t-blue-500 flex items-center justify-center text-[10px] font-bold text-slate-400">12K</div>
           <div className="bg-slate-100 rounded-md border border-slate-200 border-t-2 border-t-amber-500 flex items-center justify-center text-[10px] font-bold text-slate-400">45</div>
           <div className="bg-slate-100 rounded-md border border-slate-200 border-t-2 border-t-green-500 flex items-center justify-center text-[10px] font-bold text-slate-400">99%</div>
           <div className="bg-slate-100 rounded-md border border-slate-200 border-t-2 border-t-rose-500 flex items-center justify-center text-[10px] font-bold text-slate-400">23</div>
        </div>
      </div>
    ),
  },
]

// Severity colors
const SEVERITY_COLORS = {
  HIGH: { bg: 'bg-red-100', text: 'text-red-700', dot: 'bg-red-500' },
  MEDIUM: { bg: 'bg-amber-100', text: 'text-amber-700', dot: 'bg-amber-500' },
  INFO: { bg: 'bg-blue-100', text: 'text-blue-700', dot: 'bg-blue-500' },
}

// Source icons
const SOURCE_ICONS: Record<string, string> = {
  AUTH: 'AU',
  VPN: 'VN',
  DB: 'DB',
  FW: 'FW',
  FILE: 'FI',
  EPP: 'EP',
  APP: 'AP',
}

interface TimelinePanelProps {
  caseId: string
  onInsertComponent?: (componentId: string, config?: Record<string, unknown>) => void
  onInsertFinding?: (finding: { title: string; content: string; source: string }) => void
  className?: string
}

export const TimelinePanel = ({
  caseId,
  onInsertComponent,
  onInsertFinding,
  className,
}: TimelinePanelProps) => {
  // Data state
  const [stats, setStats] = useState<TimelineStats | null>(null)
  const [anchors, setAnchors] = useState<AnchorEvent[]>([])
  const [recentEvents, setRecentEvents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Filter state
  const [searchQuery, setSearchQuery] = useState('')
  const [severityFilter, setSeverityFilter] = useState<string>('all')
  const [sourceFilter, setSourceFilter] = useState<string>('all')
  
  // Section expanded state
  const [componentsExpanded, setComponentsExpanded] = useState(true)
  const [insightsExpanded, setInsightsExpanded] = useState(true)
  const [anchorsExpanded, setAnchorsExpanded] = useState(true)
  const [eventsExpanded, setEventsExpanded] = useState(true)

  const setPanelBadge = useStudioStore((s) => s.setPanelBadge)

  // Load timeline data
  const loadData = useCallback(async () => {
    if (!caseId) return
    
    try {
      setLoading(true)
      setError(null)
      
      // Fetch stats, anchors, and recent events in parallel
      const [statsData, anchorsData, eventsData] = await Promise.all([
        api.get(`/cases/${caseId}/timeline/stats`).catch(() => null),
        api.get(`/cases/${caseId}/timeline/anchors`).catch(() => []),
        api.get(`/cases/${caseId}/timeline?limit=20`).catch(() => []),
      ])
      
      if (statsData) {
        setStats(statsData)
        setPanelBadge('timeline', statsData.total_events ?? 0)
      }
      if (Array.isArray(anchorsData)) setAnchors(anchorsData)
      if (eventsData && Array.isArray(eventsData.clusters)) setRecentEvents(eventsData.clusters)
    } catch (err) {
      console.error('Failed to load timeline data:', err)
      setError('Failed to load timeline data')
    } finally {
      setLoading(false)
    }
  }, [caseId, setPanelBadge])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Generate insights from stats
  const insights = React.useMemo(() => {
    if (!stats) return []
    
    const results: Array<{
      id: string
      title: string
      description: string
      severity: 'critical' | 'high' | 'medium' | 'low'
      metric?: string
    }> = []
    
    // Total events insight
    if (stats.total_events > 0) {
      results.push({
        id: 'total-events',
        title: `${stats.total_events.toLocaleString()} Events Analyzed`,
        description: `Unified timeline contains ${stats.total_events.toLocaleString()} events from ${Object.keys(stats.sources).length} sources`,
        severity: 'low',
        metric: stats.total_events.toString(),
      })
    }
    
    // Anchor events insight
    if (stats.total_anchors > 0) {
      results.push({
        id: 'anchor-events',
        title: `${stats.total_anchors} Key Events Identified`,
        description: 'Anchor points marking significant activities in the investigation',
        severity: 'medium',
        metric: stats.total_anchors.toString(),
      })
    }
    
    // Peak activity hour
    const peakHour = Object.entries(stats.events_by_hour)
      .sort(([, a], [, b]) => b - a)[0]
    if (peakHour) {
      results.push({
        id: 'peak-hour',
        title: `Peak Activity: ${peakHour[0]}:00`,
        description: `Highest event volume with ${peakHour[1]} events at ${peakHour[0]}:00`,
        severity: 'high',
        metric: peakHour[1].toString(),
      })
    }
    
    // Top actor insight
    const topActor = Object.entries(stats.actors)
      .sort(([, a], [, b]) => b - a)[0]
    if (topActor) {
      results.push({
        id: 'top-actor',
        title: `Most Active: ${topActor[0]}`,
        description: `${topActor[1]} events attributed to this actor`,
        severity: 'medium',
        metric: topActor[1].toString(),
      })
    }
    
    return results
  }, [stats])

  // Handle component insertion
  const handleInsertComponent = (componentId: string) => {
    onInsertComponent?.(componentId, {
      caseId,
      module: 'timeline',
      dataEndpoint: `/api/cases/${caseId}/timeline/stats`,
    })
  }

  // Handle finding insertion
  const handleInsertFinding = (insight: typeof insights[0]) => {
    onInsertFinding?.({
      title: insight.title,
      content: insight.description,
      source: 'timeline',
    })
  }

  // Format timestamp
  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return ts
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col h-full">
        <PanelHeader
          title="Timeline"
          panelId="timeline"
          icon={<Clock className="h-4 w-4" />}
          color="#06b6d4"
        />
        <PanelLoading message="Loading timeline data..." />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col h-full">
        <PanelHeader
          title="Timeline"
          panelId="timeline"
          icon={<Clock className="h-4 w-4" />}
          color="#06b6d4"
        />
        <PanelEmptyState
          icon={<AlertTriangle className="h-8 w-8" />}
          title="Error Loading Timeline"
          description={error}
          action={
            <Button size="sm" onClick={loadData}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div className={cn("flex flex-col h-full", className)}>
      <PanelHeader
        title="Timeline"
        panelId="timeline"
        icon={<Clock className="h-4 w-4" />}
        color="#06b6d4"
        showSearch={true}
        searchPlaceholder="Search events..."
        searchValue={searchQuery}
        onSearchChange={setSearchQuery}
        actions={
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={loadData}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        }
      />
      
      <PanelContent>
        {/* Quick Stats */}
        {stats && (
          <div className="grid grid-cols-2 gap-2 mb-4">
            <MetricCard
              label="Events"
              value={stats.total_events.toLocaleString()}
              module="timeline"
              icon={<Activity className="h-4 w-4 text-cyan-500" />}
            />
            <MetricCard
              label="Anchors"
              value={stats.total_anchors.toString()}
              module="timeline"
              icon={<Anchor className="h-4 w-4 text-indigo-500" />}
            />
            <MetricCard
              label="Sources"
              value={Object.keys(stats.sources).length.toString()}
              module="timeline"
              icon={<TrendingUp className="h-4 w-4 text-sky-500" />}
            />
            <MetricCard
              label="Actors"
              value={Object.keys(stats.actors).length.toString()}
              module="timeline"
              icon={<Users className="h-4 w-4 text-cyan-600" />}
            />
          </div>
        )}

        {/* Insertable Components Section */}
        <Collapsible open={componentsExpanded} onOpenChange={setComponentsExpanded}>
          <CollapsibleTrigger asChild>
            <button className="flex items-center justify-between w-full py-2 text-sm font-medium text-left hover:text-foreground text-muted-foreground">
              <span className="flex items-center gap-2">
                <BarChart2 className="h-4 w-4" />
                Insert Components
              </span>
              <ChevronRight className={cn(
                "h-4 w-4 transition-transform",
                componentsExpanded && "rotate-90"
              )} />
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="grid gap-2 pb-4">
              {TIMELINE_COMPONENTS.map((component) => (
                <ComponentCard
                  key={component.id}
                  id={component.id}
                  name={component.name}
                  module="timeline"
                  description={component.description}
                  icon={<component.icon strokeWidth={1.5} />}
                  type={component.type}
                  preview={component.preview as React.ReactNode}
                  onInsert={() => handleInsertComponent(component.id)}
                  draggable
                />
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Key Insights Section */}
        {insights.length > 0 && (
          <Collapsible open={insightsExpanded} onOpenChange={setInsightsExpanded}>
            <CollapsibleTrigger asChild>
              <button className="flex items-center justify-between w-full py-2 text-sm font-medium text-left hover:text-foreground text-muted-foreground">
                <span className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  Key Insights
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                    {insights.length}
                  </Badge>
                </span>
                <ChevronRight className={cn(
                  "h-4 w-4 transition-transform",
                  insightsExpanded && "rotate-90"
                )} />
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="space-y-2 pb-4">
                {insights.map((insight) => (
                  <FindingCard
                    key={insight.id}
                    title={insight.title}
                    module="timeline"
                    description={insight.description}
                    severity={insight.severity}
                    metric={insight.metric}
                    onInsert={() => handleInsertFinding(insight)}
                  />
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* Anchor Events Section */}
        {anchors.length > 0 && (
          <Collapsible open={anchorsExpanded} onOpenChange={setAnchorsExpanded}>
            <CollapsibleTrigger asChild>
              <button className="flex items-center justify-between w-full py-2 text-sm font-medium text-left hover:text-foreground text-muted-foreground">
                <span className="flex items-center gap-2">
                  <Anchor className="h-4 w-4" />
                  Anchor Events
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                    {anchors.length}
                  </Badge>
                </span>
                <ChevronRight className={cn(
                  "h-4 w-4 transition-transform",
                  anchorsExpanded && "rotate-90"
                )} />
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="space-y-2 pb-4">
                {anchors.slice(0, 10).map((anchor) => (
                  <div
                    key={anchor.anchor_id}
                    className="group flex items-start gap-3 p-2.5 rounded-lg border bg-card hover:bg-accent/50 transition-colors cursor-pointer"
                  >
                    <div className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-indigo-100">
                      <Flag className="h-3 w-3 text-indigo-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{anchor.label}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <Badge
                          variant="outline"
                          className={cn(
                            "h-4 px-1.5 text-[10px]",
                            anchor.auto_detected ? "text-cyan-600" : "text-indigo-600"
                          )}
                        >
                          {anchor.auto_detected ? 'Auto' : 'Manual'}
                        </Badge>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100"
                      onClick={() => onInsertFinding?.({
                        title: 'Anchor Event',
                        content: anchor.label,
                        source: 'timeline',
                      })}
                    >
                      <Plus className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
                {anchors.length > 10 && (
                  <Button variant="ghost" size="sm" className="w-full text-xs">
                    View all {anchors.length} anchors
                  </Button>
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* Recent Events Section */}
        <Collapsible open={eventsExpanded} onOpenChange={setEventsExpanded}>
          <CollapsibleTrigger asChild>
            <button className="flex items-center justify-between w-full py-2 text-sm font-medium text-left hover:text-foreground text-muted-foreground">
              <span className="flex items-center gap-2">
                <Activity className="h-4 w-4" />
                Recent Events
                <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                  {recentEvents.length}
                </Badge>
              </span>
              <ChevronRight className={cn(
                "h-4 w-4 transition-transform",
                eventsExpanded && "rotate-90"
              )} />
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            {/* Filters */}
            <div className="flex gap-2 mb-3">
              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger className="h-7 text-xs flex-1">
                  <SelectValue placeholder="Severity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Severities</SelectItem>
                  <SelectItem value="HIGH">High</SelectItem>
                  <SelectItem value="MEDIUM">Medium</SelectItem>
                  <SelectItem value="INFO">Info</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sourceFilter} onValueChange={setSourceFilter}>
                <SelectTrigger className="h-7 text-xs flex-1">
                  <SelectValue placeholder="Source" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Sources</SelectItem>
                  {stats && Object.keys(stats.sources).map((source) => (
                    <SelectItem key={source} value={source}>
                        {SOURCE_ICONS[source] || 'NA'} {source}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            {/* Events list (Clustered) */}
            <div className="space-y-1.5 pb-4">
              {recentEvents
                .slice(0, 15)
                .map((cluster, i) => (
                  <div
                    key={i}
                    className={cn(
                      "flex items-center gap-2 p-2 rounded-md text-xs transition-colors hover:bg-accent/50 border border-transparent",
                      cluster.cluster_id === 'outliers' && "border-red-500/20 bg-red-50/50"
                    )}
                  >
                    <div className={cn(
                      "w-2 h-2 rounded-full flex-shrink-0",
                      cluster.cluster_id === 'outliers' ? SEVERITY_COLORS.HIGH.dot : SEVERITY_COLORS.INFO.dot
                    )} />
                    <span className="w-16 flex-shrink-0 font-geist-mono text-muted-foreground">
                      {cluster.start ? (formatTime(cluster.start).split(',')[1]?.trim() || formatTime(cluster.start)) : 'N/A'}
                    </span>
                    <span className="font-medium truncate flex-1">
                      Cluster {i + 1} ({cluster.event_count || 0} items)
                    </span>
                    {cluster.cluster_id === 'outliers' && (
                      <span className="text-muted-foreground truncate max-w-[80px]">
                        Scattered
                      </span>
                    )}
                  </div>
                ))}
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* Source Distribution */}
        {stats && Object.keys(stats.sources).length > 0 && (
          <div className="pt-2 border-t">
            <h4 className="text-xs font-medium text-muted-foreground mb-2">
              Events by Source
            </h4>
            <div className="space-y-1.5">
              {Object.entries(stats.sources)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 6)
                .map(([source, count]) => {
                  const percentage = stats.total_events > 0 
                    ? Math.round((count / stats.total_events) * 100)
                    : 0
                  return (
                    <div key={source} className="flex items-center gap-2">
                      <span className="text-xs w-12">
                        {SOURCE_ICONS[source] || 'NA'} {source}
                      </span>
                      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                        <div 
                          className="h-full rounded-full bg-gradient-to-r from-cyan-400 to-indigo-500 transition-all"
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground w-12 text-right">
                        {count.toLocaleString()}
                      </span>
                    </div>
                  )
                })}
            </div>
          </div>
        )}
      </PanelContent>
    </div>
  )
}


