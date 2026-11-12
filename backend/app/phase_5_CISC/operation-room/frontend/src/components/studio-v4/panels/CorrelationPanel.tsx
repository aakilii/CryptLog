'use client'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import { api } from '@/lib/api'
import {
  AlertCircle,
  GitBranch,
  GitMerge,
  GitPullRequest,
  Link2,
  Network,
  Plus,
  RefreshCw,
  Share2
} from 'lucide-react'
import NextImage from 'next/image'
import React, { useCallback, useEffect, useState } from 'react'
import {
  ComponentCard,
  PanelContent,
  PanelEmptyState,
  PanelHeader,
  PanelLoading,
} from '../ExpandablePanel'
import { useStudioStore } from '../store/useStudioStore'
import { emitEvidenceDrill } from './evidenceDrill'
import { getQuestionSpec } from './investigatorQuestionTaxonomy'

// Correlation Components Constants
const CORRELATION_COMPONENTS = [
  {
    id: 'correlation-graph',
    name: 'Correlation Graph',
    description: 'Visual map of cross-module linked artifacts',
    icon: Share2,
    type: 'correlation-graph' as const,
    preview: '/api/placeholder/correlation-graph.svg',
  },
  {
    id: 'correlation-matrix',
    name: 'Relationship Matrix',
    description: 'Grid showing intersection of entities across dimensions',
    icon: Network,
    type: 'correlation-matrix' as const,
    preview: '/api/placeholder/correlation-matrix.svg',
  },
  {
    id: 'correlation-chain',
    name: 'Event Chain',
    description: 'Sequential link of correlated events',
    icon: GitBranch,
    type: 'event-chain' as const,
    preview: '/api/placeholder/correlation-chain.svg',
  },
  {
    id: 'actor-sequence-table',
    name: 'Actor Sequence Table',
    description: 'Ranked actor sequence table for behavior reconstruction',
    icon: GitPullRequest,
    type: 'actor-sequence' as const,
    preview: (
      <div className="w-full h-full p-2 bg-slate-900/5 flex flex-col gap-1 opacity-80 cursor-default">
        {['alice', 'svc-admin', 'backup-job'].map((actor, idx) => (
          <div key={actor} className="flex items-center gap-2 text-[9px]">
            <span className="w-16 text-slate-500 truncate">{actor}</span>
            <div className="h-1.5 flex-1 rounded bg-slate-200 overflow-hidden">
              <div className={idx === 0 ? 'h-full w-4/5 bg-fuchsia-500' : idx === 1 ? 'h-full w-2/3 bg-violet-500' : 'h-full w-1/2 bg-indigo-500'} />
            </div>
          </div>
        ))}
      </div>
    ),
  },
]

const CORRELATION_QUESTION_SPEC = getQuestionSpec('actor_behavior')

interface CorrelatedEntity {
  correlation_id: string
  primary_entity: string
  primary_type: string
  related_entity: string
  related_type: string
  confidence_score: number
  relationship_type: string
}

interface CorrelationPanelProps {
  caseId: string
  onInsertComponent?: (componentId: string, config?: Record<string, unknown>) => void
  onInsertEntity?: (entity: CorrelatedEntity) => void
}

export const CorrelationPanel = ({
  caseId,
  onInsertComponent,
  onInsertEntity,
}: CorrelationPanelProps) => {
  const setPanelBadge = useStudioStore((s) => s.setPanelBadge)
  const [correlations, setCorrelations] = useState<CorrelatedEntity[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const handleDrillToEvidence = useCallback((entity: CorrelatedEntity) => {
    emitEvidenceDrill({
      sourcePanel: 'correlation',
      module: 'correlation',
      title: `${entity.primary_entity} → ${entity.related_entity}`,
      summary: `Correlation type ${entity.relationship_type} at ${(entity.confidence_score * 100).toFixed(0)}% confidence.`,
      questionType: CORRELATION_QUESTION_SPEC?.questionType,
      visualPattern: CORRELATION_QUESTION_SPEC?.visualPattern,
      drillPath: CORRELATION_QUESTION_SPEC?.drillPath,
      findingRef: entity.correlation_id,
      evidenceRef: entity.correlation_id,
      anchorRef: `${entity.primary_entity}:${entity.related_entity}`,
      confidence: entity.confidence_score,
    })
  }, [])

  const loadData = useCallback(async () => {
    if (!caseId) return
    try {
      setLoading(true)
      // Example endpoint: fetch cross-module correlations
      const data = await api.get(`/cases/${caseId}/correlation/graph`).catch(() => [])
      if (Array.isArray(data)) {
        setCorrelations(data)
        setPanelBadge('correlation', data.length)
      } else {
        setPanelBadge('correlation', 0)
      }
    } catch (err) {
      console.error('Failed to load correlation data:', err)
      setError('Failed to load correlation data')
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
        title="Correlation Engine"
        panelId="correlation"
        icon={<Share2 className="h-4 w-4" />}
        color="#d946ef"
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
            <TabsTrigger value="links">Links</TabsTrigger>
            <TabsTrigger value="components">Components</TabsTrigger>
          </TabsList>

          <TabsContent value="components" className="space-y-4 outline-none">
            <h3 className="font-geist text-sm font-semibold mb-3">Correlation Visuals</h3>
            <div className="grid grid-cols-1 gap-2">
              {CORRELATION_COMPONENTS.map((comp) => (
                <ComponentCard
                  key={comp.id}
                  id={comp.id}
                  name={comp.name}
                  description={comp.description}
                  icon={<comp.icon strokeWidth={1.5} />}
                  preview={typeof comp.preview === 'string'
                    ? <NextImage src={comp.preview} alt={comp.name} width={320} height={180} unoptimized className="w-full h-full object-cover opacity-50" />
                    : comp.preview}
                  onClick={() => onInsertComponent?.(comp.id, {
                    module: 'correlation',
                    dataEndpoint: `/api/cases/${caseId}/correlation/graph`,
                    questionType: CORRELATION_QUESTION_SPEC?.questionType,
                    visualPattern: CORRELATION_QUESTION_SPEC?.visualPattern,
                    tracePath: CORRELATION_QUESTION_SPEC?.drillPath,
                  })}
                  onDragStart={(e: React.DragEvent) => {
                    e.dataTransfer.setData('application/json', JSON.stringify({
                      type: 'component',
                      componentId: comp.id,
                      module: 'correlation'
                    }))
                  }}
                />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="links" className="space-y-4 outline-none">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-geist text-sm font-semibold">Verified Links</h3>
              <Badge variant="outline" className="font-geist-mono border-fuchsia-500/30 text-fuchsia-600 dark:text-fuchsia-400">
                {correlations.length} Found
              </Badge>
            </div>

            {loading ? (
              <PanelLoading message="Running correlation engine..." />
            ) : error ? (
              <PanelEmptyState
                icon={<AlertCircle className="h-6 w-6 text-fuchsia-500" />}
                title="Correlation Error"
                description={error}
                action={(
                  <Button variant="outline" size="sm" onClick={loadData} className="border-fuchsia-200 hover:bg-fuchsia-50">
                    Retry Analysis
                  </Button>
                )}
              />
            ) : correlations.length === 0 ? (
              <PanelEmptyState
                icon={<Link2 className="h-6 w-6 text-fuchsia-500/50" />}
                title="No Correlations"
                description="No cross-module linkages have been verified yet."
              />
            ) : (
              <div className="space-y-2">
                {correlations.map((corr) => (
                  <div
                    key={corr.correlation_id}
                    className="group flex flex-col gap-2 p-3 rounded-md border border-slate-200 dark:border-slate-800 bg-card hover:bg-fuchsia-50 dark:hover:bg-fuchsia-950/20 hover:border-fuchsia-500/30 transition-colors cursor-pointer"
                    onClick={() => onInsertEntity?.(corr)}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData('application/json', JSON.stringify({
                        type: 'entity',
                        data: corr,
                        module: 'correlation'
                      }))
                    }}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex flex-col gap-1 w-full relative">
                        {/* Source Entity */}
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="text-[10px] px-1 h-4 min-w-12 justify-center">
                            {corr.primary_type}
                          </Badge>
                          <span className="font-geist text-xs font-medium truncate max-w-[160px]">
                            {corr.primary_entity}
                          </span>
                        </div>

                        {/* Link Icon */}
                        <div className="flex items-center pl-4 my-1 opacity-50">
                          <div className="w-1 h-3 border-l tracking-widest border-fuchsia-400" />
                          <GitMerge className="h-3 w-3 text-fuchsia-500 ml-1" />
                          <span className="text-[9px] font-geist-mono uppercase tracking-wider ml-1 text-fuchsia-600 dark:text-fuchsia-400">
                            {corr.relationship_type}
                          </span>
                        </div>

                        {/* Target Entity */}
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="text-[10px] px-1 h-4 min-w-12 justify-center">
                            {corr.related_type}
                          </Badge>
                          <span className="font-geist text-xs font-medium truncate max-w-[160px]">
                            {corr.related_entity}
                          </span>
                        </div>
                      </div>

                      <div className="absolute top-2 right-2 flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(event) => {
                            event.stopPropagation()
                            onInsertEntity?.(corr)
                          }}
                        >
                          <Plus className="h-3 w-3 text-fuchsia-500" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(event) => {
                            event.stopPropagation()
                            handleDrillToEvidence(corr)
                          }}
                        >
                          <Link2 className="h-3 w-3 text-fuchsia-500" />
                        </Button>
                      </div>
                    </div>

                    <div className="flex items-center justify-between mt-1 pt-2 border-t border-fuchsia-100 dark:border-fuchsia-900/30">
                      <span className="font-geist-mono text-[10px] text-muted-foreground">
                        Confidence
                      </span>
                      <div className="flex items-center gap-1">
                        <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-fuchsia-500"
                            style={{ width: `${corr.confidence_score * 100}%` }}
                          />
                        </div>
                        <span className="font-geist-mono text-[10px] text-fuchsia-600 dark:text-fuchsia-400">
                          {Math.round(corr.confidence_score * 100)}%
                        </span>
                      </div>
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
