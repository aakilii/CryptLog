'use client'

import React, { useState, useCallback, useEffect, useRef } from 'react'
import type { Editor } from '@tiptap/core'
import {
  Palette, BarChart3, Layout, Ruler, Pin, RefreshCw,
  ChevronDown, X, Eye, EyeOff,
} from 'lucide-react'
import { cn } from '@operation-room/lib/utils'
import { Button } from '@operation-room/components/ui/button'
import { Separator } from '@operation-room/components/ui/separator'
import { Switch } from '@operation-room/components/ui/switch'
import { Label } from '@operation-room/components/ui/label'
import { RefreshDiffDialog } from '../dialogs/RefreshDiffDialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@operation-room/components/ui/select'
import { useStudioStore } from '../store/useStudioStore'

// ── Forensic-safe color palettes ────────────────────────────────────────
const CHART_PALETTES = [
  { id: 'default', name: 'Professional', colors: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'] },
  { id: 'ocean', name: 'Ocean', colors: ['#0ea5e9', '#06b6d4', '#14b8a6', '#22c55e', '#84cc16'] },
  { id: 'warm', name: 'Warm', colors: ['#f43f5e', '#f97316', '#eab308', '#a3e635', '#22d3ee'] },
  { id: 'monochrome', name: 'Monochrome', colors: ['#1e293b', '#334155', '#64748b', '#94a3b8', '#cbd5e1'] },
  { id: 'forensic', name: 'Forensic', colors: ['#dc2626', '#ea580c', '#d97706', '#0284c7', '#7c3aed'] },
]

const CHART_SIZES = [
  { id: 'compact', label: 'Compact', height: '160px' },
  { id: 'standard', label: 'Standard', height: '280px' },
  { id: 'full', label: 'Full Width', height: '400px' },
]

const LEGEND_POSITIONS = [
  { id: 'none', label: 'None' },
  { id: 'top', label: 'Top' },
  { id: 'bottom', label: 'Bottom' },
  { id: 'right', label: 'Right' },
]

// ── Chart Inspector ─────────────────────────────────────────────────────
interface ChartInspectorProps {
  editor: Editor | null
  onRefreshData?: (blockId: string) => void
}

export const ChartInspector = ({ editor, onRefreshData }: ChartInspectorProps) => {
  const caseId = useStudioStore((state) => state.caseId) || ''
  const panelRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  const [blockId, setBlockId] = useState<string | null>(null)
  const [coords, setCoords] = useState({ top: 0, right: 0 })

  // Config state
  const [palette, setPalette] = useState('default')
  const [size, setSize] = useState('standard')
  const [showLabels, setShowLabels] = useState(true)
  const [showLegend, setShowLegend] = useState('bottom')
  const [showGrid, setShowGrid] = useState(true)
  const [pinned, setPinned] = useState(false)
  const [refreshDialogOpen, setRefreshDialogOpen] = useState(false)
  const [selectedBlockData, setSelectedBlockData] = useState<any>(null)
  const [selectedBlockSource, setSelectedBlockSource] = useState('')
  const [selectedBlockTitle, setSelectedBlockTitle] = useState('')

  // Watch for evidence block selection
  useEffect(() => {
    if (!editor) return

    const onSelectionUpdate = () => {
      // Check if an evidence block is currently selected
      const isEvidenceActive = editor.isActive('evidenceBlock')
      if (!isEvidenceActive) {
        setVisible(false)
        return
      }

      // Get the selected node attributes
      const attrs = editor.getAttributes('evidenceBlock')
      if (!attrs || (attrs.type !== 'chart' && attrs.type !== 'timeline-event' && attrs.type !== 'shap-explanation')) {
        setVisible(false)
        return
      }

      setBlockId(attrs.id)

      // Store current block info for refresh dialog
      setSelectedBlockData(attrs.data || {})
      setSelectedBlockSource(attrs.source || 'unknown')
      setSelectedBlockTitle(attrs.title || 'Untitled')

      // Load existing config if present
      const data = attrs.data || {}
      if (data.colorScheme) setPalette(data.colorScheme)
      if (data.size) setSize(data.size)
      if (data.showLabels !== undefined) setShowLabels(data.showLabels)
      if (data.showLegend) setShowLegend(data.showLegend)
      if (data.showGrid !== undefined) setShowGrid(data.showGrid)
      if (data.pinnedToTop !== undefined) setPinned(data.pinnedToTop)

      // Position near the selected block
      const { from } = editor.state.selection
      const view = editor.view
      const nodeCoords = view.coordsAtPos(from)
      
      setCoords({
        top: nodeCoords.top + window.scrollY,
        right: 16,
      })
      setVisible(true)
    }

    editor.on('selectionUpdate', onSelectionUpdate)
    return () => { editor.off('selectionUpdate', onSelectionUpdate) }
  }, [editor])

  // Apply config change to the selected evidence block
  const applyConfig = useCallback((key: string, value: any) => {
    if (!editor || !blockId) return

    // Find the node and update its data
    const { doc } = editor.state
    doc.descendants((node, pos) => {
      if (node.type.name === 'evidenceBlock' && node.attrs.id === blockId) {
        const updatedData = { ...node.attrs.data, [key]: value }
        // Compute new config hash for audit trail
        const configStr = JSON.stringify({ palette, size, showLabels, showLegend, showGrid, pinned, [key]: value })
        let configHash = 0
        for (let i = 0; i < configStr.length; i++) {
          configHash = ((configHash << 5) - configHash) + configStr.charCodeAt(i)
          configHash |= 0
        }
        const updatedMetadata = {
          ...node.attrs.metadata,
          configHash: `cfg:${Math.abs(configHash).toString(16)}`,
        }
        editor.view.dispatch(
          editor.state.tr.setNodeMarkup(pos, undefined, {
            ...node.attrs,
            data: updatedData,
            metadata: updatedMetadata,
          })
        )
        return false // stop traversal
      }
    })
  }, [editor, blockId, palette, size, showLabels, showLegend, showGrid, pinned])

  if (!visible) return null

  return (
    <div
      ref={panelRef}
      className="fixed z-50 right-4"
      style={{ top: coords.top }}
      onMouseDown={(e) => e.preventDefault()}
    >
      <div className={cn(
        "w-[240px] rounded-xl border shadow-xl",
        "bg-white/95 dark:bg-zinc-900/95 backdrop-blur-xl",
        "border-slate-200/80 dark:border-white/10",
        "animate-in slide-in-from-right-4 duration-200"
      )}>
        {/* Header */}
        <div className="flex items-center justify-between px-3 py-2.5 border-b">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-3.5 w-3.5 text-sky-500" />
            <span className="text-xs font-semibold">Chart Inspector</span>
          </div>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setVisible(false)}>
            <X className="h-3 w-3" />
          </Button>
        </div>

        <div className="p-3 space-y-4">
          {/* Color palette */}
          <div>
            <Label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2 block">
              <Palette className="h-3 w-3 inline mr-1" />
              Color Palette
            </Label>
            <div className="grid grid-cols-5 gap-1.5">
              {CHART_PALETTES.map(p => (
                <button
                  key={p.id}
                  className={cn(
                    "flex flex-col gap-0.5 p-1 rounded-md border transition-all",
                    palette === p.id ? "border-sky-400 bg-sky-50 dark:bg-sky-950/30" : "border-transparent hover:border-slate-300"
                  )}
                  onClick={() => { setPalette(p.id); applyConfig('colorScheme', p.id) }}
                  title={p.name}
                >
                  {p.colors.slice(0, 3).map((c, i) => (
                    <div key={i} className="h-1.5 w-full rounded-full" style={{ backgroundColor: c }} />
                  ))}
                </button>
              ))}
            </div>
          </div>

          <Separator />

          {/* Size */}
          <div>
            <Label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2 block">
              <Ruler className="h-3 w-3 inline mr-1" />
              Size
            </Label>
            <Select value={size} onValueChange={(v) => { setSize(v); applyConfig('size', v) }}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CHART_SIZES.map(s => (
                  <SelectItem key={s.id} value={s.id} className="text-xs">{s.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Separator />

          {/* Toggles */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label className="text-xs flex items-center gap-1.5">
                {showLabels ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
                Axis Labels
              </Label>
              <Switch checked={showLabels} onCheckedChange={(v: boolean) => { setShowLabels(v); applyConfig('showLabels', v) }} className="scale-75" />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-xs flex items-center gap-1.5">
                <Layout className="h-3 w-3" />
                Grid Lines
              </Label>
              <Switch checked={showGrid} onCheckedChange={(v: boolean) => { setShowGrid(v); applyConfig('showGrid', v) }} className="scale-75" />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-xs flex items-center gap-1.5">
                <Pin className="h-3 w-3" />
                Pin to Top
              </Label>
              <Switch checked={pinned} onCheckedChange={(v: boolean) => { setPinned(v); applyConfig('pinnedToTop', v) }} className="scale-75" />
            </div>
          </div>

          <Separator />

          {/* Legend position */}
          <div>
            <Label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2 block">
              Legend Position
            </Label>
            <Select value={showLegend} onValueChange={(v) => { setShowLegend(v); applyConfig('showLegend', v) }}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LEGEND_POSITIONS.map(l => (
                  <SelectItem key={l.id} value={l.id} className="text-xs">{l.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <Separator />

          {/* Refresh from source */}
          <Button
            variant="outline"
            size="sm"
            className="w-full h-8 text-xs gap-1.5"
            onClick={() => setRefreshDialogOpen(true)}
          >
            <RefreshCw className="h-3 w-3" />
            Refresh from Source
          </Button>
        </div>
      </div>

      {/* Refresh diff dialog */}
      {blockId && (
        <RefreshDiffDialog
          open={refreshDialogOpen}
          onOpenChange={setRefreshDialogOpen}
          caseId={caseId}
          blockId={blockId}
          blockTitle={selectedBlockTitle}
          blockSource={selectedBlockSource}
          currentData={selectedBlockData}
          onAccept={(newData) => {
            applyConfig('_refreshedData', newData)
          }}
        />
      )}
    </div>
  )
}
