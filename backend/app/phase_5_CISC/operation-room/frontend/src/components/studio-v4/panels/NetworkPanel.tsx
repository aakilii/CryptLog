'use client'

import React, { useEffect, useState, useCallback } from 'react'
import {
  Network,
  Server,
  Activity,
  AlertTriangle,
  Globe,
  Wifi,
  ShieldAlert,
  Search,
  Plus,
  RefreshCw
} from 'lucide-react'
import { api } from '@operation-room/lib/api'
import {
  PanelHeader,
  PanelContent,
  PanelLoading,
  PanelEmptyState,
  ComponentCard,
} from '../ExpandablePanel'
import { useStudioStore } from '../store/useStudioStore'
import { Button } from '@operation-room/components/ui/button'
import { Badge } from '@operation-room/components/ui/badge'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@operation-room/components/ui/tabs'

// Network Components Constants
const NETWORK_COMPONENTS = [
  {
    id: 'network-force-graph',
    name: 'Entity Force Graph',
    description: 'Interactive 3D or 2D force-directed network graph',
    icon: Network,
    type: 'force-graph' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 relative overflow-hidden flex items-center justify-center opacity-80 cursor-default">
        <div className="absolute w-2 h-2 rounded-full bg-blue-500 left-1/4 top-1/4" />
        <div className="absolute w-3 h-3 rounded-full bg-rose-500 right-1/4 top-1/3" />
        <div className="absolute w-2.5 h-2.5 rounded-full bg-emerald-500 left-1/3 bottom-1/4" />
        <div className="absolute w-4 h-4 rounded-full bg-indigo-500 right-1/3 bottom-1/3" />
        
        <svg className="absolute inset-0" style={{ width: '100%', height: '100%' }}>
           <path d="M 30 20 L 70 30 L 60 70 L 30 20" stroke="currentColor" strokeWidth="1" className="text-slate-300" fill="none" />
           <path d="M 60 70 L 40 80" stroke="currentColor" strokeWidth="1" className="text-slate-300" fill="none" />
        </svg>
      </div>
    ),
  },
  {
    id: 'network-traffic-map',
    name: 'Geospatial Traffic Map',
    description: 'Global map showing origin and destination IPs',
    icon: Globe,
    type: 'geo-map' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 relative flex items-center justify-center overflow-hidden opacity-80 cursor-default">
         <Globe className="absolute text-slate-200" style={{ width: '120%', height: '120%' }} strokeWidth={0.5} />
         <div className="absolute w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse shadow-[0_0_10px_rgba(244,63,94,0.8)] top-1/3 left-1/3" />
         <div className="absolute w-1.5 h-1.5 rounded-full bg-blue-500 bottom-1/3 right-1/3" />
         <svg className="absolute inset-0" style={{ width: '100%', height: '100%' }}>
           <path d="M 35 35 Q 50 10 65 65" stroke="#f43f5e" strokeWidth="1" strokeDasharray="2 2" fill="none" className="opacity-70" />
         </svg>
      </div>
    ),
  },
  {
    id: 'network-conn-table',
    name: 'Active Connections Table',
    description: 'Tabular view of high-risk network connections',
    icon: Activity,
    type: 'conn-table' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 flex flex-col gap-1 opacity-80 cursor-default">
         <div className="flex gap-2 border-b border-slate-200 pb-1">
            <div className="h-1.5 w-8 bg-slate-300 rounded-sm" />
            <div className="h-1.5 w-12 bg-slate-300 rounded-sm" />
            <div className="h-1.5 w-6 bg-slate-300 rounded-sm" />
         </div>
         {Array.from({length: 4}).map((_, i) => (
           <div key={i} className="flex gap-2 py-0.5 items-center">
              <div className="h-1 w-8 bg-slate-200 rounded-sm" />
              <div className="h-1 flex-1 bg-slate-200 rounded-sm" />
              <div className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: i === 0 ? '#f43f5e' : i === 1 ? '#eab308' : '#10b981' }} />
           </div>
         ))}
      </div>
    ),
  },
]

interface NetworkEntity {
  entity_id: string
  ip_address: string
  domain?: string
  entity_type: string
  risk_score: number
  bytes_transferred: number
  connections_count: number
}

interface NetworkPanelProps {
  caseId: string
  onInsertComponent?: (componentId: string, config?: Record<string, unknown>) => void
  onInsertEntity?: (entity: NetworkEntity) => void
}

export const NetworkPanel = ({
  caseId,
  onInsertComponent,
  onInsertEntity,
}: NetworkPanelProps) => {
  const setPanelBadge = useStudioStore((s) => s.setPanelBadge)
  const [entities, setEntities] = useState<NetworkEntity[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    if (!caseId) return
    try {
      setLoading(true)
      // Example endpoint: fetch high-risk network entities
      const data = await api.get(`/cases/${caseId}/network/entities?risk=high`).catch(() => [])
      if (Array.isArray(data)) {
        setEntities(data)
        setPanelBadge('network', data.length)
      } else {
        setPanelBadge('network', 0)
      }
    } catch (err) {
      console.error('Failed to load network data:', err)
      setError('Failed to load network data')
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    loadData()
  }, [loadData])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PanelHeader
        title="Network Analysis"
        panelId="network"
        icon={<Network className="h-4 w-4" />}
        color="#3b82f6"
        showSearch={false}
        actions={
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={loadData}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        }
      />
      <PanelContent>
        <Tabs defaultValue="components" className="w-full">
          <TabsList className="w-full grid grid-cols-2 mb-4">
            <TabsTrigger value="entities">Entities</TabsTrigger>
            <TabsTrigger value="components">Components</TabsTrigger>
          </TabsList>

          <TabsContent value="components" className="space-y-4 outline-none">
            <h3 className="font-geist text-sm font-semibold mb-3">Network Visualizations</h3>
            <div className="grid grid-cols-1 gap-4 pb-4 px-1">
              {NETWORK_COMPONENTS.map((comp) => (
                <ComponentCard
                  key={comp.id}
                  id={comp.id}
                  name={comp.name}
                  description={comp.description}
                  icon={<comp.icon strokeWidth={1.5} />}
                  preview={comp.preview as React.ReactNode}
                  onClick={() => onInsertComponent?.(comp.id)}
                  onDragStart={(e: React.DragEvent) => {
                    e.dataTransfer.setData('application/json', JSON.stringify({
                      type: 'component',
                      componentId: comp.id,
                      module: 'network'
                    }))
                  }}
                />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="entities" className="space-y-4 outline-none">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-geist text-sm font-semibold">High-Risk Nodes</h3>
              <Badge variant="destructive" className="font-geist-mono">
                {entities.length} Found
              </Badge>
            </div>

            {loading ? (
              <PanelLoading message="Analyzing network topology..." />
            ) : error ? (
              <PanelEmptyState
                icon={<AlertTriangle className="h-6 w-6 text-destructive" />}
                title="Analysis Error"
                description={error}
                action={(
                  <Button variant="outline" size="sm" onClick={loadData}>
                    Retry Analysis
                  </Button>
                )}
              />
            ) : entities.length === 0 ? (
              <PanelEmptyState
                icon={<ShieldAlert className="h-6 w-6" />}
                title="No Critical Nodes"
                description="No high-risk network connections identified."
              />
            ) : (
              <div className="space-y-2">
                {entities.map((entity) => (
                  <div
                    key={entity.entity_id}
                    className="group flex flex-col gap-2 p-3 rounded-md border bg-card hover:bg-destructive/5 hover:border-destructive/30 transition-colors cursor-pointer"
                    onClick={() => onInsertEntity?.(entity)}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData('application/json', JSON.stringify({
                        type: 'entity',
                        data: entity,
                        module: 'network'
                      }))
                    }}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <Server className="h-4 w-4 text-destructive" />
                        <span className="font-geist text-sm font-medium leading-none">
                          {entity.ip_address}
                        </span>
                      </div>
                      <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Plus className="h-3 w-3" />
                      </Button>
                    </div>
                    
                    <div className="flex items-center justify-between mt-1">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-[10px] px-1.5 h-4 border-destructive/20 text-destructive">
                          Risk: {entity.risk_score}/100
                        </Badge>
                        {entity.domain && (
                          <span className="font-geist-mono text-[10px] text-muted-foreground truncate max-w-[120px]">
                            {entity.domain}
                          </span>
                        )}
                      </div>
                      <span className="font-geist-mono text-[10px] text-muted-foreground">
                        {entity.connections_count} conns
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </PanelContent>
    </div>
  )
}
