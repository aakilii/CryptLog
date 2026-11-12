'use client'

import React, { useMemo } from 'react'
import { Rnd } from 'react-rnd'
import { CanvasElement, useStudioStore, calculateElementMinHeight } from '../store/useStudioStore'
import { EvidenceContent } from '@operation-room/components/tiptap/EvidenceBlockNode'
import { cn } from '@operation-room/lib/utils'
import { GripHorizontal, X, Settings2, ShieldCheck, ShieldAlert } from 'lucide-react'

export const WidgetRenderer = ({
  element,
  pageIndex,
  onDragStart,
  onDragMove,
  onDragEnd
}: {
  element: CanvasElement;
  pageIndex: number
  onDragStart?: (elementId: string, pageIndex: number) => void
  onDragMove?: (element: CanvasElement, pageIndex: number, x: number, y: number) => { x: number; y: number }
  onDragEnd?: () => void
}) => {
  const { updateElement, deleteElements, selectedElementIds, setSelectedElements, globalTimeSlice, focusMode } = useStudioStore()
  const [dragPosition, setDragPosition] = React.useState<{ x: number; y: number } | null>(null)

  const isSelected = selectedElementIds.includes(element.id)
  const handleSelect = () => { setSelectedElements([element.id]) }
  // Calculate dynamic minimum height using precisely the same logic as the PDF headless exporter
  const autoMinHeight = useMemo(() => calculateElementMinHeight(element), [element])
    const isVisualComponent = (element.type as string) === 'evidence' || element.type === 'component' || ['shap-explanation', 'anomaly', 'chart'].includes(element.data?.type || '');
    const effectiveHeight = Math.max(element.height || 0, autoMinHeight);
    const effectiveMinHeight = autoMinHeight;

  // Use the universal renderer with correctly stitched component configs overriding base filters
  const content = useMemo(() => {
    let syncedData = element.data.data


    // Storyboard mode (Focus filtering)
    if (focusMode === 'Story' && syncedData) {
      if (Array.isArray(syncedData.events)) {
        // Filter noise, retain only critical correlation nodes or sample mock
        syncedData = {
          ...syncedData,
          events: syncedData.events.filter((e: any) => e.critical_path || e.severity === 'high' || e.action === 'ENCRYPT')
        }
      }
    }

    // Phase 1: Brush-and-Link Global Time Slice filtering
    if (globalTimeSlice && syncedData && typeof syncedData === 'object') {
      const start = new Date(globalTimeSlice.start).getTime()
      const end = new Date(globalTimeSlice.end).getTime()

      if (Array.isArray(syncedData.events)) {
        syncedData = {
          ...syncedData,
          events: syncedData.events.filter((e: any) => {
            const t = new Date(e.timestamp || e.time).getTime()
            return t >= start && t <= end
          })
        }
      } else if (Array.isArray(syncedData.flows)) {
        syncedData = {
          ...syncedData,
          flows: syncedData.flows.filter((f: any) => {
            const t = new Date(f.timestamp || f.time).getTime()
            return t >= start && t <= end
          })
        }
      }
    }

    return (
      <EvidenceContent
        type={element.data.type || 'chart'}
        data={syncedData}
        filters={{ ...(element.data.filters || {}), ...(element.config || {}) }}
        dimensions={{ width: Math.max(element.width, 250), height: effectiveHeight }}
        displayMode="full"
      />
    )
  }, [element.data, element.width, element.height, autoMinHeight, element.config, globalTimeSlice, focusMode])

  return (
    <>
      <div
        className={cn(
          "group w-full bg-card transition-shadow flex flex-col",
          isSelected ? "ring-2 ring-sky-500 shadow-lg z-50" : "hover:ring-1 hover:ring-sky-500/50 shadow-sm",
          "rounded-lg overflow-hidden border border-slate-200/60 dark:border-slate-800"
        )}
        style={{ minHeight: effectiveMinHeight }}
      >
        {/* Widget Header & Controls */}
        <div 
          className={cn(
            "h-6 bg-slate-100/80 dark:bg-slate-900/80 backdrop-blur-sm border-b flex items-center shrink-0 justify-between px-2 cursor-grab active:cursor-grabbing widget-drag-handle transition-opacity",
            isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          )}
        >
          <GripHorizontal className="h-3.5 w-3.5 text-muted-foreground mr-2" />
          <span className="text-[10px] flex-1 font-ui font-semibold uppercase text-muted-foreground tracking-wider truncate flex items-center gap-1.5">
            {element.data.title || element.data.source || 'Widget'}
            {/* Phase 4: Chain-of-Custody overlay */}
            {element.isOriginal !== undefined && (
              <span className="group/hash relative inline-flex items-center">
                {element.isOriginal ? (
                  <ShieldCheck className="h-3 w-3 text-emerald-500" />
                ) : (
                  <ShieldAlert className="h-3 w-3 text-amber-500" />
                )}
                {element.contentHash && (
                  <span className="absolute left-full ml-1 px-1.5 py-0.5 rounded bg-slate-800 text-slate-200 text-[8px] tracking-widest font-mono opacity-0 group-hover/hash:opacity-100 transition-opacity whitespace-nowrap z-[100]">
                    {element.contentHash}
                  </span>
                )}
              </span>
            )}
          </span>
          <div className="flex items-center shrink-0 ml-2 opacity-0 group-hover:opacity-100 transition-opacity bg-white dark:bg-slate-950 rounded-md shadow-sm border border-slate-200 dark:border-slate-800">
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedElements([element.id]); }}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 text-slate-500 dark:text-slate-400 hover:text-sky-600 dark:hover:text-sky-400 hover:bg-sky-50 dark:hover:bg-sky-900/30 transition-colors border-r border-slate-200 dark:border-slate-800",
                isSelected ? "text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-900/20 font-medium" : ""
              )}
              title="Open Inspector & Apply Filters"
            >
              <Settings2 className="h-4 w-4" />
              <span className="text-[10px] uppercase font-bold tracking-wider">FILTERS</span>
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); deleteElements(pageIndex, [element.id]); }}
              className="flex items-center px-2.5 py-1 text-slate-500 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors rounded-r-md"
              title="Remove Widget"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Widget Content Body */}
        <div className="w-full h-full flex flex-col flex-1 overflow-hidden relative pointer-events-none">
          {focusMode !== 'Evidence' ? (
            <div className="pointer-events-auto basis-full flex-1 min-h-0 w-full relative">
              {content}
            </div>
          ) : (
            /* Phase 2: Evidence Mode Cryptographic Data Reveal (Replaces Content) */
            <div className="pointer-events-auto h-full w-full bg-slate-950 text-emerald-400 p-3 font-mono text-[10px] overflow-y-auto border-t-2 border-emerald-500 z-50 overflow-x-hidden break-words">
              <div className="text-emerald-500 font-bold mb-2 border-b border-emerald-900 pb-1 flex justify-between uppercase sticky top-0 bg-slate-950">
                <span>Cryptographic Verification Overlay</span>
                <span>P95 Anomaly: {(element.data.confidence ?? 0.95).toFixed(2)}</span>
              </div>
              <div className="mb-2 break-words">
                <span className="text-emerald-700 font-bold">ROW_SHA256:</span><br/>
                <span className="text-emerald-300">{element.contentHash || 'PENDING...'}</span>
              </div>
              <div className="mb-2 break-words">
                <span className="text-emerald-700 font-bold">DUCKDB_QUERY:</span><br/>
                <span className="whitespace-pre-wrap text-emerald-100">{element.data.query || 'SELECT * FROM source_events;'}</span>
              </div>
              <div className="break-words pb-4">
                <span className="text-emerald-700 font-bold">RAW_META:</span><br/>
                <span className="text-emerald-100 opacity-80 whitespace-pre-wrap block w-full mt-1">
                  {JSON.stringify(element.data, null, 2)}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

