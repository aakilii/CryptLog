'use client'

import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import {
  AlertTriangle,
  Activity,
  Users,
  TrendingUp,
  BarChart2,
  PieChart,
  RefreshCw,
  ChevronRight,
  Plus,
  Play,
  Loader2,
  LayoutList,
  Gauge,
  Sparkles,
  ArrowDown,
  Brain,
  Settings,
  Clock,
} from 'lucide-react'
import {
  ResponsiveContainer, ScatterChart, Scatter, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, PieChart as RechartsPieChart, Pie, Cell, ZAxis
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
import { useStudioStore } from '../store/useStudioStore'
import { Button } from '@operation-room/components/ui/button'
import { Badge } from '@operation-room/components/ui/badge'
import { Progress } from '@operation-room/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@operation-room/components/ui/select'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@operation-room/components/ui/tooltip'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@operation-room/components/ui/collapsible'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@operation-room/components/ui/dialog'
import { Label } from '@operation-room/components/ui/label'
import { Slider } from '@operation-room/components/ui/slider'

// Normalise the anomaly summary response so missing fields don't crash the UI
const normalizeSummary = (data: Partial<AnomalySummary> & { error?: string } | null): AnomalySummary | null => {
  if (!data || data.error) return null

  const scoreStats = (data.score_stats || {}) as Partial<AnomalySummary['score_stats']>

  return {
    run_id: data.run_id || '',
    model_type: data.model_type || 'ensemble',
    contamination: data.contamination ?? 0.1,
    total_events: data.total_events ?? 0,
    anomaly_count: data.anomaly_count ?? 0,
    anomaly_rate: data.anomaly_rate ?? 0,
    score_stats: {
      mean: scoreStats.mean ?? 0,
      std: scoreStats.std ?? 0,
      min: scoreStats.min ?? 0,
      max: scoreStats.max ?? 0,
      p50: scoreStats.p50 ?? 0,
      p90: scoreStats.p90 ?? 0,
      p95: scoreStats.p95 ?? 0,
    },
    top_anomalies: data.top_anomalies || [],
    by_source: data.by_source || {},
    by_actor: data.by_actor || {},
    shap_global_importance: data.shap_global_importance || [],
    shap_per_event: data.shap_per_event || [],
    context_engine_status: data.context_engine_status || 'not_started',
    sequence_anomaly_count: data.sequence_anomaly_count ?? 0,
    sequence_group_count: data.sequence_group_count ?? (data as any).sequence_groups ?? 0,
    sequence_anomalies: data.sequence_anomalies || [],
  }
}

// Types
interface AnomalySummary {
  run_id: string
  model_type: string
  contamination: number
  total_events: number
  anomaly_count: number
  anomaly_rate: number
  score_stats: {
    mean: number
    std: number
    min: number
    max: number
    p50: number
    p90: number
    p95: number
  }
  top_anomalies: Array<{
    tl_event_id: string
    score: number
    is_anomaly: boolean
    timestamp: string
    actor: string
    source_type: string
    action: string
    target: string
    severity: string
  }>
  by_source: Record<string, { total: number; anomalies: number }>
  by_actor: Record<string, { total: number; anomalies: number }>
  shap_global_importance: Array<{
    feature: string
    importance: number
    importance_pct: number
    description: string
  }>
  shap_per_event: Array<{
    tl_event_id: string
    anomaly_score: number
    actor: string
    source_type: string
    action: string
    feature_contributions: Array<{
      feature: string
      shap_value: number
      abs_shap: number
      direction: string
      description: string
    }>
    top_driver: string
    top_driver_desc: string
  }>
  context_engine_status?: string
  sequence_anomaly_count?: number
  sequence_group_count?: number
  sequence_anomalies?: Array<{
    sequence_id: string
    run_id: string
    case_id: string
    actor: string
    sequence_string: string
    transformer_confidence: number
    created_at: string
  }>
}

// Insertable anomaly components
const ANOMALY_COMPONENTS = [
  {
    id: 'anomaly-score-timeline',
    name: 'Anomaly Score Timeline',
    description: 'Scatter plot of anomaly scores over time',
    icon: Activity,
    type: 'scatter-chart' as const,
    preview: (
      <div className="w-full h-[80px] p-1 bg-slate-900/5 relative flex justify-center items-center opacity-80 cursor-default">
         <ResponsiveContainer width="100%" height={70}>
            <ScatterChart margin={{ top: 10, right: 10, bottom: -10, left: -20 }}>
               <CartesianGrid strokeDasharray="3 3" opacity={0.2} vertical={false} />
               <XAxis type="number" dataKey="x" hide />
               <YAxis type="number" dataKey="y" hide />
               <Scatter data={[{x: 1, y: 30}, {x: 2, y: 40}, {x: 3, y: 80}, {x: 4, y: 90}, {x: 5, y: 30}, {x: 6, y: 85}]} fill="#f43f5e" isAnimationActive={false} />
            </ScatterChart>
         </ResponsiveContainer>
      </div>
    ),
  },
  {
    id: 'anomaly-shap-importance',
    name: 'SHAP Feature Importance',
    description: 'Top features contributing to anomalies',
    icon: BarChart2,
    type: 'bar-chart' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 flex flex-col justify-center gap-1 opacity-80 cursor-default">
         {[60, 40, 20, 10].map((v, i) => (
           <div key={i} className="flex items-center gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-slate-300" />
              <div className="h-1.5 rounded-r bg-emerald-500" style={{ width: `${v}%` }} />
           </div>
         ))}
      </div>
    ),
  },
  {
    id: 'anomaly-shap-waterfall',
    name: 'SHAP Waterfall',
    description: 'Feature contributions breakdown',
    icon: ArrowDown,
    type: 'waterfall' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 flex flex-col justify-center gap-1 opacity-80 cursor-default relative">
         <div className="absolute left-1/2 top-1 bottom-1 w-px bg-slate-300 border-dashed" />
         <div className="h-1.5 ml-[50%] bg-rose-500 rounded-r z-10 w-1/4" />
         <div className="h-1.5 ml-[50%] bg-emerald-500 rounded-l z-10 w-1/3 -translate-x-full" />
         <div className="h-1.5 ml-[50%] bg-rose-500 rounded-r z-10 w-[15%]" />
      </div>
    ),
  },
  {
    id: 'anomaly-source-dist',
    name: 'Source Distribution',
    description: 'Anomalies by log source',
    icon: PieChart,
    type: 'pie-chart' as const,
    preview: (
      <div className="w-full h-full bg-slate-900/5 flex justify-center items-center opacity-80 cursor-default">
        <ResponsiveContainer width={60} height={60}>
          <RechartsPieChart>
             <Pie data={[{v:40}, {v:30}, {v:20}, {v:10}]} cx="50%" cy="50%" innerRadius={15} outerRadius={25} dataKey="v" stroke="none" isAnimationActive={false}>
               <Cell fill="#6366f1" />
               <Cell fill="#eab308" />
               <Cell fill="#ef4444" />
               <Cell fill="#10b981" />
             </Pie>
          </RechartsPieChart>
        </ResponsiveContainer>
      </div>
    ),
  },
  {
    id: 'anomaly-actor-rate',
    name: 'Actor Anomaly Rate',
    description: 'Anomaly rate per user/actor',
    icon: Users,
    type: 'bar-chart' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 flex items-end justify-center gap-2 opacity-80 cursor-default">
         <div className="w-2 h-1/3 rounded-t bg-indigo-400" />
         <div className="w-2 h-2/3 rounded-t bg-indigo-500" />
         <div className="w-2 h-1/4 rounded-t bg-indigo-300" />
         <div className="w-2 h-[80%] rounded-t bg-indigo-600" />
      </div>
    ),
  },
  {
    id: 'anomaly-stats',
    name: 'Anomaly Statistics',
    description: 'Summary metrics card',
    icon: Gauge,
    type: 'stat-card' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 flex flex-col justify-center gap-1 opacity-80 cursor-default">
         <div className="grid grid-cols-2 gap-1 h-3/4">
            <div className="bg-slate-100 rounded border border-slate-200" />
            <div className="bg-slate-100 rounded border border-slate-200 border-t-2 border-t-rose-500" />
         </div>
      </div>
    ),
  },
  {
    id: 'anomaly-top-list',
    name: 'Top Anomalies Table',
    description: 'Highest-scoring anomalies',
    icon: LayoutList,
    type: 'table' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 flex flex-col gap-[2px] opacity-80 cursor-default">
         <div className="flex gap-1 border-b border-slate-200 pb-[2px] mb-1">
            <div className="h-1 w-6 bg-slate-300 rounded-sm" />
            <div className="h-1 w-10 bg-slate-300 rounded-sm" />
         </div>
         {Array.from({length: 4}).map((_, i) => (
           <div key={i} className="flex gap-1 py-[1px] items-center">
              <div className="h-1 w-1 rounded-full" style={{ backgroundColor: i < 2 ? '#f43f5e' : '#eab308' }} />
              <div className="h-1 flex-1 bg-slate-200 rounded-sm max-w-[80%]" />
           </div>
         ))}
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

// Score color based on value
const getScoreColor = (score: number) => {
  if (score >= 0.8) return 'text-red-600'
  if (score >= 0.6) return 'text-orange-500'
  if (score >= 0.4) return 'text-amber-500'
  return 'text-green-500'
}

const getScoreBg = (score: number) => {
  if (score >= 0.8) return 'bg-red-100'
  if (score >= 0.6) return 'bg-orange-100'
  if (score >= 0.4) return 'bg-amber-100'
  return 'bg-green-100'
}

interface AnomalyPanelProps {
  caseId: string
  onInsertComponent?: (componentId: string, config?: Record<string, unknown>) => void
  onInsertFinding?: (finding: { title: string; content: string; source: string }) => void
  className?: string
}

export const AnomalyPanel = ({
  caseId,
  onInsertComponent,
  onInsertFinding,
  className,
}: AnomalyPanelProps) => {
  // Data state
  const [summary, setSummary] = useState<AnomalySummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  
  // Detection settings
  const [showSettings, setShowSettings] = useState(false)
  const [modelType, setModelType] = useState('ensemble')
  const [contamination, setContamination] = useState([0.1])
  
  // Section expanded state
  const [componentsExpanded, setComponentsExpanded] = useState(true)
  const [insightsExpanded, setInsightsExpanded] = useState(true)
  const [shapExpanded, setShapExpanded] = useState(true)
  const [anomaliesExpanded, setAnomMaliesExpanded] = useState(true)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const setPanelBadge = useStudioStore((s) => s.setPanelBadge)

  // Load anomaly data
  const loadData = useCallback(async (silent = false) => {
    if (!caseId) return
    
    try {
      if (!silent) setLoading(true)
      setError(null)
      
      const summaryData = await api.get(`/cases/${caseId}/anomalies/summary`).catch(() => null)

      // Treat "no summary" responses as empty state instead of crashing the panel
      if (summaryData?.error === 'No summary found' || summaryData?.error === 'No data to summarise') {
        setSummary(null)
        return
      }

      const normalised = normalizeSummary(summaryData)
      if (normalised) {
        setSummary(normalised)
        setPanelBadge('anomaly', normalised.anomaly_count || 0)
      } else {
        setSummary(null)
        setPanelBadge('anomaly', 0)
        if (summaryData?.error) {
          setError(typeof summaryData.error === 'string' ? summaryData.error : 'Failed to load anomaly data')
        }
      }
    } catch (err) {
      console.error('Failed to load anomaly data:', err)
      setError('Failed to load anomaly data')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    const shouldPoll = summary?.context_engine_status === 'started' || running

    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }

    if (shouldPoll) {
      pollRef.current = setInterval(() => {
        loadData(true)
      }, 2500)
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [loadData, running, summary?.context_engine_status])

  // Run detection
  const handleRunDetection = async () => {
    try {
      setRunning(true)
      await api.post(`/cases/${caseId}/anomalies/run`, {
        model_type: modelType,
        contamination: contamination[0],
      })
      setShowSettings(false)
      // Reload data after a delay for processing
      setTimeout(loadData, 2000)
    } catch (err) {
      console.error('Failed to run detection:', err)
    } finally {
      setRunning(false)
    }
  }

  // Generate insights from summary
  const insights = useMemo(() => {
    if (!summary) return []
    
    const results: Array<{
      id: string
      title: string
      description: string
      severity: 'critical' | 'high' | 'medium' | 'low'
      metric?: string
    }> = []
    
    // Anomaly count insight
    if (summary.anomaly_count > 0) {
      results.push({
        id: 'anomaly-count',
        title: `${summary.anomaly_count} Anomalies Detected`,
        description: `${summary.anomaly_rate.toFixed(1)}% of ${summary.total_events.toLocaleString()} events flagged as anomalous`,
        severity: summary.anomaly_count > 50 ? 'critical' : summary.anomaly_count > 20 ? 'high' : 'medium',
        metric: summary.anomaly_count.toString(),
      })
    }
    
    // Max score insight
    if (summary.score_stats.max > 0.8) {
      results.push({
        id: 'max-score',
        title: `High-Confidence Anomaly: ${(summary.score_stats.max * 100).toFixed(0)}%`,
        description: 'Maximum anomaly score indicates highly suspicious activity',
        severity: 'critical',
        metric: `${(summary.score_stats.max * 100).toFixed(0)}%`,
      })
    }
    
    // Top actor insight
    const topActor = Object.entries(summary.by_actor)
      .map(([actor, data]) => ({ actor, ...data }))
      .sort((a, b) => b.anomalies - a.anomalies)[0]
    if (topActor && topActor.anomalies > 0) {
      results.push({
        id: 'top-actor',
        title: `Most Anomalous: ${topActor.actor}`,
        description: `${topActor.anomalies} anomalies out of ${topActor.total} events (${((topActor.anomalies / topActor.total) * 100).toFixed(1)}%)`,
        severity: topActor.anomalies > 10 ? 'high' : 'medium',
        metric: topActor.anomalies.toString(),
      })
    }
    
    // Top SHAP feature insight
    if (summary.shap_global_importance?.length > 0) {
      const topFeature = summary.shap_global_importance[0]
      results.push({
        id: 'top-feature',
        title: `Key Driver: ${topFeature.description}`,
        description: `${topFeature.importance_pct.toFixed(1)}% contribution to anomaly detection`,
        severity: 'medium',
        metric: `${topFeature.importance_pct.toFixed(0)}%`,
      })
    }
    
    return results
  }, [summary])

  // Handle component insertion
  const handleInsertComponent = (componentId: string) => {
    onInsertComponent?.(componentId, {
      caseId,
      module: 'anomaly',
      dataEndpoint: `/api/cases/${caseId}/anomalies/summary`,
    })
  }

  // Handle finding insertion
  const handleInsertFinding = (insight: typeof insights[0]) => {
    onInsertFinding?.({
      title: insight.title,
      content: insight.description,
      source: 'anomaly',
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

  // Render — Component catalog ALWAYS visible, data sections conditional
  return (
    <div className={cn("flex flex-col h-full min-h-0", className)}>
      <PanelHeader
        title="Anomaly Detection"
        panelId="anomaly"
        icon={<AlertTriangle className="h-4 w-4" />}
        color="#f59e0b"
        showSearch={false}
        actions={
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setShowSettings(true)}>
                  <Settings className="h-3.5 w-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Re-run detection</TooltipContent>
            </Tooltip>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => loadData()}>
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
        }
      />
      <PanelContent>
        {/* ── Metrics (if data available) ──────────── */}
        {summary && (
          <div className="grid grid-cols-2 gap-2 mb-4">
            <MetricCard
              label="Anomalies"
              value={summary.anomaly_count}
              module="anomaly"
              icon={<AlertTriangle className="h-4 w-4 text-rose-600" />}
            />
            <MetricCard
              label="Rate"
              value={`${summary.anomaly_rate.toFixed(1)}%`}
              module="anomaly"
              icon={<TrendingUp className="h-4 w-4 text-amber-500" />}
            />
            <MetricCard
              label="Max Score"
              value={`${(summary.score_stats.max * 100).toFixed(0)}%`}
              module="anomaly"
              icon={<Gauge className="h-4 w-4 text-rose-600" />}
            />
            <MetricCard
              label="P95 Score"
              value={`${(summary.score_stats.p95 * 100).toFixed(0)}%`}
              module="anomaly"
              icon={<Activity className="h-4 w-4 text-orange-500" />}
            />
          </div>
        )}

        {summary && (
          <div className="flex items-center justify-between mb-4 p-2 bg-muted/50 rounded-lg text-xs">
            <span className="text-muted-foreground">
              <Brain className="h-3 w-3 inline mr-1" />
              {summary.model_type}
            </span>
            <span className="text-muted-foreground">
              <Clock className="h-3 w-3 inline mr-1" />
              {summary.total_events.toLocaleString()} events
            </span>
            <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
              {summary.context_engine_status === 'completed'
                ? `Context Ready · ${summary.sequence_anomaly_count || 0}`
                : summary.context_engine_status === 'started'
                  ? `Context Running · ${summary.sequence_group_count || 0}`
                  : summary.context_engine_status === 'failed'
                    ? 'Context Failed'
                    : 'Context Idle'}
            </Badge>
          </div>
        )}

        {/* ── Component Catalog — ALWAYS visible ──── */}
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
            <div className="grid grid-cols-1 gap-4 pb-4 px-1">
              {ANOMALY_COMPONENTS.map((component) => (
                <ComponentCard
                  key={component.id}
                  id={component.id}
                  name={component.name}
                  module="anomaly"
                  description={component.description}
                  icon={<component.icon strokeWidth={1.5} />}
                  type={component.type}
                  preview={(component as any).preview as React.ReactNode}
                  onInsert={() => handleInsertComponent(component.id)}
                  draggable
                />
              ))}
            </div>
          </CollapsibleContent>
        </Collapsible>

        {/* ── Inline status indicators ────────────── */}
        {loading && <PanelLoading message="Loading anomaly data..." />}

        {!loading && !summary && !error && (
          <PanelEmptyState
            icon={<Brain className="h-10 w-10" />}
            title="No Detection Run"
            description="Run anomaly detection to identify suspicious events"
            action={
              <Button size="sm" className="gap-2" onClick={() => setShowSettings(true)}>
                <Play className="h-4 w-4" />
                Run Detection
              </Button>
            }
          />
        )}

        {!loading && error && (
          <PanelEmptyState
            icon={<AlertTriangle className="h-8 w-8" />}
            title="Error"
            description={error}
            action={
              <Button size="sm" onClick={() => loadData()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry
              </Button>
            }
          />
        )}

        {/* ── Key Insights ────────────────────────── */}
        {insights.length > 0 && (
          <Collapsible open={insightsExpanded} onOpenChange={setInsightsExpanded}>
            <CollapsibleTrigger asChild>
              <button className="flex items-center justify-between w-full py-2 text-sm font-medium text-left hover:text-foreground text-muted-foreground">
                <span className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4" />
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
                    module="anomaly"
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

        {/* ── SHAP Feature Importance ─────────────── */}
        {summary?.shap_global_importance && summary.shap_global_importance.length > 0 && (
          <Collapsible open={shapExpanded} onOpenChange={setShapExpanded}>
            <CollapsibleTrigger asChild>
              <button className="flex items-center justify-between w-full py-2 text-sm font-medium text-left hover:text-foreground text-muted-foreground">
                <span className="flex items-center gap-2">
                  <Brain className="h-4 w-4" />
                  SHAP Explainability
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                    {summary.shap_global_importance.length}
                  </Badge>
                </span>
                <ChevronRight className={cn(
                  "h-4 w-4 transition-transform",
                  shapExpanded && "rotate-90"
                )} />
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="space-y-2 pb-4">
                {summary.shap_global_importance.slice(0, 6).map((feature, idx) => (
                  <div
                    key={feature.feature}
                    className="group flex items-center gap-2 p-2 rounded-lg border hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex h-5 w-5 items-center justify-center rounded bg-gradient-to-br from-amber-500 to-rose-600 text-[10px] font-bold text-white">
                      {idx + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium truncate">
                          {feature.description}
                        </span>
                        <Badge variant="outline" className="h-4 px-1.5 text-[10px]">
                          {feature.importance_pct.toFixed(1)}%
                        </Badge>
                      </div>
                      <div className="mt-1">
                        <Progress 
                          value={feature.importance_pct} 
                          className="h-1.5"
                        />
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100"
                      onClick={() => onInsertFinding?.({
                        title: `SHAP: ${feature.description}`,
                        content: `Feature contributes ${feature.importance_pct.toFixed(1)}% to anomaly detection (importance: ${feature.importance.toFixed(4)})`,
                        source: 'anomaly-shap',
                      })}
                    >
                      <Plus className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* ── Top Anomalies ───────────────────────── */}
        {summary?.top_anomalies && summary.top_anomalies.length > 0 && (
          <Collapsible open={anomaliesExpanded} onOpenChange={setAnomMaliesExpanded}>
            <CollapsibleTrigger asChild>
              <button className="flex items-center justify-between w-full py-2 text-sm font-medium text-left hover:text-foreground text-muted-foreground">
                <span className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" />
                  Top Anomalies
                  <Badge variant="secondary" className="ml-1 h-5 px-1.5 text-xs">
                    {summary.top_anomalies.length}
                  </Badge>
                </span>
                <ChevronRight className={cn(
                  "h-4 w-4 transition-transform",
                  anomaliesExpanded && "rotate-90"
                )} />
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="space-y-2 pb-4">
                {summary.top_anomalies.slice(0, 10).map((anomaly) => (
                  <div
                    key={anomaly.tl_event_id}
                    className="group flex items-start gap-2 p-2.5 rounded-lg border hover:bg-accent/50 transition-colors cursor-pointer"
                  >
                    <div className={cn(
                      "flex-shrink-0 w-10 h-10 rounded-lg flex flex-col items-center justify-center text-xs font-bold",
                      getScoreBg(anomaly.score),
                      getScoreColor(anomaly.score)
                    )}>
                      {(anomaly.score * 100).toFixed(0)}
                      <span className="text-[8px] font-normal">%</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-sm font-medium truncate">
                          {anomaly.action || 'Unknown Action'}
                        </span>
                        <Badge 
                          variant="outline" 
                          className={cn(
                            "h-4 px-1 text-[9px]",
                            SEVERITY_COLORS[anomaly.severity as keyof typeof SEVERITY_COLORS]?.text
                          )}
                        >
                          {anomaly.severity}
                        </Badge>
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5 truncate">
                        {anomaly.actor} → {anomaly.target || 'N/A'}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                        <span>{anomaly.source_type}</span>
                        <span>•</span>
                        <span>{formatTime(anomaly.timestamp)}</span>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 opacity-0 group-hover:opacity-100 flex-shrink-0"
                      onClick={() => onInsertFinding?.({
                        title: `Anomaly: ${anomaly.action || 'Event'} (${(anomaly.score * 100).toFixed(0)}%)`,
                        content: `Actor: ${anomaly.actor}, Target: ${anomaly.target || 'N/A'}, Source: ${anomaly.source_type}, Time: ${formatTime(anomaly.timestamp)}`,
                        source: 'anomaly',
                      })}
                    >
                      <Plus className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* ── Source Distribution ──────────────────── */}
        {summary && Object.keys(summary.by_source).length > 0 && (
          <div className="pt-2 border-t">
            <h4 className="text-xs font-medium text-muted-foreground mb-2">
              Anomalies by Source
            </h4>
            <div className="space-y-1.5">
              {Object.entries(summary.by_source)
                .sort(([, a], [, b]) => b.anomalies - a.anomalies)
                .slice(0, 5)
                .map(([source, data]) => {
                  const rate = data.total > 0 
                    ? ((data.anomalies / data.total) * 100).toFixed(1)
                    : '0'
                  return (
                    <div key={source} className="flex items-center gap-2 text-xs">
                      <span className="w-12 truncate font-medium">{source}</span>
                      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                        <div 
                          className="h-full rounded-full bg-gradient-to-r from-amber-500 to-rose-600"
                          style={{ width: `${Math.min(100, parseFloat(rate) * 5)}%` }}
                        />
                      </div>
                      <span className="w-16 text-right text-muted-foreground">
                        {data.anomalies}/{data.total}
                      </span>
                    </div>
                  )
                })}
            </div>
          </div>
        )}
      </PanelContent>

      {/* Settings Dialog */}
      <Dialog open={showSettings} onOpenChange={setShowSettings}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Re-run Anomaly Detection</DialogTitle>
            <DialogDescription>
              Configure the ML model parameters
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Model Type</Label>
              <Select value={modelType} onValueChange={setModelType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ensemble">Ensemble (Recommended)</SelectItem>
                  <SelectItem value="IsolationForest">Isolation Forest</SelectItem>
                  <SelectItem value="LOF">Local Outlier Factor</SelectItem>
                  <SelectItem value="DistilBERT">DistilBERT (Context)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Contamination Rate: {(contamination[0] * 100).toFixed(0)}%</Label>
              <Slider
                value={contamination}
                onValueChange={setContamination}
                min={0.01}
                max={0.3}
                step={0.01}
              />
              <p className="text-xs text-muted-foreground">
                Expected proportion of outliers in the dataset
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSettings(false)}>
              Cancel
            </Button>
            <Button onClick={handleRunDetection} disabled={running}>
              {running && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Start Detection
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
