'use client'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { Plus } from 'lucide-react'
import NextImage from 'next/image'
import React, { useRef } from 'react'
import { CanvasElement, useStudioStore } from '../store/useStudioStore'
import { AlignmentOverlay } from './AlignmentOverlay'
import { TextRenderer } from './TextRenderer'
import { useAlignment } from './useAlignment'
import { WidgetRenderer } from './WidgetRenderer'

interface DocumentCanvasProps {
  children?: React.ReactNode // Legacy prop; not used heavily in freeform mode unless for background layers
  zoom: number
  className?: string
  onDropNewComponent?: (pageIndex: number, componentId: string, x: number, y: number, payloadData: any) => void
}

export const DocumentCanvas = ({ children, zoom, className, onDropNewComponent }: DocumentCanvasProps) => {
  const containerRef = useRef<HTMLDivElement>(null)

  // Destructure zustand store
  const {
    pages,
    currentPage,
    addPage,
    setCurrentPage,
    setSelectedElements
  } = useStudioStore()

  const {
    activeGuides,
    distances,
    isDragging,
    startDrag,
    updateDrag,
    endDrag,
    toggleSnapToGrid,
    toggleSnapToElements,
    isSnapToGridEnabled,
    isSnapToElementsEnabled,
  } = useAlignment({
    canvasWidth: 794,
    canvasHeight: 1123,
    enabled: true,
  })

  const scale = zoom / 100

  const handleElementDragMove = (
    element: CanvasElement,
    pageIndex: number,
    x: number,
    y: number
  ) => {
    const page = pages[pageIndex]
    if (!page) {
      return { x, y }
    }

    const snapped = updateDrag(element, x, y, page.elements || [])
    return { x: snapped.snappedX, y: snapped.snappedY }
  }

  // Click outside to deselect
  const handleCanvasClick = (e: React.MouseEvent) => {
    // Only clear if clicking directly on the canvas background, not inside a widget
    if ((e.target as HTMLElement).hasAttribute('data-canvas-bg')) {
      setSelectedElements([])
    }
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative flex-1 overflow-auto bg-[#e8edf2] dark:bg-[#0c0c0c] flex flex-col items-center",
        className
      )}
      onClick={handleCanvasClick}
    >
      {/* Premium Background Pattern */}
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_14%_12%,rgba(6,182,212,0.08),transparent_34%),radial-gradient(circle_at_84%_10%,rgba(139,92,246,0.08),transparent_38%)] dark:bg-[radial-gradient(circle_at_14%_12%,rgba(6,182,212,0.04),transparent_34%),radial-gradient(circle_at_84%_10%,rgba(139,92,246,0.04),transparent_38%)]" />
      <div className="pointer-events-none fixed inset-0 opacity-40 dark:opacity-15 bg-[linear-gradient(rgba(100,116,139,0.06)_1px,transparent_1px),linear-gradient(90deg,rgba(100,116,139,0.06)_1px,transparent_1px)] bg-[size:28px_28px]" />

      {/* Zoom-scaled wrapper */}
      <div
        className="relative my-8 origin-top transition-transform duration-200 ease-out z-10"
        style={{
          width: '210mm',
          transform: `scale(${scale})`,
        }}
      >
        <div className="absolute -top-10 right-0 z-20 flex items-center gap-2 rounded-md border border-slate-200 bg-white/90 px-2 py-1 text-[11px] shadow-sm">
          <button
            type="button"
            className={cn("rounded px-2 py-0.5", isSnapToGridEnabled ? "bg-sky-100 text-sky-700" : "bg-slate-100 text-slate-600")}
            onClick={toggleSnapToGrid}
          >
            Grid Snap
          </button>
          <button
            type="button"
            className={cn("rounded px-2 py-0.5", isSnapToElementsEnabled ? "bg-sky-100 text-sky-700" : "bg-slate-100 text-slate-600")}
            onClick={toggleSnapToElements}
          >
            Element Snap
          </button>
        </div>

        {/* Render each page as a separate A4 sheet */}
        {pages.map((page, pageIndex) => (
          <div key={page.id} className="relative mb-6 group">
            {/* Outline Page Active Ring */}
            <div className={cn(
              "absolute -inset-2 rounded-xl transition-all duration-300 pointer-events-none",
              currentPage === pageIndex ? "ring-2 ring-sky-500/20" : ""
            )} />

            {/* Page sheet boundary */}
            <div
              id={`page-${page.id}`}
              className={cn(
                "relative w-full bg-white dark:bg-[#111111] border border-slate-200/80 dark:border-white/10",
                "shadow-[0_4px_24px_-8px_rgba(15,23,42,0.12),0_24px_48px_-16px_rgba(15,23,42,0.08)]",
                "dark:shadow-[0_4px_24px_-8px_rgba(0,0,0,0.4),0_24px_48px_-16px_rgba(0,0,0,0.5)]",
              )}
              style={{ minHeight: '297mm', height: 'auto', pageBreakAfter: 'always' }}
              onClick={() => setCurrentPage(pageIndex)}
              onDragOver={(e) => {
                e.preventDefault()
                e.dataTransfer.dropEffect = 'copy'
              }}
              onDrop={(e) => {
                e.preventDefault()
                try {
                  const data = e.dataTransfer.getData('application/json')
                  if (!data) return

                  const payload = JSON.parse(data)
                  if (payload && onDropNewComponent) {

                    // Calculate drop coordinates relative to this specific page
                    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()

                    // Adjust coordinates for zoom scale
                    const x = (e.clientX - rect.left) / scale
                    const y = (e.clientY - rect.top) / scale

                    onDropNewComponent(pageIndex, payload.componentId || payload.type, x, y, payload)
                  }
                } catch (err) {
                  // IGNORE
                }
              }}
            >
              <div
                className="absolute inset-x-[16mm] inset-y-[20mm] pointer-events-none border border-transparent group-hover:border-sky-500/10 border-dashed transition-colors"
                style={{ zIndex: 0 }}
              />

              {/* Auto-Paginated Bounded Flow Flexbox layer */}
              <div
                className="absolute inset-[16mm] flex flex-col gap-4 overflow-visible"
                data-canvas-bg="true"
                style={{ breakInside: 'auto' }}
              >
                {page.elements?.map(el => (
                  <React.Fragment key={el.id}>
                    {(el.type === 'component' || el.type === 'evidence') && (
                      <div style={{ breakInside: 'avoid', breakAfter: 'auto' }} className="w-full relative shrink-0">
                        <WidgetRenderer
                          element={el}
                          pageIndex={pageIndex}
                          onDragStart={startDrag}
                          onDragMove={handleElementDragMove}
                          onDragEnd={endDrag}
                        />
                      </div>
                    )}
                    {el.type === 'text' && (
                      <div style={{ breakInside: 'auto', breakAfter: 'auto' }} className="w-full relative shrink-0">
                        <TextRenderer
                          element={el}
                          pageIndex={pageIndex}
                          onDragStart={startDrag}
                          onDragMove={handleElementDragMove}
                          onDragEnd={endDrag}
                        />
                      </div>
                    )}
                    {el.type === 'image' && (
                      <div style={{ breakInside: 'avoid', breakAfter: 'auto' }} className="w-full relative shrink-0">
                        <div className="group rounded-lg border border-slate-200/60 dark:border-slate-800 overflow-hidden bg-card shadow-sm">
                          <div className="h-6 bg-slate-100/80 dark:bg-slate-900/80 border-b flex items-center px-2">
                            <span className="text-[10px] font-ui font-semibold uppercase text-muted-foreground tracking-wider truncate">{el.data.name || 'Image'}</span>
                          </div>
                          {el.data.url ? (
                            <NextImage
                              src={el.data.url}
                              alt={el.data.name || 'Uploaded image'}
                              width={1200}
                              height={800}
                              unoptimized
                              className="w-full h-auto object-contain max-h-[400px]"
                            />
                          ) : (
                            <div className="flex items-center justify-center h-[200px] text-muted-foreground text-sm">No image source</div>
                          )}
                        </div>
                      </div>
                    )}
                    {el.type === 'shape' && (
                      <div style={{ breakInside: 'avoid', breakAfter: 'auto' }} className="w-full relative shrink-0">
                        <div className="rounded-lg border-2 border-dashed border-slate-300 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-center" style={{ minHeight: el.height || 100 }}>
                          <span className="text-xs text-muted-foreground font-ui">{el.data.name || 'Shape'}</span>
                        </div>
                      </div>
                    )}
                  </React.Fragment>
                ))}

                <AlignmentOverlay
                  guides={activeGuides}
                  distances={distances}
                  canvasWidth={794}
                  canvasHeight={1123}
                  visible={isDragging && currentPage === pageIndex}
                />
              </div>

              {/* Page number watermark */}
              <div className="absolute bottom-[10mm] right-[16mm] font-geist-mono text-[10px] text-slate-300 dark:text-white/10 pointer-events-none select-none">
                Page {pageIndex + 1}
              </div>
            </div>
          </div>
        ))}

        {/* Add page button at the end */}
        <div className="flex items-center justify-center py-6">
          <Button
            variant="outline"
            size="sm"
            className="h-9 gap-2 text-xs font-ui bg-white/80 dark:bg-zinc-900/80 backdrop-blur-sm border-dashed border-slate-300 dark:border-white/15 hover:border-sky-400 hover:bg-sky-50 dark:hover:bg-sky-950/30 transition-all shadow-sm"
            onClick={addPage}
          >
            <Plus className="h-3.5 w-3.5" />
            Add page
          </Button>
        </div>
      </div>
    </div>
  )
}
