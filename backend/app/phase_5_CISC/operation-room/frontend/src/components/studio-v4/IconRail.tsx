'use client'

import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FileStack,
  Clock,
  Zap,
  Workflow,
  Activity,
  Database,
  Layers,
  Archive,
  Upload,
  Type,
  LayoutGrid,
  LucideIcon,
  ChevronRight,
} from 'lucide-react'
import { cn } from '@operation-room/lib/utils'
import { useStudioStore, type PanelId } from './store/useStudioStore'
import { FORENSIC_THEME, type ForensicModule } from './forensicTheme'

// Rail item configuration
interface RailItem {
  id: PanelId
  icon: LucideIcon
  label: string
  module: ForensicModule
  shortcut?: string
  badge?: number
  color?: string
}

const createRailItem = (
  id: PanelId,
  icon: LucideIcon,
  label: string,
  shortcut: string,
  module: ForensicModule
): RailItem => {
  const theme = FORENSIC_THEME[module]
  return {
    id,
    icon,
    label,
    shortcut,
    module,
    color: theme.accent,
  }
}

const RAIL_ITEMS: RailItem[] = [
  createRailItem('templates', FileStack, 'Templates', 'T', 'case'),
  createRailItem('timeline', Clock, 'Timeline', '1', 'timeline'),
  createRailItem('anomaly', Zap, 'Anomaly', '2', 'anomaly'),
  createRailItem('correlation', Workflow, 'Correlation', '3', 'correlation'),
  createRailItem('network', Activity, 'Network', '4', 'network'),
  createRailItem('crud', Database, 'CRUD', '5', 'crud'),
  createRailItem('depth', Layers, 'Depth', '6', 'depth'),
  createRailItem('vault', Archive, 'Evidence', 'E', 'case'),
  createRailItem('uploads', Upload, 'Uploads', 'U', 'case'),
  createRailItem('text', Type, 'Text', 'X', 'case'),
  createRailItem('elements', LayoutGrid, 'Elements', 'L', 'case'),
]

// ── Individual Rail Button ────────────────────────────────────────────
interface RailButtonProps {
  item: RailItem
  isActive: boolean
  onClick: () => void
  badge?: number
  expanded: boolean
}

const RailButton = ({ item, isActive, onClick, badge, expanded }: RailButtonProps) => {
  const Icon = item.icon
  const theme = FORENSIC_THEME[item.module]

  return (
    <motion.button
      onClick={onClick}
      className={cn(
        "group relative isolate flex w-full items-center px-3 py-2.5",
        "transition-all duration-200 gap-3",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isActive
          ? cn("bg-slate-900/[0.04] dark:bg-white/[0.06]", theme.ringClass)
          : "hover:bg-muted/80"
      )}
      whileTap={{ scale: 0.97 }}
    >
      {/* Active indicator bar */}
      {isActive && (
        <motion.div
          layoutId="activeIndicator"
          className="absolute left-0 top-1/2 h-7 w-[3px] -translate-y-1/2 rounded-r-full"
          style={{ backgroundImage: theme.gradientCss }}
          initial={false}
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
        />
      )}

      {/* Icon container */}
      <div
        className={cn(
          "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg transition-all",
          isActive
            ? "text-white shadow-md"
            : "text-muted-foreground group-hover:text-foreground group-hover:bg-accent/50"
        )}
        style={isActive ? { backgroundImage: theme.gradientCss } : undefined}
      >
        <Icon className="h-[18px] w-[18px]" />
      </div>

      {/* Label — only when expanded */}
      <AnimatePresence>
        {expanded && (
          <motion.span
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.15, delay: 0.05 }}
            className={cn(
              "text-[12.5px] font-semibold whitespace-nowrap overflow-hidden",
              isActive ? "text-foreground" : "text-muted-foreground group-hover:text-foreground"
            )}
          >
            {item.label}
          </motion.span>
        )}
      </AnimatePresence>

      {/* Keyboard shortcut badge — only expanded */}
      <AnimatePresence>
        {expanded && item.shortcut && (
          <motion.kbd
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.1 }}
            className="ml-auto pointer-events-none select-none rounded border bg-muted px-1.5 py-0.5 font-mono text-[9px] font-medium text-muted-foreground flex-shrink-0"
          >
            ⌘{item.shortcut}
          </motion.kbd>
        )}
      </AnimatePresence>

      {/* Notification badge */}
      {badge !== undefined && badge > 0 && (
        <span
          className={cn(
            "flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[9px] font-bold text-primary-foreground",
            expanded ? "ml-auto" : "absolute top-1.5 right-1.5"
          )}
        >
          {badge > 99 ? '99+' : badge}
        </span>
      )}
    </motion.button>
  )
}

// ── Main Icon Rail ────────────────────────────────────────────────────
interface IconRailProps {
  className?: string
  badges?: Partial<Record<PanelId, number>>
}

export const IconRail = ({ className, badges = {} }: IconRailProps) => {
  const { activePanel, togglePanel } = useStudioStore()
  const [expanded, setExpanded] = useState(false)

  return (
    <motion.div
      className={cn(
        "flex flex-col bg-background/95 backdrop-blur-sm border-r flex-shrink-0",
        "h-full overflow-y-auto overflow-x-hidden",
        "shadow-sm",
        className
      )}
      animate={{ width: expanded ? 200 : 56 }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      {/* Module panels (top section) */}
      <div className="flex flex-col border-b pb-1.5 pt-1">
        {RAIL_ITEMS.slice(0, 7).map((item) => (
          <RailButton
            key={item.id}
            item={item}
            isActive={activePanel === item.id}
            onClick={() => togglePanel(item.id)}
            badge={badges[item.id]}
            expanded={expanded}
          />
        ))}
      </div>

      {/* Utility panels (bottom section) */}
      <div className="flex flex-col pt-1.5">
        {RAIL_ITEMS.slice(7).map((item) => (
          <RailButton
            key={item.id}
            item={item}
            isActive={activePanel === item.id}
            onClick={() => togglePanel(item.id)}
            badge={badges[item.id]}
            expanded={expanded}
          />
        ))}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Expand hint at bottom */}
      <div className="flex items-center justify-center py-3 border-t opacity-40 hover:opacity-80 transition-opacity">
        <motion.div
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
        </motion.div>
      </div>
    </motion.div>
  )
}

// Export rail items for use elsewhere
export { RAIL_ITEMS }
export type { RailItem }
