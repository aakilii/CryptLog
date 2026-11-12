'use client'

import React from 'react'
import { 
  ArrowLeft, 
  Save, 
  Download, 
  Share2, 
  MoreHorizontal,
  Check,
  Loader2,
  Clock,
  FileText,
  ChevronDown,
  Sparkles,
  StopCircle,
} from 'lucide-react'
import { cn } from '@operation-room/lib/utils'
import { useStudioStore } from './store/useStudioStore'
import { Button } from '@operation-room/components/ui/button'
import { Input } from '@operation-room/components/ui/input'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@operation-room/components/ui/dropdown-menu'
import { FORENSIC_THEME } from './forensicTheme'
import { PlaybookLauncher } from './PlaybookLauncher'
import { HelperPopover } from '@operation-room/components/ui/HelperPopover'
import { Progress } from '@operation-room/components/ui/progress'

interface TopBarProps {
  onBack?: () => void
  onSave?: () => void
  onExport?: () => void
  onShare?: () => void
  onInvestigate?: () => void
  onStopInvestigation?: () => void
  className?: string
}

export const TopBar = ({
  onBack,
  onSave,
  onExport,
  onShare,
  onInvestigate,
  onStopInvestigation,
  className,
}: TopBarProps) => {
  const caseTheme = FORENSIC_THEME.case
  const documentTitle = useStudioStore((state) => state.documentTitle)
  const setDocumentTitle = useStudioStore((state) => state.setDocumentTitle)
  const isSaving = useStudioStore((state) => state.isSaving)
  const hasChanges = useStudioStore((state) => state.hasChanges)
  const lastSaved = useStudioStore((state) => state.lastSaved)
  const focusMode = useStudioStore((state) => state.focusMode)
  const setFocusMode = useStudioStore((state) => state.setFocusMode)
  const caseId = useStudioStore((state) => state.caseId)
  const investigationRunning = useStudioStore((state) => state.investigationRunning)
  const investigationProgress = useStudioStore((state) => state.investigationProgress)
  const [isEditingTitle, setIsEditingTitle] = React.useState(false)
  const [tempTitle, setTempTitle] = React.useState(documentTitle)
  const inputRef = React.useRef<HTMLInputElement>(null)
  
  const handleTitleSubmit = () => {
    if (tempTitle.trim()) {
      setDocumentTitle(tempTitle.trim())
    } else {
      setTempTitle(documentTitle)
    }
    setIsEditingTitle(false)
  }
  
  const handleTitleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleTitleSubmit()
    } else if (e.key === 'Escape') {
      setTempTitle(documentTitle)
      setIsEditingTitle(false)
    }
  }
  
  React.useEffect(() => {
    if (isEditingTitle && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditingTitle])
  
  const formatLastSaved = () => {
    if (!lastSaved) return 'Not saved yet'
    const now = new Date()
    const diff = now.getTime() - lastSaved.getTime()
    const minutes = Math.floor(diff / 60000)
    if (minutes < 1) return 'Just now'
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    return lastSaved.toLocaleDateString()
  }
  
  return (
    <div 
      className={cn(
        "flex h-12 items-center justify-between border-b bg-background/95 px-4 backdrop-blur-sm",
        className
      )}
    >
      {/* Left section: Back + Title */}
      <div className="flex items-center gap-3">
          {/* Back button (tooltip removed) */}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onBack}
            aria-label="Back to Case"
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          
          {/* Document icon */}
          <div
            className="flex h-8 w-8 items-center justify-center rounded-md text-white shadow-sm"
            style={{ backgroundImage: caseTheme.gradientCss }}
          >
            <FileText className="h-4 w-4" />
          </div>
          
          {/* Title */}
          <div className="flex items-center gap-2">
            {isEditingTitle ? (
              <Input
                ref={inputRef}
                value={tempTitle}
                onChange={(e) => setTempTitle(e.target.value)}
                onBlur={handleTitleSubmit}
                onKeyDown={handleTitleKeyDown}
                className="h-8 w-64 font-geist text-sm font-medium"
              />
            ) : (
              <button
                onClick={() => {
                  setTempTitle(documentTitle)
                  setIsEditingTitle(true)
                }}
                className="rounded px-2 py-1 font-geist text-sm font-medium transition-colors hover:bg-muted"
              >
                {documentTitle}
              </button>
            )}
            
            {/* Save status indicator */}
            <div className="flex items-center gap-1.5 font-ui text-xs text-muted-foreground">
              {isSaving ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Saving...</span>
                </>
              ) : hasChanges ? (
                <>
                  <div className="h-2 w-2 rounded-full bg-amber-500" />
                  <span>Unsaved changes</span>
                </>
              ) : lastSaved ? (
                <>
                  <Check className="h-3 w-3 text-green-500" />
                  <span>{formatLastSaved()}</span>
                </>
              ) : null}
            </div>
          </div>
      </div>

      {/* Middle Section: Storyboard Focus Toggle */}
      <div className="hidden md:flex items-center justify-center absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 bg-slate-100 p-1 rounded-md border border-slate-200 shadow-sm z-10 transition-colors">
        {(['Story', 'Evidence', 'Review', 'Redact'] as const).map((mode) => (
          <Button
            key={mode}
            variant={focusMode === mode ? "default" : "ghost"}
            size="sm"
            className={cn(
              "h-7 px-3 text-xs font-semibold rounded-sm transition-all duration-200", 
              focusMode === mode 
                ? "bg-slate-900 text-white shadow-sm" 
                : "text-slate-500 hover:bg-slate-200 hover:text-slate-900"
            )}
            onClick={() => setFocusMode(mode)}
          >
            {mode}
          </Button>
        ))}
      </div>

      {/* Right section: Actions */}
      <div className="flex items-center gap-2">
          {/* AI Investigate Button */}
          {investigationRunning ? (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-violet-500 to-purple-600 rounded-md">
              <Loader2 className="h-4 w-4 text-white animate-spin" />
              <span className="text-xs font-medium text-white">
                {investigationProgress}%
              </span>
              <div className="w-16 h-1.5 bg-white/30 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-white rounded-full transition-all duration-300"
                  style={{ width: `${investigationProgress}%` }}
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 text-white hover:bg-white/20"
                onClick={onStopInvestigation}
              >
                <StopCircle className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <Button
              variant="default"
              size="sm"
              className="h-8 gap-1.5 bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 text-white font-ui"
              onClick={onInvestigate}
            >
              <Sparkles className="h-4 w-4" />
              AI Investigate
            </Button>
          )}
          
          {/* Phase 2: The Playbook Guardrails */}
          <PlaybookLauncher caseId={caseId || 'CASE-FORENSIC-001'} />
          
          {/* Save button */}
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 font-ui"
            onClick={onSave}
            disabled={isSaving || !hasChanges}
            aria-label="Save document"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save
          </Button>
          
          {/* Export button — opens ExportGateDialog */}
          <div className="relative flex h-8 items-center cursor-pointer group" onClick={() => onExport?.()}> 
            <span className="absolute -left-1 flex h-full items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-sky-400 opacity-20"></span>
              <div className="pointer-events-auto">
                <HelperPopover
                  title="Governance Gate"
                  description="Finalize report generation. Evaluates admissibility, validates evidence UUIDs, and checks signatures against unbacked claims before rendering PDF."
                  side="bottom"
                />
              </div>
            </span>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1.5 font-ui ml-2 pointer-events-none"
            >
              <Download className="h-4 w-4" />
              Export
            </Button>
          </div>
          
          {/* Share button */}
          <Button
            variant="default"
            size="sm"
            className="h-8 gap-1.5 bg-primary font-ui hover:bg-primary/90"
            onClick={onShare}
            aria-label="Share document"
          >
            <Share2 className="h-4 w-4" />
            Share
          </Button>
          
          {/* More options */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem>Document Settings</DropdownMenuItem>
              <DropdownMenuItem>Version History</DropdownMenuItem>
              <DropdownMenuItem>Print Preview</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem>Keyboard Shortcuts</DropdownMenuItem>
              <DropdownMenuItem>Help & Documentation</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
  )
}
