'use client'

import React, { useState, useCallback } from 'react'
import {
  AlertTriangle, Shield, CheckCircle2, XCircle,
  FileDown, FileText, File, Loader2,
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
import { Input } from '@operation-room/components/ui/input'
import { Label } from '@operation-room/components/ui/label'
import { Badge } from '@operation-room/components/ui/badge'
import { ScrollArea } from '@operation-room/components/ui/scroll-area'
import { api } from '@operation-room/lib/api'

// ── Types ───────────────────────────────────────────────────────────────
interface Violation {
  type: string
  blockId: string
  title: string
  source: string
  severity: string
  message: string
}

interface PreCheckResult {
  blocked: boolean
  total_evidence_blocks: number
  cited_evidence_blocks: number
  violations: Violation[]
  warnings: Violation[]
  doc_id: string
  content_hash: string
  title: string
}

interface ExportGateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  caseId: string
  docId: string
  onExportComplete?: (result: any) => void
  onScrollToBlock?: (blockId: string) => void
}

const EXPORT_FORMATS = [
  { id: 'pdf', label: 'PDF', icon: FileDown, desc: 'Court-ready document' },
  { id: 'docx', label: 'DOCX', icon: FileText, desc: 'Editable Word document' },
  { id: 'html', label: 'HTML', icon: File, desc: 'Web-viewable report' },
]

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-amber-500',
  low: 'bg-blue-500',
  info: 'bg-slate-400',
}

export const ExportGateDialog = ({
  open,
  onOpenChange,
  caseId,
  docId,
  onExportComplete,
  onScrollToBlock,
}: ExportGateDialogProps) => {
  const [checking, setChecking] = useState(false)
  const [checkResult, setCheckResult] = useState<PreCheckResult | null>(null)
  const [format, setFormat] = useState<string>('pdf')
  const [engine, setEngine] = useState<'current' | 'dynamite'>('current')
  const [exporting, setExporting] = useState(false)
  const [overrideReason, setOverrideReason] = useState('')
  const [showOverride, setShowOverride] = useState(false)
  const [coverId, setCoverId] = useState<string>('1')
  const [loadingPhase, setLoadingPhase] = useState<number>(-1)
  const [exportError, setExportError] = useState<string>('')

  const LOADING_PHASES = [
    "ESTABLISHING SECURE UPLINK...",
    "PARSING JSON PAYLOAD...",
    "INJECTING HEX OFFSETS...",
    "COMPILING 30-PAGE DOSSIER...",
    "FINALIZING GHOSTWRITER ENGINE..."
  ]

  // Run citation pre-check
  const runPreCheck = useCallback(async () => {
    setChecking(true)
    try {
      const result = await api.post(`/v4/studio/cases/${caseId}/exports/precheck`, {
        doc_id: docId,
      })
      setCheckResult(result)
    } catch (err) {
      console.error('[ExportGate] Pre-check failed:', err)
      // If pre-check fails, allow export with warning
      setCheckResult({
        blocked: false,
        total_evidence_blocks: 0,
        cited_evidence_blocks: 0,
        violations: [],
        warnings: [{ type: 'precheck_failed', blockId: '', title: 'Citation check unavailable', source: 'System', severity: 'info', message: 'Proceed with caution' }],
        doc_id: docId,
        content_hash: '',
        title: '',
      })
    } finally {
      setChecking(false)
    }
  }, [caseId, docId])

  // Trigger pre-check when dialog opens
  React.useEffect(() => {
    if (open && !checkResult) runPreCheck()
    if (!open) { setCheckResult(null); setShowOverride(false); setOverrideReason('') }
  }, [open, runPreCheck, checkResult])

  // Execute export
  const handleExport = useCallback(async () => {
    setExporting(true)
    setExportError('')
    
    // Trigger 5-phase ghostwriter animation
    for (let i = 0; i < LOADING_PHASES.length; i++) {
        setLoadingPhase(i);
        await new Promise(resolve => setTimeout(resolve, 1200));
    }

    try {
      const result = await api.post(`/v4/studio/cases/${caseId}/exports/${format}`, {
        doc_id: docId,
        actor: 'investigator',
        override_reason: overrideReason || undefined,
        frontend_url: window.location.origin,
        cover_id: format === 'pdf' ? `template_${coverId}` : undefined,
        engine: format === 'pdf' ? engine : 'current',
      })
      onExportComplete?.(result)
      onOpenChange(false)
    } catch (err: any) {
      console.error('[ExportGate] Export failed:', err)
      setExportError(err.message || 'Export failed')
    } finally {
      setExporting(false)
      setLoadingPhase(-1)
    }
  }, [caseId, docId, format, overrideReason, coverId, onExportComplete, onOpenChange])

  const isBlocked = checkResult?.blocked && !overrideReason.trim()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-sky-500" />
            Export Report
          </DialogTitle>
          <DialogDescription>
            Citation integrity check and export format selection
          </DialogDescription>
        </DialogHeader>

        {/* Pre-check status */}
        <div className="space-y-4">
          {checking ? (
            <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">Running citation integrity check...</span>
            </div>
          ) : checkResult ? (
            <>
              {/* Summary */}
              <div className={cn(
                "flex items-center gap-3 p-3 rounded-lg border",
                checkResult.blocked
                  ? "bg-red-50 border-red-200 dark:bg-red-950/20 dark:border-red-800"
                  : "bg-emerald-50 border-emerald-200 dark:bg-emerald-950/20 dark:border-emerald-800"
              )}>
                {checkResult.blocked
                  ? <XCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
                  : <CheckCircle2 className="h-5 w-5 text-emerald-500 flex-shrink-0" />
                }
                <div>
                  <p className="text-sm font-medium">
                    {checkResult.blocked
                      ? 'Export blocked — uncited critical evidence found'
                      : 'Citation check passed'}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {checkResult.cited_evidence_blocks}/{checkResult.total_evidence_blocks} evidence blocks cited
                  </p>
                </div>
              </div>

              {/* Violations list */}
              {checkResult.violations.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-xs font-semibold uppercase tracking-wider text-red-600">
                    Blocking Violations ({checkResult.violations.length})
                  </Label>
                  <ScrollArea className="max-h-40">
                    <div className="space-y-1.5">
                      {checkResult.violations.map((v, i) => (
                        <button
                          key={i}
                          className="w-full flex items-start gap-2 p-2 rounded-md border border-red-100 bg-red-50/50 hover:bg-red-50 text-left transition-colors dark:bg-red-950/10 dark:border-red-900"
                          onClick={() => { onScrollToBlock?.(v.blockId); onOpenChange(false) }}
                        >
                          <div className={cn("w-2 h-2 rounded-full mt-1.5 flex-shrink-0", SEVERITY_COLORS[v.severity])} />
                          <div>
                            <p className="text-xs font-medium">{v.title}</p>
                            <p className="text-[10px] text-muted-foreground">{v.message}</p>
                          </div>
                          <Badge variant="outline" className="text-[9px] ml-auto flex-shrink-0">{v.source}</Badge>
                        </button>
                      ))}
                    </div>
                  </ScrollArea>
                </div>
              )}

              {/* Warnings */}
              {checkResult.warnings.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-xs font-semibold uppercase tracking-wider text-amber-600">
                    Warnings ({checkResult.warnings.length})
                  </Label>
                  <ScrollArea className="max-h-28">
                    <div className="space-y-1">
                      {checkResult.warnings.map((w, i) => (
                        <div key={i} className="flex items-center gap-2 px-2 py-1 text-xs text-muted-foreground">
                          <AlertTriangle className="h-3 w-3 text-amber-500 flex-shrink-0" />
                          <span className="truncate">{w.title}</span>
                          <Badge variant="outline" className="text-[9px] ml-auto flex-shrink-0">{w.source}</Badge>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </div>
              )}

              {/* Override option */}
              {checkResult.blocked && (
                <div className="space-y-2 border-t pt-3">
                  {!showOverride ? (
                    <Button variant="ghost" size="sm" className="text-xs text-red-600 hover:text-red-700" onClick={() => setShowOverride(true)}>
                      Override export block (non-standard)
                    </Button>
                  ) : (
                    <div className="space-y-2">
                      <Label className="text-xs">Justification for override (required):</Label>
                      <Input
                        value={overrideReason}
                        onChange={(e) => setOverrideReason(e.target.value)}
                        placeholder="e.g. Draft for internal review only"
                        className="h-8 text-xs"
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Cover Template Selection (PDF Only) */}
              {format === 'pdf' && (
                <div className="space-y-2 border-t pt-3">
                  <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Phantom Cover Engine
                  </Label>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { id: '1', name: 'Executive White', bg: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)', text: 'text-slate-800' },
                      { id: '2', name: 'Cyber Indigo', bg: 'linear-gradient(135deg, #0f172a 0%, #312e81 100%)', text: 'text-white' },
                      { id: '3', name: 'Midnight Flare', bg: 'linear-gradient(135deg, #09090b 0%, #4c0519 100%)', text: 'text-rose-100' },
                    ].map(cov => (
                      <button
                        key={cov.id}
                        className={cn(
                          "relative overflow-hidden rounded-md border-2 transition-all p-1 h-24 flex flex-col items-center justify-center",
                          coverId === cov.id
                            ? "border-sky-500 shadow-[0_0_15px_rgba(14,165,233,0.3)] scale-105 z-10"
                            : "border-transparent hover:border-slate-500/30 grayscale hover:grayscale-0 opacity-70 hover:opacity-100"
                        )}
                        style={{ background: cov.bg }}
                        onClick={() => setCoverId(cov.id)}
                      >
                         <Shield className={cn("h-6 w-6 mb-2 opacity-50", cov.text)} />
                         <div className={cn("text-[10px] font-bold tracking-widest uppercase", cov.text)}>
                           {cov.name}
                         </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Format selection */}
              <div className="space-y-2 border-t pt-3">
                <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Export Format
                </Label>
                <div className="grid grid-cols-3 gap-2">
                  {EXPORT_FORMATS.map(f => (
                    <button
                      key={f.id}
                      className={cn(
                        "flex flex-col items-center gap-1.5 p-3 rounded-lg border transition-all",
                        format === f.id
                          ? "border-sky-400 bg-sky-50 dark:bg-sky-950/30"
                          : "border-slate-200 hover:border-slate-300 dark:border-slate-800"
                      )}
                      onClick={() => setFormat(f.id)}
                    >
                      <f.icon className={cn("h-5 w-5", format === f.id ? "text-sky-500" : "text-muted-foreground")} />
                      <span className="text-xs font-medium">{f.label}</span>
                      <span className="text-[9px] text-muted-foreground">{f.desc}</span>
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={checking || exporting || !!isBlocked}
            onClick={handleExport}
            className="gap-1.5 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-700 hover:to-indigo-700"
          >
            {exporting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Exporting...
              </>
            ) : (
              <>
                <FileDown className="h-4 w-4" />
                Export {format.toUpperCase()}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
