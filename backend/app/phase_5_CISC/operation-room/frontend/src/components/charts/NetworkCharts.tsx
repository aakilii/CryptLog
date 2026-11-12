'use client'

import * as React from 'react'
import { cn } from '@operation-room/lib/utils'
import { Badge } from '@operation-room/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@operation-room/components/ui/card'
import { ScrollArea } from '@operation-room/components/ui/scroll-area'
import {
  Network,
  ArrowRight,
  ArrowUpRight,
  ArrowDownRight,
  Globe,
  Server,
  Shield,
  AlertTriangle,
  Download,
  Upload,
} from 'lucide-react'

// ============================================================================
// Types
// ============================================================================

export interface NetworkFlow {
  id: string
  src_ip: string
  dst_ip: string
  src_port?: number
  dst_port?: number
  protocol?: string
  bytes_sent?: number
  bytes_received?: number
  packets?: number
  direction: 'inbound' | 'outbound' | 'internal' | 'external'
  timestamp?: string
  duration_ms?: number
  is_suspicious?: boolean
  threat_score?: number
  geo_src?: { country?: string; city?: string }
  geo_dst?: { country?: string; city?: string }
  metadata?: Record<string, any>
}

export interface NetworkNode {
  id: string
  ip: string
  label?: string
  type: 'internal' | 'external' | 'server' | 'unknown'
  total_bytes?: number
  connection_count?: number
  threat_level?: 'critical' | 'high' | 'medium' | 'low' | 'none'
}

// ============================================================================
// Utility Functions
// ============================================================================

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`
}

function getThreatColor(score?: number, level?: string): string {
  if (level === 'critical' || (score && score > 0.8)) return 'text-red-600 bg-red-100 border-red-200'
  if (level === 'high' || (score && score > 0.6)) return 'text-orange-600 bg-orange-100 border-orange-200'
  if (level === 'medium' || (score && score > 0.4)) return 'text-yellow-600 bg-yellow-100 border-yellow-200'
  if (level === 'low' || (score && score > 0.2)) return 'text-green-600 bg-green-100 border-green-200'
  return 'text-slate-600 bg-slate-100 border-slate-200'
}

// ============================================================================
// Network Flow Table
// ============================================================================

interface NetworkFlowTableProps {
  flows: NetworkFlow[]
  maxRows?: number
  showGeo?: boolean
  onFlowClick?: (flow: NetworkFlow) => void
  className?: string
}

export function NetworkFlowTable({
  flows,
  maxRows = 20,
  showGeo = false,
  onFlowClick,
  className,
}: NetworkFlowTableProps) {
  const displayFlows = flows.slice(0, maxRows)

  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-sm">
        <thead className="bg-muted/50 border-b">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Direction</th>
            <th className="px-3 py-2 text-left font-medium">Source</th>
            <th className="px-3 py-2 text-left font-medium">Destination</th>
            <th className="px-3 py-2 text-left font-medium">Protocol</th>
            <th className="px-3 py-2 text-right font-medium">Bytes</th>
            <th className="px-3 py-2 text-center font-medium">Threat</th>
            {showGeo && <th className="px-3 py-2 text-left font-medium">Geo</th>}
          </tr>
        </thead>
        <tbody>
          {displayFlows.map((flow) => (
            <tr
              key={flow.id}
              className={cn(
                "border-b hover:bg-muted/30 transition-colors",
                flow.is_suspicious && "bg-red-50",
                onFlowClick && "cursor-pointer"
              )}
              onClick={() => onFlowClick?.(flow)}
            >
              <td className="px-3 py-2">
                <DirectionBadge direction={flow.direction} />
              </td>
              <td className="px-3 py-2 font-mono text-xs">
                {flow.src_ip}
                {flow.src_port && <span className="text-muted-foreground">:{flow.src_port}</span>}
              </td>
              <td className="px-3 py-2 font-mono text-xs">
                {flow.dst_ip}
                {flow.dst_port && <span className="text-muted-foreground">:{flow.dst_port}</span>}
              </td>
              <td className="px-3 py-2">
                <Badge variant="outline" className="text-xs">
                  {flow.protocol || 'TCP'}
                </Badge>
              </td>
              <td className="px-3 py-2 text-right font-mono text-xs">
                {formatBytes((flow.bytes_sent || 0) + (flow.bytes_received || 0))}
              </td>
              <td className="px-3 py-2 text-center">
                {flow.threat_score !== undefined ? (
                  <span className={cn(
                    "px-2 py-0.5 rounded text-xs font-medium",
                    getThreatColor(flow.threat_score)
                  )}>
                    {(flow.threat_score * 100).toFixed(0)}%
                  </span>
                ) : flow.is_suspicious ? (
                  <AlertTriangle className="h-4 w-4 text-orange-500 mx-auto" />
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </td>
              {showGeo && (
                <td className="px-3 py-2 text-xs">
                  {flow.geo_dst?.country || flow.geo_src?.country || '-'}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {flows.length > maxRows && (
        <div className="p-2 text-center text-xs text-muted-foreground border-t">
          Showing {maxRows} of {flows.length} flows
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Direction Badge
// ============================================================================

function DirectionBadge({ direction }: { direction: NetworkFlow['direction'] }) {
  const config = {
    inbound: { icon: ArrowDownRight, color: 'text-blue-600 bg-blue-100', label: 'IN' },
    outbound: { icon: ArrowUpRight, color: 'text-red-600 bg-red-100', label: 'OUT' },
    internal: { icon: ArrowRight, color: 'text-green-600 bg-green-100', label: 'INT' },
    external: { icon: Globe, color: 'text-purple-600 bg-purple-100', label: 'EXT' },
  }
  
  const { icon: Icon, color, label } = config[direction]
  
  return (
    <span className={cn("inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium", color)}>
      <Icon className="h-3 w-3" />
      {label}
    </span>
  )
}

// ============================================================================
// Network Topology Visualization (Simple SVG)
// ============================================================================

interface NetworkTopologyProps {
  nodes: NetworkNode[]
  flows: NetworkFlow[]
  width?: number
  height?: number
  onNodeClick?: (node: NetworkNode) => void
  className?: string
}

export function NetworkTopology({
  nodes,
  flows,
  width = 600,
  height = 400,
  onNodeClick,
  className,
}: NetworkTopologyProps) {
  // Simple force-directed layout simulation
  const layout = React.useMemo(() => {
    const nodeMap = new Map<string, { x: number; y: number; node: NetworkNode }>()
    const centerX = width / 2
    const centerY = height / 2
    const radius = Math.min(width, height) * 0.35

    // Position internal nodes in center, external on edges
    const internalNodes = nodes.filter(n => n.type === 'internal' || n.type === 'server')
    const externalNodes = nodes.filter(n => n.type === 'external' || n.type === 'unknown')

    // Arrange internal nodes in inner circle
    internalNodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / internalNodes.length
      nodeMap.set(node.ip, {
        x: centerX + Math.cos(angle) * radius * 0.4,
        y: centerY + Math.sin(angle) * radius * 0.4,
        node,
      })
    })

    // Arrange external nodes in outer circle
    externalNodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / externalNodes.length
      nodeMap.set(node.ip, {
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
        node,
      })
    })

    return nodeMap
  }, [nodes, width, height])

  // Create edges from flows
  const edges = React.useMemo(() => {
    const edgeMap = new Map<string, { src: string; dst: string; bytes: number; suspicious: boolean }>()
    
    flows.forEach(flow => {
      const key = `${flow.src_ip}->${flow.dst_ip}`
      const existing = edgeMap.get(key)
      if (existing) {
        existing.bytes += (flow.bytes_sent || 0) + (flow.bytes_received || 0)
        existing.suspicious = existing.suspicious || !!flow.is_suspicious
      } else {
        edgeMap.set(key, {
          src: flow.src_ip,
          dst: flow.dst_ip,
          bytes: (flow.bytes_sent || 0) + (flow.bytes_received || 0),
          suspicious: !!flow.is_suspicious,
        })
      }
    })

    return Array.from(edgeMap.values())
  }, [flows])

  const maxBytes = Math.max(...edges.map(e => e.bytes), 1)

  return (
    <div className={cn("relative bg-muted/20 rounded-lg border", className)}>
      <svg width={width} height={height} className="block">
        {/* Draw edges */}
        {edges.map((edge, i) => {
          const src = layout.get(edge.src)
          const dst = layout.get(edge.dst)
          if (!src || !dst) return null

          const strokeWidth = Math.max(1, (edge.bytes / maxBytes) * 4)
          
          return (
            <line
              key={i}
              x1={src.x}
              y1={src.y}
              x2={dst.x}
              y2={dst.y}
              stroke={edge.suspicious ? '#ef4444' : '#94a3b8'}
              strokeWidth={strokeWidth}
              strokeOpacity={0.6}
              markerEnd="url(#arrowhead)"
            />
          )
        })}

        {/* Arrow marker */}
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="7"
            refX="9"
            refY="3.5"
            orient="auto"
          >
            <polygon points="0 0, 10 3.5, 0 7" fill="#94a3b8" />
          </marker>
        </defs>

        {/* Draw nodes */}
        {Array.from(layout.values()).map(({ x, y, node }) => {
          const isServer = node.type === 'server'
          const isExternal = node.type === 'external'
          const threatColor = getThreatColor(undefined, node.threat_level)

          return (
            <g
              key={node.id}
              transform={`translate(${x}, ${y})`}
              className={cn("cursor-pointer", onNodeClick && "hover:opacity-80")}
              onClick={() => onNodeClick?.(node)}
            >
              {/* Node circle */}
              <circle
                r={isServer ? 24 : 18}
                className={cn(
                  "fill-white stroke-2",
                  isExternal ? "stroke-purple-400" : "stroke-blue-400",
                  node.threat_level === 'critical' && "stroke-red-500",
                  node.threat_level === 'high' && "stroke-orange-500"
                )}
              />
              
              {/* Icon */}
              {isServer ? (
                <Server className="h-5 w-5 -translate-x-2.5 -translate-y-2.5 text-blue-600" />
              ) : isExternal ? (
                <Globe className="h-4 w-4 -translate-x-2 -translate-y-2 text-purple-600" />
              ) : (
                <Network className="h-4 w-4 -translate-x-2 -translate-y-2 text-slate-600" />
              )}

              {/* Label */}
              <text
                y={isServer ? 36 : 28}
                textAnchor="middle"
                className="text-[10px] fill-muted-foreground font-mono"
              >
                {node.label || node.ip.split('.').slice(-2).join('.')}
              </text>
            </g>
          )
        })}
      </svg>

      {/* Legend */}
      <div className="absolute bottom-2 right-2 flex gap-2 text-xs">
        <span className="flex items-center gap-1">
          <Server className="h-3 w-3 text-blue-600" /> Server
        </span>
        <span className="flex items-center gap-1">
          <Globe className="h-3 w-3 text-purple-600" /> External
        </span>
      </div>
    </div>
  )
}

// ============================================================================
// Network Statistics Card
// ============================================================================

interface NetworkStatsProps {
  flows: NetworkFlow[]
  className?: string
}

export function NetworkStats({ flows, className }: NetworkStatsProps) {
  const stats = React.useMemo(() => {
    let totalBytes = 0
    let outboundBytes = 0
    let suspiciousCount = 0
    const uniqueIPs = new Set<string>()
    const protocols = new Map<string, number>()
    const topDestinations = new Map<string, number>()

    flows.forEach(flow => {
      const bytes = (flow.bytes_sent || 0) + (flow.bytes_received || 0)
      totalBytes += bytes
      
      if (flow.direction === 'outbound' || flow.direction === 'external') {
        outboundBytes += bytes
      }
      
      if (flow.is_suspicious) suspiciousCount++
      
      uniqueIPs.add(flow.src_ip)
      uniqueIPs.add(flow.dst_ip)
      
      const proto = flow.protocol || 'TCP'
      protocols.set(proto, (protocols.get(proto) || 0) + 1)
      
      topDestinations.set(flow.dst_ip, (topDestinations.get(flow.dst_ip) || 0) + bytes)
    })

    const topDest = Array.from(topDestinations.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)

    return {
      totalFlows: flows.length,
      totalBytes,
      outboundBytes,
      suspiciousCount,
      uniqueIPs: uniqueIPs.size,
      protocols: Array.from(protocols.entries()),
      topDestinations: topDest,
    }
  }, [flows])

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          <Network className="h-4 w-4" />
          Network Statistics
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-muted-foreground">Total Traffic</p>
            <p className="text-xl font-bold">{formatBytes(stats.totalBytes)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Outbound</p>
            <p className="text-xl font-bold text-orange-600">{formatBytes(stats.outboundBytes)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Unique IPs</p>
            <p className="text-lg font-semibold">{stats.uniqueIPs}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Suspicious</p>
            <p className={cn("text-lg font-semibold", stats.suspiciousCount > 0 && "text-red-600")}>
              {stats.suspiciousCount}
            </p>
          </div>
        </div>

        {/* Top Destinations */}
        <div>
          <p className="text-xs text-muted-foreground mb-2">Top Destinations</p>
          <div className="space-y-1">
            {stats.topDestinations.map(([ip, bytes]) => (
              <div key={ip} className="flex items-center justify-between text-xs">
                <span className="font-mono">{ip}</span>
                <span className="text-muted-foreground">{formatBytes(bytes)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Protocols */}
        <div className="flex gap-2 flex-wrap">
          {stats.protocols.map(([proto, count]) => (
            <Badge key={proto} variant="outline" className="text-xs">
              {proto}: {count}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export default NetworkFlowTable
