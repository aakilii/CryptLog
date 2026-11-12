'use client'

import * as React from 'react'
import { cn } from '@operation-room/lib/utils'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@operation-room/components/ui/tooltip'
import type { ModuleType } from '@operation-room/lib/utils'
import { MODULE_ICON_COLORS, MODULE_BG_COLORS, MODULE_ICONS } from '@operation-room/components/icons/ModuleIcons'

interface MetricCardProps {
  title: string
  value: string | number
  change?: {
    value: number
    direction: 'up' | 'down' | 'neutral'
    label?: string
  }
  sparkline?: number[]
  icon?: React.ReactNode
  module?: ModuleType
  description?: string
  className?: string
  onClick?: () => void
}

/**
 * Premium Metric Card Component
 * Displays a KPI with optional trend indicator and sparkline
 */
export function MetricCard({
  title,
  value,
  change,
  sparkline,
  icon,
  module,
  description,
  className,
  onClick,
}: MetricCardProps) {
  const ModuleIconComponent = module ? MODULE_ICONS[module] : null
  const moduleColor = module ? MODULE_ICON_COLORS[module] : ''
  const moduleBg = module ? MODULE_BG_COLORS[module] : ''

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              'group relative flex flex-col p-4 rounded-xl border bg-card transition-all',
              'hover:shadow-md hover:border-primary/20',
              onClick && 'cursor-pointer',
              className
            )}
            onClick={onClick}
            role={onClick ? 'button' : undefined}
            tabIndex={onClick ? 0 : undefined}
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground font-medium truncate">
                {title}
              </span>
              {(icon || ModuleIconComponent) && (
                <div className={cn(
                  'p-1.5 rounded-lg transition-colors',
                  module ? moduleBg : 'bg-muted',
                  'group-hover:scale-105'
                )}>
                  {icon || (ModuleIconComponent && (
                    <ModuleIconComponent className={cn('h-4 w-4', moduleColor)} />
                  ))}
                </div>
              )}
            </div>

            {/* Value */}
            <div className="flex items-baseline gap-2">
              <span className={cn(
                'text-2xl font-bold tracking-tight',
                module && moduleColor
              )}>
                {typeof value === 'number' ? value.toLocaleString() : value}
              </span>
              
              {/* Change indicator */}
              {change && (
                <div className={cn(
                  'flex items-center gap-0.5 text-xs font-medium',
                  change.direction === 'up' && 'text-green-600 dark:text-green-400',
                  change.direction === 'down' && 'text-red-600 dark:text-red-400',
                  change.direction === 'neutral' && 'text-muted-foreground'
                )}>
                  {change.direction === 'up' && <TrendingUp className="h-3 w-3" />}
                  {change.direction === 'down' && <TrendingDown className="h-3 w-3" />}
                  {change.direction === 'neutral' && <Minus className="h-3 w-3" />}
                  <span>
                    {change.direction !== 'neutral' && (change.value > 0 ? '+' : '')}
                    {change.value}%
                  </span>
                </div>
              )}
            </div>

            {/* Change label */}
            {change?.label && (
              <span className="text-xs text-muted-foreground mt-1">
                {change.label}
              </span>
            )}

            {/* Sparkline */}
            {sparkline && sparkline.length > 0 && (
              <div className="mt-3 h-8">
                <Sparkline data={sparkline} color={module ? moduleColor : undefined} />
              </div>
            )}
          </div>
        </TooltipTrigger>
        {description && (
          <TooltipContent side="bottom" className="max-w-xs">
            <p className="text-sm">{description}</p>
          </TooltipContent>
        )}
      </Tooltip>
    </TooltipProvider>
  )
}

/**
 * Simple SVG Sparkline Component
 */
function Sparkline({ 
  data, 
  color = 'text-primary',
  className 
}: { 
  data: number[]
  color?: string
  className?: string 
}) {
  if (data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  const width = 100
  const height = 32
  const padding = 2

  const points = data.map((value, index) => {
    const x = padding + (index / (data.length - 1)) * (width - padding * 2)
    const y = height - padding - ((value - min) / range) * (height - padding * 2)
    return `${x},${y}`
  }).join(' ')

  // Create gradient path
  const areaPoints = `${padding},${height - padding} ${points} ${width - padding},${height - padding}`

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={cn('w-full h-full', className)}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="sparkline-gradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.3" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </linearGradient>
      </defs>
      
      {/* Area fill */}
      <polygon
        points={areaPoints}
        fill="url(#sparkline-gradient)"
        className={color}
      />
      
      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={color}
      />
      
      {/* End dot */}
      <circle
        cx={width - padding}
        cy={height - padding - ((data[data.length - 1] - min) / range) * (height - padding * 2)}
        r="2"
        fill="currentColor"
        className={color}
      />
    </svg>
  )
}

/**
 * Metric Grid - Responsive grid of metric cards
 */
interface MetricGridProps {
  children: React.ReactNode
  columns?: 2 | 3 | 4 | 5
  className?: string
}

export function MetricGrid({ children, columns = 4, className }: MetricGridProps) {
  const gridCols = {
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
    5: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5',
  }

  return (
    <div className={cn('grid gap-4', gridCols[columns], className)}>
      {children}
    </div>
  )
}

/**
 * Compact Metric - Smaller inline metric display
 */
interface CompactMetricProps {
  label: string
  value: string | number
  icon?: React.ReactNode
  className?: string
}

export function CompactMetric({ label, value, icon, className }: CompactMetricProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      {icon && (
        <div className="p-1 rounded bg-muted">
          {icon}
        </div>
      )}
      <div>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="text-sm font-semibold">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </div>
      </div>
    </div>
  )
}
