'use client'

import React, { createContext, useContext, useState, useCallback, useMemo } from 'react'
import { ModuleSource, EvidenceType } from '@operation-room/components/tiptap/EvidenceBlockNode'

// ═══════════════════════════════════════════════════════════════════════════
// Cross-Reference System for Evidence Citations
// ═══════════════════════════════════════════════════════════════════════════

export interface CrossReference {
  id: string
  type: 'evidence' | 'figure' | 'table' | 'appendix'
  label: string
  displayId: string  // e.g., "EVD-TL-001", "Figure 3", "Table 2"
  source: ModuleSource
  evidenceType?: EvidenceType
  pageRef?: number
  sectionRef?: string
  hash?: string
  timestamp: string
  metadata?: Record<string, any>
}

export interface Citation {
  id: string
  refId: string  // Points to CrossReference.id
  context: string  // Surrounding text
  position: number  // Character position in document
  sectionId?: string
}

interface CrossReferenceContextType {
  // References
  references: Map<string, CrossReference>
  addReference: (ref: Omit<CrossReference, 'id' | 'timestamp'>) => string
  updateReference: (id: string, updates: Partial<CrossReference>) => void
  removeReference: (id: string) => void
  getReference: (id: string) => CrossReference | undefined
  
  // Citations
  citations: Map<string, Citation>
  addCitation: (refId: string, context: string, position: number, sectionId?: string) => string
  removeCitation: (id: string) => void
  getCitationsForRef: (refId: string) => Citation[]
  
  // Lookups
  getByDisplayId: (displayId: string) => CrossReference | undefined
  getByType: (type: CrossReference['type']) => CrossReference[]
  getBySource: (source: ModuleSource) => CrossReference[]
  
  // Counters
  getNextFigureNumber: () => number
  getNextTableNumber: () => number
  getNextEvidenceNumber: (source: ModuleSource) => number
  
  // Validation
  validateAllCitations: () => { valid: Citation[]; invalid: Citation[] }
  
  // Export
  generateCitationAppendix: () => CrossReference[]
  toJSON: () => string
  fromJSON: (json: string) => void
  
  // Reset
  clear: () => void
}

const CrossReferenceContext = createContext<CrossReferenceContextType | null>(null)

// Source abbreviations for display IDs
const SOURCE_ABBREV: Record<ModuleSource, string> = {
  timeline: 'TL',
  anomaly: 'AN',
  correlation: 'CR',
  crud: 'CD',
  network: 'NW',
  depth: 'DP',
  case: 'CS',
}

export function CrossReferenceProvider({ children }: { children: React.ReactNode }) {
  const [references, setReferences] = useState<Map<string, CrossReference>>(new Map())
  const [citations, setCitations] = useState<Map<string, Citation>>(new Map())
  const [figureCounter, setFigureCounter] = useState(1)
  const [tableCounter, setTableCounter] = useState(1)
  const [evidenceCounters, setEvidenceCounters] = useState<Record<ModuleSource, number>>({
    timeline: 1,
    anomaly: 1,
    correlation: 1,
    crud: 1,
    network: 1,
    depth: 1,
    case: 1,
  })

  // Generate unique ID
  const generateId = useCallback(() => {
    return `ref-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }, [])

  // Add a new reference
  const addReference = useCallback((ref: Omit<CrossReference, 'id' | 'timestamp'>) => {
    const id = generateId()
    const newRef: CrossReference = {
      ...ref,
      id,
      timestamp: new Date().toISOString(),
    }
    
    setReferences(prev => new Map(prev).set(id, newRef))
    return id
  }, [generateId])

  // Update existing reference
  const updateReference = useCallback((id: string, updates: Partial<CrossReference>) => {
    setReferences(prev => {
      const map = new Map(prev)
      const existing = map.get(id)
      if (existing) {
        map.set(id, { ...existing, ...updates })
      }
      return map
    })
  }, [])

  // Remove reference and its citations
  const removeReference = useCallback((id: string) => {
    setReferences(prev => {
      const map = new Map(prev)
      map.delete(id)
      return map
    })
    
    // Also remove all citations pointing to this reference
    setCitations(prev => {
      const map = new Map(prev)
      const toDelete: string[] = []
      map.forEach((citation, citationId) => {
        if (citation.refId === id) {
          toDelete.push(citationId)
        }
      })
      toDelete.forEach(cid => map.delete(cid))
      return map
    })
  }, [])

  // Get reference by ID
  const getReference = useCallback((id: string) => {
    return references.get(id)
  }, [references])

  // Add citation
  const addCitation = useCallback((refId: string, context: string, position: number, sectionId?: string) => {
    const id = `cite-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    const citation: Citation = { id, refId, context, position, sectionId }
    setCitations(prev => new Map(prev).set(id, citation))
    return id
  }, [])

  // Remove citation
  const removeCitation = useCallback((id: string) => {
    setCitations(prev => {
      const map = new Map(prev)
      map.delete(id)
      return map
    })
  }, [])

  // Get all citations for a reference
  const getCitationsForRef = useCallback((refId: string) => {
    return Array.from(citations.values()).filter(c => c.refId === refId)
  }, [citations])

  // Lookup by display ID
  const getByDisplayId = useCallback((displayId: string) => {
    return Array.from(references.values()).find(r => r.displayId === displayId)
  }, [references])

  // Lookup by type
  const getByType = useCallback((type: CrossReference['type']) => {
    return Array.from(references.values()).filter(r => r.type === type)
  }, [references])

  // Lookup by source
  const getBySource = useCallback((source: ModuleSource) => {
    return Array.from(references.values()).filter(r => r.source === source)
  }, [references])

  // Counter helpers
  const getNextFigureNumber = useCallback(() => {
    const num = figureCounter
    setFigureCounter(n => n + 1)
    return num
  }, [figureCounter])

  const getNextTableNumber = useCallback(() => {
    const num = tableCounter
    setTableCounter(n => n + 1)
    return num
  }, [tableCounter])

  const getNextEvidenceNumber = useCallback((source: ModuleSource) => {
    const num = evidenceCounters[source]
    setEvidenceCounters(prev => ({ ...prev, [source]: prev[source] + 1 }))
    return num
  }, [evidenceCounters])

  // Validate all citations point to valid references
  const validateAllCitations = useCallback(() => {
    const valid: Citation[] = []
    const invalid: Citation[] = []
    
    citations.forEach(citation => {
      if (references.has(citation.refId)) {
        valid.push(citation)
      } else {
        invalid.push(citation)
      }
    })
    
    return { valid, invalid }
  }, [citations, references])

  // Generate citation appendix (sorted by display ID)
  const generateCitationAppendix = useCallback(() => {
    return Array.from(references.values())
      .sort((a, b) => a.displayId.localeCompare(b.displayId))
  }, [references])

  // Export to JSON
  const toJSON = useCallback(() => {
    return JSON.stringify({
      references: Array.from(references.entries()),
      citations: Array.from(citations.entries()),
      counters: {
        figure: figureCounter,
        table: tableCounter,
        evidence: evidenceCounters,
      }
    })
  }, [references, citations, figureCounter, tableCounter, evidenceCounters])

  // Import from JSON
  const fromJSON = useCallback((json: string) => {
    try {
      const data = JSON.parse(json)
      setReferences(new Map(data.references))
      setCitations(new Map(data.citations))
      setFigureCounter(data.counters.figure || 1)
      setTableCounter(data.counters.table || 1)
      setEvidenceCounters(data.counters.evidence || {
        timeline: 1, anomaly: 1, correlation: 1, crud: 1, network: 1, depth: 1, case: 1
      })
    } catch (e) {
      console.error('Failed to parse cross-reference data:', e)
    }
  }, [])

  // Clear all
  const clear = useCallback(() => {
    setReferences(new Map())
    setCitations(new Map())
    setFigureCounter(1)
    setTableCounter(1)
    setEvidenceCounters({
      timeline: 1, anomaly: 1, correlation: 1, crud: 1, network: 1, depth: 1, case: 1
    })
  }, [])

  const value = useMemo(() => ({
    references,
    addReference,
    updateReference,
    removeReference,
    getReference,
    citations,
    addCitation,
    removeCitation,
    getCitationsForRef,
    getByDisplayId,
    getByType,
    getBySource,
    getNextFigureNumber,
    getNextTableNumber,
    getNextEvidenceNumber,
    validateAllCitations,
    generateCitationAppendix,
    toJSON,
    fromJSON,
    clear,
  }), [
    references, addReference, updateReference, removeReference, getReference,
    citations, addCitation, removeCitation, getCitationsForRef,
    getByDisplayId, getByType, getBySource,
    getNextFigureNumber, getNextTableNumber, getNextEvidenceNumber,
    validateAllCitations, generateCitationAppendix,
    toJSON, fromJSON, clear
  ])

  return (
    <CrossReferenceContext.Provider value={value}>
      {children}
    </CrossReferenceContext.Provider>
  )
}

export function useCrossReferences() {
  const context = useContext(CrossReferenceContext)
  if (!context) {
    throw new Error('useCrossReferences must be used within a CrossReferenceProvider')
  }
  return context
}

// ═══════════════════════════════════════════════════════════════════════════
// Utility: Generate display ID for evidence
// ═══════════════════════════════════════════════════════════════════════════

export function generateEvidenceDisplayId(source: ModuleSource, number: number): string {
  return `EVD-${SOURCE_ABBREV[source]}-${String(number).padStart(3, '0')}`
}

export function generateFigureDisplayId(number: number): string {
  return `Figure ${number}`
}

export function generateTableDisplayId(number: number): string {
  return `Table ${number}`
}

// ═══════════════════════════════════════════════════════════════════════════
// Component: Inline Citation Reference
// ═══════════════════════════════════════════════════════════════════════════

interface CitationRefProps {
  refId: string
  className?: string
}

export function CitationRef({ refId, className }: CitationRefProps) {
  const { getReference } = useCrossReferences()
  const ref = getReference(refId)
  
  if (!ref) {
    return <span className={`text-red-500 ${className}`}>[Invalid Ref]</span>
  }
  
  return (
    <span 
      className={`inline-flex items-center px-1.5 py-0.5 bg-blue-100 text-blue-800 text-xs font-mono rounded cursor-pointer hover:bg-blue-200 transition-colors ${className}`}
      title={`${ref.label} (${ref.source})`}
      onClick={() => {
        // Dispatch event to navigate to evidence
        window.dispatchEvent(new CustomEvent('evidence:navigate', {
          detail: { refId: ref.id, source: ref.source }
        }))
      }}
    >
      [{ref.displayId}]
    </span>
  )
}

// ═══════════════════════════════════════════════════════════════════════════
// Component: Reference Appendix
// ═══════════════════════════════════════════════════════════════════════════

interface ReferenceAppendixProps {
  className?: string
}

export function ReferenceAppendix({ className }: ReferenceAppendixProps) {
  const { generateCitationAppendix, getCitationsForRef } = useCrossReferences()
  const refs = generateCitationAppendix()
  
  if (refs.length === 0) {
    return (
      <div className={`text-muted-foreground text-sm ${className}`}>
        No evidence references in this document.
      </div>
    )
  }
  
  return (
    <div className={`space-y-4 ${className}`}>
      <h3 className="text-lg font-semibold">Evidence Reference Appendix</h3>
      <div className="divide-y">
        {refs.map(ref => {
          const citations = getCitationsForRef(ref.id)
          return (
            <div key={ref.id} className="py-3">
              <div className="flex items-start justify-between">
                <div>
                  <span className="font-mono text-sm font-medium text-blue-600">
                    [{ref.displayId}]
                  </span>
                  <span className="ml-2 text-sm">{ref.label}</span>
                </div>
                <span className="text-xs text-muted-foreground">
                  {citations.length} citation{citations.length !== 1 ? 's' : ''}
                </span>
              </div>
              {ref.hash && (
                <div className="mt-1 text-xs text-muted-foreground font-mono">
                  SHA-256: {ref.hash.substring(0, 16)}...
                </div>
              )}
              {ref.pageRef && (
                <div className="mt-1 text-xs text-muted-foreground">
                  Page {ref.pageRef}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
