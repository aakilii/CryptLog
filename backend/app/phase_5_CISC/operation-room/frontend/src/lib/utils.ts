import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Merge Tailwind CSS classes with clsx
 * Handles conflicting classes intelligently
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format a date to a human-readable string
 */
export function formatDate(date: Date | string, options?: Intl.DateTimeFormatOptions): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...options,
  })
}

/**
 * Format a date to ISO timestamp
 */
export function formatTimestamp(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toISOString()
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
export function formatRelativeTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  
  if (days > 0) return `${days}d ago`
  if (hours > 0) return `${hours}h ago`
  if (minutes > 0) return `${minutes}m ago`
  return 'just now'
}

/**
 * Truncate a string with ellipsis
 */
export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length) + '...'
}

/**
 * Truncate a hash for display
 */
export function truncateHash(hash: string, length: number = 8): string {
  if (hash.length <= length * 2) return hash
  return `${hash.slice(0, length)}...${hash.slice(-length)}`
}

/**
 * Generate a unique ID
 */
export function generateId(prefix: string = 'id'): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

/**
 * Debounce a function
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}

/**
 * Format number with commas
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num)
}

/**
 * Format percentage
 */
export function formatPercentage(value: number, decimals: number = 1): string {
  return `${(value * 100).toFixed(decimals)}%`
}

/**
 * Format bytes to human-readable size
 */
export function formatBytes(bytes: number, decimals: number = 2): string {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const dm = decimals < 0 ? 0 : decimals
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`
}

/**
 * Module type for the NFLIP platform
 */
export type ModuleType = 'timeline' | 'anomaly' | 'correlation' | 'crud' | 'network' | 'depth' | 'case'

/**
 * Severity level type
 */
export type SeverityLevel = 'critical' | 'high' | 'medium' | 'low' | 'info'

/**
 * Get module color class
 */
export function getModuleColor(module: ModuleType): string {
  const colors: Record<ModuleType, string> = {
    timeline: 'text-module-timeline',
    anomaly: 'text-module-anomaly',
    correlation: 'text-module-correlation',
    crud: 'text-module-crud',
    network: 'text-module-network',
    depth: 'text-module-depth',
    case: 'text-module-case',
  }
  return colors[module]
}

/**
 * Get module background color class
 */
export function getModuleBgColor(module: ModuleType): string {
  const colors: Record<ModuleType, string> = {
    timeline: 'bg-module-timeline/10',
    anomaly: 'bg-module-anomaly/10',
    correlation: 'bg-module-correlation/10',
    crud: 'bg-module-crud/10',
    network: 'bg-module-network/10',
    depth: 'bg-module-depth/10',
    case: 'bg-module-case/10',
  }
  return colors[module]
}

/**
 * Get severity color class
 */
export function getSeverityColor(severity: SeverityLevel): string {
  const colors: Record<SeverityLevel, string> = {
    critical: 'text-severity-critical',
    high: 'text-severity-high',
    medium: 'text-severity-medium',
    low: 'text-severity-low',
    info: 'text-severity-info',
  }
  return colors[severity]
}

/**
 * Get severity background color class
 */
export function getSeverityBgColor(severity: SeverityLevel): string {
  const colors: Record<SeverityLevel, string> = {
    critical: 'bg-severity-critical/10',
    high: 'bg-severity-high/10',
    medium: 'bg-severity-medium/10',
    low: 'bg-severity-low/10',
    info: 'bg-severity-info/10',
  }
  return colors[severity]
}
