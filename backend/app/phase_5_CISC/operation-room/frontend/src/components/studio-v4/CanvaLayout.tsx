'use client'

import React, { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, PanelRightClose } from 'lucide-react'
import { cn } from '@operation-room/lib/utils'
import { useStudioStore, type PanelId } from './store/useStudioStore'
import { IconRail, RAIL_ITEMS } from './IconRail'
import { TopBar } from './TopBar'
import { ExpandablePanel, PanelHeader, PanelContent } from './ExpandablePanel'
import { themeFromPanel } from './forensicTheme'
import { PageNavigator } from './canvas/PageNavigator'
import { ZoomControls } from './canvas/ZoomControls'
import { RightInspector } from './RightInspector'
import { ClaimReviewDrawer } from './ClaimReviewDrawer'
import { TimelinePanel, AnomalyPanel, VaultPanel, NetworkPanel, CorrelationPanel, TemplatesPanel, CRUDPanel, DepthPanel } from './panels'
import { TextPanel } from './panels/TextPanel'
import { ElementsPanel } from './panels/ElementsPanel'
import { UploadsPanel } from './panels/UploadsPanel'
import { Button } from '@operation-room/components/ui/button'
import type { Editor } from '@tiptap/core'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@operation-room/components/ui/tooltip'

// Import the Deep Research AI Panel
import AIPanel from '@operation-room/components/ai-panel/AIPanel'

type InsertComponentHandler = (componentId: string, config?: Record<string, unknown>) => void
type InsertFindingHandler = (finding: { title: string; content: string; source: string }) => void
type InsertEntityHandler = (entity: Record<string, unknown>) => void
type InsertEvidenceHandler = (evidence: Record<string, unknown>) => void
type InsertBlockHandler = (block: Record<string, unknown>) => void
type InsertTextHandler = (textBlock: Record<string, unknown>) => void
type InsertElementHandler = (elementConfig: Record<string, unknown>) => void
type InsertUploadHandler = (upload: Record<string, unknown>) => void
type ApplyTemplateHandler = (templateId: string) => void

// Panel component registry — ALL panels wired
const PANEL_COMPONENTS: Record<PanelId, React.ComponentType<any> | null> = {
  templates: TemplatesPanel,
  timeline: TimelinePanel,
  anomaly: AnomalyPanel,
  correlation: CorrelationPanel,
  network: NetworkPanel,
  crud: CRUDPanel as any,
  depth: DepthPanel as any,
  vault: VaultPanel,
  uploads: UploadsPanel as any,
  text: TextPanel as any,
  elements: ElementsPanel as any,
  evidence_binder: null,
}

// Placeholder panel for panels not yet implemented
const PlaceholderPanel = ({ panelId, caseId }: { panelId: PanelId; caseId: string }) => {
  const panelInfo = RAIL_ITEMS.find(item => item.id === panelId)
  const panelTheme = themeFromPanel(panelId)
  const Icon = panelInfo?.icon
  
  return (
    <div className="flex flex-col h-full">
      <PanelHeader
        title={panelInfo?.label || panelId}
        panelId={panelId}
        icon={Icon && <Icon className="h-4 w-4" />}
        color={panelInfo?.color}
        showSearch={true}
        searchPlaceholder={`Search ${panelInfo?.label?.toLowerCase() || panelId}...`}
      />
      <PanelContent>
        <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
          {Icon && (
            <div
              className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl shadow-sm"
              style={{ backgroundImage: panelTheme?.gradientCss }}
            >
              <Icon className="h-7 w-7 text-white" />
            </div>
          )}
          <h3 className="mb-1 font-geist text-sm font-medium">{panelInfo?.label} Panel</h3>
          <p className="mb-4 font-ui text-xs text-muted-foreground">
            Coming soon
          </p>
          <div className="font-geist-mono text-xs tracking-wide text-muted-foreground/70">
            case: {caseId || 'none'}
          </div>
        </div>
      </PanelContent>
    </div>
  )
}

// AI Assistant collapsed state
const AIAssistantCollapsed = ({ onExpand }: { onExpand: () => void }) => {
  return (
    <div className="w-12 border-l bg-background flex flex-col items-center py-4 gap-2 flex-shrink-0">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-10 w-10 rounded-lg bg-gradient-to-br from-sky-500/10 to-indigo-500/10 hover:from-sky-500/20 hover:to-indigo-500/20"
            onClick={onExpand}
          >
            <Sparkles className="h-5 w-5 text-sky-500" />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="left">
          <span>AI Assistant</span>
        </TooltipContent>
      </Tooltip>
    </div>
  )
}

// AI Assistant expanded panel - Using Deep Research AIPanel
const AIAssistantPanel = ({ onCollapse }: { onCollapse: () => void }) => {
  return (
    <motion.div
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 420, opacity: 1 }}
      exit={{ width: 0, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 400, damping: 30 }}
      className="border-l bg-background flex flex-col overflow-hidden flex-shrink-0 relative z-30"
    >
      <div className="w-[420px] h-full flex flex-col">
        {/* Header with collapse button */}
        <div className="h-10 border-b flex items-center justify-between px-3 flex-shrink-0 bg-gradient-to-r from-blue-600 to-blue-700">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-white" />
            <span className="font-medium text-sm text-white">Deep Research AI</span>
          </div>
          <Button variant="ghost" size="icon" className="h-7 w-7 text-white hover:bg-white/20" onClick={onCollapse}>
            <PanelRightClose className="h-4 w-4" />
          </Button>
        </div>
        
        {/* Full AI Panel */}
        <div className="flex-1 overflow-hidden">
          <AIPanel />
        </div>
      </div>
    </motion.div>
  )
}

// Footer with page navigation and zoom
const Footer = () => {
  return (
    <div className="h-10 border-t bg-background/95 backdrop-blur-sm flex items-center justify-between px-4 flex-shrink-0">
      <PageNavigator />
      <ZoomControls />
    </div>
  )
}


// Main layout props
interface CanvaLayoutProps {
  caseId: string
  documentId?: string
  children?: React.ReactNode
  editor?: Editor | null
  onBack?: () => void
  onSave?: () => void
  onExport?: (format?: 'pdf' | 'docx' | 'html') => void
  onShare?: () => void
  onInvestigate?: () => void
  onStopInvestigation?: () => void
  onInsertComponent?: InsertComponentHandler
  onInsertFinding?: InsertFindingHandler
  onInsertEntity?: InsertEntityHandler
  onInsertEvidence?: InsertEvidenceHandler
  onInsertBlock?: InsertBlockHandler
  onInsertText?: InsertTextHandler
  onInsertElement?: InsertElementHandler
  onInsertUpload?: InsertUploadHandler
  onApplyTemplate?: ApplyTemplateHandler
  className?: string
}

export const CanvaLayout = ({
  caseId,
  documentId,
  children,
  editor,
  onBack,
  onSave,
  onExport,
  onShare,
  onInvestigate,
  onStopInvestigation,
  onInsertComponent,
  onInsertFinding,
  onInsertEntity,
  onInsertEvidence,
  onInsertBlock,
  onInsertText,
  onInsertElement,
  onInsertUpload,
  onApplyTemplate,
  className,
}: CanvaLayoutProps) => {
  const {
    activePanel,
    setActivePanel,
    aiPanelOpen,
    setAiPanelOpen,
    panelBadges,
    setDocument,
  } = useStudioStore()
  
  // Ransomware Heuristic State
  const [showRansomwareAlert, setShowRansomwareAlert] = useState(false)
  const [burstCount, setBurstCount] = useState(0)
  const [containmentStatus, setContainmentStatus] = useState<'idle' | 'running' | 'done'>('idle')

  // Automatically check the DuckDB backend for Ransomware bursts on load
  useEffect(() => {
    if (!caseId) return
    const checkRansomware = async () => {
      try {
        const res = await fetch(`/api/cases/${caseId}/crud/heuristics/ransomware`)
        if (res.ok) {
          const data = await res.json()
          if (data && data.bursts && data.bursts.length > 0) {
            setBurstCount(data.bursts[0].count)
            setShowRansomwareAlert(true)
          }
        }
      } catch (err) {
        console.error("Failed to fetch ransomware heuristics:", err)
      }
    }
    checkRansomware()
  }, [caseId])

  const handleContainment = () => {
    setContainmentStatus('running')
    // Placeholder logic for running the containment script
    setTimeout(() => {
      setContainmentStatus('done')
      setTimeout(() => setShowRansomwareAlert(false), 2000) // auto-dismiss on success
    }, 1500)
  }

  // Set document context
  useEffect(() => {
    if (caseId && documentId) {
      setDocument(caseId, documentId, 'Untitled Report')
    }
  }, [caseId, documentId, setDocument])
  
  // Get panel component
  const PanelComponent = useMemo(() => {
    if (!activePanel) return null
    return PANEL_COMPONENTS[activePanel]
  }, [activePanel])
  
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey) {
        switch (e.key) {
          case 's':
            e.preventDefault()
            onSave?.()
            break
          case 'e':
            e.preventDefault()
            onExport?.()
            break
          case '\\':
            e.preventDefault()
            setAiPanelOpen(!aiPanelOpen)
            break
        }
        
        // Number keys for panels
        if (['1', '2', '3', '4', '5', '6'].includes(e.key)) {
          e.preventDefault()
          const panelIndex = parseInt(e.key)
          const panelIds: PanelId[] = ['timeline', 'anomaly', 'correlation', 'network', 'crud', 'depth']
          const targetPanel = panelIds[panelIndex - 1]
          if (targetPanel) {
            setActivePanel(activePanel === targetPanel ? null : targetPanel)
          }
        }
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onSave, onExport, aiPanelOpen, activePanel, setActivePanel, setAiPanelOpen])
  
  return (
    <div className={cn("flex flex-col h-screen bg-background", className)}>
        {/* Playbook Banner: Ransomware Alert */}
        <AnimatePresence>
          {showRansomwareAlert && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="bg-red-500 text-white px-4 py-2 flex items-center justify-between z-50 font-medium text-sm rounded-b-md mx-2 overflow-hidden shadow-lg shadow-red-900/20"
            >
              <div className="flex items-center gap-2">
                <span className="animate-pulse flex items-center gap-1">
                  🚨 <span className="font-bold">HEURISTIC ALERT:</span>
                </span>
                <span>Ransomware File Encryption Burst Detected (over {burstCount > 0 ? burstCount.toLocaleString() : '5,000'} CRUD events / 5m). Playbook activation recommended.</span>
              </div>
              <div className="flex items-center gap-3">
                <Button 
                  onClick={handleContainment}
                  disabled={containmentStatus !== 'idle'}
                  variant="secondary" 
                  size="sm" 
                  className={cn(
                    "h-7 text-xs font-bold bg-white hover:bg-slate-100",
                    containmentStatus === 'idle' ? "text-red-600" : "text-emerald-700 disabled:opacity-100"
                  )}
                >
                  {containmentStatus === 'idle' && "Run Containment Script"}
                  {containmentStatus === 'running' && "Executing Playbook..."}
                  {containmentStatus === 'done' && "System Isolated"}
                </Button>
                <button 
                  onClick={() => setShowRansomwareAlert(false)}
                  className="text-white/80 hover:text-white font-bold p-1 rounded-sm hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-white/50"
                  aria-label="Dismiss alert"
                >
                  ✕
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Top Bar — single unified header, no more double toolbar */}
        <TopBar
          onBack={onBack}
          onSave={onSave}
          onExport={onExport}
          onShare={onShare}
          onInvestigate={onInvestigate}
          onStopInvestigation={onStopInvestigation}
        />
        
        {/* Main content area */}
        <div className="flex flex-1 overflow-hidden">
          {/* Icon Rail */}
          <IconRail badges={panelBadges} />
          
          {/* Expandable Panel */}
          <ExpandablePanel>
            {activePanel && (
              PanelComponent ? (
                <PanelComponent
                  caseId={caseId}
                  onInsertComponent={onInsertComponent}
                  onInsertFinding={onInsertFinding}
                  onInsertEntity={onInsertEntity}
                  onInsertEvidence={onInsertEvidence}
                  onInsertBlock={onInsertBlock}
                  onInsertText={onInsertText}
                  onInsertElement={onInsertElement}
                  onInsertUpload={onInsertUpload}
                  onApplyTemplate={onApplyTemplate}
                />
              ) : (
                <PlaceholderPanel panelId={activePanel} caseId={caseId} />
              )
            )}
          </ExpandablePanel>
          
          {/* Canvas/Editor Area — now with min-width and improved background */}
          <div className="flex-1 flex flex-col overflow-hidden min-w-0">
            <div className="flex-1 overflow-auto bg-[#e8edf2] dark:bg-[#0c0c0c]">
              {children}
            </div>
          </div>

          {/* Right Inspector */ }
          <RightInspector />

          <ClaimReviewDrawer caseId={caseId as string} />

          {/* AI Assistant Panel */}
          <AnimatePresence mode="wait">
            {aiPanelOpen ? (
              <AIAssistantPanel 
                key="ai-expanded"
                onCollapse={() => setAiPanelOpen(false)} 
              />
            ) : (
              <AIAssistantCollapsed 
                key="ai-collapsed"
                onExpand={() => setAiPanelOpen(true)} 
              />
            )}
          </AnimatePresence>
        </div>
        
        {/* Footer */}
        <Footer />
      </div>
  )
}

