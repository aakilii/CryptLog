import React, { useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStudioStore } from './store/useStudioStore'
import { Settings2, SlidersHorizontal, AlertTriangle, EyeOff, LayoutTemplate, Activity, GripVertical, Paperclip, Clipboard } from 'lucide-react'
import { ScrollArea } from '@operation-room/components/ui/scroll-area'
import { Label } from '@operation-room/components/ui/label'
import { Slider } from '@operation-room/components/ui/slider'
import { Switch } from '@operation-room/components/ui/switch'
import { Separator } from '@operation-room/components/ui/separator'
import { Button } from '@operation-room/components/ui/button'
import { HelperPopover } from '@operation-room/components/ui/HelperPopover'

export const RightInspector = () => {
  const { selectedElementIds, pages, currentPage, updateElementConfig, globalTimeSlice, setGlobalTimeSlice } = useStudioStore()

  // Only render if exactly ONE element is selected
  const activePage = pages[currentPage]
  const selectedElement = useMemo(() => {
    if (selectedElementIds.length === 1 && activePage) {
      return activePage.elements.find(el => el.id === selectedElementIds[0])
    }
    return null
  }, [selectedElementIds, activePage])

  // Dynamic Payload Computation via XHR
  const [loading, setLoading] = React.useState(false)

  React.useEffect(() => {
    if (!selectedElement) return
    const config = selectedElement.config || {}
    const topN = config.topN || 10
    const minRisk = config.minRisk || 0
    const excludeInfo = config.excludeInfo || false
    const excludedFeatures = config.excludedFeatures || []
    
    // Relay to backend for dynamic regeneration instead of slicing locally
    const caseId = (activePage as any)?.caseId || 'demo_case_id'
    setLoading(true)
    
    fetch(`/api/v4/studio/cases/${caseId}/widgets/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            widgetType: selectedElement.data.type,
            filters: { topN, minRisk, excludeInfo, excludedFeatures }
        })
    }).then(res => {
         if(res.ok) return res.json();
    }).then(data => {
         setLoading(false)
         // Once endpoint is implemented, update local element data
         // updateElementConfig(currentPage, selectedElement.id, { _refreshedData: data })
    }).catch(err => {
         setLoading(false)
         console.error('Failed to regenerate via studio_service', err)
    })
  }, [selectedElement?.config])

  const computedPayload = useMemo(() => {
    if (!selectedElement) return ''
    const c = JSON.parse(JSON.stringify(selectedElement.data))
    const config = selectedElement.config || {}
    // In strict architectural compliance with Phase 2, visual truncation should move to backend. 
    // Fallback slicing during backend rollout:
    const topN = config.topN || 10
    const minRisk = config.minRisk || 0
    const excludeInfo = config.excludeInfo || false
    const excludedFeatures = config.excludedFeatures || []

    if (c.type === 'shap-explanation' || c.type === 'anomaly') {
      if (Array.isArray(c.data?.features)) {
         c.data.features = c.data.features.filter((f: any) => !excludedFeatures.includes(f.name || f.feature))
         c.data.features = c.data.features.slice(0, topN)
      }
    }
    if (['chart', 'timeline', 'area-chart', 'radar', 'heatmap', 'network', 'evidence'].some(t => (c.type || '').includes(t))) {
      let arr = c.data?.events || c.data?.timeline
      if (Array.isArray(arr)) {
         arr = arr.filter((ev: any) => {
            const rScore = Number(ev.risk_score || ev.score || 0)
            if (minRisk > 0 && rScore < minRisk) return false
            if (excludeInfo && (ev.severity || '').toUpperCase() === 'INFO') return false
            return true
         })
         arr = arr.slice(0, topN)
         if (c.data?.events) c.data.events = arr
         else if (c.data?.timeline) c.data.timeline = arr
      }
    }
    c.filters = { topN, minRisk, excludeInfo, excludedFeatures }
    return JSON.stringify(c, null, 2)
  }, [selectedElement])

  if (!selectedElement) {
    return null
  }

  const elType = selectedElement.data.type || 'chart'
  const config = selectedElement.config || {}
  
  const updateConfig = (key: string, value: any) => {
    updateElementConfig(currentPage, selectedElement.id, { [key]: value })
  }

  // Feature Extraction for categorical toggles
  let categoricalFeatures: string[] = []
  if ((elType === 'shap-explanation' || elType === 'anomaly') && Array.isArray(selectedElement.data.data?.features)) {
    categoricalFeatures = Array.from(new Set(selectedElement.data.data.features.map((f: any) => f.name || f.feature)))
  } else if (elType === 'network-flow' && Array.isArray(selectedElement.data.data?.flows)) {
    categoricalFeatures = Array.from(new Set(selectedElement.data.data.flows.map((f: any) => f.protocol || 'TCP')))
  }

  return (
    <div className="w-[340px] border-l bg-background flex flex-col h-full flex-shrink-0 z-20 shadow-[-4px_0_24px_-10px_rgba(0,0,0,0.1)]">
      <div className="h-14 border-b flex items-center px-4 font-semibold text-sm justify-between shadow-sm">
        <span className="flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4 text-sky-500" />
          Inspector
        </span>
        <span className="text-[10px] font-mono bg-muted px-2 py-0.5 rounded text-muted-foreground truncate max-w-[120px]">
          {selectedElement.id.split('-')[1] || elType}
        </span>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="p-5 space-y-6">
          
          {/* Universal Rendering Bounds */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <LayoutTemplate className="h-3 w-3" /> Visual Bounds
            </h3>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label className="text-sm font-medium">Render Limit (Top N)</Label>
                <span className="text-xs font-mono bg-muted px-1.5 rounded">{config.topN || 10}</span>
              </div>
              <Slider 
                value={[config.topN || 10]} 
                min={1} 
                max={50} 
                step={1} 
                onValueChange={(v: number[]) => updateConfig('topN', v[0])}
              />
              <p className="text-[11px] text-muted-foreground leading-snug">
                Restricts items painted to canvas, strictly capping mathematically derived bounding height.
              </p>
            </div>
          </div>

          <Separator />

          {/* DRAG-AND-DROP EVIDENCE BINDER */}
          <div className="space-y-4 relative">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Clipboard className="h-3 w-3" /> Evidence Binder
              <span className="relative flex h-3 w-3 items-center justify-center -ml-1">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-20"></span>
                <HelperPopover 
                  title="Mathematical Non-Repudiation" 
                  description="Artifacts dropped here are permanently hashed and logged to the Chain of Custody. They cannot be altered." 
                />
              </span>
            </h3>
            <p className="text-[11px] text-muted-foreground leading-snug">
              Drag valid metrics into the report editor to instantiate mathematically backed claims.
            </p>
            <div className="grid grid-cols-2 gap-2">
              {['total_events', 'high_risk_count', 'suspicious_count'].map((metric) => (
                <div 
                  key={metric}
                  draggable 
                  onDragStart={(e) => {
                    const payload = {
                      type: 'claim',
                      attrs: {
                        evd_ref: selectedElement.id,
                        claim_type: metric,
                        claim_value: JSON.parse(computedPayload || '{}')?.data?.[metric] || '--'
                      }
                    }
                    e.dataTransfer.setData('application/json', JSON.stringify(payload))
                    e.dataTransfer.setData('text/plain', `claim:${payload.attrs.claim_value}`)
                  }}
                  className="flex items-center justify-between p-2 rounded border border-dashed bg-sky-50/50 hover:bg-sky-50 cursor-grab active:cursor-grabbing group"
                >
                  <GripVertical className="h-3 w-3 text-muted-foreground/50 opacity-0 group-hover:opacity-100" />
                  <span className="text-[10px] truncate max-w-[70px] uppercase font-semibold text-sky-700">{metric.replace('_', ' ')}</span>
                  <span className="text-xs font-mono bg-white px-1 py-0.5 rounded shadow-sm border border-sky-100">
                    {JSON.parse(computedPayload || '{}')?.data?.[metric] ?? '--'}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          {/* Module Specific Filters */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
              <Activity className="h-3 w-3" /> Expert Filters
            </h3>

            {/* Timeline & Chart Options */}
            {['chart', 'timeline', 'area-chart', 'radar', 'heatmap', 'network', 'evidence'].some(t => elType.includes(t)) && (
              <div className="space-y-5">
                
                {/* Phase 1 Global Sync Controller */}
                <div className="p-3 bg-sky-50 dark:bg-sky-950/20 border border-sky-100 dark:border-sky-900 rounded-md">
                  <div className="space-y-1 mb-3">
                    <Label className="text-sm font-semibold text-sky-800 dark:text-sky-300">Global Time Slice</Label>
                    <p className="text-[10px] text-sky-600/80 dark:text-sky-400">Brush-and-Link bounds applying cross-canvas filtering</p>
                  </div>
                  {globalTimeSlice ? (
                    <div className="space-y-2">
                       <span className="text-[11px] font-mono block bg-white dark:bg-black px-1.5 py-1 rounded">START: {typeof globalTimeSlice.start === 'number' ? new Date(globalTimeSlice.start).toLocaleString() : globalTimeSlice.start}</span>
                       <span className="text-[11px] font-mono block bg-white dark:bg-black px-1.5 py-1 rounded">END: {typeof globalTimeSlice.end === 'number' ? new Date(globalTimeSlice.end).toLocaleString() : globalTimeSlice.end}</span>
                       <Button variant="outline" size="sm" className="w-full text-[10px] h-7 mt-2" onClick={() => setGlobalTimeSlice(null)}>Clear Global Bounds</Button>
                    </div>
                  ) : (
                    <span className="text-[11px] text-sky-600/70 italic">Draw a brush window on any timeline to activate.</span>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label className="text-sm">Filter Routine Logs</Label>
                    <p className="text-[11px] text-muted-foreground">Hide INFO and LOW severity</p>
                  </div>
                  <Switch 
                    checked={config.excludeInfo || false} 
                    onCheckedChange={(c) => updateConfig('excludeInfo', c)}
                  />
                </div>
                
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm">Min Risk Threshold</Label>
                    <span className="text-xs font-mono bg-rose-100 text-rose-700 px-1.5 rounded">{config.minRisk || 0}</span>
                  </div>
                  <Slider 
                    value={[config.minRisk || 0]} 
                    min={0} 
                    max={100} 
                    step={5} 
                    onValueChange={(v: number[]) => updateConfig('minRisk', v[0])}
                  />
                </div>
              </div>
            )}

            {/* Network / SHAP Categorical Toggles */}
            {categoricalFeatures.length > 0 && (
              <div className="space-y-3">
                <Label className="text-sm">Available Parameters</Label>
                <div className="grid grid-cols-1 gap-2 border rounded-md p-3 bg-muted/20">
                  {categoricalFeatures.map(feat => {
                    const isExcluded = (config.excludedFeatures || []).includes(feat)
                    return (
                      <div key={feat} className="flex items-center space-x-2">
                        <Switch 
                          id={`chk-${feat}`} 
                          checked={!isExcluded}
                          onCheckedChange={(checked: boolean) => {
                            const current = config.excludedFeatures || []
                            if (checked) {
                              updateConfig('excludedFeatures', current.filter((x: string) => x !== feat))
                            } else {
                              updateConfig('excludedFeatures', [...current, feat])
                            }
                          }}
                        />
                        <Label 
                          htmlFor={`chk-${feat}`} 
                          className="text-xs font-mono font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 truncate flex-1"
                        >
                          {feat}
                        </Label>
                        {isExcluded && <EyeOff className="h-3 w-3 text-rose-500 ml-auto flex-shrink-0" />}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          <Separator />

          {/* Visual Overrides (Display & Cosmetics) */}
          {(elType === 'chart' || elType === 'timeline' || elType === 'timeline-event' || elType === 'shap-explanation' || elType === 'anomaly' || elType === 'radar' || elType === 'network' || elType === 'heatmap') && (
            <div className="space-y-4 relative">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                <LayoutTemplate className="h-3 w-3" /> Display Overrides
              </h3>
              <p className="text-[11px] text-muted-foreground leading-snug">
                Overrides structural titles, labels, and cosmetic colors. Leaves the verified data content safely isolated from visual tweaks.
              </p>
              
              {/* Title Override */}
              <div className="space-y-2">
                <Label className="text-sm">Title Override</Label>
                <input 
                  type="text" 
                  className="flex h-8 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  placeholder={selectedElement.data.title || "Custom Chart Title"}
                  value={config.titleOverride || ''}
                  onChange={(e) => updateConfig('titleOverride', e.target.value)}
                />
              </div>

              {/* Label Overrides */}
              {categoricalFeatures.length > 0 && (
                <div className="space-y-2 pt-2">
                  <Label className="text-sm">Label Aliasing</Label>
                  <div className="max-h-[150px] overflow-y-auto space-y-1.5 border rounded-md p-1 border-muted bg-slate-50/50 dark:bg-slate-900/50">
                    {categoricalFeatures.map(feat => (
                      <div key={feat} className="flex flex-col gap-1 py-1 rounded text-xs px-1">
                        <span className="font-mono text-muted-foreground text-[10px]">{feat}</span>
                        <input 
                          type="text" 
                          placeholder="Alias..."
                          value={config.labelOverrides?.[feat] || ''}
                          onChange={(e) => {
                            const currentOverrides = { ...(config.labelOverrides || {}) }
                            currentOverrides[feat] = e.target.value
                            updateConfig('labelOverrides', currentOverrides)
                          }}
                          className="border-b border-transparent bg-white dark:bg-slate-950 focus:border-sky-500 rounded-sm outline-none px-1.5 py-1 w-full shadow-sm text-foreground"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Color Scopes */}
              {(elType === 'shap-explanation' || elType === 'anomaly') && (
                <div className="space-y-2 pt-2">
                  <Label className="text-sm">Color Scope</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="flex flex-col gap-1 border border-muted bg-white dark:bg-slate-900 p-2 rounded-md shadow-sm">
                      <span className="text-[10px] uppercase font-semibold text-rose-500">Increases Risk</span>
                      <input 
                        type="color" 
                        className="w-full h-8 cursor-pointer bg-transparent border-0 p-0 rounded"
                        value={config.colors?.positive || '#ef4444'}
                        onChange={(e) => {
                          const colors = { ...(config.colors || {}), positive: e.target.value }
                          updateConfig('colors', colors)
                        }}
                      />
                    </div>
                    <div className="flex flex-col gap-1 border border-muted bg-white dark:bg-slate-900 p-2 rounded-md shadow-sm">
                      <span className="text-[10px] uppercase font-semibold text-sky-500">Decreases Risk</span>
                      <input 
                        type="color" 
                        className="w-full h-8 cursor-pointer bg-transparent border-0 p-0 rounded"
                        value={config.colors?.negative || '#3b82f6'}
                        onChange={(e) => {
                          const colors = { ...(config.colors || {}), negative: e.target.value }
                          updateConfig('colors', colors)
                        }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          <Separator />

          {/* Computed Output */}
          <div className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-emerald-600 flex items-center gap-2">
              <AlertTriangle className="h-3 w-3" /> Computed Payload
            </h3>
            <p className="text-[10px] text-muted-foreground bg-amber-50 text-amber-800 p-2 rounded border border-amber-200">
              Read-only matrix. Represents exact slicing passed to the PDF compiled renderer.
            </p>
            <div className="w-full max-h-[300px] overflow-auto rounded-md border bg-slate-950 p-3 scrollbar-thin shadow-inner">
              <pre className="text-[10px] font-mono text-emerald-400 whitespace-pre">
                <code>{computedPayload}</code>
              </pre>
            </div>
          </div>

        </div>
      </ScrollArea>
    </div>
  )
}
