'use client'

import React, { useEffect, useState, useCallback, useMemo } from 'react'
import {
  Archive,
  FileText,
  Hash,
  Activity,
  ShieldCheck,
  Search,
  Plus,
  FileCheck,
  TerminalSquare,
  RefreshCw,
  Link2,
  Link2Off,
  Eye,
  AlertTriangle,
} from 'lucide-react'
import NextImage from 'next/image'
import { api } from '@operation-room/lib/api'
import {
  PanelHeader,
  PanelContent,
  PanelLoading,
  PanelEmptyState,
  ComponentCard,
  FindingCard,
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

// Vault Components Constants
const VAULT_COMPONENTS = [
  {
    id: 'vault-chain-of-custody',
    name: 'Chain of Custody Log',
    description: 'Insert full cryptographic evidence log table',
    icon: ShieldCheck,
    type: 'coc-table' as const,
    preview: '/api/placeholder/vault-coc.svg',
  },
  {
    id: 'vault-evidence-summary',
    name: 'Evidence Manifest summary',
    description: 'List of all hashed artefacts in this case',
    icon: Archive,
    type: 'evidence-manifest' as const,
    preview: '/api/placeholder/vault-manifest.svg',
  },
  {
    id: 'vault-hash-verification',
    name: 'Hash Verification Block',
    description: 'Visual indicator of cryptographic integrity',
    icon: Hash,
    type: 'hash-block' as const,
    preview: '/api/placeholder/vault-hash.svg',
  },
]

interface EvidenceItem {
  hash_id: string
  artefact_name: string
  artefact_type: string
  hash_algorithm: string
  hash_value: string
  record_count: number
  byte_size: number
  created_at: string
}

interface VaultPanelProps {
  caseId: string
  onInsertComponent?: (componentId: string, config?: Record<string, unknown>) => void
  onInsertEvidence?: (evidence: EvidenceItem) => void
}

export const VaultPanel = ({
  caseId,
  onInsertComponent,
  onInsertEvidence,
}: VaultPanelProps) => {
  const setPanelBadge = useStudioStore((s) => s.setPanelBadge)
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Where-used tracking: scan the editor for evidence block references
  const [usageMap, setUsageMap] = useState<Record<string, string[]>>({})

  const loadData = useCallback(async () => {
    if (!caseId) return
    try {
      setLoading(true)
      const data = await api.getEvidenceCards(caseId).catch(() => [])
      if (Array.isArray(data)) {
        const mapped = data.map((d: any) => ({
          hash_id: d.id,
          artefact_name: d.title,
          artefact_type: 'evidence-card',
          hash_algorithm: 'SHA-256',
          hash_value: d.hash || 'unknown',
          record_count: d.evidence_ref?.pointers?.length || 0,
          byte_size: 0,
          created_at: new Date().toISOString(), // Fallback
          raw_card: d
        }))
        setEvidenceList(mapped)
        setPanelBadge('vault', mapped.length)
      }
    } catch (err) {
      console.error('Failed to load vault data:', err)
      setError('Failed to load vault data')
    } finally {
      setLoading(false)
    }
  }, [caseId, setPanelBadge])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Scan document AST for evidence block references to vault items
  const scanWhereUsed = useCallback(async () => {
    if (!caseId) return
    try {
      // Fetch the current document to scan its AST
      const docsResponse = await api.get(`/v4/studio/cases/${caseId}/docs`).catch(() => [])
      const docs = Array.isArray(docsResponse) ? docsResponse : docsResponse?.documents || []
      if (!docs.length) return

      const doc = await api.get(`/v4/studio/cases/${caseId}/docs/${docs[0].doc_id}`).catch(() => null)
      if (!doc?.ast) return

      const usage: Record<string, string[]> = {}
      
      // Walk the AST looking for evidenceBlock nodes
      const walk = (node: any, path: string) => {
        if (!node || typeof node !== 'object') return
        if (node.type === 'evidenceBlock') {
          const source = node.attrs?.source || 'unknown'
          const title = node.attrs?.title || 'Untitled'
          const blockId = node.attrs?.id || 'unknown'
          
          // Match by source hash or module name
          if (source === 'vault' || source === 'case') {
            const dataHash = node.attrs?.metadata?.hash || ''
            if (!usage[dataHash]) usage[dataHash] = []
            usage[dataHash].push(title)
          }
          // Track all evidence blocks by citation
          const citationId = node.attrs?.metadata?.citationId
          if (citationId) {
            if (!usage[citationId]) usage[citationId] = []
            usage[citationId].push(`${title} (${path})`)
          }
        }
        if (Array.isArray(node.content)) {
          node.content.forEach((child: any, i: number) => walk(child, `${path}/${i}`))
        }
      }
      walk(doc.ast, 'root')
      setUsageMap(usage)
    } catch (err) {
      console.warn('Where-used scan failed:', err)
    }
  }, [caseId])

  useEffect(() => {
    scanWhereUsed()
  }, [scanWhereUsed])

  // Compute orphan count
  const orphanCount = useMemo(() => {
    if (!evidenceList.length) return 0
    return evidenceList.filter(item => {
      const hashKey = `sha256:${item.hash_value.substring(0, 12)}`
      return !Object.keys(usageMap).some(k => k.includes(item.hash_value.substring(0, 8)))
    }).length
  }, [evidenceList, usageMap])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <PanelHeader
        title="Evidence Vault"
        panelId="vault"
        icon={<Archive className="h-4 w-4" />}
        showSearch={false}
        actions={
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => { loadData(); scanWhereUsed() }}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        }
      />
      <PanelContent>
        <Tabs defaultValue="evidence" className="w-full">
          <TabsList className="w-full grid grid-cols-3 mb-4">
            <TabsTrigger value="evidence">Evidence</TabsTrigger>
            <TabsTrigger value="usage">
              Usage
              {orphanCount > 0 && (
                <Badge variant="destructive" className="ml-1 h-4 px-1 text-[9px]">{orphanCount}</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="components">Blocks</TabsTrigger>
          </TabsList>

          <TabsContent value="components" className="space-y-4 outline-none">
            <h3 className="font-geist text-sm font-semibold mb-3">Evidence Blocks</h3>
            <div className="grid grid-cols-1 gap-2">
              {VAULT_COMPONENTS.map((comp) => (
                <ComponentCard
                  key={comp.id}
                  name={comp.name}
                  description={comp.description}
                  icon={<comp.icon strokeWidth={1.5} />}
                  preview={<NextImage src={comp.preview} alt={comp.name} width={320} height={180} unoptimized className="w-full h-full object-cover opacity-50" />}
                  onClick={() => onInsertComponent?.(comp.id)}
                  onDragStart={(e: React.DragEvent) => {
                    e.dataTransfer.setData('application/json', JSON.stringify({
                      type: 'component',
                      componentId: comp.id,
                      module: 'vault'
                    }))
                  }}
                />
              ))}
            </div>
          </TabsContent>

          <TabsContent value="evidence" className="space-y-4 outline-none">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-geist text-sm font-semibold">Verified Artefacts</h3>
              <Badge variant="outline" className="font-geist-mono">
                {evidenceList.length} Items
              </Badge>
            </div>

            {loading ? (
              <PanelLoading message="Loading evidence vault..." />
            ) : error ? (
              <PanelEmptyState
                icon={<Archive className="h-6 w-6" />}
                title="Vault Error"
                description={error}
                action={(
                  <Button variant="outline" size="sm" onClick={loadData}>
                    Retry
                  </Button>
                )}
              />
            ) : evidenceList.length === 0 ? (
              <PanelEmptyState
                icon={<Archive className="h-6 w-6" />}
                title="Empty Vault"
                description="No hashed evidence found in this case vault."
              />
            ) : (
              <div className="space-y-2">
                {evidenceList.map((item) => (
                  <div
                    key={item.hash_id}
                    className="group flex flex-col gap-2 p-3 rounded-md border bg-card hover:bg-accent/5 transition-colors cursor-pointer"
                    onClick={() => onInsertEvidence?.(item)}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData('application/json', JSON.stringify({
                        type: 'evidence',
                        data: item,
                        module: 'vault'
                      }))
                    }}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <FileCheck className="h-4 w-4 text-emerald-500" />
                        <span className="font-geist text-sm font-medium leading-none">
                          {item.artefact_name}
                        </span>
                      </div>
                      <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity">
                        <Plus className="h-3 w-3" />
                      </Button>
                    </div>
                    
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant="secondary" className="text-[10px] px-1.5 h-4">
                        {item.artefact_type}
                      </Badge>
                      <span className="font-geist-mono text-[10px] text-muted-foreground truncate w-32">
                        {item.hash_algorithm}: {item.hash_value.substring(0, 8)}...
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Where-Used Tab */}
          <TabsContent value="usage" className="space-y-4 outline-none">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-geist text-sm font-semibold">Evidence Usage</h3>
              <Button variant="ghost" size="sm" className="h-6 text-xs gap-1" onClick={scanWhereUsed}>
                <RefreshCw className="h-3 w-3" />
                Scan
              </Button>
            </div>

            {Object.keys(usageMap).length === 0 ? (
              <PanelEmptyState
                icon={<Link2Off className="h-6 w-6" />}
                title="No References Found"
                description="No evidence blocks are referenced in the current report. Insert evidence from the Evidence tab."
              />
            ) : (
              <div className="space-y-2">
                {/* Referenced items */}
                {Object.entries(usageMap).map(([key, refs]) => (
                  <div key={key} className="p-2.5 rounded-lg border bg-emerald-50/30 dark:bg-emerald-950/10">
                    <div className="flex items-center gap-2 mb-1">
                      <Link2 className="h-3.5 w-3.5 text-emerald-600" />
                      <span className="font-geist-mono text-[10px] text-muted-foreground truncate">{key}</span>
                    </div>
                    <div className="space-y-0.5">
                      {refs.map((ref, i) => (
                        <div key={i} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                          <Eye className="h-3 w-3 text-emerald-500" />
                          <span className="truncate">{ref}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

                {/* Orphan detection */}
                {orphanCount > 0 && (
                  <div className="border-t pt-3 mt-3">
                    <FindingCard
                      title={`${orphanCount} Unused Evidence Items`}
                      description="These vault items are not referenced in the current report"
                      severity="medium"
                      module="case"
                      metric={orphanCount.toString()}
                    />
                  </div>
                )}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </PanelContent>
    </div>
  )
}
