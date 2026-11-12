'use client'

import React, { useState, useEffect } from 'react'
import { Database, ArrowUpDown, Edit3, PlusCircle, Trash2, Eye, RefreshCw } from 'lucide-react'
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

interface CRUDPanelProps {
  caseId: string
  onInsertBlock?: (block: any) => void
}

const CRUD_ICONS: Record<string, React.ReactNode> = {
  create: <PlusCircle className="h-3.5 w-3.5 text-emerald-500" />,
  read: <Eye className="h-3.5 w-3.5 text-blue-500" />,
  update: <Edit3 className="h-3.5 w-3.5 text-amber-500" />,
  delete: <Trash2 className="h-3.5 w-3.5 text-red-500" />,
}

export const CRUDPanel = ({ caseId, onInsertBlock }: CRUDPanelProps) => {
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [summary, setSummary] = useState<any>(null)
  const [findings, setFindings] = useState<any[]>([])
  const setPanelBadge = useStudioStore((s) => s.setPanelBadge)

  const loadData = React.useCallback(async () => {
    try {
      setLoading(true)
      const [summaryRes, findingsRes] = await Promise.allSettled([
        api.get(`/api/cases/${caseId}/crud/summary`),
        api.get(`/api/cases/${caseId}/crud/findings`),
      ])
      if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value)
      if (findingsRes.status === 'fulfilled') {
        const found = findingsRes.value?.findings || []
        setFindings(found)
        setPanelBadge('crud', found.length)
      } else {
        setPanelBadge('crud', 0)
      }
    } catch (err) {
      console.warn('[CRUDPanel] Failed to load:', err)
    } finally {
      setLoading(false)
    }
  }, [caseId, setPanelBadge])

  useEffect(() => {
    loadData()
  }, [loadData])

  if (loading) return <PanelLoading message="Loading CRUD analysis..." />

  const metrics = [
    { label: 'Create', value: summary?.create_count || 0, icon: CRUD_ICONS.create },
    { label: 'Read', value: summary?.read_count || 0, icon: CRUD_ICONS.read },
    { label: 'Update', value: summary?.update_count || 0, icon: CRUD_ICONS.update },
    { label: 'Delete', value: summary?.delete_count || 0, icon: CRUD_ICONS.delete },
  ]

  const filteredFindings = search
    ? findings.filter((f: any) => JSON.stringify(f).toLowerCase().includes(search.toLowerCase()))
    : findings

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PanelHeader
        title="CRUD Analysis"
        panelId="crud"
        icon={<Database className="h-4 w-4" />}
        showSearch={true}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search operations..."
        actions={
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={loadData}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        }
      />
      <PanelContent>
        {/* Summary metrics */}
        <PanelSection title="Operations Summary" icon={<ArrowUpDown className="h-3.5 w-3.5" />}>
          <div className="grid grid-cols-2 gap-2">
            {metrics.map(m => (
              <MetricCard
                key={m.label}
                label={m.label}
                value={m.value}
                module="crud"
                icon={m.icon}
                onClick={() => onInsertBlock?.({
                  type: 'evidenceBlock',
                  attrs: {
                    type: 'metric',
                    source: 'crud',
                    title: `${m.label} Operations`,
                    data: { value: m.value, label: m.label },
                  }
                })}
              />
            ))}
          </div>
        </PanelSection>

        {/* Key findings */}
        <PanelSection title="Key Findings" icon={<Database className="h-3.5 w-3.5" />}>
          {filteredFindings.length === 0 ? (
            <PanelEmptyState
              icon={<Database className="h-8 w-8" />}
              title="No CRUD findings"
              description="Run CRUD analysis to populate findings"
            />
          ) : (
            <div className="space-y-2">
              {filteredFindings.slice(0, 10).map((finding: any, i: number) => (
                <FindingCard
                  key={i}
                  title={finding.title || finding.description?.slice(0, 50)}
                  description={finding.description}
                  severity={finding.severity || 'info'}
                  module="crud"
                  onInsert={() => onInsertBlock?.({
                    type: 'evidenceBlock',
                    attrs: {
                      type: 'finding',
                      source: 'crud',
                      title: finding.title || 'CRUD Finding',
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
