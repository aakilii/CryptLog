import {
  AlertTriangle,
  Clock3,
  Database,
  Flame,
  GitBranch,
  Globe,
  Shield,
  type LucideIcon,
} from 'lucide-react'
import type { PanelId } from './store/useStudioStore'

export type ForensicModule =
  | 'timeline'
  | 'anomaly'
  | 'correlation'
  | 'network'
  | 'crud'
  | 'depth'
  | 'case'

export interface ForensicThemeConfig {
  id: ForensicModule
  label: string
  icon: LucideIcon
  accent: string
  textClass: string
  ringClass: string
  gradientClass: string
  softGradientClass: string
  surfaceClass: string
  chartPalette: [string, string, string, string]
  gradientCss: string
}

export const FORENSIC_THEME: Record<ForensicModule, ForensicThemeConfig> = {
  timeline: {
    id: 'timeline',
    label: 'Timeline Narrative',
    icon: Clock3,
    accent: '#06b6d4',
    textClass: 'text-cyan-600',
    ringClass: 'ring-cyan-400/35',
    gradientClass: 'bg-gradient-to-r from-cyan-400 to-indigo-500',
    softGradientClass: 'bg-gradient-to-r from-cyan-400/15 to-indigo-500/15',
    surfaceClass: 'bg-cyan-50/60 border-cyan-200/65',
    chartPalette: ['#06b6d4', '#6366f1', '#0891b2', '#4f46e5'],
    gradientCss: 'linear-gradient(135deg, #22d3ee 0%, #6366f1 100%)',
  },
  anomaly: {
    id: 'anomaly',
    label: 'Anomaly Detection',
    icon: AlertTriangle,
    accent: '#f59e0b',
    textClass: 'text-amber-600',
    ringClass: 'ring-amber-400/40',
    gradientClass: 'bg-gradient-to-r from-amber-500 to-rose-600',
    softGradientClass: 'bg-gradient-to-r from-amber-500/15 to-rose-600/15',
    surfaceClass: 'bg-amber-50/60 border-amber-200/70',
    chartPalette: ['#f59e0b', '#e11d48', '#f97316', '#fb7185'],
    gradientCss: 'linear-gradient(135deg, #f59e0b 0%, #e11d48 100%)',
  },
  correlation: {
    id: 'correlation',
    label: 'Correlation Mapping',
    icon: GitBranch,
    accent: '#8b5cf6',
    textClass: 'text-violet-600',
    ringClass: 'ring-violet-400/35',
    gradientClass: 'bg-gradient-to-r from-violet-500 to-fuchsia-500',
    softGradientClass: 'bg-gradient-to-r from-violet-500/15 to-fuchsia-500/15',
    surfaceClass: 'bg-violet-50/60 border-violet-200/70',
    chartPalette: ['#8b5cf6', '#d946ef', '#7c3aed', '#c026d3'],
    gradientCss: 'linear-gradient(135deg, #8b5cf6 0%, #d946ef 100%)',
  },
  network: {
    id: 'network',
    label: 'Network Activity',
    icon: Globe,
    accent: '#10b981',
    textClass: 'text-emerald-600',
    ringClass: 'ring-emerald-400/35',
    gradientClass: 'bg-gradient-to-r from-emerald-400 to-teal-500',
    softGradientClass: 'bg-gradient-to-r from-emerald-400/15 to-teal-500/15',
    surfaceClass: 'bg-emerald-50/60 border-emerald-200/70',
    chartPalette: ['#10b981', '#14b8a6', '#059669', '#0f766e'],
    gradientCss: 'linear-gradient(135deg, #34d399 0%, #14b8a6 100%)',
  },
  crud: {
    id: 'crud',
    label: 'CRUD & Data Access',
    icon: Database,
    accent: '#3b82f6',
    textClass: 'text-blue-600',
    ringClass: 'ring-blue-400/35',
    gradientClass: 'bg-gradient-to-r from-slate-400 to-blue-500',
    softGradientClass: 'bg-gradient-to-r from-slate-400/20 to-blue-500/15',
    surfaceClass: 'bg-slate-50/70 border-slate-200/75',
    chartPalette: ['#64748b', '#3b82f6', '#475569', '#2563eb'],
    gradientCss: 'linear-gradient(135deg, #94a3b8 0%, #3b82f6 100%)',
  },
  depth: {
    id: 'depth',
    label: 'Depth & Impact',
    icon: Flame,
    accent: '#dc2626',
    textClass: 'text-red-600',
    ringClass: 'ring-red-400/35',
    gradientClass: 'bg-gradient-to-r from-red-600 to-orange-500',
    softGradientClass: 'bg-gradient-to-r from-red-600/15 to-orange-500/15',
    surfaceClass: 'bg-red-50/60 border-red-200/70',
    chartPalette: ['#dc2626', '#f97316', '#b91c1c', '#ea580c'],
    gradientCss: 'linear-gradient(135deg, #dc2626 0%, #f97316 100%)',
  },
  case: {
    id: 'case',
    label: 'Case & Evidence Vault',
    icon: Shield,
    accent: '#fbbf24',
    textClass: 'text-amber-500',
    ringClass: 'ring-amber-300/45',
    gradientClass: 'bg-gradient-to-r from-zinc-400 to-amber-400',
    softGradientClass: 'bg-gradient-to-r from-zinc-400/20 to-amber-400/20',
    surfaceClass: 'bg-zinc-50/70 border-zinc-300/70',
    chartPalette: ['#a1a1aa', '#fbbf24', '#71717a', '#f59e0b'],
    gradientCss: 'linear-gradient(135deg, #a1a1aa 0%, #fbbf24 100%)',
  },
}

export const FORENSIC_MODULE_ORDER: ForensicModule[] = [
  'timeline',
  'anomaly',
  'correlation',
  'network',
  'crud',
  'depth',
  'case',
]

const PANEL_THEME_MAP: Record<PanelId, ForensicModule> = {
  templates: 'case',
  timeline: 'timeline',
  anomaly: 'anomaly',
  correlation: 'correlation',
  network: 'network',
  crud: 'crud',
  depth: 'depth',
  vault: 'case',
  uploads: 'case',
  text: 'case',
  elements: 'case',
  evidence_binder: 'case',
}

export const moduleFromPanel = (panelId?: PanelId | null): ForensicModule | null => {
  if (!panelId) return null
  return PANEL_THEME_MAP[panelId] || null
}

export const themeFromPanel = (panelId?: PanelId | null): ForensicThemeConfig | null => {
  const moduleId = moduleFromPanel(panelId)
  return moduleId ? FORENSIC_THEME[moduleId] : null
}
