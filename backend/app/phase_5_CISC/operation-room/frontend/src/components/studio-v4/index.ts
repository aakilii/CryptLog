// Studio V4 — Canva-Style Report Builder

// Layout components
export { CanvaLayout } from './CanvaLayout'
export { IconRail, RAIL_ITEMS, type RailItem } from './IconRail'
export { TopBar } from './TopBar'
export {
  ExpandablePanel,
  PanelHeader,
  PanelContent,
  PanelSection,
  PanelEmptyState,
  PanelLoading,
  ComponentCard,
  MetricCard,
  FindingCard,
} from './ExpandablePanel'

// Store
export {
  useStudioStore,
  useActivePanel,
  useSelection,
  useZoom,
  useAiPanel,
  useSaveState,
  type PanelId,
  type SelectionType,
  type SelectionContext,
  type PageMeta,
} from './store/useStudioStore'

// Context
export { EditorProvider, useEditorContext } from './context/EditorContext'

// Toolbar
export { CanvaToolbar, ChartToolbar, EvidenceToolbar, FloatingToolbar, ChartInspector } from './toolbar'

// Dialogs
export { ExportGateDialog } from './dialogs/ExportGateDialog'

// Panels — all modules
export {
  TimelinePanel,
  AnomalyPanel,
  CorrelationPanel,
  NetworkPanel,
  CRUDPanel,
  DepthPanel,
  VaultPanel,
  TextPanel,
  ElementsPanel,
  UploadsPanel,
  TemplatesPanel,
} from './panels'

// Canvas
export { DocumentCanvas } from './canvas/DocumentCanvas'
export { PageNavigator } from './canvas/PageNavigator'
export { ZoomControls } from './canvas/ZoomControls'

// Theme
export { FORENSIC_THEME, FORENSIC_MODULE_ORDER, type ForensicModule, type ForensicThemeConfig } from './forensicTheme'
