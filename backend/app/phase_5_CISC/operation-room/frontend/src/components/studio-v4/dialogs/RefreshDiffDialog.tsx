'use client'

import React, { useState, useCallback } from 'react'
import {
  RefreshCw, Check, X, ArrowRight, Clock, Loader2,
  ChevronUp, ChevronDown, Equal,
} from 'lucide-react'
import { cn } from '@operation-room/lib/utils'
import { Button } from '@operation-room/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@operation-room/components/ui/dialog'
import { Badge } from '@operation-room/components/ui/badge'
import { ScrollArea } from '@operation-room/components/ui/scroll-area'
import { api } from '@operation-room/lib/api'

// ── Types ───────────────────────────────────────────────────────────────
interface DataDiff {
  field: string
  oldValue: any
  newValue: any
  changeType: 'added' | 'removed' | 'modified' | 'unchanged'
}

interface RefreshDiffDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  caseId: string
  blockId: string
  blockTitle: string
  blockSource: string
  currentData: any
  onAccept: (newData: any) => void
}

// ── Diff Computation ────────────────────────────────────────────────────
function computeDiff(oldData: any, newData: any, prefix = ''): DataDiff[] {
  const diffs: DataDiff[] = []
  
  if (oldData === null || oldData === undefined) return [{ field: prefix || 'data', oldValue: null, newValue: newData, changeType: 'added' }]
  if (newData === null || newData === undefined) return [{ field: prefix || 'data', oldValue: oldData, newValue: null, changeType: 'removed' }]
  
  if (typeof oldData !== 'object' || typeof newData !== 'object') {
    if (oldData !== newData) {
      return [{ field: prefix || 'value', oldValue: oldData, newValue: newData, changeType: 'modified' }]
    }
    return [{ field: prefix || 'value', oldValue: oldData, newValue: newData, changeType: 'unchanged' }]
  }
  
  const allKeys = Array.from(new Set(Object.keys(oldData).concat(Object.keys(newData))))
  for (const key of allKeys) {
    const fieldPath = prefix ? `${prefix}.${key}` : key
    if (!(key in oldData)) {
      diffs.push({ field: fieldPath, oldValue: undefined, newValue: newData[key], changeType: 'added' })
    } else if (!(key in newData)) {
      diffs.push({ field: fieldPath, oldValue: oldData[key], newValue: undefined, changeType: 'removed' })
    } else if (JSON.stringify(oldData[key]) !== JSON.stringify(newData[key])) {
      if (typeof oldData[key] === 'object' && typeof newData[key] === 'object') {
        diffs.push(...computeDiff(oldData[key], newData[key], fieldPath))
      } else {
        diffs.push({ field: fieldPath, oldValue: oldData[key], newValue: newData[key], changeType: 'modified' })
      }
    }
  }
  
  return diffs
}

const CHANGE_ICONS = {
  added: <ChevronUp className="h-3 w-3 text-emerald-500" />,
  removed: <ChevronDown className="h-3 w-3 text-red-500" />,
  modified: <ArrowRight className="h-3 w-3 text-amber-500" />,
  unchanged: <Equal className="h-3 w-3 text-muted-foreground" />,
}

const CHANGE_COLORS = {
  added: 'bg-emerald-50 border-emerald-200 dark:bg-emerald-950/20',
  removed: 'bg-red-50 border-red-200 dark:bg-red-950/20',
  modified: 'bg-amber-50 border-amber-200 dark:bg-amber-950/20',
  unchanged: 'bg-muted/30 border-muted',
}

function formatValue(val: any): string {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'object') return JSON.stringify(val, null, 2).slice(0, 100)
  if (typeof val === 'number') return val.toLocaleString()
  return String(val).slice(0, 100)
}

// ── Dialog Component ────────────────────────────────────────────────────
export const RefreshDiffDialog = ({
  open,
  onOpenChange,
  caseId,
  blockId,
  blockTitle,
  blockSource,
  currentData,
  onAccept,
}: RefreshDiffDialogProps) => {
  const [loading, setLoading] = useState(false)
  const [newData, setNewData] = useState<any>(null)
  const [diffs, setDiffs] = useState<DataDiff[]>([])
  const [fetchedAt, setFetchedAt] = useState<string | null>(null)

  // Fetch fresh data from the source endpoint
  const fetchFreshData = useCallback(async () => {
    if (!caseId) {
      alert('Refresh failed: Missing case context for source refresh.')
      return
    }

    setLoading(true)
    try {
      // Map source module to its data endpoint
      const endpointMap: Record<string, string> = {
        timeline: `/cases/${caseId}/timeline/stats`,
        anomaly: `/cases/${caseId}/anomalies/summary`,
        correlation: `/cases/${caseId}/correlation/graph`,
        network: `/cases/${caseId}/network/summary`,
        crud: `/cases/${caseId}/crud/summary`,
        depth: `/cases/${caseId}/depth`,
      }

      const endpoint = endpointMap[blockSource] || `/cases/${caseId}/${blockSource}/summary`
      const freshData = await api.get(endpoint)
      
      setNewData(freshData)
      setFetchedAt(new Date().toISOString())
      
      // Compute diff
      const computed = computeDiff(currentData, freshData)
      setDiffs(computed)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to fetch latest source data.'
      alert(`Refresh failed: ${message}`)
    } finally {
      setLoading(false)
    }
  }, [caseId, blockSource, currentData])

  // Auto-fetch when dialog opens
  React.useEffect(() => {
    if (open && !newData) fetchFreshData()
    if (!open) { setNewData(null); setDiffs([]) }
  }, [open, fetchFreshData, newData])

  const changedDiffs = diffs.filter(d => d.changeType !== 'unchanged')
  const hasChanges = changedDiffs.length > 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RefreshCw className="h-5 w-5 text-sky-500" />
            Refresh from Source
          </DialogTitle>
          <DialogDescription>
            Compare current evidence data with latest source data for "{blockTitle}"
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Fetching latest data from {blockSource}...</span>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Summary */}
            <div className={cn(
              "flex items-center gap-3 p-3 rounded-lg border",
              hasChanges
                ? "bg-amber-50 border-amber-200 dark:bg-amber-950/20"
                : "bg-emerald-50 border-emerald-200 dark:bg-emerald-950/20"
            )}>
              {hasChanges
                ? <ArrowRight className="h-5 w-5 text-amber-500" />
                : <Check className="h-5 w-5 text-emerald-500" />
              }
              <div>
                <p className="text-sm font-medium">
                  {hasChanges
                    ? `${changedDiffs.length} field${changedDiffs.length > 1 ? 's' : ''} changed`
                    : 'Data is up to date — no changes detected'}
                </p>
                {fetchedAt && (
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    Checked at {new Date(fetchedAt).toLocaleTimeString()}
                  </p>
                )}
              </div>
            </div>

            {/* Diff list */}
            {changedDiffs.length > 0 && (
              <ScrollArea className="max-h-60">
                <div className="space-y-1.5">
                  {changedDiffs.map((diff, i) => (
                    <div key={i} className={cn("p-2 rounded-md border text-xs", CHANGE_COLORS[diff.changeType])}>
                      <div className="flex items-center gap-2 mb-1">
                        {CHANGE_ICONS[diff.changeType]}
                        <span className="font-geist-mono font-medium">{diff.field}</span>
                        <Badge variant="outline" className="text-[9px] ml-auto">{diff.changeType}</Badge>
                      </div>
                      <div className="flex items-center gap-2 pl-5">
                        <span className="text-muted-foreground line-through">{formatValue(diff.oldValue)}</span>
                        <ArrowRight className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                        <span className="font-medium">{formatValue(diff.newValue)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Keep Current
          </Button>
          <Button
            disabled={loading || !hasChanges}
            onClick={() => { onAccept(newData); onOpenChange(false) }}
            className="gap-1.5 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-700 hover:to-indigo-700"
          >
            <Check className="h-4 w-4" />
            Accept Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
