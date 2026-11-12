'use client'

import * as React from 'react'
import { cn } from '@operation-room/lib/utils'
import { useStudioStore } from '@operation-room/components/studio-v4/store/useStudioStore'
import { Badge } from '@operation-room/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@operation-room/components/ui/card'
import { ScrollArea } from '@operation-room/components/ui/scroll-area'
import { ActionTooltip } from '@operation-room/components/ui/ActionTooltip'
import {
  GitBranch,
  Circle,
  ArrowRight,
  AlertTriangle,
  CheckCircle,
  Link2,
  Target,
  Layers,
  Users,
} from 'lucide-react'

// ============================================================================
// Types
// ============================================================================

export interface CorrelationNode {
  id: string
  label: string
  type: 'event' | 'actor' | 'resource' | 'anomaly' | 'root_cause'
  weight?: number
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info'
  timestamp?: string
  metadata?: Record<string, any>
}

export interface CorrelationEdge {
  source: string
  target: string
  weight?: number
  label?: string
  type?: 'causal' | 'temporal' | 'similarity' | 'attribution'
}

export interface CorrelationCluster {
  id: string
  name: string
  nodes: string[]
  confidence?: number
  root_cause?: string
}

export interface CausalChain {
  id: string
  description: string
  events: Array<{
    id: string
    description: string
    confidence: number
  }>
  root_cause: string
  impact: string
  confidence: number
}

// ============================================================================
// Color & Style Utilities
// ============================================================================

const nodeTypeConfig: Record<string, { color: string; bgColor: string; icon: React.FC<{ className?: string }> }> = {
  event: { color: 'text-blue-600', bgColor: 'bg-blue-100', icon: Circle },
  actor: { color: 'text-purple-600', bgColor: 'bg-purple-100', icon: Users },
  resource: { color: 'text-green-600', bgColor: 'bg-green-100', icon: Layers },
  anomaly: { color: 'text-orange-600', bgColor: 'bg-orange-100', icon: AlertTriangle },
  root_cause: { color: 'text-red-600', bgColor: 'bg-red-100', icon: Target },
}

const severityColors: Record<string, string> = {
  critical: 'border-red-500 shadow-red-200',
  high: 'border-orange-500 shadow-orange-200',
  medium: 'border-yellow-500 shadow-yellow-200',
  low: 'border-green-500 shadow-green-200',
  info: 'border-blue-500 shadow-blue-200',
}

// ============================================================================
// Correlation Graph (SVG-based)
// ============================================================================

interface CorrelationGraphProps {
  nodes: CorrelationNode[]
  edges: CorrelationEdge[]
  clusters?: CorrelationCluster[]
  width?: number
  height?: number
  onNodeClick?: (node: CorrelationNode) => void
  highlightPath?: string[]
  className?: string
}

export function CorrelationGraph({
  nodes,
  edges,
  clusters,
  width = 700,
  height = 500,
  onNodeClick,
  highlightPath = [],
  className,
}: CorrelationGraphProps) {
  const { focusMode } = useStudioStore()

  const filteredEdges = React.useMemo(() => {
    if (focusMode === 'Story') {
      return edges.filter(e => {
        // BUG FIX: Intentionally default un-vetted data to 0 instead of 1
        // so executives don't see unverified assumptions masquerading as 100% facts.
        const conf = e.weight ?? (e as any).confidence_score ?? (e as any).confidence ?? 0;
        return conf >= 0.8;
      });
    }
    return edges;
  }, [edges, focusMode])
  // Simple hierarchical layout
  const layout = React.useMemo(() => {
    const nodeMap = new Map<string, { x: number; y: number; node: CorrelationNode }>()
    
    // Group nodes by type
    const groups: Record<string, CorrelationNode[]> = {
      root_cause: [],
      anomaly: [],
      event: [],
      actor: [],
      resource: [],
    }
    
    nodes.forEach(node => {
      const type = node.type || 'event'
      if (!groups[type]) groups[type] = []
      groups[type].push(node)
    })

    // Layout order (top to bottom): root_cause → anomaly → event → actor/resource
    const orderedGroups = ['root_cause', 'anomaly', 'event', 'actor', 'resource']
    let yOffset = 60

    orderedGroups.forEach(groupType => {
      const group = groups[groupType]
      if (!group || group.length === 0) return

      const xStep = width / (group.length + 1)
      
      group.forEach((node, i) => {
        nodeMap.set(node.id, {
          x: xStep * (i + 1),
          y: yOffset,
          node,
        })
      })

      yOffset += 100
    })

    return nodeMap
  }, [nodes, width])

  const highlightSet = new Set(highlightPath)

  return (
    <div className={cn("relative bg-muted/10 rounded-lg border overflow-hidden", className)}>
      <svg width={width} height={height}>
        {/* Cluster backgrounds */}
        {clusters?.map((cluster, i) => {
          const clusterNodes = cluster.nodes
            .map(id => layout.get(id))
            .filter(Boolean) as { x: number; y: number }[]
          
          if (clusterNodes.length < 2) return null
          
          const minX = Math.min(...clusterNodes.map(n => n.x)) - 30
          const maxX = Math.max(...clusterNodes.map(n => n.x)) + 30
          const minY = Math.min(...clusterNodes.map(n => n.y)) - 25
          const maxY = Math.max(...clusterNodes.map(n => n.y)) + 25

          return (
            <rect
              key={cluster.id}
              x={minX}
              y={minY}
              width={maxX - minX}
              height={maxY - minY}
              rx={12}
              fill={`hsla(${(i * 60) % 360}, 70%, 50%, 0.1)`}
              stroke={`hsla(${(i * 60) % 360}, 70%, 50%, 0.3)`}
              strokeWidth={2}
              strokeDasharray="4"
            />
          )
        })}

        {/* Phase 2: Join Confidence Routing */}
        {filteredEdges.map((edge: any, i) => {
          const src = layout.get(edge.source)
          const dst = layout.get(edge.target)
          if (!src || !dst) return null

          const isHighlighted = highlightSet.has(edge.source) && highlightSet.has(edge.target)
          const confidence = edge.confidence_score !== undefined ? edge.confidence_score : 1.0;
          
          let strokeColor = '#94a3b8'
          let strokeDash = undefined
          let opacity = isHighlighted ? 1 : 0.6
          
          if (isHighlighted) {
            strokeColor = '#3b82f6'
          } else if (edge.type === 'causal') {
            strokeColor = '#ef4444'
          } else if (confidence > 0.8) {
            strokeColor = '#10B981' // emerald
          } else if (confidence < 0.5) {
            strokeColor = '#F59E0B' // amber
            strokeDash = '4 4' // dotted
            opacity = 0.4
          }

          const strokeWidth = isHighlighted ? 3 : Math.max(1, (edge.weight || 0.5) * 2)

          // Calculate control point for curved edges
          const midX = (src.x + dst.x) / 2
          const midY = (src.y + dst.y) / 2
          const offset = (src.x - dst.x) * 0.2

          return (
            <ActionTooltip 
              key={i} 
              isSvg 
              label={`Confidence: ${confidence.toFixed(2)}${edge.join_reason ? ` (${edge.join_reason})` : ''}`}
            >
              <g>
                <path
                  d={`M ${src.x} ${src.y} Q ${midX + offset} ${midY} ${dst.x} ${dst.y}`}
                  fill="none"
                  stroke={strokeColor}
                  className="transition-all duration-300"
                  strokeWidth={strokeWidth}
                  strokeOpacity={opacity}
                  strokeDasharray={strokeDash}
                  markerEnd="url(#correlation-arrow)"
                />
                {edge.label && (
                  <text
                    x={midX}
                    y={midY - 5}
                    textAnchor="middle"
                    className="text-[9px] fill-muted-foreground"
                  >
                    {edge.label}
                  </text>
                )}
              </g>
            </ActionTooltip>
          )
        })}

        {/* Arrow marker */}
        <defs>
          <marker
            id="correlation-arrow"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8" />
          </marker>
        </defs>

        {/* Nodes */}
        {Array.from(layout.values()).map(({ x, y, node }) => {
          const config = nodeTypeConfig[node.type] || nodeTypeConfig.event
          const Icon = config.icon
          const isHighlighted = highlightSet.has(node.id)
          const severity = node.severity || 'info'

          return (
            <g
              key={node.id}
              transform={`translate(${x}, ${y})`}
              className={cn("cursor-pointer transition-transform", onNodeClick && "hover:scale-110")}
              onClick={() => onNodeClick?.(node)}
            >
              {/* Node background */}
              <circle
                r={node.type === 'root_cause' ? 28 : 22}
                className={cn(
                  "fill-white stroke-2 shadow-sm",
                  severityColors[severity],
                  isHighlighted && "stroke-[3px] stroke-blue-500"
                )}
                style={{ filter: isHighlighted ? 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.5))' : undefined }}
              />
              
              {/* Inner colored circle */}
              <circle
                r={node.type === 'root_cause' ? 18 : 14}
                className={config.bgColor}
              />
              
              {/* Icon - positioned at center */}
              <foreignObject x={-8} y={-8} width={16} height={16}>
                <Icon className={cn("h-4 w-4", config.color)} />
              </foreignObject>

              {/* Label */}
              <text
                y={node.type === 'root_cause' ? 42 : 36}
                textAnchor="middle"
                className="text-[10px] fill-foreground font-medium"
              >
                {node.label?.length > 15 ? node.label.slice(0, 12) + '...' : node.label}
              </text>
            </g>
          )
        })}
      </svg>

      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex gap-3 text-xs bg-background/80 px-2 py-1 rounded">
        {Object.entries(nodeTypeConfig).map(([type, config]) => {
          const Icon = config.icon
          return (
            <span key={type} className="flex items-center gap-1">
              <Icon className={cn("h-3 w-3", config.color)} />
              {type.replace('_', ' ')}
            </span>
          )
        })}
      </div>
    </div>
  )
}

// ============================================================================
// Causal Chain Timeline
// ============================================================================

interface CausalChainViewProps {
  chain: CausalChain
  onEventClick?: (eventId: string) => void
  className?: string
}

export function CausalChainView({
  chain,
  onEventClick,
  className,
}: CausalChainViewProps) {
  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <GitBranch className="h-4 w-4" />
            Causal Chain Analysis
          </CardTitle>
          <Badge 
            variant="outline" 
            className={cn(
              "text-xs",
              chain.confidence > 0.8 ? "text-green-600" : 
              chain.confidence > 0.5 ? "text-yellow-600" : "text-red-600"
            )}
          >
            {(chain.confidence * 100).toFixed(0)}% confidence
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">{chain.description}</p>
      </CardHeader>
      <CardContent>
        {/* Root Cause */}
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-2 text-sm font-medium text-red-700">
            <Target className="h-4 w-4" />
            Root Cause
          </div>
          <p className="text-sm mt-1">{chain.root_cause}</p>
        </div>

        {/* Event Chain */}
        <div className="relative pl-6 space-y-3">
          {/* Vertical line */}
          <div className="absolute left-2 top-2 bottom-2 w-0.5 bg-gradient-to-b from-red-400 to-blue-400" />

          {chain.events.map((event, index) => (
            <div
              key={event.id}
              className={cn(
                "relative p-3 bg-muted/50 rounded-lg border",
                onEventClick && "cursor-pointer hover:bg-muted"
              )}
              onClick={() => onEventClick?.(event.id)}
            >
              {/* Timeline dot */}
              <div className="absolute -left-4 top-4 w-4 h-4 rounded-full bg-white border-2 border-primary flex items-center justify-center">
                <span className="text-[8px] font-bold">{index + 1}</span>
              </div>

              <div className="flex items-start justify-between gap-2">
                <p className="text-sm">{event.description}</p>
                <Badge variant="outline" className="text-xs shrink-0">
                  {(event.confidence * 100).toFixed(0)}%
                </Badge>
              </div>
            </div>
          ))}
        </div>

        {/* Impact */}
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center gap-2 text-sm font-medium text-blue-700">
            <AlertTriangle className="h-4 w-4" />
            Impact Assessment
          </div>
          <p className="text-sm mt-1">{chain.impact}</p>
        </div>
      </CardContent>
    </Card>
  )
}

// ============================================================================
// Correlation Clusters List
// ============================================================================

interface CorrelationClustersProps {
  clusters: CorrelationCluster[]
  nodes: CorrelationNode[]
  onClusterClick?: (cluster: CorrelationCluster) => void
  className?: string
}

export function CorrelationClusters({
  clusters,
  nodes,
  onClusterClick,
  className,
}: CorrelationClustersProps) {
  const nodeMap = React.useMemo(() => 
    new Map(nodes.map(n => [n.id, n])),
    [nodes]
  )

  return (
    <div className={cn("space-y-3", className)}>
      {clusters.map((cluster, index) => {
        const clusterNodes = cluster.nodes
          .map(id => nodeMap.get(id))
          .filter(Boolean) as CorrelationNode[]
        
        const rootCauseNode = cluster.root_cause 
          ? nodeMap.get(cluster.root_cause) 
          : clusterNodes.find(n => n.type === 'root_cause')

        return (
          <Card
            key={cluster.id}
            className={cn(
              "transition-shadow",
              onClusterClick && "cursor-pointer hover:shadow-md"
            )}
            onClick={() => onClusterClick?.(cluster)}
          >
            <CardContent className="p-4">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div 
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: `hsl(${(index * 60) % 360}, 70%, 50%)` }}
                  />
                  <span className="font-medium text-sm">{cluster.name}</span>
                </div>
                {cluster.confidence !== undefined && (
                  <Badge variant="outline" className="text-xs">
                    {(cluster.confidence * 100).toFixed(0)}%
                  </Badge>
                )}
              </div>

              {/* Root cause highlight */}
              {rootCauseNode && (
                <div className="mb-2 p-2 bg-red-50 rounded border border-red-200 text-xs">
                  <span className="font-medium text-red-700">Root Cause:</span>{' '}
                  {rootCauseNode.label}
                </div>
              )}

              {/* Node count */}
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                <span>{clusterNodes.length} related events</span>
                <span className="flex items-center gap-1">
                  <Link2 className="h-3 w-3" />
                  Correlated
                </span>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

// ============================================================================
// Correlation Summary Stats
// ============================================================================

interface CorrelationSummaryProps {
  nodes: CorrelationNode[]
  edges: CorrelationEdge[]
  clusters?: CorrelationCluster[]
  className?: string
}

export function CorrelationSummary({
  nodes,
  edges,
  clusters,
  className,
}: CorrelationSummaryProps) {
  const stats = React.useMemo(() => {
    const typeCount: Record<string, number> = {}
    let criticalCount = 0
    
    nodes.forEach(n => {
      typeCount[n.type] = (typeCount[n.type] || 0) + 1
      if (n.severity === 'critical' || n.severity === 'high') criticalCount++
    })

    const causalEdges = edges.filter(e => e.type === 'causal').length
    const avgWeight = edges.length > 0 
      ? edges.reduce((sum, e) => sum + (e.weight || 0.5), 0) / edges.length
      : 0

    return {
      totalNodes: nodes.length,
      totalEdges: edges.length,
      clusterCount: clusters?.length || 0,
      criticalCount,
      causalEdges,
      avgWeight,
      typeCount,
    }
  }, [nodes, edges, clusters])

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <GitBranch className="h-4 w-4" />
          Correlation Summary
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground text-xs">Total Nodes</p>
            <p className="text-2xl font-bold">{stats.totalNodes}</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Connections</p>
            <p className="text-2xl font-bold">{stats.totalEdges}</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Clusters</p>
            <p className="text-lg font-semibold text-primary">{stats.clusterCount}</p>
          </div>
          <div>
            <p className="text-muted-foreground text-xs">Critical Events</p>
            <p className={cn("text-lg font-semibold", stats.criticalCount > 0 && "text-red-600")}>
              {stats.criticalCount}
            </p>
          </div>
        </div>

        {/* Type breakdown */}
        <div className="mt-4 flex gap-2 flex-wrap">
          {Object.entries(stats.typeCount).map(([type, count]) => {
            const config = nodeTypeConfig[type] || nodeTypeConfig.event
            return (
              <Badge 
                key={type} 
                variant="outline" 
                className={cn("text-xs", config.bgColor, config.color)}
              >
                {type}: {count}
              </Badge>
            )
          })}
        </div>

        {/* Causal analysis */}
        <div className="mt-4 p-2 bg-muted/50 rounded text-xs">
          <span className="text-muted-foreground">Causal relationships:</span>{' '}
          <span className="font-medium">{stats.causalEdges}</span>
          <span className="mx-2">•</span>
          <span className="text-muted-foreground">Avg. correlation:</span>{' '}
          <span className="font-medium">{(stats.avgWeight * 100).toFixed(0)}%</span>
        </div>
      </CardContent>
    </Card>
  )
}

export default CorrelationGraph
