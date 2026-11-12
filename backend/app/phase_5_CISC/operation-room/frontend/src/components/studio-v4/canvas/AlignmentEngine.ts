'use client'

/**
 * AlignmentEngine - Canva-like alignment and snapping system
 * 
 * Phase 4: Provides smart alignment guides, snap-to-grid, and element alignment
 * recommendations for the Report Studio canvas.
 */

import { CanvasElement } from '../store/useStudioStore'

// Alignment configuration
export const ALIGNMENT_CONFIG = {
  snapThreshold: 8,        // Pixels to snap
  gridSize: 10,            // Grid snap size
  showGuides: true,        // Show alignment guides
  snapToGrid: true,        // Enable grid snapping
  snapToElements: true,    // Enable element snapping
  snapToCenter: true,      // Enable center line snapping
  marginGuide: 20,         // Page margin guide distance
}

// Alignment guide types
export type GuideType = 'vertical' | 'horizontal' | 'center-h' | 'center-v' | 'margin' | 'element'

export interface AlignmentGuide {
  id: string
  type: GuideType
  position: number           // X for vertical, Y for horizontal
  label?: string             // Distance label
  sourceElementId?: string   // Element this guide relates to
  isActive: boolean
}

export interface SnapResult {
  snappedX: number
  snappedY: number
  deltaX: number
  deltaY: number
  activeGuides: AlignmentGuide[]
  distances: ElementDistance[]
}

export interface ElementDistance {
  elementId: string
  edge: 'top' | 'right' | 'bottom' | 'left'
  distance: number
}

export interface ElementBounds {
  id: string
  x: number
  y: number
  width: number
  height: number
  centerX: number
  centerY: number
  right: number
  bottom: number
}

/**
 * Calculate element bounds from canvas element
 */
export function getElementBounds(element: CanvasElement): ElementBounds {
  return {
    id: element.id,
    x: element.x,
    y: element.y,
    width: element.width,
    height: element.height,
    centerX: element.x + element.width / 2,
    centerY: element.y + element.height / 2,
    right: element.x + element.width,
    bottom: element.y + element.height,
  }
}

/**
 * Main alignment engine class
 */
export class AlignmentEngine {
  private config: typeof ALIGNMENT_CONFIG
  private canvasWidth: number
  private canvasHeight: number

  constructor(
    canvasWidth: number = 794,  // A4 width in pixels at 96 DPI
    canvasHeight: number = 1123, // A4 height in pixels at 96 DPI
    config?: Partial<typeof ALIGNMENT_CONFIG>
  ) {
    this.canvasWidth = canvasWidth
    this.canvasHeight = canvasHeight
    this.config = { ...ALIGNMENT_CONFIG, ...config }
  }

  setConfig(config: Partial<typeof ALIGNMENT_CONFIG>) {
    this.config = { ...this.config, ...config }
  }

  /**
   * Calculate snap position for a moving element
   */
  calculateSnap(
    movingElement: ElementBounds,
    otherElements: ElementBounds[],
    newX: number,
    newY: number
  ): SnapResult {
    const activeGuides: AlignmentGuide[] = []
    const distances: ElementDistance[] = []
    
    let snappedX = newX
    let snappedY = newY
    
    const moving = {
      ...movingElement,
      x: newX,
      y: newY,
      centerX: newX + movingElement.width / 2,
      centerY: newY + movingElement.height / 2,
      right: newX + movingElement.width,
      bottom: newY + movingElement.height,
    }

    // Grid snapping
    if (this.config.snapToGrid) {
      const gridSnap = this.snapToGrid(moving.x, moving.y)
      if (gridSnap.snapped) {
        snappedX = gridSnap.x
        snappedY = gridSnap.y
      }
    }

    // Page center guides
    if (this.config.snapToCenter) {
      const centerX = this.canvasWidth / 2
      const centerY = this.canvasHeight / 2

      // Horizontal center
      if (Math.abs(moving.centerX - centerX) < this.config.snapThreshold) {
        snappedX = centerX - movingElement.width / 2
        activeGuides.push({
          id: 'guide-center-v',
          type: 'center-v',
          position: centerX,
          label: 'Center',
          isActive: true,
        })
      }

      // Vertical center
      if (Math.abs(moving.centerY - centerY) < this.config.snapThreshold) {
        snappedY = centerY - movingElement.height / 2
        activeGuides.push({
          id: 'guide-center-h',
          type: 'center-h',
          position: centerY,
          label: 'Center',
          isActive: true,
        })
      }
    }

    // Page margin guides
    const margin = this.config.marginGuide
    
    // Left margin
    if (Math.abs(moving.x - margin) < this.config.snapThreshold) {
      snappedX = margin
      activeGuides.push({
        id: 'guide-margin-left',
        type: 'margin',
        position: margin,
        isActive: true,
      })
    }
    
    // Right margin
    if (Math.abs(moving.right - (this.canvasWidth - margin)) < this.config.snapThreshold) {
      snappedX = this.canvasWidth - margin - movingElement.width
      activeGuides.push({
        id: 'guide-margin-right',
        type: 'margin',
        position: this.canvasWidth - margin,
        isActive: true,
      })
    }

    // Top margin
    if (Math.abs(moving.y - margin) < this.config.snapThreshold) {
      snappedY = margin
      activeGuides.push({
        id: 'guide-margin-top',
        type: 'margin',
        position: margin,
        isActive: true,
      })
    }

    // Element alignment
    if (this.config.snapToElements) {
      for (const other of otherElements) {
        if (other.id === movingElement.id) continue

        // Left edge alignment
        if (Math.abs(moving.x - other.x) < this.config.snapThreshold) {
          snappedX = other.x
          activeGuides.push({
            id: `guide-left-${other.id}`,
            type: 'vertical',
            position: other.x,
            sourceElementId: other.id,
            isActive: true,
          })
        }

        // Right edge alignment
        if (Math.abs(moving.right - other.right) < this.config.snapThreshold) {
          snappedX = other.right - movingElement.width
          activeGuides.push({
            id: `guide-right-${other.id}`,
            type: 'vertical',
            position: other.right,
            sourceElementId: other.id,
            isActive: true,
          })
        }

        // Center X alignment
        if (Math.abs(moving.centerX - other.centerX) < this.config.snapThreshold) {
          snappedX = other.centerX - movingElement.width / 2
          activeGuides.push({
            id: `guide-cx-${other.id}`,
            type: 'vertical',
            position: other.centerX,
            sourceElementId: other.id,
            isActive: true,
          })
        }

        // Top edge alignment
        if (Math.abs(moving.y - other.y) < this.config.snapThreshold) {
          snappedY = other.y
          activeGuides.push({
            id: `guide-top-${other.id}`,
            type: 'horizontal',
            position: other.y,
            sourceElementId: other.id,
            isActive: true,
          })
        }

        // Bottom edge alignment
        if (Math.abs(moving.bottom - other.bottom) < this.config.snapThreshold) {
          snappedY = other.bottom - movingElement.height
          activeGuides.push({
            id: `guide-bottom-${other.id}`,
            type: 'horizontal',
            position: other.bottom,
            sourceElementId: other.id,
            isActive: true,
          })
        }

        // Center Y alignment
        if (Math.abs(moving.centerY - other.centerY) < this.config.snapThreshold) {
          snappedY = other.centerY - movingElement.height / 2
          activeGuides.push({
            id: `guide-cy-${other.id}`,
            type: 'horizontal',
            position: other.centerY,
            sourceElementId: other.id,
            isActive: true,
          })
        }

        // Calculate distances for display
        this.calculateDistances(moving, other, distances)
      }
    }

    return {
      snappedX,
      snappedY,
      deltaX: snappedX - newX,
      deltaY: snappedY - newY,
      activeGuides,
      distances,
    }
  }

  /**
   * Snap to grid
   */
  private snapToGrid(x: number, y: number): { x: number; y: number; snapped: boolean } {
    const gridX = Math.round(x / this.config.gridSize) * this.config.gridSize
    const gridY = Math.round(y / this.config.gridSize) * this.config.gridSize
    
    const snappedX = Math.abs(x - gridX) < this.config.snapThreshold
    const snappedY = Math.abs(y - gridY) < this.config.snapThreshold

    return {
      x: snappedX ? gridX : x,
      y: snappedY ? gridY : y,
      snapped: snappedX || snappedY,
    }
  }

  /**
   * Calculate distances between elements for display
   */
  private calculateDistances(
    moving: ElementBounds,
    other: ElementBounds,
    distances: ElementDistance[]
  ): void {
    // Horizontal distance (left-right)
    if (moving.right < other.x) {
      distances.push({
        elementId: other.id,
        edge: 'left',
        distance: other.x - moving.right,
      })
    } else if (moving.x > other.right) {
      distances.push({
        elementId: other.id,
        edge: 'right',
        distance: moving.x - other.right,
      })
    }

    // Vertical distance (top-bottom)
    if (moving.bottom < other.y) {
      distances.push({
        elementId: other.id,
        edge: 'top',
        distance: other.y - moving.bottom,
      })
    } else if (moving.y > other.bottom) {
      distances.push({
        elementId: other.id,
        edge: 'bottom',
        distance: moving.y - other.bottom,
      })
    }
  }

  /**
   * Align selected elements
   */
  alignElements(
    elements: CanvasElement[],
    alignment: 'left' | 'center' | 'right' | 'top' | 'middle' | 'bottom' | 'distribute-h' | 'distribute-v'
  ): CanvasElement[] {
    if (elements.length < 2) return elements

    const bounds = elements.map(getElementBounds)

    switch (alignment) {
      case 'left': {
        const minX = Math.min(...bounds.map(b => b.x))
        return elements.map(el => ({ ...el, x: minX }))
      }
      case 'center': {
        const avgCenterX = bounds.reduce((sum, b) => sum + b.centerX, 0) / bounds.length
        return elements.map(el => ({ ...el, x: avgCenterX - el.width / 2 }))
      }
      case 'right': {
        const maxRight = Math.max(...bounds.map(b => b.right))
        return elements.map(el => ({ ...el, x: maxRight - el.width }))
      }
      case 'top': {
        const minY = Math.min(...bounds.map(b => b.y))
        return elements.map(el => ({ ...el, y: minY }))
      }
      case 'middle': {
        const avgCenterY = bounds.reduce((sum, b) => sum + b.centerY, 0) / bounds.length
        return elements.map(el => ({ ...el, y: avgCenterY - el.height / 2 }))
      }
      case 'bottom': {
        const maxBottom = Math.max(...bounds.map(b => b.bottom))
        return elements.map(el => ({ ...el, y: maxBottom - el.height }))
      }
      case 'distribute-h': {
        return this.distributeHorizontally(elements)
      }
      case 'distribute-v': {
        return this.distributeVertically(elements)
      }
      default:
        return elements
    }
  }

  /**
   * Distribute elements evenly horizontally
   */
  private distributeHorizontally(elements: CanvasElement[]): CanvasElement[] {
    if (elements.length < 3) return elements

    const sorted = [...elements].sort((a, b) => a.x - b.x)
    const totalWidth = sorted.reduce((sum, el) => sum + el.width, 0)
    const minX = sorted[0].x
    const maxRight = sorted[sorted.length - 1].x + sorted[sorted.length - 1].width
    const availableSpace = maxRight - minX - totalWidth
    const gap = availableSpace / (sorted.length - 1)

    let currentX = minX
    return sorted.map(el => {
      const newEl = { ...el, x: currentX }
      currentX += el.width + gap
      return newEl
    })
  }

  /**
   * Distribute elements evenly vertically
   */
  private distributeVertically(elements: CanvasElement[]): CanvasElement[] {
    if (elements.length < 3) return elements

    const sorted = [...elements].sort((a, b) => a.y - b.y)
    const totalHeight = sorted.reduce((sum, el) => sum + el.height, 0)
    const minY = sorted[0].y
    const maxBottom = sorted[sorted.length - 1].y + sorted[sorted.length - 1].height
    const availableSpace = maxBottom - minY - totalHeight
    const gap = availableSpace / (sorted.length - 1)

    let currentY = minY
    return sorted.map(el => {
      const newEl = { ...el, y: currentY }
      currentY += el.height + gap
      return newEl
    })
  }

  /**
   * Get smart spacing recommendations
   */
  getSpacingRecommendations(
    movingElement: ElementBounds,
    otherElements: ElementBounds[]
  ): { gap: number; direction: 'horizontal' | 'vertical'; message: string }[] {
    const recommendations: { gap: number; direction: 'horizontal' | 'vertical'; message: string }[] = []

    // Find nearby elements and calculate common gaps
    const horizontalGaps = new Map<number, number>()
    const verticalGaps = new Map<number, number>()

    for (const other of otherElements) {
      if (other.id === movingElement.id) continue

      // Horizontal gap
      if (movingElement.right < other.x) {
        const gap = Math.round(other.x - movingElement.right)
        horizontalGaps.set(gap, (horizontalGaps.get(gap) || 0) + 1)
      } else if (movingElement.x > other.right) {
        const gap = Math.round(movingElement.x - other.right)
        horizontalGaps.set(gap, (horizontalGaps.get(gap) || 0) + 1)
      }

      // Vertical gap
      if (movingElement.bottom < other.y) {
        const gap = Math.round(other.y - movingElement.bottom)
        verticalGaps.set(gap, (verticalGaps.get(gap) || 0) + 1)
      } else if (movingElement.y > other.bottom) {
        const gap = Math.round(movingElement.y - other.bottom)
        verticalGaps.set(gap, (verticalGaps.get(gap) || 0) + 1)
      }
    }

    // Find most common gaps and suggest them
    const suggestGap = (gaps: Map<number, number>, direction: 'horizontal' | 'vertical') => {
      let maxCount = 0
      let suggestedGap = 0
      gaps.forEach((count, gap) => {
        if (count > maxCount && gap > 5 && gap < 100) {
          maxCount = count
          suggestedGap = gap
        }
      })
      if (maxCount >= 2) {
        recommendations.push({
          gap: suggestedGap,
          direction,
          message: `Match ${direction} spacing: ${suggestedGap}px`,
        })
      }
    }

    suggestGap(horizontalGaps, 'horizontal')
    suggestGap(verticalGaps, 'vertical')

    return recommendations
  }
}

// Export singleton instance for common use
export const alignmentEngine = new AlignmentEngine()
