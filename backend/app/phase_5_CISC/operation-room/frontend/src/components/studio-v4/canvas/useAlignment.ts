'use client'

/**
 * useAlignment - Hook for Canva-like alignment system
 * 
 * Phase 4: Provides alignment state management and snap calculations
 * during element drag operations.
 */

import { useState, useCallback, useRef, useMemo } from 'react'
import { 
  AlignmentEngine, 
  AlignmentGuide, 
  ElementDistance, 
  getElementBounds,
  ALIGNMENT_CONFIG
} from './AlignmentEngine'
import { CanvasElement } from '../store/useStudioStore'

interface UseAlignmentOptions {
  canvasWidth?: number
  canvasHeight?: number
  enabled?: boolean
  config?: Partial<typeof ALIGNMENT_CONFIG>
}

interface UseAlignmentReturn {
  // State
  activeGuides: AlignmentGuide[]
  distances: ElementDistance[]
  isDragging: boolean
  
  // Methods
  startDrag: (elementId: string) => void
  updateDrag: (
    movingElement: CanvasElement,
    newX: number,
    newY: number,
    allElements: CanvasElement[]
  ) => { snappedX: number; snappedY: number }
  endDrag: () => void
  
  // Alignment actions
  alignSelected: (
    elements: CanvasElement[],
    alignment: 'left' | 'center' | 'right' | 'top' | 'middle' | 'bottom' | 'distribute-h' | 'distribute-v'
  ) => CanvasElement[]
  
  // Recommendations
  getRecommendations: (
    element: CanvasElement,
    otherElements: CanvasElement[]
  ) => { gap: number; direction: 'horizontal' | 'vertical'; message: string }[]
  
  // Config
  toggleSnapToGrid: () => void
  toggleSnapToElements: () => void
  setSnapToGridEnabled: (enabled: boolean) => void
  setSnapToElementsEnabled: (enabled: boolean) => void
  isSnapToGridEnabled: boolean
  isSnapToElementsEnabled: boolean
}

export function useAlignment(options: UseAlignmentOptions = {}): UseAlignmentReturn {
  const {
    canvasWidth = 794,
    canvasHeight = 1123,
    enabled = true,
    config: customConfig
  } = options
  
  // Memoized alignment engine
  const engine = useMemo(() => {
    return new AlignmentEngine(canvasWidth, canvasHeight, customConfig)
  }, [canvasWidth, canvasHeight, customConfig])
  
  // State
  const [activeGuides, setActiveGuides] = useState<AlignmentGuide[]>([])
  const [distances, setDistances] = useState<ElementDistance[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [snapToGrid, setSnapToGrid] = useState(ALIGNMENT_CONFIG.snapToGrid)
  const [snapToElements, setSnapToElements] = useState(ALIGNMENT_CONFIG.snapToElements)
  
  // Track current dragging element
  const draggingElementId = useRef<string | null>(null)
  
  /**
   * Start a drag operation
   */
  const startDrag = useCallback((elementId: string) => {
    if (!enabled) return
    draggingElementId.current = elementId
    setIsDragging(true)
  }, [enabled])
  
  /**
   * Update drag position with snap calculation
   */
  const updateDrag = useCallback((
    movingElement: CanvasElement,
    newX: number,
    newY: number,
    allElements: CanvasElement[]
  ): { snappedX: number; snappedY: number } => {
    if (!enabled || !isDragging) {
      return { snappedX: newX, snappedY: newY }
    }

    engine.setConfig({
      snapToGrid,
      snapToElements,
    })
    
    // Get bounds for all elements
    const movingBounds = getElementBounds(movingElement)
    const otherBounds = allElements
      .filter(el => el.id !== movingElement.id)
      .map(getElementBounds)
    
    // Calculate snap
    const result = engine.calculateSnap(
      movingBounds,
      otherBounds,
      newX,
      newY
    )
    
    // Update state
    setActiveGuides(result.activeGuides)
    setDistances(result.distances)
    
    return {
      snappedX: result.snappedX,
      snappedY: result.snappedY
    }
  }, [enabled, isDragging, engine, snapToGrid, snapToElements])
  
  /**
   * End drag operation
   */
  const endDrag = useCallback(() => {
    draggingElementId.current = null
    setIsDragging(false)
    setActiveGuides([])
    setDistances([])
  }, [])
  
  /**
   * Align selected elements
   */
  const alignSelected = useCallback((
    elements: CanvasElement[],
    alignment: 'left' | 'center' | 'right' | 'top' | 'middle' | 'bottom' | 'distribute-h' | 'distribute-v'
  ): CanvasElement[] => {
    if (!enabled || elements.length < 2) return elements
    return engine.alignElements(elements, alignment)
  }, [enabled, engine])
  
  /**
   * Get spacing recommendations for an element
   */
  const getRecommendations = useCallback((
    element: CanvasElement,
    otherElements: CanvasElement[]
  ): { gap: number; direction: 'horizontal' | 'vertical'; message: string }[] => {
    if (!enabled) return []
    
    const movingBounds = getElementBounds(element)
    const otherBounds = otherElements
      .filter(el => el.id !== element.id)
      .map(getElementBounds)
    
    return engine.getSpacingRecommendations(movingBounds, otherBounds)
  }, [enabled, engine])
  
  /**
   * Toggle snap to grid
   */
  const toggleSnapToGrid = useCallback(() => {
    setSnapToGrid(prev => !prev)
  }, [])
  
  /**
   * Toggle snap to elements
   */
  const toggleSnapToElements = useCallback(() => {
    setSnapToElements(prev => !prev)
  }, [])

  const setSnapToGridEnabled = useCallback((enabled: boolean) => {
    setSnapToGrid(enabled)
  }, [])

  const setSnapToElementsEnabled = useCallback((enabled: boolean) => {
    setSnapToElements(enabled)
  }, [])
  
  return {
    // State
    activeGuides,
    distances,
    isDragging,
    
    // Methods
    startDrag,
    updateDrag,
    endDrag,
    
    // Alignment actions
    alignSelected,
    
    // Recommendations
    getRecommendations,
    
    // Config
    toggleSnapToGrid,
    toggleSnapToElements,
    setSnapToGridEnabled,
    setSnapToElementsEnabled,
    isSnapToGridEnabled: snapToGrid,
    isSnapToElementsEnabled: snapToElements,
  }
}

export default useAlignment
