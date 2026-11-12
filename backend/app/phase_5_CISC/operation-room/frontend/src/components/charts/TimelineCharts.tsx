'use client'

import * as React from 'react'
import { cn } from '@operation-room/lib/utils'
import { Badge } from '@operation-room/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@operation-room/components/ui/card'
import { ScrollArea } from '@operation-room/components/ui/scroll-area'
import {
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ArrowRight,
  User,
  Server,
  Database,
  FileText,
  Shield,
  Zap,
} from 'lucide-react'

// ============================================================================
// Types
// ============================================================================

export interface TimelineEvent {
  id: string
  timestamp: string
  event_type: string
  source: string
  actor?: string
  target?: string
  action?: string
  message?: string
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info'
  is_anchor?: boolean
  metadata?: Record<string, any>
}

interface TimelineChartProps {
  events: TimelineEvent[]
  startTime?: string
  endTime?: string
  highlightAnchor?: boolean
  showConnectors?: boolean
  groupBy?: 'actor' | 'source' | 'hour' | 'none'
  maxHeight?: number
  onEventClick?: (event: TimelineEvent) => void
  className?: string
}

// ============================================================================
// Severity Styling
// ============================================================================

const severityConfig: Record<string, { color: string; bgColor: string; icon: React.FC<{ className?: string }> }> = {
  critical: { color: 'text-red-600', bgColor: 'bg-red-100 border-red-200', icon: XCircle },
  high: { color: 'text-orange-600', bgColor: 'bg-orange-100 border-orange-200', icon: AlertTriangle },
  medium: { color: 'text-yellow-600', bgColor: 'bg-yellow-100 border-yellow-200', icon: AlertTriangle },
  low: { color: 'text-green-600', bgColor: 'bg-green-100 border-green-200', icon: CheckCircle },
  info: { color: 'text-blue-600', bgColor: 'bg-blue-100 border-blue-200', icon: FileText },
}

const eventTypeIcons: Record<string, React.FC<{ className?: string }>> = {
  login: User,
  logout: User,
  file_access: FileText,
  database: Database,
  network: Server,
  security: Shield,
  system: Zap,
}

// ============================================================================
// Timeline Vertical Chart
// ============================================================================

export function TimelineVerticalChart({
  events,
  highlightAnchor = true,
  showConnectors = true,
  maxHeight = 600,
  onEventClick,
  className,
}: TimelineChartProps) {
  const sortedEvents = React.useMemo(() => 
    [...events].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()),
    [events]
  )

  return (
    <ScrollArea className={cn("relative", className)} style={{ maxHeight }}>
      <div className="relative pl-8">
        {/* Timeline line */}
        {showConnectors && (
          <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-border" />
        )}

        {sortedEvents.map((event, index) => {
          const rawSeverity = event.severity || 'info'
          const severity = rawSeverity.toLowerCase()
          const config = severityConfig[severity] || severityConfig['info']
          const Icon = eventTypeIcons[event.event_type?.toLowerCase()] || config.icon

          return (
            <div
              key={event.id}
              className={cn(
                "relative pb-6 last:pb-0",
                onEventClick && "cursor-pointer hover:bg-muted/50 rounded-lg transition-colors"
              )}
              onClick={() => onEventClick?.(event)}
            >
              {/* Timeline dot */}
              <div
                className={cn(
                  "absolute left-0 w-6 h-6 rounded-full flex items-center justify-center border-2 bg-background",
                  event.is_anchor && highlightAnchor 
                    ? "border-primary ring-2 ring-primary/30" 
                    : "border-muted-foreground/30"
                )}
              >
                <Icon className={cn("h-3 w-3", config.color)} />
              </div>

              {/* Event content */}
              <div className={cn("ml-4 p-3 rounded-lg border", config.bgColor)}>
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs font-mono">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </Badge>
                    <Badge className={cn("text-xs", config.bgColor, config.color)}>
                      {event.event_type}
                    </Badge>
                    {event.is_anchor && highlightAnchor && (
                      <Badge variant="default" className="text-xs bg-primary">
                        Anchor
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Actor → Target */}
                {(event.actor || event.target) && (
                  <div className="flex items-center gap-2 text-sm mb-1">
                    {event.actor && (
                      <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                        {event.actor}
                      </span>
                    )}
                    {event.actor && event.target && (
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                    )}
                    {event.target && (
                      <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                        {event.target}
                      </span>
                    )}
                  </div>
                )}

                {/* Message */}
                {event.message && (
                  <p className="text-sm text-muted-foreground">
                    {event.message}
                  </p>
                )}

                {/* Source */}
                <div className="text-xs text-muted-foreground mt-1">
                  Source: {event.source}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </ScrollArea>
  )
}

// ============================================================================
// Timeline Horizontal Swimlane
// ============================================================================

interface SwimlaneLane {
  id: string
  label: string
  events: TimelineEvent[]
}

interface TimelineSwimlaneProps {
  events: TimelineEvent[]
  groupBy: 'actor' | 'source'
  timeRange?: { start: Date; end: Date }
  pixelsPerMinute?: number
  onEventClick?: (event: TimelineEvent) => void
  className?: string
}

export function TimelineSwimlane({
  events,
  groupBy,
  timeRange,
  pixelsPerMinute = 2,
  onEventClick,
  className,
}: TimelineSwimlaneProps) {
  // Group events into lanes
  const lanes = React.useMemo(() => {
    const grouped = events.reduce((acc, event) => {
      const key = groupBy === 'actor' ? (event.actor || 'Unknown') : event.source
      if (!acc[key]) acc[key] = []
      acc[key].push(event)
      return acc
    }, {} as Record<string, TimelineEvent[]>)

    return Object.entries(grouped).map(([id, evts]) => ({
      id,
      label: id,
      events: evts.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()),
    }))
  }, [events, groupBy])

  // Calculate time range
  const { minTime, maxTime, totalMinutes } = React.useMemo(() => {
    if (timeRange) {
      const totalMins = (timeRange.end.getTime() - timeRange.start.getTime()) / 60000
      return { minTime: timeRange.start.getTime(), maxTime: timeRange.end.getTime(), totalMinutes: totalMins }
    }
    
    const times = events.map(e => new Date(e.timestamp).getTime())
    const min = Math.min(...times)
    const max = Math.max(...times)
    return { minTime: min, maxTime: max, totalMinutes: (max - min) / 60000 || 60 }
  }, [events, timeRange])

  const totalWidth = totalMinutes * pixelsPerMinute

  return (
    <div className={cn("overflow-x-auto", className)}>
      <div style={{ minWidth: totalWidth + 150 }}>
        {/* Time axis */}
        <div className="flex border-b bg-muted/30 sticky top-0 z-10">
          <div className="w-32 shrink-0 p-2 border-r font-medium text-sm">
            {groupBy === 'actor' ? 'Actor' : 'Source'}
          </div>
          <div className="flex-1 relative h-8">
            {Array.from({ length: Math.ceil(totalMinutes / 60) + 1 }, (_, i) => {
              const time = new Date(minTime + i * 60 * 60000)
              return (
                <div
                  key={i}
                  className="absolute text-xs text-muted-foreground"
                  style={{ left: i * 60 * pixelsPerMinute }}
                >
                  {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
              )
            })}
          </div>
        </div>

        {/* Lanes */}
        {lanes.map((lane) => (
          <div key={lane.id} className="flex border-b hover:bg-muted/20">
            <div className="w-32 shrink-0 p-2 border-r text-sm font-mono truncate">
              {lane.label}
            </div>
            <div className="flex-1 relative h-12">
              {lane.events.map((event) => {
                const eventTime = new Date(event.timestamp).getTime()
                const position = ((eventTime - minTime) / 60000) * pixelsPerMinute
                const rawSeverity = event.severity || 'info'
                const severity = rawSeverity.toLowerCase()
                const config = severityConfig[severity] || severityConfig['info']

                return (
                  <div
                    key={event.id}
                    className={cn(
                      "absolute top-2 w-6 h-6 rounded-full flex items-center justify-center cursor-pointer transition-transform hover:scale-125",
                      config.bgColor, "border"
                    )}
                    style={{ left: position }}
                    onClick={() => onEventClick?.(event)}
                    title={`${event.event_type} - ${event.message || ''}`}
                  >
                    <div className={cn("w-2 h-2 rounded-full", config.color.replace('text-', 'bg-'))} />
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================================================
// Timeline Summary Card
// ============================================================================

interface TimelineSummaryProps {
  events: TimelineEvent[]
  className?: string
}

export function TimelineSummary({ events, className }: TimelineSummaryProps) {
  const stats = React.useMemo(() => {
    const severityCounts: Record<string, number> = {}
    const actorCounts: Record<string, number> = {}
    const typeCounts: Record<string, number> = {}
    let anchors = 0

    events.forEach(e => {
      const rawSev = e.severity || 'info'
      const sev = rawSev.toLowerCase()
      severityCounts[sev] = (severityCounts[sev] || 0) + 1
      
      if (e.actor) actorCounts[e.actor] = (actorCounts[e.actor] || 0) + 1
      typeCounts[e.event_type] = (typeCounts[e.event_type] || 0) + 1
      if (e.is_anchor) anchors++
    })

    const times = events.map(e => new Date(e.timestamp).getTime())
    const duration = times.length > 1 
      ? ((Math.max(...times) - Math.min(...times)) / 60000).toFixed(1)
      : '0'

    return {
      total: events.length,
      anchors,
      duration,
      severityCounts,
      topActor: Object.entries(actorCounts).sort((a, b) => b[1] - a[1])[0]?.[0],
      topType: Object.entries(typeCounts).sort((a, b) => b[1] - a[1])[0]?.[0],
    }
  }, [events])

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Clock className="h-4 w-4" />
          Timeline Summary
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Total Events</p>
            <p className="text-2xl font-bold">{stats.total}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Duration</p>
            <p className="text-2xl font-bold">{stats.duration}m</p>
          </div>
          <div>
            <p className="text-muted-foreground">Anchor Points</p>
            <p className="text-lg font-semibold text-primary">{stats.anchors}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Top Actor</p>
            <p className="text-sm font-mono truncate">{stats.topActor || 'N/A'}</p>
          </div>
        </div>
        
        {/* Severity breakdown */}
        <div className="mt-4 flex gap-2 flex-wrap">
          {Object.entries(stats.severityCounts).map(([sev, count]) => (
            <Badge 
              key={sev} 
              variant="outline" 
              className={cn("text-xs", severityConfig[sev]?.bgColor)}
            >
              {sev}: {count}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export default TimelineVerticalChart
