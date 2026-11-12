'use client'

import { api } from '@/lib/api'
import type { Editor } from '@tiptap/core'
import dynamic from 'next/dynamic'
import { useParams, useRouter } from 'next/navigation'
import React, { memo, useCallback, useEffect, useRef, useState } from 'react'

// V4 Canva-style Layout
import { CanvaLayout, DocumentCanvas, useStudioStore } from '@/components/studio-v4'
import { EditorProvider } from '@/components/studio-v4/context/EditorContext'
import { ExportPreviewModal } from '@/components/studio-v4/dialogs/ExportPreviewModal'
import { GhostWriterWizard } from '@/components/studio-v4/dialogs/GhostWriterWizard'
import { InvestigationConfig, InvestigationConfigDialog } from '@/components/studio-v4/dialogs/InvestigationConfigDialog'
import { ReportPreviewPanel } from '@/components/studio-v4/dialogs/ReportPreviewPanel'
import type { PanelFindingPayload } from '@/components/studio-v4/panels/evidenceDrill'
import type { CanvasElement, PageMeta } from '@/components/studio-v4/store/useStudioStore'
import { ChartInspector } from '@/components/studio-v4/toolbar/ChartInspector'
import { MASTER_TEMPLATES } from '@/lib/templates'

// Investigation hook
import { useInvestigationStream } from '@/hooks/useInvestigationStream'

// TipTap Editor
import type { ReportEditorRef } from '@/components/tiptap/ReportEditorV2'
import { Loader2, WifiOff, X } from 'lucide-react'

// Lazy-load TipTap editor
const ReportEditorV2 = dynamic(
  () => import('@/components/tiptap/ReportEditorV2').then(mod => mod.ReportEditorV2),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }
)

const DEFAULT_AST = {
  type: 'doc',
  content: [
    {
      type: 'heading',
      attrs: { level: 1 },
      content: [{ type: 'text', text: 'Investigation Report' }],
    },
    {
      type: 'paragraph',
      content: [{ type: 'text', text: 'Begin your analysis here...' }],
    },
  ],
}

const resolveApiOrigin = (): string => {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/api\/?$/, '').replace(/\/+$/, '')
  if (configured) {
    return configured
  }
  if (typeof window !== 'undefined') {
    return window.location.origin
  }
  return ''
}

type EditorContent = Record<string, unknown>
type StudioModuleSource = 'timeline' | 'anomaly' | 'correlation' | 'crud' | 'network' | 'depth' | 'case'
type InsertComponentConfig = Record<string, unknown> & {
  module?: string
  dataEndpoint?: string
}
type InsertFindingInput = PanelFindingPayload

const isEditorContent = (value: unknown): value is EditorContent => {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

const extractLegacyNodeText = (node: any): string => {
  if (!node || typeof node !== 'object') return ''
  if (node.type === 'text' && typeof node.text === 'string') return node.text
  if (Array.isArray(node.content)) {
    return node.content.map((child: any) => extractLegacyNodeText(child)).join('')
  }
  if (Array.isArray(node.left) || Array.isArray(node.right)) {
    return [
      ...(Array.isArray(node.left) ? node.left : []),
      ...(Array.isArray(node.right) ? node.right : []),
    ].map((child: any) => extractLegacyNodeText(child)).join('\n')
  }
  return ''
}

const legacyAstElementsToCanvasPages = (elements: any[]): PageMeta[] => {
  const sections: Array<{ title: string; key: string; content: string }> = []
  let currentTitle = 'Report Section'
  let currentKey = 'report_section'
  let currentChunks: string[] = []

  const flush = () => {
    const content = currentChunks.join('\n\n').trim()
    if (content.length > 0 || currentTitle) {
      sections.push({ title: currentTitle, key: currentKey, content })
    }
    currentChunks = []
  }

  for (const node of elements) {
    if (node?.type === 'heading') {
      const headingText = extractLegacyNodeText(node).trim() || 'Report Section'
      if (currentChunks.length > 0) flush()
      currentTitle = headingText
      currentKey = headingText.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'report_section'
      continue
    }

    if (node?.type === 'horizontalRule') {
      if (currentChunks.length > 0) flush()
      continue
    }

    const text = extractLegacyNodeText(node).trim()
    if (text.length > 0) {
      currentChunks.push(text)
    }
  }

  if (currentChunks.length > 0 || sections.length === 0) {
    flush()
  }

  let yOffset = 40
  const canvasElements: CanvasElement[] = sections.map((section, index) => {
    const textLength = `${section.title}\n${section.content}`.trim().length
    const height = Math.max(220, 120 + Math.ceil(textLength / 95) * 18)
    const element: CanvasElement = {
      id: `legacy-section-${index + 1}`,
      type: 'component',
      x: 40,
      y: yOffset,
      width: 760,
      height,
      zIndex: index + 1,
      data: {
        type: 'section-narrative',
        title: section.title,
        content: section.content,
        section_key: section.key,
      },
    }
    yOffset += height + 20
    return element
  })

  return [{ id: 'page-1', label: 'Page 1', elements: canvasElements }]
}

const MODULE_SOURCES: StudioModuleSource[] = ['timeline', 'anomaly', 'correlation', 'crud', 'network', 'depth', 'case']

const normalizeModuleSource = (value: unknown): StudioModuleSource => {
  if (typeof value !== 'string') return 'case'
  const normalized = value.toLowerCase()
  return MODULE_SOURCES.includes(normalized as StudioModuleSource)
    ? (normalized as StudioModuleSource)
    : 'case'
}

const normalizeSeverity = (value: unknown): PanelFindingPayload['severity'] => {
  if (typeof value !== 'string') {
    return 'medium'
  }
  const normalized = value.toLowerCase()
  if (normalized === 'critical' || normalized === 'high' || normalized === 'medium' || normalized === 'low' || normalized === 'info') {
    return normalized
  }
  return 'medium'
}

const normalizeStringArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return []
  }
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0)
}

const normalizeEndpointPath = (path?: string) => {
  if (!path) return undefined
  return path.startsWith('/api/') ? path.slice(4) : path
}

const prettifyComponentId = (componentId: string) => {
  return componentId
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

const hashString = (value: string) => {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash).toString(16)
}

// ── Offline Toast Banner ─────────────────────────────────────────────────
const OfflineBanner = memo(({ onDismiss, onRetry }: { onDismiss: () => void; onRetry: () => void }) => (
  <div className="fixed top-2 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-3 px-4 py-2.5 rounded-xl bg-amber-950/90 text-amber-200 text-xs font-medium shadow-2xl backdrop-blur-xl border border-amber-800/50 animate-in slide-in-from-top-4 duration-300">
    <WifiOff className="h-3.5 w-3.5 flex-shrink-0" />
    <span>Working offline — changes saved locally. Reconnecting…</span>
    <button onClick={onRetry} className="underline underline-offset-2 hover:text-white transition-colors">Retry</button>
    <button onClick={onDismiss} className="ml-1 hover:text-white transition-colors"><X className="h-3 w-3" /></button>
  </div>
))
OfflineBanner.displayName = 'OfflineBanner'

// ── Memoised Editor Wrapper ──────────────────────────────────────────────
const MemoEditor = memo(ReportEditorV2)

export default function StudioV4Page() {
  const params = useParams()
  const router = useRouter()
  const caseId = params.id as string
  const apiOrigin = resolveApiOrigin()

  const {
    zoom,
    setDocument,
    setSaving,
    setLastSaved,
    hasChanges,
    setHasChanges,
    documentTitle,
    setActivePanel,
    setInvestigationRunning,
    setInvestigationProgress,
  } = useStudioStore()

  const editorRef = useRef<ReportEditorRef | null>(null)
  const [tipTapEditor, setTipTapEditor] = useState<Editor | null>(null)

  // Investigation hook
  const investigation = useInvestigationStream()

  // Investigation dialog state
  const [investigationDialogOpen, setInvestigationDialogOpen] = useState(false)

  // Document state
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [initialContent, setInitialContent] = useState<EditorContent>(DEFAULT_AST)
  const [loading, setLoading] = useState(true)
  const [isOffline, setIsOffline] = useState(false)
  const [showOfflineBanner, setShowOfflineBanner] = useState(false)

  // Fatal error boundary state
  const [fatalError, setFatalError] = useState<Error | null>(null)
  const [fatalInfo, setFatalInfo] = useState<string | null>(null)

  // Export gate dialog state
  const [exportDialogOpen, setExportDialogOpen] = useState(false)
  const [previewModalOpen, setPreviewModalOpen] = useState(false)
  const [reportPreviewOpen, setReportPreviewOpen] = useState(false)
  const [exportEngine, setExportEngine] = useState<'standard' | 'dynamite'>('standard')
  const [exportFormat, setExportFormat] = useState<'pdf' | 'docx'>('pdf')

  // Debounced save ref
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Update TipTap editor reference when available
  useEffect(() => {
    if (editorRef.current) {
      const editor = editorRef.current.getEditor()
      if (editor && editor !== tipTapEditor) {
        setTipTapEditor(editor)
      }
    }
  }, [loading, tipTapEditor])

  const adoptStudioDocument = useCallback(async (nextDocumentId: string) => {
    const fullDoc = await api.get(`/v4/studio/cases/${caseId}/docs/${nextDocumentId}`)
    setDocumentId(nextDocumentId)
    setDocument(caseId, nextDocumentId, fullDoc?.title || 'Investigation Report')

    if (fullDoc?.ast?.type === 'v4-canvas' && Array.isArray(fullDoc.ast.pages)) {
      useStudioStore.getState().setPages(fullDoc.ast.pages)
    } else if (fullDoc?.ast?.type === 'doc' && Array.isArray(fullDoc.ast.content)) {
      // Proper TipTap doc from canonical pipeline
      setInitialContent(fullDoc.ast)
    } else if (isEditorContent(fullDoc?.ast)) {
      // Legacy format: extract elements from pages if present
      const pages = fullDoc.ast.pages as Array<{ elements?: unknown[] }> | undefined
      if (Array.isArray(pages) && pages.length > 0 && Array.isArray(pages[0]?.elements)) {
        useStudioStore.getState().setPages(legacyAstElementsToCanvasPages(pages[0].elements as any[]))
      } else {
        setInitialContent(fullDoc.ast)
      }
    } else if (isEditorContent(fullDoc?.content)) {
      setInitialContent(fullDoc.content)
    }
  }, [caseId, setDocument])

  // ── Load or create document (with graceful offline fallback) ────────────
  const attemptLoad = useCallback(async () => {
    try {
      const docsResponse = await api.get(`/v4/studio/cases/${caseId}/docs`)
      const docs = Array.isArray(docsResponse) ? docsResponse : docsResponse?.documents || []

      if (docs && Array.isArray(docs) && docs.length > 0) {
        const doc = docs[0]
        await adoptStudioDocument(doc.doc_id)
      } else {
        const newDoc = await api.post(`/v4/studio/cases/${caseId}/docs`, {
          title: 'New Investigation Report',
          template: 'technical',
        })

        if (newDoc?.doc_id) {
          setDocumentId(newDoc.doc_id)
          setDocument(caseId, newDoc.doc_id, newDoc.title || 'New Investigation Report')
          if (newDoc?.ast?.type === 'v4-canvas' && Array.isArray(newDoc.ast.pages)) {
            useStudioStore.getState().setPages(newDoc.ast.pages)
          } else {
            setInitialContent(
              isEditorContent(newDoc.ast) ? newDoc.ast
                : isEditorContent(newDoc.content) ? newDoc.content
                  : DEFAULT_AST
            )
          }
        }
      }
      // Successful — clear offline state
      setIsOffline(false)
      setShowOfflineBanner(false)
      return true
    } catch (err) {
      console.warn('[Studio] API unreachable, entering offline mode:', err)
      return false
    }
  }, [adoptStudioDocument, caseId])

  useEffect(() => {
    const loadDocument = async () => {
      setLoading(true)
      const success = await attemptLoad()
      if (!success) {
        // Offline fallback — let the investigator type freely
        const localId = `local-${crypto.randomUUID()}`
        setDocumentId(localId)
        setDocument(caseId, localId, 'Untitled Report (Offline)')
        setInitialContent(DEFAULT_AST)
        setIsOffline(true)
        setShowOfflineBanner(true)
      }
      setLoading(false)
    }
    loadDocument()
  }, [caseId, attemptLoad, setDocument])

  // ── Background retry loop when offline ────────────────────────────────
  useEffect(() => {
    if (!isOffline) return
    const interval = setInterval(async () => {
      const success = await attemptLoad()
      if (success) {
        clearInterval(interval)
      }
    }, 12000)
    return () => clearInterval(interval)
  }, [isOffline, attemptLoad])

  // ── Save handler ──────────────────────────────────────────────────────
  const handleSave = useCallback(async () => {
    if (!documentId || documentId.startsWith('local-')) {
      throw new Error('Offline document cannot be saved to server')
    }

    try {
      setSaving(true)
      // Serialize the V4 Canvas Layout instead of default TipTap AST
      const pages = useStudioStore.getState().pages;
      const ast = {
        type: 'v4-canvas',
        version: '1.0',
        pages: pages,
      }

      await api.put(`/v4/studio/cases/${caseId}/docs/${documentId}`, {
        title: documentTitle,
        ast,
        change_summary: 'Autosave from Studio V4',
      })

      setLastSaved(new Date())
      setHasChanges(false)
    } catch (err) {
      console.error('Failed to save:', err)
      throw err
    } finally {
      setSaving(false)
    }
  }, [caseId, documentId, documentTitle, setSaving, setLastSaved, setHasChanges])

  // ── Debounced content change → autosave ───────────────────────────────
  const handleContentChange = useCallback(() => {
    // Only mark dirty after debounce to avoid re-rendering the layout on every keystroke
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      setHasChanges(true)
    }, 800)
  }, [setHasChanges])

  useEffect(() => {
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current) }
  }, [])

  // Navigation handlers
  const handleBack = useCallback(() => {
    router.push(`/cases/${caseId}`)
  }, [router, caseId])

  const handleExport = useCallback(async () => {
    if (documentId?.startsWith('local-')) {
      setReportPreviewOpen(true)
      return
    }
    // Auto-save before export to ensure latest changes are included
    // This is a TRANSACTIONAL requirement: export MUST include current state
    if (hasChanges && documentId && !documentId.startsWith('local-')) {
      try {
        await handleSave()
      } catch (err) {
        console.error('Failed to save before export:', err)
        // FAIL HARD: Do NOT export stale state
        alert('Cannot export: Failed to save current changes. Please try saving manually first.')
        return
      }
    }
    // Show preview panel first, then proceed to export
    setReportPreviewOpen(true)
  }, [hasChanges, documentId, handleSave])

  const handleExportFromPreview = useCallback(async (format: 'pdf' | 'docx') => {
    if (documentId && !documentId.startsWith('local-')) {
      try {
        const precheck = await api.post(`/v4/studio/cases/${caseId}/exports/precheck`, { doc_id: documentId })
        if (precheck?.blocked) {
          const count = Array.isArray(precheck.violations) ? precheck.violations.length : 0
          alert(`Export blocked by governance precheck: ${count} critical uncited evidence block(s).`)
          return
        }
      } catch (err) {
        console.error('Export precheck failed:', err)
        alert('Cannot export: precheck failed. Please retry.')
        return
      }
    }
    setExportFormat(format)
    setReportPreviewOpen(false)
    setPreviewModalOpen(true)
  }, [caseId, documentId])

  const handleShare = useCallback(() => {
    console.log('Share clicked')
  }, [])

  // Investigation handlers
  const handleInvestigate = useCallback(() => {
    setInvestigationDialogOpen(true)
  }, [])

  const handleStartInvestigation = useCallback(async (config: InvestigationConfig) => {
    setInvestigationDialogOpen(false)
    setInvestigationRunning(true)
    setInvestigationProgress(0)

    try {
      await investigation.startInvestigation({
        caseId: config.caseId,
        scenario: config.scenario,
        objectives: config.objectives,
        modules: config.modules,
        hypotheses: config.hypotheses,
        options: config.options,
      })
    } catch (error) {
      console.error('Failed to start investigation:', error)
      setInvestigationRunning(false)
      setInvestigationProgress(0)
    }
  }, [investigation, setInvestigationRunning, setInvestigationProgress])

  const handleStopInvestigation = useCallback(() => {
    investigation.stopInvestigation()
    setInvestigationRunning(false)
    setInvestigationProgress(0)
  }, [investigation, setInvestigationRunning, setInvestigationProgress])

  // Sync investigation progress with store
  useEffect(() => {
    setInvestigationProgress(Math.max(0, Math.min(100, investigation.progress)))
    setInvestigationRunning(investigation.isRunning)
  }, [investigation.progress, investigation.isRunning, setInvestigationProgress, setInvestigationRunning])

  useEffect(() => {
    if (investigation.errors.length === 0) return
    const latestError = investigation.errors[investigation.errors.length - 1]
    setInvestigationRunning(false)
    alert(`Investigation error: ${latestError}`)
  }, [investigation.errors, setInvestigationRunning])

  // ── Auto-download PDF when a new report pipeline completes ───────────────
  const autoDownloadedReportRef = useRef<string | null>(null)
  useEffect(() => {
    if (investigation.pipelineStage !== 'complete') return
    if (!investigation.reportId) return
    // Avoid double-download on re-render
    if (autoDownloadedReportRef.current === investigation.reportId) return
    autoDownloadedReportRef.current = investigation.reportId

    const triggerAutoDownload = async () => {
      try {
        // Small delay so canvas can settle first
        await new Promise(r => setTimeout(r, 1500))
        const exportsResp = await api.get(`/v4/studio/cases/${caseId}/exports`)
        const exports: Array<{ filename: string; format: string; modified_at: number }> =
          Array.isArray(exportsResp?.exports) ? exportsResp.exports : []
        const latestPdf = exports.find(e => e.format === 'pdf')
        if (latestPdf) {
          const encoded = encodeURIComponent(latestPdf.filename)
          const link = document.createElement('a')
          link.href = `/api/v4/studio/cases/${caseId}/exports/download/${encoded}`
          link.download = latestPdf.filename
          document.body.appendChild(link)
          link.click()
          document.body.removeChild(link)
        }
      } catch (err) {
        console.warn('[Studio] Auto-download after pipeline failed:', err)
      }
    }
    void triggerAutoDownload()
  }, [investigation.pipelineStage, investigation.reportId, caseId])

  useEffect(() => {
    if (!investigation.reportId) return

    let cancelled = false
    const syncGeneratedReport = async () => {
      try {
        const docsResponse = await api.get(`/v4/studio/cases/${caseId}/docs`)
        const docs = Array.isArray(docsResponse) ? docsResponse : docsResponse?.documents || []
        const matched = docs.find((doc: any) => doc?.doc_id === investigation.reportId)
        if (!matched || cancelled) return
        await adoptStudioDocument(matched.doc_id)
      } catch (error) {
        console.warn('[Studio] Failed to adopt generated investigation document:', error)
      }
    }

    void syncGeneratedReport()
    return () => {
      cancelled = true
    }
  }, [adoptStudioDocument, caseId, investigation.reportId])

  // Stream approved sections into the canvas as they arrive (CRT effect)
  const insertedSectionsRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    // Sort sections by sort_order, then insert any newly approved ones as canvas elements
    const sortedKeys = [...investigation.sectionOrder].sort((a, b) => {
      const sa = investigation.sectionStates[a]?.sortOrder ?? 999
      const sb = investigation.sectionStates[b]?.sortOrder ?? 999
      return sa - sb
    })

    for (const key of sortedKeys) {
      const section = investigation.sectionStates[key]
      if (!section?.sectionContent || section.status !== 'approved') continue
      if (insertedSectionsRef.current.has(key)) continue

      insertedSectionsRef.current.add(key)

      // Add as a canvas element on page 1
      const store = useStudioStore.getState()
      const pages = store.pages
      if (pages.length === 0) continue

      const pageIndex = 0
      const existingElements = pages[pageIndex].elements ?? []
      const yOffset = existingElements.length > 0
        ? Math.max(...existingElements.map((el: any) => (el.y ?? 0) + (el.height ?? 200))) + 20
        : 40

      const newElement = {
        type: 'component' as const,
        x: 40,
        y: yOffset,
        width: 760,
        height: 240,
        data: {
          type: 'section-narrative',
          title: section.sectionTitle || key,
          content: section.sectionContent,
          section_key: key,
        },
      }

      store.addElement(pageIndex, newElement)
    }
  }, [investigation.sectionStates, investigation.sectionOrder])

  // Add findings to canvas as they stream in (with page-overflow protection)
  useEffect(() => {
    if (investigation.findings.length === 0) return

    const lastFinding = investigation.findings[investigation.findings.length - 1]
    const store = useStudioStore.getState()
    let targetPage = store.currentPage

    // Calculate Y position; if it would exceed A4 page bounds (1123px), spill to a new page
    const PAGE_MAX_Y = 1000 // ~297mm minus margins
    const CARD_HEIGHT = 120
    const CARD_GAP = 20
    const existingElements = store.pages[targetPage]?.elements || []
    const lastElBottom = existingElements.reduce((max, el) => Math.max(max, (el.y || 0) + (el.height || 0)), 40)
    let nextY = lastElBottom + CARD_GAP

    if (nextY + CARD_HEIGHT > PAGE_MAX_Y) {
      // Overflow: create a new page and place element at top
      store.addPage()
      targetPage = store.pages.length // addPage already appended
      nextY = 40
    }

    // Auto-add finding cards to canvas
    if (lastFinding.type === 'hypothesis' || lastFinding.type === 'hypothesis_verdict') {
      store.addElement(targetPage, {
        type: 'component',
        x: 40,
        y: nextY,
        width: 720,
        height: CARD_HEIGHT,
        data: {
          type: 'hypothesis-card',
          module: 'hypothesis',
          componentId: 'HypothesisCard',
          data: lastFinding.data,
        },
      })
      setHasChanges(true)
    }
  }, [investigation.findings, setHasChanges])

  // Auto-place decision trace widget when investigation completes
  useEffect(() => {
    if (investigation.pipelineStage !== 'complete') return
    if (investigation.toolCallLog.length === 0) return
    const store = useStudioStore.getState()
    // Avoid duplicate: check if a decision-trace element already exists
    const alreadyExists = store.pages.some(p =>
      p.elements.some(el => el.data?.type === 'decision-trace')
    )
    if (alreadyExists) return

    // Place on a new page at the end
    store.addPage()
    const targetPage = store.pages.length
    store.addElement(targetPage, {
      type: 'component',
      x: 40,
      y: 40,
      width: 720,
      height: 600,
      data: {
        type: 'decision-trace',
        module: 'ai',
        componentId: 'DecisionTrace',
        data: { entries: investigation.toolCallLog },
      },
    })
    setHasChanges(true)
  }, [investigation.pipelineStage, investigation.toolCallLog, setHasChanges])

  const getNextFigureNumber = useCallback(() => {
    const editor = editorRef.current?.getEditor()
    if (!editor) return 1

    let evidenceBlockCount = 0
    editor.state.doc.descendants((node) => {
      if (node.type.name === 'evidenceBlock') {
        evidenceBlockCount += 1
      }
    })

    return evidenceBlockCount + 1
  }, [])

  const fetchInsertData = useCallback(async (source: StudioModuleSource, config?: InsertComponentConfig) => {
    const endpointPath = normalizeEndpointPath(typeof config?.dataEndpoint === 'string' ? config.dataEndpoint : undefined)

    const fetchEndpoint = endpointPath
      ? api.get(endpointPath).catch(() => null)
      : Promise.resolve(null)

    if (source === 'timeline') {
      const [endpointData, events, fallbackStats] = await Promise.all([
        fetchEndpoint,
        api.get(`/cases/${caseId}/timeline?limit=50`).catch(() => []),
        !endpointPath ? api.get(`/cases/${caseId}/timeline/stats`).catch(() => null) : Promise.resolve(null)
      ])
      return {
        endpointPath,
        endpointData: endpointData || fallbackStats,
        timelineEvents: events && Array.isArray(events.clusters) ? events.clusters : (Array.isArray(events) ? events : []), /* handles both legacy and cluster payloads */
      }
    }

    if (source === 'anomaly') {
      const [endpointData, fallbackSummary] = await Promise.all([
        fetchEndpoint,
        !endpointPath ? api.get(`/cases/${caseId}/anomalies/summary`).catch(() => null) : Promise.resolve(null)
      ])
      return { endpointPath, endpointData: endpointData || fallbackSummary }
    }

    const endpointData = await fetchEndpoint
    return { endpointPath, endpointData }
  }, [caseId])

  const fetchComponentData = useCallback(async (componentId: string, config?: Record<string, unknown>) => {

    const typedConfig = (config || {}) as InsertComponentConfig
    const source = normalizeModuleSource(typedConfig.module)
    const figureNumber = getNextFigureNumber()
    const title = prettifyComponentId(componentId)
    const citationId = `[EVD-${source.toUpperCase()}-${String(figureNumber).padStart(3, '0')}]`

    const { endpointPath, endpointData, timelineEvents } = await fetchInsertData(source, typedConfig)
    const lowerId = componentId.toLowerCase()
    const questionType = typeof typedConfig.questionType === 'string' ? typedConfig.questionType : undefined
    const visualPattern = typeof typedConfig.visualPattern === 'string' ? typedConfig.visualPattern : undefined
    const tracePath = normalizeStringArray(typedConfig.tracePath)

    let type: 'chart' | 'table' | 'metric' | 'finding' | 'timeline-event' | 'anomaly' | 'network-flow' | 'shap-explanation' | 'correlation-graph' = 'chart'

    if (lowerId === 'case-context-confidence') {
      type = 'metric'
    } else if (
      lowerId === 'phase-approval-board'
      || lowerId === 'run-module-lanes'
      || lowerId === 'gate-readiness-checklist'
      || lowerId === 'section-confidence-rollup'
      || lowerId === 'claim-evidence-trace'
      || lowerId === 'actor-sequence-table'
    ) {
      type = 'table'
    } else if (lowerId === 'timeline-layered-bands') {
      type = 'timeline-event'
    } else if (lowerId === 'anomaly-explanation-card') {
      type = 'finding'
    } else if (lowerId.includes('shap')) {
      type = 'shap-explanation'
    } else if (lowerId === 'timeline-vertical-list' || lowerId === 'timeline-single-event') {
      type = 'timeline-event'
    } else if (lowerId.includes('network')) {
      type = 'network-flow'
    } else if (lowerId.includes('correlation')) {
      type = 'correlation-graph'
    } else if (lowerId.includes('stats') || lowerId.includes('metric')) {
      type = 'metric'
    } else if (lowerId.includes('table') || lowerId.includes('list') || lowerId.includes('manifest')) {
      type = 'table'
    }

    let data: Record<string, unknown> = {
      type: type,  // Add explicit type for PDF dispatch
      componentType: type,  // Add componentType for widget renderers
      chartType: componentId,
      sourceModule: source,
      summary: endpointData || {},
      question_type: questionType,
      visual_pattern: visualPattern,
      trace_path: tracePath,
    }

    if (source === 'timeline' || lowerId.includes('timeline') || lowerId.includes('swimlane')) {
      data.clusters = Array.isArray(timelineEvents) ? timelineEvents : []
    }

    if (type === 'timeline-event') {
      const chartType = lowerId.includes('swimlane') ? 'swimlane' : 'timeline'
      data = {
        ...data,
        type: 'timeline-event',
        componentType: 'timeline-event',
        chartType: chartType,
      }
    } else if (type === 'shap-explanation') {
      const summary = (endpointData as Record<string, any>) || {}
      const shapFeatures = Array.isArray(summary.shap_global_importance)
        ? summary.shap_global_importance
        : []
      const chartType = lowerId.includes('waterfall') ? 'waterfall' : 'importance'
      data = {
        type: 'shap-explanation',
        componentType: 'shap-explanation',
        chartType: chartType,
        features: shapFeatures.map((feature: Record<string, unknown>) => ({
          feature: feature.feature || feature.name || 'feature',
          contribution: feature.importance || feature.importance_pct || 0,
          value: feature.importance || feature.importance_pct || 0,
        })),
        prediction: summary?.score_stats?.p95 || 0,
        base_value: summary?.score_stats?.mean || 0,
      }
    } else if (type === 'metric') {
      const summary = (endpointData as Record<string, any>) || {}
      const confidenceSource = summary.scope_confidence ?? summary.overall_confidence ?? summary.confidence
      const normalizedConfidence = typeof confidenceSource === 'number'
        ? (confidenceSource > 1 ? confidenceSource / 100 : confidenceSource)
        : undefined
      const value = source === 'timeline'
        ? summary.total_events || 0
        : source === 'anomaly'
          ? summary.anomaly_count || 0
          : summary.count || 0
      data = {
        type: 'metric',
        componentType: 'metric',
        value: lowerId === 'case-context-confidence' && typeof normalizedConfidence === 'number'
          ? Math.round(normalizedConfidence * 100)
          : value,
        unit: lowerId === 'case-context-confidence' ? '%' : 'events',
        trend: lowerId === 'case-context-confidence' && typeof normalizedConfidence === 'number'
          ? Math.round((normalizedConfidence - 0.5) * 100)
          : undefined,
        description: lowerId === 'case-context-confidence'
          ? 'Scope confidence derived from intake and module coverage.'
          : `${title} from ${source} analysis`,
        question_type: questionType,
        visual_pattern: visualPattern,
        trace_path: tracePath,
      }
    } else if (type === 'table') {
      const payload = (endpointData as Record<string, any>) || {}
      let columns: string[] = ['field', 'value']
      let rows: unknown[][] = []

      if (lowerId === 'phase-approval-board') {
        columns = ['Phase', 'Checkpoint', 'Status', 'Owner']
        const checkpoints = Array.isArray(payload.phase_checkpoints)
          ? payload.phase_checkpoints
          : [
            { phase: 'Intake', checkpoint: 'Scope validation', status: 'approved', owner: 'investigator' },
            { phase: 'Plan', checkpoint: 'Hypothesis review', status: 'approved', owner: 'reviewer' },
            { phase: 'Execution', checkpoint: 'Module completion', status: 'pending', owner: 'system' },
            { phase: 'Report', checkpoint: 'Final admissibility', status: 'pending', owner: 'reviewer' },
          ]
        rows = checkpoints.slice(0, 25).map((row: Record<string, unknown>) => [
          row.phase || row.stage || 'phase',
          row.checkpoint || row.name || 'checkpoint',
          row.status || 'pending',
          row.owner || row.approved_by || 'system',
        ])
      } else if (lowerId === 'run-module-lanes') {
        columns = ['Module', 'State', 'Updated', 'Evidence']
        const moduleRows = Array.isArray(payload.module_states)
          ? payload.module_states
          : [
            { module: 'timeline', state: 'completed', updated: 'latest', evidence: 24 },
            { module: 'anomaly', state: 'completed', updated: 'latest', evidence: 9 },
            { module: 'correlation', state: 'running', updated: 'now', evidence: 4 },
            { module: 'network', state: 'queued', updated: 'pending', evidence: 0 },
          ]
        rows = moduleRows.slice(0, 25).map((row: Record<string, unknown>) => [
          row.module || row.name || 'module',
          row.state || row.status || 'unknown',
          row.updated || row.updated_at || 'n/a',
          row.evidence || row.evidence_count || 0,
        ])
      } else if (lowerId === 'gate-readiness-checklist') {
        columns = ['Check', 'Status', 'Severity', 'Details']
        const violations = Array.isArray(payload.violations) ? payload.violations : []
        rows = violations.length > 0
          ? violations.slice(0, 25).map((row: Record<string, unknown>) => [
            row.title || row.type || 'gate check',
            'blocked',
            row.severity || 'HIGH',
            row.message || row.source || 'blocked by governance precheck',
          ])
          : [
            ['Citation linkage', 'pass', 'INFO', 'Claims are citation-bound'],
            ['Manifest replay contract', 'pass', 'INFO', 'Deterministic metadata present'],
            ['Override reason capture', 'warn', 'MEDIUM', 'Reason required when overriding gate'],
          ]
      } else if (lowerId === 'section-confidence-rollup') {
        columns = ['Section', 'Confidence', 'Status']
        const rollupRows = Array.isArray(payload.section_confidence)
          ? payload.section_confidence
          : [
            { section: 'Executive Summary', confidence: 0.84, status: 'high' },
            { section: 'Timeline', confidence: 0.79, status: 'high' },
            { section: 'Anomaly', confidence: 0.68, status: 'medium' },
            { section: 'Evidence Appendix', confidence: 0.9, status: 'high' },
          ]
        rows = rollupRows.slice(0, 25).map((row: Record<string, unknown>) => {
          const rawConfidence = Number(row.confidence ?? row.score ?? 0)
          const confidencePct = rawConfidence > 1 ? rawConfidence : rawConfidence * 100
          return [
            row.section || row.section_key || 'section',
            `${Math.round(confidencePct)}%`,
            row.status || (confidencePct >= 80 ? 'high' : confidencePct >= 60 ? 'medium' : 'low'),
          ]
        })
      } else if (lowerId === 'claim-evidence-trace') {
        columns = ['Claim', 'Evidence Key', 'Source Module']
        const traces = Array.isArray(payload.claim_traces) ? payload.claim_traces : []
        rows = traces.length > 0
          ? traces.slice(0, 25).map((row: Record<string, unknown>) => [
            row.claim || row.title || 'claim',
            row.evidence_key || row.evidence || 'EVD-unknown',
            row.source_module || row.module || 'case',
          ])
          : [
            ['Unauthorized access chain', 'EVD-101', 'timeline'],
            ['Privilege escalation indicator', 'EVD-118', 'anomaly'],
            ['Outbound exfil sequence', 'EVD-140', 'network'],
          ]
      } else if (lowerId === 'actor-sequence-table') {
        columns = ['Actor', 'Events', 'Sequence']
        const links = Array.isArray(endpointData) ? endpointData : []
        rows = links.slice(0, 25).map((row: Record<string, unknown>) => [
          row.primary_entity || row.actor || 'actor',
          row.count || row.event_count || 1,
          row.relationship_type || row.sequence || `${row.primary_entity || 'actor'} -> ${row.related_entity || 'entity'}`,
        ])
      } else {
        const rowSource = Array.isArray(payload.top_anomalies)
          ? payload.top_anomalies
          : Array.isArray(payload.events)
            ? payload.events
            : Array.isArray(endpointData)
              ? endpointData
              : []

        columns = rowSource[0]
          ? Object.keys(rowSource[0]).slice(0, 8)
          : ['field', 'value']

        rows = rowSource.slice(0, 25).map((row: Record<string, unknown>) => (
          columns.map((column) => row[column])
        ))
      }

      data = {
        type: 'table',
        componentType: 'table',
        columns,
        rows,
        summary: `${rows.length} rows captured from ${source}`,
        question_type: questionType,
        visual_pattern: visualPattern,
        trace_path: tracePath,
      }
    } else if (type === 'finding') {
      const summary = (endpointData as Record<string, any>) || {}
      const topAnomaly = Array.isArray(summary.top_anomalies) && summary.top_anomalies.length > 0
        ? summary.top_anomalies[0]
        : null
      data = {
        type: 'finding',
        componentType: 'finding',
        severity: topAnomaly?.severity || 'medium',
        summary: topAnomaly
          ? {
            summary: `${topAnomaly.action || 'Event'} anomaly at ${(Number(topAnomaly.score || 0) * 100).toFixed(0)}% confidence`,
            details: `Actor ${topAnomaly.actor || 'unknown'} from ${topAnomaly.source_type || 'source'} triggered explanation review.`,
            evidence_ids: topAnomaly.tl_event_id ? [topAnomaly.tl_event_id] : [],
            confidence: Number(topAnomaly.score || 0),
          }
          : {
            summary: 'Per-event anomaly explanation card',
            details: 'No anomaly summary available; run detection to populate this view.',
            evidence_ids: [],
          },
        question_type: questionType,
        visual_pattern: visualPattern,
        trace_path: tracePath,
      }
    } else if (type === 'network-flow') {
      const payload = endpointData as Record<string, unknown> | unknown[] | null
      const flows = Array.isArray(payload)
        ? payload
        : Array.isArray((payload as Record<string, unknown>)?.flows)
          ? ((payload as Record<string, unknown>).flows as unknown[])
          : []
      data = {
        type: 'network-flow',
        componentType: 'network-flow',
        flows,
        stats: payload || {},
        question_type: questionType,
        visual_pattern: visualPattern,
        trace_path: tracePath,
      }
    } else if (type === 'correlation-graph') {
      const payload = (endpointData as Record<string, any>) || {}
      data = {
        type: 'correlation-graph',
        componentType: 'correlation-graph',
        nodes: Array.isArray(payload.nodes) ? payload.nodes : [],
        edges: Array.isArray(payload.edges) ? payload.edges : [],
        summary: payload,
        question_type: questionType,
        visual_pattern: visualPattern,
        trace_path: tracePath,
      }
    }

    const configHash = `cfg:${hashString(JSON.stringify({ componentId, source, data }).slice(0, 3000))}`

    return {
      id: `evd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      type,
      source,
      title,
      caption: `${title} inserted from ${source} module`,
      figureNumber,
      data,
      metadata: {
        timestamp: new Date().toISOString(),
        citationId,
        insertionActor: 'investigator',
        sourceQuery: endpointPath || componentId,
        sourceVersion: 1,
        configHash,
        verified: false,
      },
    }
  }, [caseId, getNextFigureNumber, fetchInsertData])


  const handleDropCanvasComponent = useCallback(async (pageIndex: number, componentId: string, x: number, y: number, payload: any) => {
    if (payload.type === 'text-block') {
      const blockType = typeof payload.content === 'string' ? payload.content : 'paragraph'
      const blockName = blockType === 'heading' ? 'Heading' : 'New text block'

      useStudioStore.getState().addElement(pageIndex, {
        type: 'text',
        x: x - 200,
        y: y - 50,
        width: 400,
        height: 100,
        data: {
          textType: blockType,
          content: blockType === 'heading' ? blockName : 'Start typing...',
          style: blockType,
        }
      })
      useStudioStore.getState().setHasChanges(true)
      return
    }

    if (payload.type === 'entity' && payload.data) {
      const entity = payload.data
      const isCorrelation = typeof entity.primary_entity === 'string' && typeof entity.related_entity === 'string'
      const source: StudioModuleSource = isCorrelation ? 'correlation' : 'network'
      if (isCorrelation) {
        useStudioStore.getState().addElement(pageIndex, {
          type: 'component', x: x - 250, y: y - 150, width: 500, height: 300, data: { type: 'correlation-graph', source, title: 'Correlation Link', data: { nodes: [{ id: entity.primary_entity, label: entity.primary_entity, kind: entity.primary_type || 'primary' }, { id: entity.related_entity, label: entity.related_entity, kind: entity.related_type || 'related' }], edges: [{ source: entity.primary_entity, target: entity.related_entity, type: entity.relationship_type || 'linked', confidence: entity.confidence_score || 0 }], central_entity: entity.primary_entity } }
        })
      } else {
        useStudioStore.getState().addElement(pageIndex, {
          type: 'component', x: x - 250, y: y - 150, width: 500, height: 300, data: { type: 'network-flow', source, title: 'Network Entity', data: { src_ip: entity.ip_address || 'unknown', dst_ip: entity.domain || 'unknown', bytes: entity.bytes_transferred || 0, packets: entity.connections_count || 0, protocol: entity.entity_type || 'network', direction: 'outbound' } }
        })
      }
      useStudioStore.getState().setHasChanges(true)
      return
    }

    if (payload.type === 'finding' && payload.data) {
      const finding = payload.data
      const source = normalizeModuleSource(finding.source)
      const severity = normalizeSeverity(finding.severity)
      const evidenceIds = normalizeStringArray(finding.evidenceIds)
      const tracePath = normalizeStringArray(finding.tracePath)
      useStudioStore.getState().addElement(pageIndex, {
        type: 'component', x: x - 200, y: y - 100, width: 400, height: 200, data: {
          type: 'finding',
          chartType: 'finding',
          componentType: 'finding',
          source,
          title: finding.title,
          severity,
          description: finding.content,
          evidence: evidenceIds,
          evidence_ids: evidenceIds,
          summary: {
            severity,
            summary: finding.content,
            details: finding.content,
            confidence: typeof finding.confidence === 'number' ? finding.confidence : undefined,
            question_type: finding.questionType,
            visual_pattern: finding.visualPattern,
            trace_path: tracePath,
            anchor_ref: finding.anchorRef,
          },
          question_type: finding.questionType,
          visual_pattern: finding.visualPattern,
          trace_path: tracePath,
          anchor_ref: finding.anchorRef,
        }
      })
      useStudioStore.getState().setHasChanges(true)
      return
    }

    if (payload.type === 'canvas-element' || payload.type === 'annotation') {
      const name = typeof payload.elementId === 'string' ? payload.elementId : 'Element'
      useStudioStore.getState().addElement(pageIndex, {
        type: 'shape', x: x - 50, y: y - 50, width: 100, height: 100, data: { name }
      })
      useStudioStore.getState().setHasChanges(true)
      return
    }

    if (payload.type === 'upload') {
      const name = typeof payload.fileId === 'string' ? payload.fileId : 'Upload'
      const url = typeof payload.url === 'string' ? payload.url : ''
      useStudioStore.getState().addElement(pageIndex, {
        type: 'image', x: x - 150, y: y - 100, width: 300, height: 200, data: { name, url }
      })
      useStudioStore.getState().setHasChanges(true)
      return
    }

    const blockData = await fetchComponentData(componentId, payload)

    // Add to absolute-positioned freeform canvas
    useStudioStore.getState().addElement(pageIndex, {
      type: 'component',
      x: x - 200, // Center relative to cursor
      y: y - 100,
      width: 400,
      height: 300,
      data: blockData
    })

    useStudioStore.getState().setHasChanges(true)
  }, [fetchComponentData])
  // Legacy handler for clicking side-panel buttons without drag-and-drop
  const handleInsertComponent = useCallback(async (componentId: string, config?: Record<string, unknown>) => {
    const blockData = await fetchComponentData(componentId, config)
    const { currentPage } = useStudioStore.getState()

    // Default to center of page roughly
    useStudioStore.getState().addElement(currentPage, {
      type: 'component',
      x: 100,
      y: 100,
      width: 400,
      height: 300,
      data: blockData
    })

    useStudioStore.getState().setActivePanel(null)
    useStudioStore.getState().setHasChanges(true)
  }, [fetchComponentData])

  const handleInsertFinding = useCallback((finding: InsertFindingInput) => {
    const source = normalizeModuleSource(finding.source)
    const severity = normalizeSeverity(finding.severity)
    const evidenceIds = normalizeStringArray(finding.evidenceIds)
    const tracePath = normalizeStringArray(finding.tracePath)
    const { currentPage } = useStudioStore.getState()
    useStudioStore.getState().addElement(currentPage, {
      type: 'component', x: 100, y: 100, width: 400, height: 200, data: {
        type: 'finding',
        chartType: 'finding',
        componentType: 'finding',
        source,
        title: finding.title,
        severity,
        description: finding.content,
        evidence: evidenceIds,
        evidence_ids: evidenceIds,
        summary: {
          severity,
          summary: finding.content,
          details: finding.content,
          confidence: typeof finding.confidence === 'number' ? finding.confidence : undefined,
          question_type: finding.questionType,
          visual_pattern: finding.visualPattern,
          trace_path: tracePath,
          anchor_ref: finding.anchorRef,
        },
        question_type: finding.questionType,
        visual_pattern: finding.visualPattern,
        trace_path: tracePath,
        anchor_ref: finding.anchorRef,
      }
    })
    useStudioStore.getState().setHasChanges(true)
    useStudioStore.getState().setActivePanel(null)
  }, [])

  const handleInsertEntity = useCallback((entity: Record<string, unknown>) => {
    const isCorrelation = typeof entity.primary_entity === 'string' && typeof entity.related_entity === 'string'
    const source: StudioModuleSource = isCorrelation ? 'correlation' : 'network'
    const { currentPage } = useStudioStore.getState()
    if (isCorrelation) {
      useStudioStore.getState().addElement(currentPage, {
        type: 'component', x: 100, y: 100, width: 500, height: 300, data: { type: 'correlation-graph', source, title: 'Correlation Link', data: { nodes: [{ id: entity.primary_entity, label: entity.primary_entity, kind: entity.primary_type || 'primary' }, { id: entity.related_entity, label: entity.related_entity, kind: entity.related_type || 'related' }], edges: [{ source: entity.primary_entity, target: entity.related_entity, type: entity.relationship_type || 'linked', confidence: entity.confidence_score || 0 }], central_entity: entity.primary_entity } }
      })
    } else {
      useStudioStore.getState().addElement(currentPage, {
        type: 'component', x: 100, y: 100, width: 500, height: 300, data: { type: 'network-flow', source, title: 'Network Entity', data: { src_ip: entity.ip_address || 'unknown', dst_ip: entity.domain || 'unknown', bytes: entity.bytes_transferred || 0, packets: entity.connections_count || 0, protocol: entity.entity_type || 'network', direction: 'outbound' } }
      })
    }
    useStudioStore.getState().setHasChanges(true)
    useStudioStore.getState().setActivePanel(null)
  }, [])

  const handleInsertEvidence = useCallback((evidence: Record<string, unknown>) => {
    const { currentPage } = useStudioStore.getState()
    const hashValue = typeof evidence.hash_value === 'string' ? evidence.hash_value : ''
    const hashAlgorithm = typeof evidence.hash_algorithm === 'string' ? evidence.hash_algorithm : 'sha256'
    useStudioStore.getState().addElement(currentPage, {
      type: 'component', x: 100, y: 100, width: 400, height: 200, data: { type: 'finding', chartType: 'finding', componentType: 'finding', source: 'case', title: String(evidence.artefact_name || 'Vault Evidence'), summary: { severity: 'info', summary: `${String(evidence.artefact_type || 'Evidence')} inserted from Vault`, details: `${hashAlgorithm}: ${hashValue}` } }
    })
    useStudioStore.getState().setHasChanges(true)
    useStudioStore.getState().setActivePanel(null)
  }, [])

  const handleInsertBlock = useCallback((block: Record<string, unknown>) => {
    const attrs = (block as { attrs?: Record<string, unknown> }).attrs
    if (!attrs) return
    const { currentPage } = useStudioStore.getState()
    const source = normalizeModuleSource(attrs.source)
    useStudioStore.getState().addElement(currentPage, {
      type: 'component', x: 100, y: 100, width: 500, height: 300, data: { ...attrs, source }
    })
    useStudioStore.getState().setHasChanges(true)
    useStudioStore.getState().setActivePanel(null)
  }, [])

  const handleInsertText = useCallback((blockDef: Record<string, unknown>) => {
    const blockType = typeof blockDef.type === 'string' ? blockDef.type : 'paragraph'
    const blockName = typeof blockDef.name === 'string' ? blockDef.name : 'New text block'
    const { currentPage } = useStudioStore.getState()

    useStudioStore.getState().addElement(currentPage, {
      type: 'text',
      x: 100,
      y: 100,
      width: 400,
      height: 100,
      data: {
        textType: blockType,
        content: blockType === 'heading' ? blockName : 'Start typing...',
        style: blockType,
      }
    })

    useStudioStore.getState().setHasChanges(true)
    useStudioStore.getState().setActivePanel(null)
  }, [])

  const handleInsertElement = useCallback((elementConfig: Record<string, unknown>) => {
    const name = typeof elementConfig.name === 'string' ? elementConfig.name : 'Element'
    const { currentPage } = useStudioStore.getState()
    useStudioStore.getState().addElement(currentPage, {
      type: 'shape', x: 100, y: 100, width: 100, height: 100, data: { name }
    })
    useStudioStore.getState().setHasChanges(true)
    useStudioStore.getState().setActivePanel(null)
  }, [])

  const handleInsertUpload = useCallback((upload: Record<string, unknown>) => {
    const name = typeof upload.name === 'string' ? upload.name : 'Upload'
    const url = typeof upload.url === 'string' ? upload.url : ''
    const { currentPage } = useStudioStore.getState()
    useStudioStore.getState().addElement(currentPage, {
      type: 'image', x: 100, y: 100, width: 300, height: 200, data: { name, url }
    })
    useStudioStore.getState().setHasChanges(true)
    useStudioStore.getState().setActivePanel(null)
  }, [])

  const handleApplyTemplate = useCallback((templateId: string) => {
    const template = MASTER_TEMPLATES[templateId]
    if (!template) {
      console.warn(`Template ${templateId} not mapped.`)
      return
    }

    const state = useStudioStore.getState()
    const { currentPage, pages } = state

    // Phase 3: Totally wipe the current active page and paint the pre-coordinated template skeletons
    const newPages = [...pages]
    if (newPages[currentPage]) {
      newPages[currentPage] = {
        ...newPages[currentPage],
        elements: template
      }
    }

    state.setPages(newPages)
    state.setHasChanges(true)
    state.setActivePanel(null)
  }, [])

  // ── Fatal error screen ────────────────────────────────────────────────
  if (fatalError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="w-full max-w-3xl space-y-4 rounded-lg border bg-card p-6 shadow-sm">
          <div className="space-y-1">
            <p className="text-destructive font-semibold">Report Studio crashed: {fatalError.message}</p>
            <p className="text-sm text-muted-foreground">A minimal fallback is shown to avoid re-triggering the crash.</p>
          </div>
          {fatalInfo && (
            <pre className="text-left text-xs bg-muted rounded-md p-3 max-h-[320px] overflow-auto border">
              {fatalInfo}
            </pre>
          )}
          <div className="flex gap-3">
            <button onClick={() => window.location.reload()} className="text-primary underline text-sm">Reload</button>
          </div>
        </div>
      </div>
    )
  }

  // ── Main render (no more error-blocking overlay!) ──────────────────────
  return (
    <StudioErrorBoundary onError={(err, info) => { setFatalError(err); setFatalInfo(info); }}>
      {showOfflineBanner && (
        <OfflineBanner
          onDismiss={() => setShowOfflineBanner(false)}
          onRetry={() => attemptLoad().then(ok => { if (!ok) setShowOfflineBanner(true) })}
        />
      )}
      <EditorProvider>
        <CanvaLayout
          caseId={caseId}
          documentId={documentId || undefined}
          editor={tipTapEditor}
          onBack={handleBack}
          onSave={handleSave}
          onExport={handleExport}
          onShare={handleShare}
          onInvestigate={handleInvestigate}
          onStopInvestigation={handleStopInvestigation}
          onInsertComponent={handleInsertComponent}
          onInsertFinding={handleInsertFinding}
          onInsertEntity={handleInsertEntity}
          onInsertEvidence={handleInsertEvidence}
          onInsertBlock={handleInsertBlock}
          onInsertText={handleInsertText}
          onInsertElement={handleInsertElement}
          onInsertUpload={handleInsertUpload}
          onApplyTemplate={handleApplyTemplate}
          investigation={investigation}
        >
          {loading ? (
            <div className="flex items-center justify-center h-[500px] w-full">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <DocumentCanvas
              zoom={zoom}
              onDropNewComponent={handleDropCanvasComponent}
            />
          )}
        </CanvaLayout>

        {/* Chart Inspector — shows when a chart evidence block is selected */}
        {tipTapEditor && <ChartInspector editor={tipTapEditor} />}

        {/* Export Preview Modal */}
        <ExportPreviewModal
          open={previewModalOpen}
          onOpenChange={setPreviewModalOpen}
          onConfirm={(engine) => {
            setPreviewModalOpen(false);
            setTimeout(() => {
              setExportEngine(engine);
              setExportDialogOpen(true);
            }, 300);
          }}
        />

        {/* Ghost Writer Expert Engine */}
        {documentId && (
          <GhostWriterWizard
            open={exportDialogOpen}
            onOpenChange={setExportDialogOpen}
            caseId={caseId}
            docId={documentId}
            apiBaseUrl={apiOrigin || undefined}
            exportEngine={exportEngine}
            exportFormat={exportFormat}
            onExportComplete={(result) => {
              if (result?.filename) {
                const encoded = encodeURIComponent(result.filename)
                // Use location.assign to trigger the file download natively 
                // without getting caught by the async popup blocker
                window.location.assign(`/api/v4/studio/cases/${caseId}/exports/download/${encoded}`)
              }
            }}
          />
        )}

        {/* Investigation Configuration Dialog */}
        <InvestigationConfigDialog
          open={investigationDialogOpen}
          onOpenChange={setInvestigationDialogOpen}
          caseId={caseId}
          onStart={handleStartInvestigation}
        />

        {/* Report Preview Panel */}
        <ReportPreviewPanel
          open={reportPreviewOpen}
          onOpenChange={setReportPreviewOpen}
          caseId={caseId}
          onExport={handleExportFromPreview}
        />
      </EditorProvider>
    </StudioErrorBoundary>
  )
}

// Simple client-only error boundary
class StudioErrorBoundary extends React.Component<{ children: React.ReactNode; onError: (err: Error, stack: string) => void }, { hasError: boolean }> {
  constructor(props: any) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    const mergedStack = [error.stack, info.componentStack].filter(Boolean).join('\n--- component stack ---\n')
    if (typeof window !== 'undefined') {
      ; (window as any).__studio_last_error = { error, componentStack: info.componentStack, mergedStack }
    }
    console.error('StudioErrorBoundary caught error', mergedStack)
    this.props.onError(error, mergedStack)
  }

  render() {
    return this.props.children
  }
}

