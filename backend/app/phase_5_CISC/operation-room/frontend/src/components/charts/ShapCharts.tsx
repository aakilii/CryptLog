'use client'

import * as React from 'react'
import { cn } from '@operation-room/lib/utils'
import { 
  Tooltip, 
  TooltipContent, 
  TooltipProvider, 
  TooltipTrigger 
} from '@operation-room/components/ui/tooltip'
import { Badge } from '@operation-room/components/ui/badge'
import { Info, TrendingUp, TrendingDown } from 'lucide-react'

/**
 * SHAP Feature Data Interface
 */
interface ShapFeature {
  feature: string
  value: number
  baseValue?: number
  contribution: number
  percentageContribution?: number
  featureValue?: string | number
}

/**
 * Color utilities for SHAP visualizations
 */
const getContributionColor = (contribution: number, intensity: number = 1) => {
  const absContribution = Math.abs(contribution)
  const alpha = Math.min(0.8, absContribution * intensity)
  
  if (contribution > 0) {
    return `rgba(220, 38, 38, ${alpha})` // Red for positive
  } else if (contribution < 0) {
    return `rgba(37, 99, 235, ${alpha})` // Blue for negative
  }
  return `rgba(156, 163, 175, 0.5)` // Gray for zero
}

const getContributionClass = (contribution: number) => {
  if (contribution > 0) return 'text-red-600 dark:text-red-400'
  if (contribution < 0) return 'text-blue-600 dark:text-blue-400'
  return 'text-muted-foreground'
}

// ============================================================================
// SHAP Feature Importance Bar Chart
// ============================================================================

interface ShapFeatureImportanceProps {
  features: ShapFeature[]
  maxFeatures?: number
  title?: string
  description?: string
  showValues?: boolean
  showPercentages?: boolean
  colorIntensity?: number
  animated?: boolean
  className?: string
  colors?: { positive?: string; negative?: string }
  onFeatureClick?: (feature: ShapFeature) => void
}

/**
 * SHAP Feature Importance - Horizontal Bar Chart
 * Shows the absolute importance of each feature
 */
export function ShapFeatureImportance({
  features,
  maxFeatures = 10,
  title = 'Feature Importance',
  description,
  showValues = true,
  showPercentages = true,
  colorIntensity = 2,
  animated = true,
  className,
  colors,
  onFeatureClick,
}: ShapFeatureImportanceProps) {
  // Sort by absolute contribution and limit
  const sortedFeatures = React.useMemo(() => {
    return [...features]
      .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
      .slice(0, maxFeatures)
  }, [features, maxFeatures])

  const maxContribution = sortedFeatures.length > 0 ? Math.max(...sortedFeatures.map(f => Math.abs(f.contribution))) : 1
  const totalContribution = sortedFeatures.reduce((sum, f) => sum + Math.abs(f.contribution), 0)

  return (
    <TooltipProvider>
      <div className={cn('space-y-4', className)}>
        {/* Header */}
        {(title || description) && (
          <div className="space-y-1">
            {title && (
              <h4 className="text-sm font-semibold flex items-center gap-2">
                {title}
                {description && (
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="h-4 w-4 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p className="text-sm">{description}</p>
                    </TooltipContent>
                  </Tooltip>
                )}
              </h4>
            )}
          </div>
        )}

        {/* Feature bars */}
        <div className="space-y-3">
          {sortedFeatures.map((feature, index) => {
            const percentage = (Math.abs(feature.contribution) / totalContribution) * 100
            const barWidth = (Math.abs(feature.contribution) / maxContribution) * 100

            return (
              <div
                key={feature.feature}
                className={cn(
                  'group',
                  onFeatureClick && 'cursor-pointer hover:bg-muted/50 rounded-lg p-2 -mx-2'
                )}
                onClick={() => onFeatureClick?.(feature)}
              >
                {/* Feature label and value */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-sm font-medium truncate">
                      {feature.feature}
                    </span>
                    {feature.featureValue !== undefined && (
                      <Badge variant="outline" className="text-xs font-mono shrink-0">
                        = {feature.featureValue}
                      </Badge>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-2 shrink-0">
                    {showPercentages && (
                      <span className="text-xs text-muted-foreground">
                        {percentage.toFixed(1)}%
                      </span>
                    )}
                    {showValues && (
                      <span className={cn(
                        'text-sm font-semibold font-mono',
                        getContributionClass(feature.contribution)
                      )}>
                        {feature.contribution > 0 ? '+' : ''}
                        {feature.contribution.toFixed(3)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Bar */}
                <div className="relative h-4 bg-muted rounded-full overflow-hidden">
                  <div
                    className={cn(
                      'absolute inset-y-0 left-0 rounded-full',
                      animated && 'transition-all duration-500 ease-out'
                    )}
                    style={{
                      width: `${barWidth}%`,
                      backgroundColor: feature.contribution > 0 
                        ? (colors?.positive || getContributionColor(feature.contribution, colorIntensity)) 
                        : feature.contribution < 0 
                          ? (colors?.negative || getContributionColor(feature.contribution, colorIntensity)) 
                          : getContributionColor(feature.contribution, colorIntensity),
                      transitionDelay: animated ? `${index * 50}ms` : undefined,
                    }}
                  />
                  
                  {/* Direction indicator */}
                  <div className="absolute inset-0 flex items-center px-2">
                    {feature.contribution > 0 ? (
                      <TrendingUp className="h-3 w-3 text-white/70" />
                    ) : feature.contribution < 0 ? (
                      <TrendingDown className="h-3 w-3 text-white/70" />
                    ) : null}
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Legend */}
        <div className="flex items-center justify-center gap-6 text-xs text-muted-foreground border-t pt-3">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-red-500/60" />
            <span>Increases risk</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-blue-500/60" />
            <span>Decreases risk</span>
          </div>
        </div>
      </div>
    </TooltipProvider>
  )
}

// ============================================================================
// SHAP Waterfall Chart
// ============================================================================

interface ShapWaterfallProps {
  features: ShapFeature[]
  baseValue: number
  outputValue: number
  maxFeatures?: number
  title?: string
  description?: string
  outputLabel?: string
  baseLabel?: string
  animated?: boolean
  className?: string
  colors?: {
    positive?: string
    negative?: string
  }
}

/**
 * SHAP Waterfall Chart
 * Shows how features contribute to moving from base value to output
 */
export function ShapWaterfall({
  features,
  baseValue,
  outputValue,
  maxFeatures = 8,
  title = 'Prediction Explanation',
  description,
  outputLabel = 'Final Score',
  baseLabel = 'Base Value',
  animated = true,
  className,
  colors,
}: ShapWaterfallProps) {
  // Sort and limit features
  const sortedFeatures = React.useMemo(() => {
    return [...features]
      .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
      .slice(0, maxFeatures)
  }, [features, maxFeatures])

  // Calculate cumulative values for waterfall
  const waterfallData = React.useMemo(() => {
    let cumulative = baseValue
    const data = sortedFeatures.map(feature => {
      const start = cumulative
      cumulative += feature.contribution
      return {
        ...feature,
        start,
        end: cumulative,
      }
    })
    return data
  }, [sortedFeatures, baseValue])

  // Calculate scale
  const allValues = [baseValue, outputValue, ...waterfallData.flatMap(d => [d.start, d.end])]
  const minValue = Math.min(...allValues)
  const maxValue = Math.max(...allValues)
  const range = maxValue - minValue
  const padding = range * 0.1

  const scaleX = (value: number) => {
    return ((value - minValue + padding) / (range + padding * 2)) * 100
  }

  const barHeight = 28
  const rowHeight = 40

  return (
    <TooltipProvider>
      <div className={cn('space-y-4', className)}>
        {/* Header */}
        {(title || description) && (
          <div className="space-y-1">
            {title && (
              <h4 className="text-sm font-semibold flex items-center gap-2">
                {title}
                {description && (
                  <Tooltip>
                    <TooltipTrigger>
                      <Info className="h-4 w-4 text-muted-foreground" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p className="text-sm">{description}</p>
                    </TooltipContent>
                  </Tooltip>
                )}
              </h4>
            )}
          </div>
        )}

        {/* Waterfall chart */}
        <div className="relative">
          {/* Base value row */}
          <div className="flex items-center gap-4 mb-2" style={{ height: rowHeight }}>
            <div className="w-32 shrink-0 text-right">
              <span className="text-sm text-muted-foreground">{baseLabel}</span>
            </div>
            <div className="flex-1 relative h-full flex items-center">
              <div 
                className="absolute h-[2px] bg-muted-foreground/20"
                style={{ left: `${scaleX(baseValue)}%`, right: 0 }}
              />
              <div
                className="absolute w-3 h-3 rounded-full bg-gray-400 border-2 border-background shadow"
                style={{ left: `${scaleX(baseValue)}%`, transform: 'translateX(-50%)' }}
              />
            </div>
            <div className="w-24 shrink-0">
              <span className="text-sm font-mono font-semibold">{baseValue.toFixed(3)}</span>
            </div>
          </div>

          {/* Feature rows */}
          {waterfallData.map((feature, index) => (
            <div 
              key={feature.feature} 
              className="flex items-center gap-4 group"
              style={{ height: rowHeight }}
            >
              <div className="w-32 shrink-0 text-right">
                <Tooltip>
                  <TooltipTrigger>
                    <span className="text-sm truncate block cursor-help">
                      {feature.feature}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    <div className="space-y-1">
                      <div className="font-semibold">{feature.feature}</div>
                      {feature.featureValue !== undefined && (
                        <div className="text-xs">Value: {feature.featureValue}</div>
                      )}
                    </div>
                  </TooltipContent>
                </Tooltip>
              </div>
              
              <div className="flex-1 relative" style={{ height: barHeight }}>
                {/* Connector line from previous */}
                {index > 0 && (
                  <div
                    className="absolute w-[1px] bg-muted-foreground/20"
                    style={{
                      left: `${scaleX(feature.start)}%`,
                      top: -((rowHeight - barHeight) / 2 + 2),
                      height: (rowHeight - barHeight) / 2 + 4,
                    }}
                  />
                )}

                {/* Bar */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div
                      className={cn(
                        'absolute top-0 h-full rounded-md shadow-sm cursor-pointer',
                        'transition-opacity hover:opacity-80',
                        animated && 'transition-all duration-500 ease-out'
                      )}
                      style={{
                        left: `${Math.min(scaleX(feature.start), scaleX(feature.end))}%`,
                        width: `${Math.abs(scaleX(feature.end) - scaleX(feature.start))}%`,
                        backgroundColor: feature.contribution > 0 
                          ? (colors?.positive || getContributionColor(feature.contribution, 1.5)) 
                          : feature.contribution < 0 
                            ? (colors?.negative || getContributionColor(feature.contribution, 1.5)) 
                            : getContributionColor(feature.contribution, 1.5),
                        transitionDelay: animated ? `${index * 100}ms` : undefined,
                      }}
                    >
                      {/* Arrow indicator */}
                      <div className={cn(
                        'absolute top-1/2 -translate-y-1/2',
                        feature.contribution > 0 ? 'right-1' : 'left-1'
                      )}>
                        {feature.contribution > 0 ? (
                          <TrendingUp className="h-4 w-4 text-white/80" />
                        ) : (
                          <TrendingDown className="h-4 w-4 text-white/80" />
                        )}
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <div className="space-y-1">
                      <div className="font-semibold">{feature.feature}</div>
                      <div className="text-xs">
                        Contribution: {feature.contribution > 0 ? '+' : ''}{feature.contribution.toFixed(4)}
                      </div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </div>
              
              <div className="w-24 shrink-0">
                <span className={cn(
                  'text-sm font-mono font-semibold',
                  getContributionClass(feature.contribution)
                )}>
                  {feature.contribution > 0 ? '+' : ''}{feature.contribution.toFixed(3)}
                </span>
              </div>
            </div>
          ))}

          {/* Output value row */}
          <div className="flex items-center gap-4 mt-2 pt-2 border-t" style={{ height: rowHeight }}>
            <div className="w-32 shrink-0 text-right">
              <span className="text-sm font-semibold">{outputLabel}</span>
            </div>
            <div className="flex-1 relative h-full flex items-center">
              <div
                className={cn(
                  'absolute w-4 h-4 rounded-full border-2 border-background shadow',
                  outputValue > baseValue ? 'bg-red-500' : 'bg-blue-500'
                )}
                style={{ left: `${scaleX(outputValue)}%`, transform: 'translateX(-50%)' }}
              />
            </div>
            <div className="w-24 shrink-0">
              <span className={cn(
                'text-sm font-mono font-bold',
                outputValue > baseValue ? 'text-red-600' : 'text-blue-600'
              )}>
                {outputValue.toFixed(3)}
              </span>
            </div>
          </div>
        </div>

        {/* Legend */}
        <div className="flex items-center justify-center gap-6 text-xs text-muted-foreground border-t pt-3">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-red-500/60" />
            <span>Pushes higher</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded bg-blue-500/60" />
            <span>Pushes lower</span>
          </div>
        </div>
      </div>
    </TooltipProvider>
  )
}

// ============================================================================
// SHAP Summary Dot Plot
// ============================================================================

interface ShapSummaryDotProps {
  // Array of samples, each with feature values and SHAP values
  samples: Array<{
    id: string
    features: Record<string, number>
    shapValues: Record<string, number>
  }>
  featureNames: string[]
  maxFeatures?: number
  title?: string
  className?: string
}

/**
 * SHAP Summary Dot Plot
 * Shows distribution of SHAP values across all samples
 */
export function ShapSummaryDot({
  samples,
  featureNames,
  maxFeatures = 10,
  title = 'SHAP Summary',
  className,
}: ShapSummaryDotProps) {
  // Calculate mean absolute SHAP value for each feature to sort
  const featureImportance = React.useMemo(() => {
    return featureNames.map(feature => ({
      feature,
      meanAbsShap: samples.reduce((sum, sample) => 
        sum + Math.abs(sample.shapValues[feature] || 0), 0
      ) / samples.length,
    }))
    .sort((a, b) => b.meanAbsShap - a.meanAbsShap)
    .slice(0, maxFeatures)
  }, [samples, featureNames, maxFeatures])

  // Get value range for color scaling
  const valueRanges = React.useMemo(() => {
    const ranges: Record<string, { min: number; max: number }> = {}
    featureImportance.forEach(({ feature }) => {
      const values = samples.map(s => s.features[feature])
      ranges[feature] = {
        min: Math.min(...values),
        max: Math.max(...values),
      }
    })
    return ranges
  }, [samples, featureImportance])

  // Get SHAP value range
  const shapRange = React.useMemo(() => {
    const allShap = samples.flatMap(s => Object.values(s.shapValues))
    return {
      min: Math.min(...allShap),
      max: Math.max(...allShap),
    }
  }, [samples])

  const scaleX = (shapValue: number) => {
    return ((shapValue - shapRange.min) / (shapRange.max - shapRange.min)) * 100
  }

  const getValueColor = (value: number, feature: string) => {
    const { min, max } = valueRanges[feature]
    const normalized = (value - min) / (max - min || 1)
    // Blue to red gradient
    const r = Math.round(normalized * 220)
    const b = Math.round((1 - normalized) * 220)
    return `rgb(${r}, 50, ${b})`
  }

  return (
    <TooltipProvider>
      <div className={cn('space-y-4', className)}>
        {title && (
          <h4 className="text-sm font-semibold">{title}</h4>
        )}

        <div className="space-y-2">
          {featureImportance.map(({ feature }) => (
            <div key={feature} className="flex items-center gap-4">
              <div className="w-32 shrink-0 text-right">
                <span className="text-xs truncate block">{feature}</span>
              </div>
              
              <div className="flex-1 relative h-8">
                {/* Center line */}
                <div 
                  className="absolute top-1/2 w-[1px] h-4 -translate-y-1/2 bg-muted-foreground/50"
                  style={{ left: `${scaleX(0)}%` }}
                />
                
                {/* Dots */}
                {samples.map((sample, idx) => {
                  const shapValue = sample.shapValues[feature] || 0
                  const featureValue = sample.features[feature]
                  
                  return (
                    <Tooltip key={sample.id}>
                      <TooltipTrigger asChild>
                        <div
                          className="absolute w-2 h-2 rounded-full -translate-x-1/2 -translate-y-1/2 top-1/2 cursor-pointer hover:scale-150 transition-transform"
                          style={{
                            left: `${scaleX(shapValue)}%`,
                            backgroundColor: getValueColor(featureValue, feature),
                          }}
                        />
                      </TooltipTrigger>
                      <TooltipContent>
                        <div className="text-xs space-y-1">
                          <div>Sample: {sample.id}</div>
                          <div>Value: {featureValue.toFixed(2)}</div>
                          <div>SHAP: {shapValue.toFixed(4)}</div>
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-3">
          <span>Low ← SHAP value (impact) → High</span>
          <div className="flex items-center gap-2">
            <span>Feature value:</span>
            <div className="flex h-3 w-16 rounded overflow-hidden">
              <div className="flex-1 bg-gradient-to-r from-blue-500 to-red-500" />
            </div>
            <span>Low → High</span>
          </div>
        </div>
      </div>
    </TooltipProvider>
  )
}

// ============================================================================
// SHAP Force Plot (Single Prediction)
// ============================================================================

interface ShapForceProps {
  features: ShapFeature[]
  baseValue: number
  outputValue: number
  maxFeatures?: number
  title?: string
  className?: string
}

/**
 * SHAP Force Plot
 * Compact visualization showing forces pushing prediction
 */
export function ShapForce({
  features,
  baseValue,
  outputValue,
  maxFeatures = 6,
  title,
  className,
}: ShapForceProps) {
  const sortedPositive = features
    .filter(f => f.contribution > 0)
    .sort((a, b) => b.contribution - a.contribution)
    .slice(0, maxFeatures / 2)

  const sortedNegative = features
    .filter(f => f.contribution < 0)
    .sort((a, b) => a.contribution - b.contribution)
    .slice(0, maxFeatures / 2)

  const totalPositive = sortedPositive.reduce((sum, f) => sum + f.contribution, 0)
  const totalNegative = Math.abs(sortedNegative.reduce((sum, f) => sum + f.contribution, 0))

  return (
    <TooltipProvider>
      <div className={cn('space-y-3', className)}>
        {title && <h4 className="text-sm font-semibold">{title}</h4>}

        {/* Main force bar */}
        <div className="relative h-12 flex items-center">
          {/* Base marker */}
          <div className="absolute left-0 h-full flex flex-col justify-center items-center">
            <span className="text-xs text-muted-foreground">Base</span>
            <span className="text-sm font-mono">{baseValue.toFixed(2)}</span>
          </div>

          {/* Force bar */}
          <div className="absolute left-16 right-16 h-8 flex rounded-lg overflow-hidden shadow-inner bg-muted">
            {/* Negative forces (blue, left side) */}
            <div 
              className="h-full bg-gradient-to-r from-blue-500 to-blue-400 flex items-center justify-start px-2"
              style={{ width: `${(totalNegative / (totalPositive + totalNegative)) * 100}%` }}
            >
              {sortedNegative.slice(0, 2).map(f => (
                <Tooltip key={f.feature}>
                  <TooltipTrigger asChild>
                    <span className="text-xs text-white/90 truncate max-w-[60px]">
                      {f.feature}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    {f.feature}: {f.contribution.toFixed(4)}
                  </TooltipContent>
                </Tooltip>
              ))}
            </div>

            {/* Positive forces (red, right side) */}
            <div 
              className="h-full bg-gradient-to-r from-red-400 to-red-500 flex items-center justify-end px-2"
              style={{ width: `${(totalPositive / (totalPositive + totalNegative)) * 100}%` }}
            >
              {sortedPositive.slice(0, 2).map(f => (
                <Tooltip key={f.feature}>
                  <TooltipTrigger asChild>
                    <span className="text-xs text-white/90 truncate max-w-[60px]">
                      {f.feature}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    {f.feature}: +{f.contribution.toFixed(4)}
                  </TooltipContent>
                </Tooltip>
              ))}
            </div>
          </div>

          {/* Output marker */}
          <div className="absolute right-0 h-full flex flex-col justify-center items-center">
            <span className="text-xs text-muted-foreground">Output</span>
            <span className={cn(
              'text-sm font-mono font-bold',
              outputValue > baseValue ? 'text-red-600' : 'text-blue-600'
            )}>
              {outputValue.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Summary */}
        <div className="flex justify-between text-xs text-muted-foreground">
          <span className="text-blue-600">← Decreases ({sortedNegative.length} features)</span>
          <span className="text-red-600">Increases ({sortedPositive.length} features) →</span>
        </div>
      </div>
    </TooltipProvider>
  )
}
