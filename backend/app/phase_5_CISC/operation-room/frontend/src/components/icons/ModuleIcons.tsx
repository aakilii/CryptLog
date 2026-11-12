/**
 * NFLIP Module Icons
 * Consistent icon system using Lucide React
 * Replaces all emoji icons with professional SVG icons
 */

import {
  Clock,
  AlertTriangle,
  GitBranch,
  Database,
  Globe,
  Layers,
  Briefcase,
  FileText,
  Shield,
  Hash,
  CheckCircle,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Info,
  Sparkles,
  Bot,
  Download,
  Upload,
  Save,
  Undo,
  Redo,
  Plus,
  Minus,
  X,
  Search,
  Settings,
  MoreHorizontal,
  MoreVertical,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Link,
  Copy,
  Clipboard,
  ClipboardCheck,
  Eye,
  EyeOff,
  Edit,
  Trash2,
  RefreshCw,
  Loader2,
  Calendar,
  Filter,
  LayoutGrid,
  List,
  Table,
  BarChart3,
  PieChart,
  LineChart,
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  Target,
  Radar,
  Network,
  Server,
  HardDrive,
  Folder,
  FolderOpen,
  File,
  FileCheck,
  FilePlus,
  FileWarning,
  Lock,
  Unlock,
  Key,
  User,
  Users,
  UserCheck,
  MessageSquare,
  Send,
  Bookmark,
  Star,
  Flag,
  Tag,
  BarChart2,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@operation-room/lib/utils'
import type { ModuleType, SeverityLevel } from '@operation-room/lib/utils'

// Module icon mapping
export const MODULE_ICONS: Record<ModuleType, LucideIcon> = {
  timeline: Clock,
  anomaly: AlertTriangle,
  correlation: GitBranch,
  crud: Database,
  network: Globe,
  depth: Layers,
  case: Briefcase,
} as const

// Module icon colors (Tailwind classes)
export const MODULE_ICON_COLORS: Record<ModuleType, string> = {
  timeline: 'text-cyan-600 dark:text-cyan-400',
  anomaly: 'text-amber-600 dark:text-amber-400',
  correlation: 'text-violet-600 dark:text-violet-400',
  crud: 'text-blue-600 dark:text-blue-400',
  network: 'text-emerald-600 dark:text-emerald-400',
  depth: 'text-red-600 dark:text-red-400',
  case: 'text-amber-500 dark:text-amber-300',
} as const

// Module background colors
export const MODULE_BG_COLORS: Record<ModuleType, string> = {
  timeline: 'bg-cyan-100 dark:bg-cyan-900/30',
  anomaly: 'bg-amber-100 dark:bg-amber-900/30',
  correlation: 'bg-violet-100 dark:bg-violet-900/30',
  crud: 'bg-blue-100 dark:bg-blue-900/30',
  network: 'bg-emerald-100 dark:bg-emerald-900/30',
  depth: 'bg-red-100 dark:bg-red-900/30',
  case: 'bg-zinc-100 dark:bg-zinc-900/30',
} as const

// Severity icon mapping
export const SEVERITY_ICONS: Record<SeverityLevel, LucideIcon> = {
  critical: XCircle,
  high: AlertTriangle,
  medium: AlertCircle,
  low: Info,
  info: Info,
} as const

// Severity icon colors
export const SEVERITY_ICON_COLORS: Record<SeverityLevel, string> = {
  critical: 'text-red-600 dark:text-red-400',
  high: 'text-orange-600 dark:text-orange-400',
  medium: 'text-yellow-600 dark:text-yellow-400',
  low: 'text-green-600 dark:text-green-400',
  info: 'text-blue-600 dark:text-blue-400',
} as const

// Module display names
export const MODULE_NAMES: Record<ModuleType, string> = {
  timeline: 'Timeline',
  anomaly: 'Anomaly Detection',
  correlation: 'Correlation & RCA',
  crud: 'CRUD Analysis',
  network: 'Network Analysis',
  depth: 'Depth Analysis',
  case: 'Case & Evidence',
} as const

// Module descriptions
export const MODULE_DESCRIPTIONS: Record<ModuleType, string> = {
  timeline: 'Event timeline and temporal analysis',
  anomaly: 'Machine learning-based anomaly detection with SHAP explainability',
  correlation: 'Entity correlation and root cause analysis',
  crud: 'Create, Read, Update, Delete access pattern analysis',
  network: 'Network traffic and communication analysis',
  depth: 'Deep dive impact and blast radius analysis',
  case: 'Case management and chain of custody',
} as const

interface ModuleIconProps {
  module: ModuleType
  size?: 'sm' | 'md' | 'lg' | 'xl'
  withBackground?: boolean
  className?: string
}

const sizeClasses = {
  sm: 'h-4 w-4',
  md: 'h-5 w-5',
  lg: 'h-6 w-6',
  xl: 'h-8 w-8',
} as const

const bgSizeClasses = {
  sm: 'p-1.5',
  md: 'p-2',
  lg: 'p-2.5',
  xl: 'p-3',
} as const

/**
 * Module Icon Component
 * Renders the appropriate icon for a given module with consistent styling
 */
export function ModuleIcon({ 
  module, 
  size = 'md', 
  withBackground = false,
  className 
}: ModuleIconProps) {
  const Icon = MODULE_ICONS[module]
  const colorClass = MODULE_ICON_COLORS[module]
  const bgClass = MODULE_BG_COLORS[module]
  const sizeClass = sizeClasses[size]
  
  if (withBackground) {
    return (
      <div className={cn(
        'inline-flex items-center justify-center rounded-lg',
        bgClass,
        bgSizeClasses[size],
        className
      )}>
        <Icon className={cn(sizeClass, colorClass)} />
      </div>
    )
  }
  
  return <Icon className={cn(sizeClass, colorClass, className)} />
}

interface SeverityIconProps {
  severity: SeverityLevel
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

/**
 * Severity Icon Component
 * Renders the appropriate icon for a given severity level
 */
export function SeverityIcon({ severity, size = 'md', className }: SeverityIconProps) {
  const Icon = SEVERITY_ICONS[severity]
  const colorClass = SEVERITY_ICON_COLORS[severity]
  const sizeClass = sizeClasses[size]
  
  return <Icon className={cn(sizeClass, colorClass, className)} />
}

// Common action icons
export const ActionIcons = {
  save: Save,
  download: Download,
  upload: Upload,
  export: Download,
  import: Upload,
  add: Plus,
  remove: Minus,
  delete: Trash2,
  edit: Edit,
  copy: Copy,
  paste: Clipboard,
  search: Search,
  filter: Filter,
  settings: Settings,
  more: MoreHorizontal,
  moreVertical: MoreVertical,
  close: X,
  refresh: RefreshCw,
  undo: Undo,
  redo: Redo,
  externalLink: ExternalLink,
  link: Link,
  eye: Eye,
  eyeOff: EyeOff,
} as const

// Status icons
export const StatusIcons = {
  success: CheckCircle2,
  error: XCircle,
  warning: AlertCircle,
  info: Info,
  loading: Loader2,
} as const

// Navigation icons
export const NavIcons = {
  chevronRight: ChevronRight,
  chevronLeft: ChevronLeft,
  chevronDown: ChevronDown,
  chevronUp: ChevronUp,
} as const

// Chart icons
export const ChartIcons = {
  bar: BarChart3,
  pie: PieChart,
  line: LineChart,
  area: Activity,
  radar: Radar,
  table: Table,
} as const

// AI/Agent icons
export const AIIcons = {
  sparkles: Sparkles,
  bot: Bot,
  magic: Sparkles,
  generate: Sparkles,
} as const

// Export all icons for direct use
export {
  // Layout
  LayoutGrid,
  List,
  Table,
  // Charts
  BarChart3,
  PieChart,
  LineChart,
  TrendingUp,
  TrendingDown,
  Activity,
  // Files
  File,
  FileText,
  FileCheck,
  FilePlus,
  FileWarning,
  Folder,
  FolderOpen,
  // Security
  Lock,
  Unlock,
  Key,
  Shield,
  Hash,
  // Users
  User,
  Users,
  UserCheck,
  // Communication
  MessageSquare,
  Send,
  // Organization
  Bookmark,
  Star,
  Flag,
  Tag,
  // Infrastructure
  Server,
  HardDrive,
  Network,
  Globe,
  // AI
  Sparkles,
  Bot,
  // Status
  CheckCircle,
  CheckCircle2,
  XCircle,
  AlertCircle,
  AlertTriangle,
  Info,
  Loader2,
  // Actions
  Plus,
  Minus,
  X,
  Edit,
  Trash2,
  Copy,
  Clipboard,
  ClipboardCheck,
  Save,
  Download,
  Upload,
  RefreshCw,
  Search,
  Filter,
  Settings,
  Eye,
  EyeOff,
  ExternalLink,
  Link,
  Undo,
  Redo,
  MoreHorizontal,
  MoreVertical,
  // Navigation
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  // Time
  Clock,
  Calendar,
  // Analysis
  Target,
  Radar,
  Zap,
  Layers,
  GitBranch,
  Database,
  Briefcase,
  BarChart2,
}
