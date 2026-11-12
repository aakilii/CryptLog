'use client'

import {
  Palette,
  Pin,
  PinOff,
  FileOutput,
  FileX,
  ShieldCheck,
  Settings2,
  Grid3X3,
  Tag,
  RefreshCw,
  ChevronDown,
} from 'lucide-react'
import { cn } from '@operation-room/lib/utils'
import { Button } from '@operation-room/components/ui/button'
import { Separator } from '@operation-room/components/ui/separator'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@operation-room/components/ui/popover'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@operation-room/components/ui/tooltip'
import { Toggle } from '@operation-room/components/ui/toggle'
import {
  FORENSIC_MODULE_ORDER,
  FORENSIC_THEME,
  type ForensicModule,
} from '../forensicTheme'

const colorSchemes = [
  {
    id: 'forensic-auto',
    name: 'Auto (Module Aware)',
    colors: ['#0ea5e9', '#6366f1', '#f59e0b', '#f97316'],
  },
  ...FORENSIC_MODULE_ORDER.map((moduleId) => ({
    id: `module-${moduleId}`,
    name: FORENSIC_THEME[moduleId].label,
    module: moduleId,
    colors: FORENSIC_THEME[moduleId].chartPalette,
  })),
  {
    id: 'forensic-contrast',
    name: 'Forensic Contrast',
    colors: ['#0f172a', '#475569', '#94a3b8', '#f8fafc'],
  },
]

// Size presets
const SIZE_PRESETS = [
  { id: 'compact', label: 'S', height: 150 },
  { id: 'standard', label: 'M', height: 250 },
  { id: 'expanded', label: 'L', height: 350 },
  { id: 'fullwidth', label: 'XL', height: 450 },
]

interface ChartConfig {
  colorScheme?: string
  height?: number | string
  showLegend?: boolean
  showLabels?: boolean
  showGrid?: boolean
  pinnedToTop?: boolean
  includeInExport?: boolean
}

const sourceToModule = (source?: string): ForensicModule => {
  const normalized = (source || '').toLowerCase()
  if (normalized.includes('timeline')) return 'timeline'
  if (normalized.includes('anomaly')) return 'anomaly'
  if (normalized.includes('correlation')) return 'correlation'
  if (normalized.includes('network')) return 'network'
  if (normalized.includes('crud')) return 'crud'
  if (normalized.includes('depth')) return 'depth'
  return 'case'
}

// Chart toolbar for when a chart/evidence block is selected
interface ChartToolbarProps {
  module?: ForensicModule
  config?: ChartConfig
  onConfigChange?: (config: ChartConfig) => void
  onRefresh?: () => void
  className?: string
}

export const ChartToolbar = ({
  module = 'case',
  config = {},
  onConfigChange,
  onRefresh,
  className,
}: ChartToolbarProps) => {
  const moduleTheme = FORENSIC_THEME[module]
  const ModuleIcon = moduleTheme.icon
  const currentColorScheme = config.colorScheme || `module-${module}`
  const currentSize = typeof config.height === 'number'
    ? SIZE_PRESETS.find(s => s.height === config.height)?.id || 'standard'
    : 'standard'

  const handleColorSchemeChange = (schemeId: string) => {
    onConfigChange?.({ ...config, colorScheme: schemeId })
  }

  const handleSizeChange = (sizeId: string) => {
    const size = SIZE_PRESETS.find(s => s.id === sizeId)
    if (size) {
      onConfigChange?.({ ...config, height: size.height })
    }
  }

  const toggleOption = (key: keyof ChartConfig) => {
    const current = config[key] as boolean | undefined
    const nextValue = current === false ? true : false
    onConfigChange?.({ ...config, [key]: nextValue })
  }

  return (
    <div className={cn(
      "flex items-center gap-1 px-2 py-1",
      "border-b bg-background/90 backdrop-blur-sm",
      className
    )}>
      <div
        className="hidden items-center gap-2 rounded-md border px-2 py-1 text-xs sm:flex"
        style={{ borderColor: `${moduleTheme.accent}55` }}
      >
        <ModuleIcon className="h-3.5 w-3.5" style={{ color: moduleTheme.accent }} />
        <span className="font-ui font-medium">{moduleTheme.label}</span>
      </div>

      {/* Color Scheme */}
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-1.5">
            <Palette className="h-4 w-4" />
            Colors
            <ChevronDown className="h-3 w-3 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-56 p-3" align="start">
          <div className="space-y-3">
            <div className="font-ui text-xs font-medium text-muted-foreground">Color Scheme</div>
            {colorSchemes.map((scheme) => (
              <button
                key={scheme.id}
                onClick={() => handleColorSchemeChange(scheme.id)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-md p-2 text-left transition-colors",
                  currentColorScheme === scheme.id
                    ? "bg-accent ring-1 ring-border"
                    : "hover:bg-muted"
                )}
              >
                <div className="flex gap-1">
                  {scheme.colors.map((color, i) => (
                    <div
                      key={i}
                      className="w-4 h-4 rounded"
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
                <div className="flex min-w-0 flex-col">
                  <span className="truncate font-ui text-sm">{scheme.name}</span>
                  {'module' in scheme && scheme.module && (
                    <span className="font-geist-mono text-[10px] uppercase text-muted-foreground">
                      {scheme.module}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </PopoverContent>
      </Popover>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Size */}
      <div className="flex items-center gap-0.5 bg-muted rounded-md p-0.5">
        {SIZE_PRESETS.map((size) => (
          <Tooltip key={size.id}>
            <TooltipTrigger asChild>
              <Button
                variant={currentSize === size.id ? "secondary" : "ghost"}
                size="sm"
                className="h-7 w-7 p-0 font-geist-mono text-xs font-medium"
                onClick={() => handleSizeChange(size.id)}
              >
                {size.label}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{size.id.charAt(0).toUpperCase() + size.id.slice(1)} ({size.height}px)</TooltipContent>
          </Tooltip>
        ))}
      </div>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Toggle Options */}
      <Tooltip>
        <TooltipTrigger asChild>
          <Toggle
            pressed={config.showLegend !== false}
            onPressedChange={() => toggleOption('showLegend')}
            size="sm"
            className="h-8 px-2 font-ui text-xs"
          >
            <Tag className="h-3.5 w-3.5 mr-1" />
            Legend
          </Toggle>
        </TooltipTrigger>
        <TooltipContent>Toggle legend visibility</TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <Toggle
            pressed={config.showLabels !== false}
            onPressedChange={() => toggleOption('showLabels')}
            size="sm"
            className="h-8 px-2 font-ui text-xs"
          >
            Labels
          </Toggle>
        </TooltipTrigger>
        <TooltipContent>Toggle data labels</TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <Toggle
            pressed={config.showGrid !== false}
            onPressedChange={() => toggleOption('showGrid')}
            size="sm"
            className="h-8 px-2 font-ui text-xs"
          >
            <Grid3X3 className="h-3.5 w-3.5 mr-1" />
            Grid
          </Toggle>
        </TooltipTrigger>
        <TooltipContent>Toggle grid lines</TooltipContent>
      </Tooltip>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Pin & Export */}
      <Tooltip>
        <TooltipTrigger asChild>
          <Toggle
            pressed={config.pinnedToTop}
            onPressedChange={() => toggleOption('pinnedToTop')}
            size="sm"
            className="h-8 px-2 font-ui text-xs"
          >
            {config.pinnedToTop ? (
              <PinOff className="h-3.5 w-3.5 mr-1" />
            ) : (
              <Pin className="h-3.5 w-3.5 mr-1" />
            )}
            Pin
          </Toggle>
        </TooltipTrigger>
        <TooltipContent>Pin chart to top of report</TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <Toggle
            pressed={config.includeInExport !== false}
            onPressedChange={() => toggleOption('includeInExport')}
            size="sm"
            className="h-8 px-2 font-ui text-xs"
          >
            {config.includeInExport !== false ? (
              <FileOutput className="h-3.5 w-3.5 mr-1" />
            ) : (
              <FileX className="h-3.5 w-3.5 mr-1" />
            )}
            Export
          </Toggle>
        </TooltipTrigger>
        <TooltipContent>Include in exported PDF/DOCX</TooltipContent>
      </Tooltip>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Refresh */}
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 px-2 font-ui"
            onClick={onRefresh}
          >
            <RefreshCw className="h-3.5 w-3.5 mr-1" />
            Refresh
          </Button>
        </TooltipTrigger>
        <TooltipContent>Refresh chart data</TooltipContent>
      </Tooltip>
    </div>
  )
}

// Evidence block toolbar
interface EvidenceToolbarProps {
  evidence?: {
    module?: ForensicModule
    type?: string
    source?: string
    verified?: boolean
    citationKey?: string
  }
  onVerify?: () => void
  onEditMetadata?: () => void
  onRemove?: () => void
  className?: string
}

export const EvidenceToolbar = ({
  evidence = {},
  onVerify,
  onEditMetadata,
  onRemove,
  className,
}: EvidenceToolbarProps) => {
  const moduleId = evidence.module || sourceToModule(evidence.source)
  const moduleTheme = FORENSIC_THEME[moduleId]

  return (
    <div className={cn(
      "flex items-center gap-1 px-2 py-1 border-b bg-background/90 backdrop-blur-sm",
      className
    )}>
      {/* Evidence info badge */}
      <div
        className="flex items-center gap-2 rounded-md border px-2 py-1 font-ui text-xs"
        style={{ borderColor: `${moduleTheme.accent}66` }}
      >
        <ShieldCheck className="h-3.5 w-3.5" style={{ color: moduleTheme.accent }} />
        <span className="font-medium text-muted-foreground">
          {evidence.source?.toUpperCase() || 'EVIDENCE'}
        </span>
        <span className="text-muted-foreground">•</span>
        <span>{evidence.type || 'unknown'}</span>
        {evidence.verified && (
          <>
            <span className="text-muted-foreground">•</span>
            <span className="font-medium text-emerald-600">Verified</span>
          </>
        )}
      </div>

      <Separator orientation="vertical" className="h-6 mx-1" />

      {/* Citation key */}
      {evidence.citationKey && (
        <div
          className="flex items-center gap-1 rounded-md px-2 py-1 font-geist-mono text-xs"
          style={{
            color: moduleTheme.accent,
            backgroundColor: `${moduleTheme.accent}1A`,
          }}
        >
          [{evidence.citationKey}]
        </div>
      )}

      <div className="flex-1" />

      {/* Actions */}
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            className="h-8 font-ui"
            onClick={onVerify}
          >
            {evidence.verified ? 'Re-verify' : 'Verify'}
          </Button>
        </TooltipTrigger>
        <TooltipContent>Verify evidence integrity</TooltipContent>
      </Tooltip>

      <Button
        variant="ghost"
        size="sm"
        className="h-8 font-ui"
        onClick={onEditMetadata}
      >
        <Settings2 className="h-3.5 w-3.5 mr-1" />
        Metadata
      </Button>

      <Button
        variant="ghost"
        size="sm"
        className="h-8 font-ui text-destructive hover:text-destructive"
        onClick={onRemove}
      >
        Remove
      </Button>
    </div>
  )
}
