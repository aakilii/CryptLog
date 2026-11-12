'use client'

import * as React from 'react'
import type { EvidenceBlockData, EvidenceBlockType } from '@operation-room/components/evidence/EvidenceBlock'
import type { ModuleType } from '@operation-room/lib/utils'

// ============================================================================
// Types
// ============================================================================

export interface FigureEntry {
  figureNumber: number
  blockId: string
  blockType: EvidenceBlockType
  module: ModuleType
  caption: string
  pageEstimate?: number
  sectionId?: string
  runId?: string
  dataHash?: string
  insertedAt: string
  lastUpdated: string
}

export interface FigureRegistryState {
  figures: Map<string, FigureEntry>  // blockId -> FigureEntry
  nextFigureNumber: number
  lastUpdated: string
}

export interface FigureReference {
  figureNumber: number
  caption: string
  pageEstimate?: number
}

// ============================================================================
// Figure Registry Context
// ============================================================================

interface FigureRegistryContextType {
  // State
  figures: FigureEntry[]
  
  // Actions
  registerFigure: (block: EvidenceBlockData, sectionId?: string) => number
  unregisterFigure: (blockId: string) => void
  updateFigureCaption: (blockId: string, caption: string) => void
  updateFigureOrder: (orderedBlockIds: string[]) => void
  getFigureByBlockId: (blockId: string) => FigureEntry | undefined
  getFigureByNumber: (figureNumber: number) => FigureEntry | undefined
  getFiguresForModule: (module: ModuleType) => FigureEntry[]
  getFiguresForSection: (sectionId: string) => FigureEntry[]
  
  // Export
  exportFigureList: () => string  // Markdown list of figures
  exportTableOfFigures: () => FigureTableEntry[]
  
  // Cross-reference helpers
  formatFigureRef: (figureNumber: number) => string
  parseFigureRefs: (text: string) => FigureReference[]
}

export interface FigureTableEntry {
  number: number
  caption: string
  module: string
  page?: number
}

const FigureRegistryContext = React.createContext<FigureRegistryContextType | null>(null)

// ============================================================================
// Provider
// ============================================================================

interface FigureRegistryProviderProps {
  children: React.ReactNode
  initialFigures?: FigureEntry[]
  onFiguresChange?: (figures: FigureEntry[]) => void
}

export function FigureRegistryProvider({
  children,
  initialFigures = [],
  onFiguresChange,
}: FigureRegistryProviderProps) {
  const [figures, setFigures] = React.useState<Map<string, FigureEntry>>(() => {
    const map = new Map<string, FigureEntry>()
    initialFigures.forEach(fig => map.set(fig.blockId, fig))
    return map
  })
  
  const [nextFigureNumber, setNextFigureNumber] = React.useState(() => {
    if (initialFigures.length === 0) return 1
    return Math.max(...initialFigures.map(f => f.figureNumber)) + 1
  })

  // Notify parent of changes
  React.useEffect(() => {
    const figuresList = Array.from(figures.values()).sort((a, b) => a.figureNumber - b.figureNumber)
    onFiguresChange?.(figuresList)
  }, [figures, onFiguresChange])

  // Register a new figure, returns assigned figure number
  const registerFigure = React.useCallback((block: EvidenceBlockData, sectionId?: string): number => {
    const figureNumber = nextFigureNumber
    
    const entry: FigureEntry = {
      figureNumber,
      blockId: block.blockId,
      blockType: block.blockType,
      module: block.module,
      caption: block.caption,
      sectionId,
      runId: block.runId,
      dataHash: block.dataHash,
      insertedAt: new Date().toISOString(),
      lastUpdated: new Date().toISOString(),
    }

    setFigures(prev => new Map(prev).set(block.blockId, entry))
    setNextFigureNumber(prev => prev + 1)
    
    return figureNumber
  }, [nextFigureNumber])

  // Unregister a figure
  const unregisterFigure = React.useCallback((blockId: string) => {
    setFigures(prev => {
      const next = new Map(prev)
      const removed = next.get(blockId)
      next.delete(blockId)
      
      // Renumber remaining figures if needed
      if (removed) {
        const sorted = Array.from(next.values()).sort((a, b) => a.figureNumber - b.figureNumber)
        sorted.forEach((fig, idx) => {
          fig.figureNumber = idx + 1
          fig.lastUpdated = new Date().toISOString()
        })
        const renumbered = new Map<string, FigureEntry>()
        sorted.forEach(fig => renumbered.set(fig.blockId, fig))
        return renumbered
      }
      
      return next
    })
  }, [])

  // Update figure caption
  const updateFigureCaption = React.useCallback((blockId: string, caption: string) => {
    setFigures(prev => {
      const next = new Map(prev)
      const entry = next.get(blockId)
      if (entry) {
        next.set(blockId, { 
          ...entry, 
          caption, 
          lastUpdated: new Date().toISOString() 
        })
      }
      return next
    })
  }, [])

  // Reorder figures based on new block order
  const updateFigureOrder = React.useCallback((orderedBlockIds: string[]) => {
    setFigures(prev => {
      const next = new Map<string, FigureEntry>()
      let figNum = 1
      
      orderedBlockIds.forEach(blockId => {
        const entry = prev.get(blockId)
        if (entry) {
          next.set(blockId, {
            ...entry,
            figureNumber: figNum++,
            lastUpdated: new Date().toISOString(),
          })
        }
      })
      
      return next
    })
  }, [])

  // Getters
  const getFigureByBlockId = React.useCallback((blockId: string) => {
    return figures.get(blockId)
  }, [figures])

  const getFigureByNumber = React.useCallback((figureNumber: number) => {
    return Array.from(figures.values()).find(f => f.figureNumber === figureNumber)
  }, [figures])

  const getFiguresForModule = React.useCallback((module: ModuleType) => {
    return Array.from(figures.values())
      .filter(f => f.module === module)
      .sort((a, b) => a.figureNumber - b.figureNumber)
  }, [figures])

  const getFiguresForSection = React.useCallback((sectionId: string) => {
    return Array.from(figures.values())
      .filter(f => f.sectionId === sectionId)
      .sort((a, b) => a.figureNumber - b.figureNumber)
  }, [figures])

  // Export list as markdown
  const exportFigureList = React.useCallback(() => {
    const sorted = Array.from(figures.values()).sort((a, b) => a.figureNumber - b.figureNumber)
    
    const lines = sorted.map(fig => {
      let line = `Figure ${fig.figureNumber}: ${fig.caption}`
      if (fig.pageEstimate) {
        line += ` (p. ${fig.pageEstimate})`
      }
      return line
    })
    
    return lines.join('\n')
  }, [figures])

  // Export table of figures
  const exportTableOfFigures = React.useCallback((): FigureTableEntry[] => {
    return Array.from(figures.values())
      .sort((a, b) => a.figureNumber - b.figureNumber)
      .map(fig => ({
        number: fig.figureNumber,
        caption: fig.caption,
        module: fig.module,
        page: fig.pageEstimate,
      }))
  }, [figures])

  // Format a figure reference (e.g., "Figure 3")
  const formatFigureRef = React.useCallback((figureNumber: number): string => {
    return `Figure ${figureNumber}`
  }, [])

  // Parse @fig:N references from text
  const parseFigureRefs = React.useCallback((text: string): FigureReference[] => {
    const regex = /@fig:(\d+)/g
    const refs: FigureReference[] = []
    let match: RegExpExecArray | null
    
    while ((match = regex.exec(text)) !== null) {
      const figNum = parseInt(match[1], 10)
      const figure = getFigureByNumber(figNum)
      if (figure) {
        refs.push({
          figureNumber: figNum,
          caption: figure.caption,
          pageEstimate: figure.pageEstimate,
        })
      }
    }
    
    return refs
  }, [getFigureByNumber])

  // Sorted figures list for consumers
  const figuresList = React.useMemo(() => {
    return Array.from(figures.values()).sort((a, b) => a.figureNumber - b.figureNumber)
  }, [figures])

  const value: FigureRegistryContextType = {
    figures: figuresList,
    registerFigure,
    unregisterFigure,
    updateFigureCaption,
    updateFigureOrder,
    getFigureByBlockId,
    getFigureByNumber,
    getFiguresForModule,
    getFiguresForSection,
    exportFigureList,
    exportTableOfFigures,
    formatFigureRef,
    parseFigureRefs,
  }

  return (
    <FigureRegistryContext.Provider value={value}>
      {children}
    </FigureRegistryContext.Provider>
  )
}

// ============================================================================
// Hook
// ============================================================================

export function useFigureRegistry() {
  const context = React.useContext(FigureRegistryContext)
  if (!context) {
    throw new Error('useFigureRegistry must be used within FigureRegistryProvider')
  }
  return context
}

// ============================================================================
// Table of Figures Component
// ============================================================================

interface TableOfFiguresProps {
  className?: string
  showPages?: boolean
  showModules?: boolean
  onFigureClick?: (figureNumber: number) => void
}

export function TableOfFigures({
  className,
  showPages = true,
  showModules = true,
  onFigureClick,
}: TableOfFiguresProps) {
  const { figures } = useFigureRegistry()

  if (figures.length === 0) {
    return (
      <div className={className}>
        <p className="text-sm text-muted-foreground italic">No figures in document</p>
      </div>
    )
  }

  return (
    <div className={className}>
      <h3 className="text-sm font-semibold mb-3">Table of Figures</h3>
      <div className="space-y-2">
        {figures.map(fig => (
          <div
            key={fig.blockId}
            className={`flex items-baseline gap-2 text-sm ${
              onFigureClick ? 'cursor-pointer hover:text-primary' : ''
            }`}
            onClick={() => onFigureClick?.(fig.figureNumber)}
          >
            <span className="font-medium shrink-0">Figure {fig.figureNumber}</span>
            <span className="flex-1 text-muted-foreground truncate">{fig.caption}</span>
            {showModules && (
              <span className="text-xs text-muted-foreground shrink-0">[{fig.module}]</span>
            )}
            {showPages && fig.pageEstimate && (
              <span className="text-xs text-muted-foreground shrink-0">p.{fig.pageEstimate}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================================================
// Figure Reference Link Component
// ============================================================================

interface FigureRefProps {
  figureNumber: number
  onClick?: () => void
  className?: string
}

export function FigureRef({ figureNumber, onClick, className }: FigureRefProps) {
  const { getFigureByNumber, formatFigureRef } = useFigureRegistry()
  const figure = getFigureByNumber(figureNumber)

  if (!figure) {
    return (
      <span className={`text-destructive ${className}`}>
        [Invalid figure reference: {figureNumber}]
      </span>
    )
  }

  return (
    <span
      className={`text-primary hover:underline cursor-pointer ${className}`}
      onClick={onClick}
      title={figure.caption}
    >
      {formatFigureRef(figureNumber)}
    </span>
  )
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Generate a unique block ID
 */
export function generateBlockId(): string {
  return `blk_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 9)}`
}

/**
 * Calculate SHA-256 hash for data integrity
 */
export async function calculateDataHash(data: any): Promise<string> {
  const text = JSON.stringify(data)
  const encoder = new TextEncoder()
  const dataBuffer = encoder.encode(text)
  const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
}

/**
 * Serialize figure registry for persistence
 */
export function serializeFigureRegistry(figures: FigureEntry[]): string {
  return JSON.stringify({
    version: 1,
    figures,
    exportedAt: new Date().toISOString(),
  })
}

/**
 * Deserialize figure registry from storage
 */
export function deserializeFigureRegistry(json: string): FigureEntry[] {
  try {
    const data = JSON.parse(json)
    if (data.version === 1 && Array.isArray(data.figures)) {
      return data.figures
    }
    return []
  } catch {
    return []
  }
}
