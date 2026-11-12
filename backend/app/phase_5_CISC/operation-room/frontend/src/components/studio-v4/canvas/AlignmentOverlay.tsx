'use client'

/**
 * AlignmentOverlay - Canva-like visual alignment guides
 * 
 * Phase 4: Renders alignment guides, distance indicators, and spacing
 * recommendations as an SVG overlay on the canvas.
 */

import React, { memo } from 'react'
import { AlignmentGuide, ElementDistance, ALIGNMENT_CONFIG } from './AlignmentEngine'

interface AlignmentOverlayProps {
  guides: AlignmentGuide[]
  distances: ElementDistance[]
  canvasWidth?: number
  canvasHeight?: number
  visible?: boolean
}

// Distance label component
const DistanceLabel = memo(({ 
  x, 
  y, 
  distance
}: { 
  x: number
  y: number
  distance: number
}) => {
  if (distance < 5) return null
  
  return (
    <g>
      {/* Background pill */}
      <rect
        x={x - 16}
        y={y - 8}
        width={32}
        height={16}
        rx={8}
        fill="rgba(59, 130, 246, 0.95)"
        filter="drop-shadow(0 1px 2px rgba(0,0,0,0.2))"
      />
      {/* Distance text */}
      <text
        x={x}
        y={y + 4}
        textAnchor="middle"
        fontSize="10"
        fontWeight="600"
        fontFamily="ui-monospace, monospace"
        fill="white"
      >
        {Math.round(distance)}
      </text>
    </g>
  )
})

DistanceLabel.displayName = 'DistanceLabel'

// Guide line component
const GuideLine = memo(({ 
  guide, 
  canvasWidth, 
  canvasHeight 
}: { 
  guide: AlignmentGuide
  canvasWidth: number
  canvasHeight: number
}) => {
  const isVertical = guide.type === 'vertical' || guide.type === 'center-v'
  const isCenter = guide.type === 'center-h' || guide.type === 'center-v'
  const isMargin = guide.type === 'margin'
  
  // Color based on guide type
  const getStrokeColor = () => {
    if (isCenter) return '#8b5cf6'  // Purple for center
    if (isMargin) return '#f59e0b'  // Amber for margin
    return '#3b82f6'  // Blue for element alignment
  }
  
  const strokeColor = getStrokeColor()
  const dashArray = isCenter ? '8 4' : isMargin ? '4 4' : '6 3'
  
  if (isVertical) {
    return (
      <g>
        <line
          x1={guide.position}
          y1={0}
          x2={guide.position}
          y2={canvasHeight}
          stroke={strokeColor}
          strokeWidth={1}
          strokeDasharray={dashArray}
          opacity={0.9}
        />
        {/* Decorative endpoints */}
        <circle
          cx={guide.position}
          cy={0}
          r={3}
          fill={strokeColor}
          opacity={0.8}
        />
        <circle
          cx={guide.position}
          cy={canvasHeight}
          r={3}
          fill={strokeColor}
          opacity={0.8}
        />
        {/* Label */}
        {guide.label && (
          <g>
            <rect
              x={guide.position - 24}
              y={canvasHeight / 2 - 10}
              width={48}
              height={20}
              rx={4}
              fill={strokeColor}
              opacity={0.9}
            />
            <text
              x={guide.position}
              y={canvasHeight / 2 + 4}
              textAnchor="middle"
              fontSize="10"
              fontWeight="600"
              fontFamily="ui-sans-serif, system-ui, sans-serif"
              fill="white"
            >
              {guide.label}
            </text>
          </g>
        )}
      </g>
    )
  }
  
  // Horizontal guide
  return (
    <g>
      <line
        x1={0}
        y1={guide.position}
        x2={canvasWidth}
        y2={guide.position}
        stroke={strokeColor}
        strokeWidth={1}
        strokeDasharray={dashArray}
        opacity={0.9}
      />
      {/* Decorative endpoints */}
      <circle
        cx={0}
        cy={guide.position}
        r={3}
        fill={strokeColor}
        opacity={0.8}
      />
      <circle
        cx={canvasWidth}
        cy={guide.position}
        r={3}
        fill={strokeColor}
        opacity={0.8}
      />
      {/* Label */}
      {guide.label && (
        <g>
          <rect
            x={canvasWidth / 2 - 24}
            y={guide.position - 10}
            width={48}
            height={20}
            rx={4}
            fill={strokeColor}
            opacity={0.9}
          />
          <text
            x={canvasWidth / 2}
            y={guide.position + 4}
            textAnchor="middle"
            fontSize="10"
            fontWeight="600"
            fontFamily="ui-sans-serif, system-ui, sans-serif"
            fill="white"
          >
            {guide.label}
          </text>
        </g>
      )}
    </g>
  )
})

GuideLine.displayName = 'GuideLine'

// Main overlay component
export const AlignmentOverlay = memo(({
  guides,
  distances,
  canvasWidth = 794,
  canvasHeight = 1123,
  visible = true
}: AlignmentOverlayProps) => {
  if (!visible || (guides.length === 0 && distances.length === 0)) {
    return null
  }
  
  return (
    <svg
      className="absolute inset-0 pointer-events-none z-[100]"
      width={canvasWidth}
      height={canvasHeight}
      style={{ overflow: 'visible' }}
    >
      {/* Subtle grid overlay when guides are active */}
      {guides.length > 0 && ALIGNMENT_CONFIG.showGuides && (
        <defs>
          <pattern
            id="alignment-grid"
            width={ALIGNMENT_CONFIG.gridSize}
            height={ALIGNMENT_CONFIG.gridSize}
            patternUnits="userSpaceOnUse"
          >
            <circle
              cx={ALIGNMENT_CONFIG.gridSize / 2}
              cy={ALIGNMENT_CONFIG.gridSize / 2}
              r={0.5}
              fill="rgba(59, 130, 246, 0.15)"
            />
          </pattern>
        </defs>
      )}
      
      {/* Render all guide lines */}
      {guides.filter(g => g.isActive).map((guide, index) => (
        <GuideLine
          key={guide.id || `guide-${index}`}
          guide={guide}
          canvasWidth={canvasWidth}
          canvasHeight={canvasHeight}
        />
      ))}

      {/* Distance markers */}
      {distances.slice(0, 6).map((distance, index) => {
        const isHorizontal = distance.edge === 'left' || distance.edge === 'right'
        const x = isHorizontal ? canvasWidth * 0.5 : canvasWidth - 28
        const y = isHorizontal ? 26 + index * 20 : canvasHeight * 0.5
        return (
          <DistanceLabel
            key={`${distance.elementId}-${distance.edge}-${index}`}
            x={x}
            y={y}
            distance={distance.distance}
          />
        )
      })}
    </svg>
  )
})

AlignmentOverlay.displayName = 'AlignmentOverlay'

export default AlignmentOverlay
