'use client'

import * as React from 'react'
import { cn } from '@operation-room/lib/utils'
import { Card, CardContent, CardFooter } from '@operation-room/components/ui/card'
import { Badge } from '@operation-room/components/ui/badge'
import { Button } from '@operation-room/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@operation-room/components/ui/tooltip'
import {
  MoreHorizontal,
  RefreshCw,
  Settings,
  Trash2,
  Copy,
  ExternalLink,
  GripVertical,
  Hash,
  Loader2,
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@operation-room/components/ui/dropdown-menu'
import { ModuleIcon, MODULE_NAMES, MODULE_BG_COLORS } from '@operation-room/components/icons/ModuleIcons'
import type { ModuleType } from '@operation-room/lib/utils'
import { truncateHash, formatRelativeTime } from '@operation-room/lib/utils'

// Evidence Block Types
export type EvidenceBlockType = 
  | 'shap-feature-importance'
  | 'shap-waterfall'
  | 'timeline-area'
  | 'timeline-bar'
  | 'timeline-severity-pie'
  | 'timeline-hourly-heatmap'
  | 'network-graph'
  | 'network-sankey'
  | 'network-flow-table'
  | 'correlation-graph'
  | 'correlation-attack-chain'
  | 'metric-card'
  | 'metric-grid'
  | 'data-table'
  | 'custom'

export interface EvidenceBlockData {
  blockId: string
  blockType: EvidenceBlockType
  module: ModuleType
  runId?: string
  figureNumber?: number
  caption: string
  dataQuery: {
    endpoint: string
    field?: string
    params?: Record<string, any>
  }
  dataSnapshot?: any
  dataHash?: string
  settings: Record<string, any>
  metadata: {
    insertedAt: string
    insertedBy: string
    lastRefreshed?: string
  }
}

interface EvidenceBlockProps {
  data: EvidenceBlockData
  selected?: boolean
  editable?: boolean
  onSelect?: () => void
  onRefresh?: () => void
  onRemove?: () => void
  onSettingsChange?: (settings: Record<string, any>) => void
  onCaptionChange?: (caption: string) => void
  className?: string
  children: React.ReactNode
}

/**
 * Evidence Block Component
 * Container for dynamic evidence visualizations in the report editor
 * 
 * Features:
 * - Draggable in editor
 * - Shows source module and run info
 * - Displays figure number and caption
 * - Shows data hash for integrity
 * - Supports refresh to get latest data
 * - Configurable settings per block type
 */
export function EvidenceBlock({
  data,
  selected = false,
  editable = true,
  onSelect,
  onRefresh,
  onRemove,
  onSettingsChange,
  onCaptionChange,
  className,
  children,
}: EvidenceBlockProps) {
  const [isRefreshing, setIsRefreshing] = React.useState(false)
  const [isEditing, setIsEditing] = React.useState(false)
  const [editedCaption, setEditedCaption] = React.useState(data.caption)

  const handleRefresh = async () => {
    if (!onRefresh) return
    setIsRefreshing(true)
    try {
      await onRefresh()
    } finally {
      setIsRefreshing(false)
    }
  }

  const handleCaptionSave = () => {
    onCaptionChange?.(editedCaption)
    setIsEditing(false)
  }

  const handleCaptionKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleCaptionSave()
    }
    if (e.key === 'Escape') {
      setEditedCaption(data.caption)
      setIsEditing(false)
    }
  }

  return (
    <TooltipProvider>
      <Card
        className={cn(
          'group relative transition-all',
          'hover:shadow-md',
          selected && 'ring-2 ring-primary shadow-lg',
          MODULE_BG_COLORS[data.module].replace('/10', '/5'),
          className
        )}
        onClick={onSelect}
        data-evidence-block
        data-block-id={data.blockId}
        data-block-type={data.blockType}
        data-module={data.module}
      >
        {/* Drag Handle (only in edit mode) */}
        {editable && (
          <div className="absolute left-0 top-0 bottom-0 w-8 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing">
            <GripVertical className="h-5 w-5 text-muted-foreground" />
          </div>
        )}

        {/* Header */}
        <div className={cn(
          'flex items-center justify-between p-3 border-b',
          'bg-gradient-to-r from-transparent to-transparent',
          editable && 'pl-8'
        )}>
          <div className="flex items-center gap-3">
            <ModuleIcon module={data.module} size="md" withBackground />
            
            <div className="flex flex-col">
              <span className="text-sm font-medium text-foreground">
                {getBlockTypeLabel(data.blockType)}
              </span>
              <span className="text-xs text-muted-foreground">
                {MODULE_NAMES[data.module]}
                {data.runId && (
                  <span className="ml-1">• {data.runId.slice(0, 8)}</span>
                )}
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1">
            {isRefreshing ? (
              <div className="p-2">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleRefresh()
                      }}
                    >
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Refresh data</TooltipContent>
                </Tooltip>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => onSettingsChange?.({})}>
                      <Settings className="h-4 w-4 mr-2" />
                      Settings
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <Copy className="h-4 w-4 mr-2" />
                      Duplicate
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <ExternalLink className="h-4 w-4 mr-2" />
                      Open in Module
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => onRemove?.()}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Remove
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </>
            )}
          </div>
        </div>

        {/* Content */}
        <CardContent className="p-4">
          {children}
        </CardContent>

        {/* Footer - Figure caption and metadata */}
        <CardFooter className="flex flex-col items-stretch gap-2 p-3 pt-0 border-t bg-muted/30">
          {/* Figure number and caption */}
          <div className="flex items-start gap-2">
            {data.figureNumber && (
              <Badge variant="outline" className="shrink-0">
                Figure {data.figureNumber}
              </Badge>
            )}
            
            {isEditing ? (
              <input
                type="text"
                value={editedCaption}
                onChange={(e) => setEditedCaption(e.target.value)}
                onBlur={handleCaptionSave}
                onKeyDown={handleCaptionKeyDown}
                className="flex-1 text-sm bg-transparent border-b border-primary focus:outline-none"
                autoFocus
              />
            ) : (
              <span
                className={cn(
                  'flex-1 text-sm text-muted-foreground',
                  editable && 'cursor-text hover:text-foreground'
                )}
                onClick={(e) => {
                  if (editable) {
                    e.stopPropagation()
                    setIsEditing(true)
                  }
                }}
              >
                {data.caption || 'Click to add caption...'}
              </span>
            )}
          </div>

          {/* Metadata row */}
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="text-xs font-normal">
                {data.module}
              </Badge>
              {data.metadata.lastRefreshed && (
                <span>
                  Updated {formatRelativeTime(data.metadata.lastRefreshed)}
                </span>
              )}
            </div>

            {data.dataHash && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-1 font-mono cursor-help">
                    <Hash className="h-3 w-3" />
                    {truncateHash(data.dataHash, 6)}
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <div className="space-y-1">
                    <div className="font-semibold">Data Integrity Hash</div>
                    <code className="text-xs">{data.dataHash}</code>
                  </div>
                </TooltipContent>
              </Tooltip>
            )}
          </div>
        </CardFooter>
      </Card>
    </TooltipProvider>
  )
}

/**
 * Get human-readable label for block type
 */
function getBlockTypeLabel(type: EvidenceBlockType): string {
  const labels: Record<EvidenceBlockType, string> = {
    'shap-feature-importance': 'SHAP Feature Importance',
    'shap-waterfall': 'SHAP Waterfall',
    'timeline-area': 'Timeline Area Chart',
    'timeline-bar': 'Timeline Bar Chart',
    'timeline-severity-pie': 'Severity Distribution',
    'timeline-hourly-heatmap': 'Hourly Activity Heatmap',
    'network-graph': 'Network Graph',
    'network-sankey': 'Data Flow Sankey',
    'network-flow-table': 'Network Flows Table',
    'correlation-graph': 'Correlation Graph',
    'correlation-attack-chain': 'Attack Chain Timeline',
    'metric-card': 'Metric Card',
    'metric-grid': 'Metrics Grid',
    'data-table': 'Data Table',
    'custom': 'Custom Block',
  }
  return labels[type] || type
}

/**
 * Evidence Block Placeholder (for drag preview)
 */
export function EvidenceBlockPlaceholder({
  module,
  blockType,
  className,
}: {
  module: ModuleType
  blockType: EvidenceBlockType
  className?: string
}) {
  return (
    <div className={cn(
      'flex flex-col items-center justify-center p-8 rounded-lg border-2 border-dashed',
      'bg-muted/50 text-muted-foreground',
      MODULE_BG_COLORS[module],
      className
    )}>
      <ModuleIcon module={module} size="xl" withBackground />
      <span className="mt-3 text-sm font-medium">{getBlockTypeLabel(blockType)}</span>
      <span className="text-xs">Drop to insert</span>
    </div>
  )
}

/**
 * Evidence Block Loading State
 */
export function EvidenceBlockLoading({
  module,
  blockType,
  className,
}: {
  module: ModuleType
  blockType: EvidenceBlockType
  className?: string
}) {
  return (
    <Card className={cn(MODULE_BG_COLORS[module].replace('/10', '/5'), className)}>
      <div className="flex items-center gap-3 p-3 border-b">
        <ModuleIcon module={module} size="md" withBackground />
        <div className="flex flex-col gap-1">
          <div className="h-4 w-32 bg-muted animate-pulse rounded" />
          <div className="h-3 w-20 bg-muted animate-pulse rounded" />
        </div>
      </div>
      <CardContent className="p-4">
        <div className="h-[200px] bg-muted animate-pulse rounded-lg flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </CardContent>
      <CardFooter className="p-3 pt-0 border-t bg-muted/30">
        <div className="flex items-center gap-2">
          <div className="h-5 w-16 bg-muted animate-pulse rounded" />
          <div className="h-4 w-48 bg-muted animate-pulse rounded" />
        </div>
      </CardFooter>
    </Card>
  )
}
