'use client'

import React, { useState, useCallback, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Search } from 'lucide-react'
import { cn } from '@operation-room/lib/utils'
import { useStudioStore, type PanelId } from './store/useStudioStore'
import { FORENSIC_THEME, themeFromPanel, type ForensicModule } from './forensicTheme'
import { Button } from '@operation-room/components/ui/button'
import { Input } from '@operation-room/components/ui/input'
import { ScrollArea } from '@operation-room/components/ui/scroll-area'

// Panel header with search
interface PanelHeaderProps {
  title: string
  panelId?: PanelId
  icon?: React.ReactNode
  color?: string
  showSearch?: boolean
  searchValue?: string
  onSearchChange?: (value: string) => void
  searchPlaceholder?: string
  onClose?: () => void
  actions?: React.ReactNode
}

export const PanelHeader = ({
  title,
  panelId,
  icon,
  color,
  showSearch = true,
  searchValue = '',
  onSearchChange,
  searchPlaceholder = 'Search...',
  onClose,
  actions,
}: PanelHeaderProps) => {
  const { setActivePanel } = useStudioStore()
  const panelTheme = themeFromPanel(panelId)
  const iconColor = color || panelTheme?.accent

  const handleClose = onClose || (() => setActivePanel(null))

  return (
    <div className="flex-shrink-0 border-b">
      {panelTheme && <div className={cn("h-[2px] w-full", panelTheme.gradientClass)} />}

      {/* Title row */}
      <div className="flex items-center justify-between px-4 py-3 min-w-0">
        <div className="flex items-center gap-2 min-w-0 flex-1 pr-2">
          {icon && (
            <span className="flex-shrink-0" style={{ color: iconColor }}>{icon}</span>
          )}
          <h2 className="font-geist text-sm font-semibold tracking-tight truncate">{title}</h2>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {actions}
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              "h-7 w-7 text-muted-foreground hover:text-foreground",
              panelTheme && "hover:bg-muted/80"
            )}
            onClick={handleClose}
            title="Close panel"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Search row */}
      {showSearch && (
        <div className="px-3 pb-3">
          <div className="relative">
            <Search
              className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              style={iconColor ? { color: iconColor } : undefined}
            />
            <Input
              value={searchValue}
              onChange={(e) => onSearchChange?.(e.target.value)}
              placeholder={searchPlaceholder}
              className="h-9 pl-8 font-ui text-sm"
            />
          </div>
        </div>
      )}
    </div>
  )
}

// Section header within panel
interface PanelSectionProps {
  title: string
  module?: ForensicModule
  icon?: React.ReactNode
  action?: React.ReactNode
  children: React.ReactNode
  defaultOpen?: boolean
  className?: string
}

export const PanelSection = ({
  title,
  module,
  icon,
  action,
  children,
  className,
}: PanelSectionProps) => {
  const moduleTheme = module ? FORENSIC_THEME[module] : null

  return (
    <div className={cn("py-3", className)}>
      <div className="flex items-center justify-between px-4 mb-2">
        <div className="flex items-center gap-2 min-w-0 flex-1 pr-2">
          {icon && (
            <span
              className="text-muted-foreground"
              style={moduleTheme ? { color: moduleTheme.accent } : undefined}
            >
              {icon}
            </span>
          )}
          <h3 className="font-ui text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {title}
          </h3>
        </div>
        {action}
      </div>
      <div className="px-3">
        {children}
      </div>
    </div>
  )
}

// Main expandable panel container
interface ExpandablePanelProps {
  children: React.ReactNode
  className?: string
}

export const ExpandablePanel = ({ children, className }: ExpandablePanelProps) => {
  const { activePanel } = useStudioStore()
  const isOpen = activePanel !== null
  const activeTheme = themeFromPanel(activePanel)
  
  // Resizing logic
  const [panelWidth, setPanelWidth] = useState(280)
  const isDragging = useRef(false)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = true
    document.body.style.cursor = 'col-resize'
  }, [])

  const handleMouseUp = useCallback(() => {
    isDragging.current = false
    document.body.style.cursor = 'default'
  }, [])

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging.current) return
    // e.clientX represents cursor X position. Assume left edge of panel is at X=64 (rail width)
    const newWidth = Math.min(Math.max(250, e.clientX - 64), 600)
    setPanelWidth(newWidth)
  }, [])

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = 'default'
    }
  }, [handleMouseMove, handleMouseUp])

  return (
    <AnimatePresence mode="wait">
      {isOpen && (
        <motion.div
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: panelWidth, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{
            type: 'spring',
            stiffness: 400,
            damping: 30,
            // Ensure width updates don't bounce out of track when dragging natively
            bounce: 0,
          }}
          className={cn(
            "absolute left-[56px] top-0 bottom-0 z-40 overflow-hidden bg-background/95 backdrop-blur shadow-2xl border-r",
            activeTheme?.surfaceClass,
            className
          )}
          style={{ width: panelWidth }}
        >
          <div className="h-full flex flex-col w-full min-h-0" style={{ width: panelWidth }}>
            {activeTheme && (
              <div className={cn("h-[2px] w-full", activeTheme.gradientClass)} />
            )}
            {children}
          </div>
          
          {/* Drag handle */}
          <div 
            className="absolute top-0 right-0 bottom-0 w-1.5 cursor-col-resize hover:bg-sky-500/50 active:bg-sky-500/80 transition-colors z-50 flex flex-col justify-center items-center group"
            onMouseDown={handleMouseDown}
          >
            <div className="h-10 w-0.5 bg-border/0 group-hover:bg-background/80 rounded" />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

// Panel content wrapper with scroll
interface PanelContentProps {
  children: React.ReactNode
  className?: string
}

export const PanelContent = ({ children, className }: PanelContentProps) => {
  return (
    <ScrollArea className={cn("flex-1 min-h-0", className)}>
      <div className="p-3 pr-4 pb-4 font-ui">
        {children}
      </div>
    </ScrollArea>
  )
}

// Empty state for panels
interface PanelEmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
}

export const PanelEmptyState = ({
  icon,
  title,
  description,
  action,
}: PanelEmptyStateProps) => {
  return (
    <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
      {icon && (
        <div className="mb-3 text-muted-foreground">
          {icon}
        </div>
      )}
      <h4 className="font-geist mb-1 text-sm font-medium">{title}</h4>
      {description && (
        <p className="mb-3 font-ui text-xs text-muted-foreground">{description}</p>
      )}
      {action}
    </div>
  )
}

// Loading state for panels
interface PanelLoadingProps {
  message?: string
}

export const PanelLoading = ({ message }: PanelLoadingProps) => {
  return (
    <div className="flex flex-col gap-3 p-3">
      {message && (
        <div className="py-2 text-center font-ui text-xs text-muted-foreground">
          {message}
        </div>
      )}
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="space-y-2">
          <div className="h-24 rounded-lg bg-muted animate-pulse" />
          <div className="h-4 w-3/4 rounded bg-muted animate-pulse" />
          <div className="h-3 w-1/2 rounded bg-muted animate-pulse" />
        </div>
      ))}
    </div>
  )
}

// Component preview card (for draggable items)
interface ComponentCardProps {
  id?: string
  name: string
  module?: ForensicModule
  description?: string
  preview?: React.ReactNode
  icon?: React.ReactNode
  type?: string
  color?: string
  onClick?: () => void
  onInsert?: () => void
  onDragStart?: (e: React.DragEvent) => void
  draggable?: boolean
  isDragging?: boolean
  className?: string
}

export const ComponentCard = ({
  id,
  name,
  module,
  description,
  preview,
  icon,
  type,
  color,
  onClick,
  onInsert,
  onDragStart,
  draggable,
  isDragging,
  className,
}: ComponentCardProps) => {
  const moduleTheme = module ? FORENSIC_THEME[module] : null
  const accentColor = moduleTheme?.accent || color || '#64748b'

  const handleDragStart = (e: React.DragEvent) => {
    if (onDragStart) {
      onDragStart(e)
    } else if (id) {
      e.dataTransfer.setData('application/json', JSON.stringify({
        type: 'component',
        componentId: id,
        module,
      }))
    }
  }

  return (
    <div
      onClick={onClick || onInsert}
      onDragStart={(e: React.DragEvent) => {
        // Set drag data
        handleDragStart(e)
        // Set effectAllowed so the browser shows the right cursor
        e.dataTransfer.effectAllowed = 'copy'
        // Create a minimal drag ghost
        const ghost = document.createElement('div')
        ghost.textContent = name
        ghost.style.cssText = 'position:absolute;top:-1000px;left:-1000px;padding:6px 12px;background:#6366f1;color:white;border-radius:6px;font-size:12px;font-family:sans-serif;white-space:nowrap;'
        document.body.appendChild(ghost)
        e.dataTransfer.setDragImage(ghost, 0, 0)
        setTimeout(() => document.body.removeChild(ghost), 0)
      }}
      draggable={draggable || !!onDragStart || !!id}
      className={cn(
        "group relative cursor-pointer overflow-hidden rounded-lg border p-3",
        "border-slate-200/80 bg-white/70 backdrop-blur-sm",
        "hover:border-primary/50 hover:bg-accent/50 hover:shadow-md hover:scale-[1.02]",
        "active:scale-[0.98] transition-all duration-150",
        isDragging && "opacity-50 cursor-grabbing shadow-lg",
        draggable && "cursor-grab active:cursor-grabbing",
        moduleTheme?.softGradientClass,
        className
      )}
    >
      {moduleTheme && <div className={cn("absolute inset-x-0 top-0 h-1", moduleTheme.gradientClass)} />}

      {/* Preview area */}
      {preview ? (
        <div
          className="aspect-[16/10] max-h-[120px] rounded bg-muted/50 mb-2 overflow-hidden flex items-center justify-center"
          style={{ borderTop: `2px solid ${accentColor}` }}
        >
          {preview}
        </div>
      ) : icon && (
        <div
          className="aspect-[16/10] rounded bg-muted/50 mb-2 flex flex-col items-center justify-center gap-2 group-hover:bg-muted/80 transition-colors"
          style={{ borderTop: `2px solid ${accentColor}` }}
        >
          <div 
            className="flex items-center justify-center w-12 h-12 rounded-full bg-background shadow-sm"
            style={{ color: accentColor }}
          >
            {icon}
          </div>
          <span className="text-[10px] font-ui font-medium text-muted-foreground uppercase opacity-70">
            {type?.replace('-', ' ')}
          </span>
        </div>
      )}

      {/* Info */}
      <div className="flex items-center gap-2 min-w-0">
        <div className="flex-1 truncate font-ui text-sm font-medium">{name}</div>
        {type && (
          <span
            className="rounded bg-muted px-1.5 py-0.5 font-geist-mono text-[10px] uppercase text-muted-foreground"
            style = {moduleTheme ? { color: moduleTheme.accent } : undefined}
          >
            {type}
          </span>
        )}
      </div>
      {description && (
        <div className="mt-0.5 truncate font-ui text-xs text-muted-foreground">{description}</div>
      )}

      {/* Drag indicator */}
      {draggable && (
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="flex flex-col gap-0.5">
            <div className="flex gap-0.5">
              <div className="w-1 h-1 rounded-full bg-muted-foreground/40" />
              <div className="w-1 h-1 rounded-full bg-muted-foreground/40" />
            </div>
            <div className="flex gap-0.5">
              <div className="w-1 h-1 rounded-full bg-muted-foreground/40" />
              <div className="w-1 h-1 rounded-full bg-muted-foreground/40" />
            </div>
            <div className="flex gap-0.5">
              <div className="w-1 h-1 rounded-full bg-muted-foreground/40" />
              <div className="w-1 h-1 rounded-full bg-muted-foreground/40" />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Metric card for insertable metrics
interface MetricCardProps {
  label: string
  value: string | number
  module?: ForensicModule
  unit?: string
  icon?: React.ReactNode
  trend?: 'up' | 'down' | 'neutral'
  color?: string
  onClick?: () => void
}

export const MetricCard = ({
  label,
  value,
  module,
  unit,
  icon,
  trend,
  color = '#64748b',
  onClick,
}: MetricCardProps) => {
  const moduleTheme = module ? FORENSIC_THEME[module] : null
  const valueColor = moduleTheme?.accent || color

  return (
    <motion.button
      onClick={onClick}
      className={cn(
        "w-full rounded-lg border p-2.5 text-left transition-all",
        "flex items-center justify-between",
        "hover:border-primary/50 hover:bg-accent/50",
        moduleTheme?.softGradientClass,
        "text-left"
      )}
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
    >
      <div className="flex items-center gap-2 min-w-0 flex-1 pr-2">
        {icon && <span className="flex-shrink-0">{icon}</span>}
        <span className="font-ui text-xs text-muted-foreground">{label}</span>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        <span
          className="font-geist text-sm font-bold"
          style={{ color: valueColor }}
        >
          {value}
        </span>
        {unit && (
          <span className="text-xs text-muted-foreground">{unit}</span>
        )}
        {trend === 'up' && <span className="text-green-500 text-xs">↑</span>}
        {trend === 'down' && <span className="text-red-500 text-xs">↓</span>}
      </div>
    </motion.button>
  )
}

// Finding item for key findings
interface FindingCardProps {
  title?: string
  text?: string
  description?: string
  module?: ForensicModule
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info'
  metric?: string
  onClick?: () => void
  onExpand?: () => void
  onInsert?: () => void
}

export const FindingCard = ({
  title,
  text,
  description,
  module,
  severity = 'info',
  metric,
  onClick,
  onExpand,
  onInsert,
}: FindingCardProps) => {
  const moduleTheme = module ? FORENSIC_THEME[module] : null
  const severityColors = {
    critical: '#dc2626',
    high: '#ef4444',
    medium: '#f59e0b',
    low: '#3b82f6',
    info: '#64748b',
  }

  const markerColor = severity === 'info' && moduleTheme
    ? moduleTheme.accent
    : severityColors[severity]

  return (
    <motion.div
      className={cn(
        "group flex cursor-pointer items-start gap-2 rounded-lg border p-2.5 transition-all",
        "hover:border-primary/50 hover:bg-accent/50",
        moduleTheme?.softGradientClass
      )}
      onClick={onClick}
      whileHover={{ x: 2 }}
    >
      <div
        className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
        style={{ backgroundColor: markerColor }}
      />
      <div className="flex-1 min-w-0">
        {title && (
          <div className="truncate font-ui text-sm font-medium">{title}</div>
        )}
        {(text || description) && (
          <div className="mt-0.5 line-clamp-2 font-ui text-xs text-muted-foreground">
            {text || description}
          </div>
        )}
      </div>
      {metric && (
        <span
          className="flex-shrink-0 font-geist-mono text-sm font-semibold text-muted-foreground"
          style={moduleTheme ? { color: moduleTheme.accent } : undefined}
        >
          {metric}
        </span>
      )}
      {(onExpand || onInsert) && (
        <Button
          variant="ghost"
          size="sm"
          className="h-6 px-2 text-[10px] font-semibold uppercase tracking-wide opacity-60 group-hover:opacity-100 transition-opacity flex-shrink-0 rounded-md"
          style={moduleTheme ? { color: moduleTheme.accent } : undefined}
          onClick={(e) => {
            e.stopPropagation()
            if (onInsert) {
              onInsert()
              return
            }
            onExpand?.()
          }}
        >
          + Insert
        </Button>
      )}
    </motion.div>
  )
}
