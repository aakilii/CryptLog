'use client'

import React, { useState, useEffect } from 'react'
import { Flame, Shield, Server, Lock, Users, RefreshCw } from 'lucide-react'
import {
  PanelHeader,
  PanelContent,
  PanelSection,
  PanelEmptyState,
  PanelLoading,
  MetricCard,
  FindingCard,
} from '../ExpandablePanel'
import { api } from '@operation-room/lib/api'
import { useStudioStore } from '../store/useStudioStore'
import { Button } from '@operation-room/components/ui/button'

interface DepthPanelProps {
  caseId: string
  onInsertBlock?: (block: any) => void
}

const DIMENSION_ICONS: Record<string, React.ReactNode> = {
  account: <Users className="h-3.5 w-3.5 text-red-500" />,
  system: <Server className="h-3.5 w-3.5 text-orange-500" />,
  data: <Shield className="h-3.5 w-3.5 text-amber-500" />,
  control: <Lock className="h-3.5 w-3.5 text-rose-600" />,
}

export const DepthPanel = ({ caseId, onInsertBlock }: DepthPanelProps) => {
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [depthData, setDepthData] = useState<any>(null)
  const [findings, setFindings] = useState<any[]>([])
  const setPanelBadge = useStudioStore((s) => s.setPanelBadge)

  const loadData = React.useCallback(async () => {
    try {
      setLoading(true)
      const [depthRes, findingsRes] = await Promise.allSettled([
        api.get(`/api/cases/${caseId}/depth`),
        api.get(`/api/cases/${caseId}/depth/findings`),
      ])
      if (depthRes.status === 'fulfilled') setDepthData(depthRes.value)
      if (findingsRes.status === 'fulfilled') {
        const found = findingsRes.value?.findings || []
        setFindings(found)
        setPanelBadge('depth', found.length)
      } else {
        setPanelBadge('depth', 0)
      }
    } catch (err) {
      console.warn('[DepthPanel] Failed to load:', err)
    } finally {
      setLoading(false)
    }
  }, [caseId, setPanelBadge])

  useEffect(() => {
    loadData()
  }, [loadData])

  if (loading) return <PanelLoading message="Loading depth assessment..." />

  const overallScore = depthData?.overall_score ?? depthData?.depth_score ?? 0
  const dimensions = [
    { key: 'account', label: 'Account', score: depthData?.account_score ?? 0 },
    { key: 'system', label: 'System', score: depthData?.system_score ?? 0 },
    { key: 'data', label: 'Data', score: depthData?.data_score ?? 0 },
    { key: 'control', label: 'Control', score: depthData?.control_score ?? 0 },
  ]

  const filteredFindings = search
    ? findings.filter((f: any) => JSON.stringify(f).toLowerCase().includes(search.toLowerCase()))
    : findings

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PanelHeader
        title="Depth & Impact"
        panelId="depth"
        icon={<Flame className="h-4 w-4" />}
        showSearch={true}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search dimensions..."
        actions={
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={loadData}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        }
      />
      <PanelContent>
        {/* Overall score */}
        <PanelSection title="Overall Depth Score" icon={<Flame className="h-3.5 w-3.5" />}>
          <MetricCard
            label="Penetration Depth"
            value={typeof overallScore === 'number' ? `${(overallScore * 100).toFixed(0)}%` : '—'}
            module="depth"
            icon={<Flame className="h-4 w-4" />}
            trend={overallScore > 0.7 ? 'up' : overallScore > 0.3 ? 'neutral' : 'down'}
            onClick={() => onInsertBlock?.({
              type: 'evidenceBlock',
              attrs: {
                type: 'metric',
                source: 'depth',
                title: 'Overall Depth Score',
                data: { value: overallScore, label: 'Penetration Depth' },
              }
            })}
          />
        </PanelSection>

        {/* Dimension scores */}
        <PanelSection title="Dimension Scores" icon={<Shield className="h-3.5 w-3.5" />}>
          <div className="grid grid-cols-2 gap-2">
            {dimensions.map(dim => (
              <MetricCard
                key={dim.key}
                label={dim.label}
                value={typeof dim.score === 'number' ? `${(dim.score * 100).toFixed(0)}%` : '—'}
                module="depth"
                icon={DIMENSION_ICONS[dim.key]}
                onClick={() => onInsertBlock?.({
                  type: 'evidenceBlock',
                  attrs: {
                    type: 'metric',
                    source: 'depth',
                    title: `${dim.label} Depth`,
                    data: { value: dim.score, dimension: dim.key },
                  }
                })}
              />
            ))}
          </div>
        </PanelSection>

        {/* Key findings */}
        <PanelSection title="Impact Findings" icon={<Flame className="h-3.5 w-3.5" />}>
          {filteredFindings.length === 0 ? (
            <PanelEmptyState
              icon={<Flame className="h-8 w-8" />}
              title="No depth findings"
              description="Run depth assessment to populate findings"
            />
          ) : (
            <div className="space-y-2">
              {filteredFindings.slice(0, 10).map((finding: any, i: number) => (
                <FindingCard
                  key={i}
                  title={finding.title || finding.description?.slice(0, 50)}
                  description={finding.description}
                  severity={finding.severity || 'high'}
                  module="depth"
                  onInsert={() => onInsertBlock?.({
                    type: 'evidenceBlock',
                    attrs: {
                      type: 'finding',
                      source: 'depth',
                      title: finding.title || 'Depth Finding',
                      data: finding,
                    }
                  })}
                />
              ))}
            </div>
          )}
        </PanelSection>
      </PanelContent>
    </div>
  )
}
