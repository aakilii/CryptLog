'use client'

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useShallow } from 'zustand/react/shallow'

// Selection context types
export type SelectionType = 'text' | 'chart' | 'evidence' | 'image' | 'table' | 'none'

export interface SelectionContext {
  type: SelectionType
  nodeId?: string
  data?: Record<string, unknown>
}

export type ElementType = 'text' | 'component' | 'image' | 'shape'

export interface CanvasElement {
  id: string
  type: ElementType
  x: number
  y: number
  width: number
  height: number
  zIndex: number
  data: Record<string, any> // Holds module, componentId, filters, or TipTap JSON
  config?: Record<string, any> // High-fidelity inspector UI configuration toggles
  isOriginal?: boolean // Phase 4: Validates payload integrity
  contentHash?: string // Phase 4: Hash signature for verification
}

export interface PageMeta {
  id: string
  label: string
  elements: CanvasElement[]
  contentHash?: string
}

// Pseudo-hash generator for Phase 4 CoC validation
function generateDataHash(data: any): string {
  if (!data) return 'sha256-b0e271'
  const str = JSON.stringify(data)
  let hash = 0
  for (let i = 0, len = str.length; i < len; i++) {
    const chr = str.charCodeAt(i)
    hash = (hash << 5) - hash + chr
    hash |= 0
  }
  const hex = Math.abs(hash).toString(16).padStart(8, '0')
  return `sha256-${hex.substring(0, 8)}`
}

// Universal dynamic height resolution used by both canvas layout engine and PDF headless exporter
export function calculateElementMinHeight(element: CanvasElement): number {
  const filters = { ...(element.data.filters || {}), ...(element.config || {}) }
  const type = element.data.type || 'chart'
  
  if (type === 'shap-explanation' || type === 'anomaly') {
    const features = Array.isArray(element.data.data?.features) ? element.data.data.features : []
    const excluded = Array.isArray(filters.excludedFeatures) ? filters.excludedFeatures : []
    let visibleCount = features.filter((f: any) => !excluded.includes(f.name || f.feature)).length
    if (filters.topN) visibleCount = Math.min(visibleCount, Number(filters.topN))
    return 145 + (visibleCount * 56)
  }

  const displayMode = element.data.displayMode || 'full'
  const chartType = element.data.data?.chartType

  if (type === 'chart' && Array.isArray(element.data.data?.events)) {
    if (!chartType || chartType === 'timeline' || chartType === 'timeline-vertical-list') {
       const eventsCount = element.data.data.events.length
       let renderCount = eventsCount
       // Check if there are active severity filters
       if (filters.minRisk || filters.excludeInfo) {
          const minRisk = Number(filters.minRisk || 0)
          renderCount = element.data.data.events.filter((ev: any) => {
             const rs = Number(ev.risk_score || ev.score || 0)
             if (minRisk > 0 && rs < minRisk) return false
             if (filters.excludeInfo && (ev.severity || '').toUpperCase() === 'INFO') return false
             return true
          }).length
       }
       if (filters.topN) renderCount = Math.min(renderCount, Number(filters.topN))
       else renderCount = Math.min(10, renderCount)
       
       return 120 + (renderCount * 95)
    }
    return displayMode === 'compact' ? 240 : 350
  }

  if (type === 'network-flow' && Array.isArray(element.data.data?.flows)) {
    if (!chartType || (!chartType.includes('density') && !chartType.includes('volume'))) {
       const flowCount = element.data.data.flows.length
       const renderCount = filters.topN ? Math.min(Number(filters.topN), flowCount) : Math.min(20, flowCount)
       return 160 + (renderCount * 45)
    }
    return displayMode === 'compact' ? 300 : 400
  }

  if (type === 'network-flow' || type === 'correlation-graph') return 350
  if (type === 'chart' || element.type === 'component') return 250
  if (element.type === 'text') return 60
  if (element.type === 'image') return 100
  if (element.type === 'shape') return 50
  
  return 80
}

// Panel IDs matching icon rail
export type PanelId =
  | 'templates'
  | 'timeline'
  | 'anomaly'
  | 'correlation'
  | 'network'
  | 'crud'
  | 'depth'
  | 'vault'
  | 'uploads'
  | 'text'
  | 'elements'
  | 'evidence_binder'

export type FocusMode = 'Story' | 'Evidence' | 'Review' | 'Redact'

export interface EvidenceCard {
  id: string
  title: string
  description?: string
  evidence_ref: {
    case_id: string
    table: string
    pointers: string[]
    rowHashes: string[]
  }
  hash?: string
}

// Store interface
interface StudioStore {
  // Focus Mode (Storyboard)
  focusMode: FocusMode
  setFocusMode: (mode: FocusMode) => void

  // Evidence Binder State
  evidenceCards: EvidenceCard[]
  fetchEvidenceCards: (caseId: string) => Promise<void>
  addEvidenceCard: (caseId: string, card: Omit<EvidenceCard, 'hash'>) => Promise<void>
  
  // Panel state
  activePanel: PanelId | null
  setActivePanel: (id: PanelId | null) => void
  togglePanel: (id: PanelId) => void
  
  // Document state
  caseId: string | null
  documentId: string | null
  documentTitle: string
  setDocument: (caseId: string, docId: string, title: string) => void
  setDocumentTitle: (title: string) => void
  
  // Save state
  isSaving: boolean
  setSaving: (saving: boolean) => void
  hasChanges: boolean
  setHasChanges: (changes: boolean) => void
  lastSaved: Date | null
  setLastSaved: (date: Date) => void
  
  // Selection state
  selection: SelectionContext | null
  setSelection: (ctx: SelectionContext | null) => void
  
  // Zoom
  zoom: number
  setZoom: (zoom: number) => void
  zoomIn: () => void
  zoomOut: () => void
  
  // AI panel
  aiPanelOpen: boolean
  setAiPanelOpen: (open: boolean) => void
  toggleAiPanel: () => void
  aiMode: 'writer' | 'suggest' | 'validate'
  setAiMode: (mode: 'writer' | 'suggest' | 'validate') => void
  
  // View modes
  isFullscreen: boolean
  toggleFullscreen: () => void
  showRulers: boolean
  toggleRulers: () => void
  
  // Evidence tracking
  evidenceCount: number
  setEvidenceCount: (count: number) => void
  
  // Page management
  pages: PageMeta[]
  currentPage: number
  setPages: (pages: PageMeta[]) => void
  addPage: () => void
  deletePage: (pageIndex: number) => void
  setCurrentPage: (index: number) => void
  reorderPages: (from: number, to: number) => void

  // Panel badge counts (per-panel item counts for the rail)
  panelBadges: Partial<Record<PanelId, number>>
  setPanelBadge: (panelId: PanelId, count: number) => void

  // Global Time Slicing (Phase 1: Brush-&-Link)
  globalTimeSlice: { start: string | number, end: string | number } | null
  setGlobalTimeSlice: (slice: { start: string | number, end: string | number } | null) => void

  // Free-form Canvas Elements
  selectedElementIds: string[]
  setSelectedElements: (ids: string[]) => void
  addElement: (pageIndex: number, element: Omit<CanvasElement, 'id' | 'zIndex'>) => void
  updateElement: (pageIndex: number, elementId: string, updates: Partial<CanvasElement>) => void
  updateElementConfig: (pageIndex: number, elementId: string, updates: Record<string, any>) => void
  deleteElements: (pageIndex: number, elementIds: string[]) => void
  bringToFront: (pageIndex: number, elementId: string) => void
  sendToBack: (pageIndex: number, elementId: string) => void

  // Investigation state
  investigationOpen: boolean
  setInvestigationOpen: (open: boolean) => void
  investigationRunning: boolean
  setInvestigationRunning: (running: boolean) => void
  investigationProgress: number
  setInvestigationProgress: (progress: number) => void
}

export const useStudioStore = create<StudioStore>()(
  persist(
    (set) => ({
      // Focus mode
      focusMode: 'Story',
      setFocusMode: (mode) => set({ focusMode: mode }),

      // Evidence Binder
      evidenceCards: [],
      fetchEvidenceCards: async (caseId: string) => {
        try {
          const res = await fetch(`/api/cases/${caseId}/evidence-cards`)
          if (res.ok) {
            const data = await res.json()
            set({ evidenceCards: data })
          }
        } catch (e) {
          console.error("Failed to fetch evidence cards", e)
        }
      },
      addEvidenceCard: async (caseId: string, card) => {
        try {
          const res = await fetch(`/api/cases/${caseId}/evidence-cards`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(card)
          })
          if (res.ok) {
            const data = await res.json()
            set((state) => ({ evidenceCards: [...state.evidenceCards, data] }))
          }
        } catch (e) {
          console.error("Failed to add evidence card", e)
        }
      },

      // Panel state
      activePanel: null,
      setActivePanel: (id) => set({ activePanel: id }),
      togglePanel: (id) => set((state) => ({
        activePanel: state.activePanel === id ? null : id
      })),
      
      // Document state
      caseId: null,
      documentId: null,
      documentTitle: 'Untitled Report',
      setDocument: (caseId, docId, title) => set({
        caseId,
        documentId: docId,
        documentTitle: title,
        hasChanges: false,
      }),
      setDocumentTitle: (title) => set({ documentTitle: title, hasChanges: true }),
      
      // Save state
      isSaving: false,
      setSaving: (saving) => set({ isSaving: saving }),
      hasChanges: false,
      setHasChanges: (changes) => set({ hasChanges: changes }),
      lastSaved: null,
      setLastSaved: (date) => set({ lastSaved: date, hasChanges: false }),
      
      // Selection state
      selection: null,
      setSelection: (ctx) => set({ selection: ctx }),
      
      // Zoom
      zoom: 100,
      setZoom: (zoom) => set({ zoom: Math.min(200, Math.max(50, zoom)) }),
      zoomIn: () => set((state) => ({ zoom: Math.min(200, state.zoom + 10) })),
      zoomOut: () => set((state) => ({ zoom: Math.max(50, state.zoom - 10) })),
      
      // AI panel
      aiPanelOpen: true,
      setAiPanelOpen: (open) => set({ aiPanelOpen: open }),
      toggleAiPanel: () => set((state) => ({ aiPanelOpen: !state.aiPanelOpen })),
      aiMode: 'writer',
      setAiMode: (mode) => set({ aiMode: mode }),
      
      // View modes
      isFullscreen: false,
      toggleFullscreen: () => set((state) => ({ isFullscreen: !state.isFullscreen })),
      showRulers: false,
      toggleRulers: () => set((state) => ({ showRulers: !state.showRulers })),
      
      // Evidence tracking
      evidenceCount: 0,
      setEvidenceCount: (count) => set({ evidenceCount: count }),
      
      // Page management
      pages: [{ id: 'page-1', label: 'Page 1', elements: [] }],
      currentPage: 0,
      setPages: (pages) => set({ pages }),
      addPage: () => set((state) => {
        const num = state.pages.length + 1
        return {
          pages: [...state.pages, { id: `page-${Date.now()}`, label: `Page ${num}`, elements: [] }],
          currentPage: state.pages.length,
          hasChanges: true,
        }
      }),
      deletePage: (pageIndex) => set((state) => {
        if (state.pages.length <= 1) return state
        const newPages = state.pages.filter((_, i) => i !== pageIndex)
        return {
          pages: newPages,
          currentPage: Math.min(state.currentPage, newPages.length - 1),
          hasChanges: true,
        }
      }),
      setCurrentPage: (index) => set({ currentPage: index }),
      reorderPages: (from, to) => set((state) => {
        const newPages = [...state.pages]
        const [moved] = newPages.splice(from, 1)
        newPages.splice(to, 0, moved)
        return { pages: newPages, hasChanges: true }
      }),

      // Panel badge counts
      panelBadges: {},
      setPanelBadge: (panelId, count) => set((state) => ({
        panelBadges: { ...state.panelBadges, [panelId]: count }
      })),

      // Global Time Slicing (Phase 1)
      globalTimeSlice: null,
      setGlobalTimeSlice: (slice) => set({ globalTimeSlice: slice }),

      // Free-form Canvas Elements
      selectedElementIds: [],
      setSelectedElements: (ids) => set({ selectedElementIds: ids }),
      
      addElement: (pageIndex, elementData) => set((state) => {
        const newPages = [...state.pages]
        const page = newPages[pageIndex]
        if (!page) return state

        const maxZ = page.elements.reduce((max, el) => Math.max(max, el.zIndex), 0)

        // Phase 4: Compute initial hash and mark as original when spawned into layout
        const initialHash = ['evidence', 'component', 'chart', 'network-flow', 'anomaly'].includes(elementData.type || elementData.data?.type) 
          ? generateDataHash(elementData.data?.data) 
          : undefined

        const newElement: CanvasElement = {
          ...elementData,
          id: `el-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
          zIndex: maxZ + 1,
          ...(initialHash ? { isOriginal: true, contentHash: initialHash } : {})
        }

        newPages[pageIndex] = {
          ...page,
          elements: [...page.elements, newElement]
        }
        return { pages: newPages, hasChanges: true, selectedElementIds: [newElement.id] }
      }),

      updateElement: (pageIndex, elementId, updates) => set((state) => {
        const newPages = [...state.pages]
        const page = newPages[pageIndex]
        if (!page) return state
        
        newPages[pageIndex] = {
          ...page,
          elements: page.elements.map(el => 
            el.id === elementId ? { ...el, ...updates } : el
          )
        }
        return { pages: newPages, hasChanges: true }
      }),

      updateElementConfig: (pageIndex, elementId, configUpdates) => set((state) => {
        const newPages = [...state.pages]
        const page = newPages[pageIndex]
        if (!page) return state
        
        newPages[pageIndex] = {
          ...page,
          elements: page.elements.map(el => 
            el.id === elementId 
              ? { 
                  ...el, 
                  config: { ...(el.config || {}), ...configUpdates },
                  // Phase 4: Manipulating data configuration instantly breaks Chain of Custody signature
                  isOriginal: false
                } : el
          )
        }
        return { pages: newPages, hasChanges: true }
      }),

      deleteElements: (pageIndex, elementIds) => set((state) => {
        const newPages = [...state.pages]
        const page = newPages[pageIndex]
        if (!page) return state
        
        newPages[pageIndex] = {
          ...page,
          elements: page.elements.filter(el => !elementIds.includes(el.id))
        }
        return { 
          pages: newPages, 
          hasChanges: true,
          selectedElementIds: state.selectedElementIds.filter(id => !elementIds.includes(id)) 
        }
      }),
      
      bringToFront: (pageIndex, elementId) => set((state) => {
        const newPages = [...state.pages]
        const page = newPages[pageIndex]
        if (!page) return state

        const maxZ = page.elements.reduce((max, el) => Math.max(max, el.zIndex), 0)
        newPages[pageIndex] = {
          ...page,
          elements: page.elements.map(el => 
            el.id === elementId ? { ...el, zIndex: maxZ + 1 } : el
          )
        }
        return { pages: newPages, hasChanges: true }
      }),
      
      sendToBack: (pageIndex, elementId) => set((state) => {
        const newPages = [...state.pages]
        const page = newPages[pageIndex]
        if (!page) return state

        const minZ = page.elements.reduce((min, el) => Math.min(min, el.zIndex), 0)
        newPages[pageIndex] = {
          ...page,
          elements: page.elements.map(el => 
            el.id === elementId ? { ...el, zIndex: minZ - 1 } : el
          )
        }
        return { pages: newPages, hasChanges: true }
      }),

      // Investigation state
      investigationOpen: false,
      setInvestigationOpen: (open) => set({ investigationOpen: open }),
      investigationRunning: false,
      setInvestigationRunning: (running) => set({ investigationRunning: running }),
      investigationProgress: 0,
      setInvestigationProgress: (progress) => set({ investigationProgress: progress }),
    }),
    {
      name: 'nflip-studio-store',
      partialize: (state) => ({
        zoom: state.zoom,
        aiPanelOpen: state.aiPanelOpen,
        showRulers: state.showRulers,
      }),
    }
  )
)

// Selector hooks for performance
export const useActivePanel = () => useStudioStore((state) => state.activePanel)
export const useSelection = () => useStudioStore((state) => state.selection)
export const useZoom = () => useStudioStore((state) => state.zoom)
export const useAiPanel = () => useStudioStore(useShallow((state) => ({
  isOpen: state.aiPanelOpen,
  mode: state.aiMode,
  toggle: state.toggleAiPanel,
  setMode: state.setAiMode,
})))
export const useSaveState = () => useStudioStore(useShallow((state) => ({
  isSaving: state.isSaving,
  hasChanges: state.hasChanges,
  lastSaved: state.lastSaved,
})))
