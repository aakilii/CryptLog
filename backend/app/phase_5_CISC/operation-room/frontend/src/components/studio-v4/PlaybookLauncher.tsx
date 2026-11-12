'use client'

import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertCircle, FilePlus, ChevronRight, Check } from 'lucide-react'
import playbooksData from '../../app/(studio)/cases/[id]/studio-v4/templates/playbooks.json'
import { Button } from '@operation-room/components/ui/button'
import { useStudioStore } from './store/useStudioStore'

import { createPortal } from 'react-dom'

export const PlaybookLauncher = ({ caseId }: { caseId: string }) => {
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [selectedPlaybook, setSelectedPlaybook] = useState<any>(null)
 
  useEffect(() => {
    setMounted(true)
  }, [])

  const [preflightLoading, setPreflightLoading] = useState(false)
  const [availableSources, setAvailableSources] = useState<string[]>([])
  const [missingSources, setMissingSources] = useState<string[]>([])
  
  const [initials, setInitials] = useState('')
  const { addPage, addElement, pages } = useStudioStore()

  useEffect(() => {
    if (!open || !caseId) return
    setPreflightLoading(true)
    fetch(`/api/cases/${caseId}/preflight-check`)
      .then(res => res.json())
      .then(data => {
        setAvailableSources(data.source_systems?.map((s: string) => String(s).toUpperCase()) || [])
      })
      .catch(console.error)
      .finally(() => setPreflightLoading(false))
  }, [open, caseId])

  useEffect(() => {
    if (!selectedPlaybook) return

    setInitials('')
    const required = selectedPlaybook.requires || []
    const missing = required.filter((req: string) => !availableSources.includes(req.toUpperCase()))
    setMissingSources(missing)
  }, [selectedPlaybook, availableSources])

  const handleLaunch = async () => {
    if (missingSources.length > 0 && initials.trim() === '') return
    
    if (missingSources.length > 0) {
      try {
        await fetch(`/api/cases/${caseId}/audit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: 'PLAYBOOK_GAP_WAIVED',
            user_initials: initials,
            missing_telemetry: missingSources,
            playbook_id: selectedPlaybook.id
          })
        })
      } catch (error) {
        console.error('Failed to log gap waiver', error)
      }
    }
    
    // Execute Layout
    const layout = selectedPlaybook.layout || []
    addPage() // create a fresh skeleton page
    
    const newPageIndex = pages.length
    
    layout.forEach((block: any) => {
      addElement(newPageIndex, {
        type: block.type,
        x: block.x,
        y: block.y,
        width: block.width,
        height: block.height,
        config: {
          label: block.label || '',
          placeholderText: block.placeholderText || ''
        },
        data: {
          type: block.type,
          content: block.content || '',
        }
      })
    })

    setOpen(false)
    setSelectedPlaybook(null)
  }

  return (
    <>
      <Button
        onClick={() => setOpen(true)}
        variant="secondary"
        size="sm"
        className="font-semibold"
      >
        <FilePlus className="w-4 h-4 mr-2" /> Launch Playbook
      </Button>

      {mounted && createPortal(
        <AnimatePresence>
          {open && (
            <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="bg-slate-950 border border-slate-800 rounded-xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[85vh]"
            >
              <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
                <h2 className="text-lg font-bold text-slate-200">Playbook Launcher</h2>
                <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-white">✕</button>
              </div>
              
              <div className="flex-1 overflow-auto flex">
                {/* Left Sidebar: Select Playbook */}
                <div className="w-1/3 border-r border-slate-800 p-2 space-y-2">
                  {playbooksData.playbooks.map(pb => (
                    <button
                      key={pb.id}
                      onClick={() => setSelectedPlaybook(pb)}
                      className={`w-full text-left p-3 rounded-lg border transition-colors ${
                        selectedPlaybook?.id === pb.id 
                          ? 'border-indigo-500 bg-indigo-500/10 text-indigo-300' 
                          : 'border-slate-800 bg-slate-900/40 text-slate-400 hover:bg-slate-800'
                      }`}
                    >
                      <div className="font-semibold text-sm">{pb.title}</div>
                    </button>
                  ))}
                </div>
                
                {/* Right Area: Preflight & Gap Detect */}
                <div className="flex-1 p-6 flex flex-col">
                  {!selectedPlaybook ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-slate-500 text-sm space-y-4">
                      <div className="w-16 h-16 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center shadow-inner">
                        <FilePlus className="w-8 h-8 text-slate-700" />
                      </div>
                      <div className="text-center group">
                        <h3 className="text-slate-300 font-semibold text-lg mb-1">Select a Playbook</h3>
                        <p className="text-slate-500 max-w-[280px]">Choose a structured investigation template to automatically populate your canvas and execute pre-flight telemetry checks.</p>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      <div>
                        <h3 className="text-xl font-semibold mb-1 text-slate-200">{selectedPlaybook.title}</h3>
                        <p className="text-sm text-slate-400">{selectedPlaybook.description}</p>
                      </div>
                      
                      <div className="bg-slate-900 border border-slate-800 p-4 rounded-lg">
                        <div className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-3">Pre-Flight Telemetry Check</div>
                        
                        {preflightLoading ? (
                          <div className="text-sm text-slate-400 animate-pulse">Running Deep Scans...</div>
                        ) : missingSources.length === 0 ? (
                          <div className="flex items-start text-emerald-400">
                            <Check className="w-5 h-5 mr-3 flex-shrink-0" />
                            <div className="text-sm border border-emerald-900/50 bg-emerald-950/30 p-2 rounded w-full">
                              All required log schemas detected ({selectedPlaybook.requires.join(', ')}). Playbook ready for execution.
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-4">
                            <div className="flex items-start text-amber-500 bg-amber-950/30 border border-amber-900/50 p-3 rounded w-full">
                              <AlertCircle className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5 text-amber-500" />
                              <div className="text-sm">
                                <span className="font-bold block text-amber-300">GAP DETECTOR TRIGGERED</span>
                                Blindspots detected. You lack the following telemetry sources to fully satisfy this Playbook:
                                <ul className="mt-2 ml-4 list-disc text-amber-400/80">
                                  {missingSources.map(s => <li key={s}>{s}</li>)}
                                </ul>
                              </div>
                            </div>
                            
                            <div className="flex flex-col space-y-2 p-2 bg-slate-900/50 rounded border border-slate-700">
                              <span className="text-sm text-slate-300 font-medium">
                                Mandatory Legal Exemption required to bypass gap detector.
                              </span>
                              <input
                                type="text"
                                placeholder="Type your initials to officially acknowledge missing telemetry"
                                value={initials}
                                onChange={(e) => setInitials(e.target.value.toUpperCase())}
                                className="bg-slate-950 border border-slate-700 text-white text-sm rounded px-3 py-2 outline-none focus:border-amber-500 transition-colors w-full uppercase placeholder:normal-case font-mono"
                                maxLength={5}
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Footer */}
              <div className="p-4 border-t border-slate-800 bg-slate-900/50 flex justify-end">
                <Button
                  onClick={handleLaunch}
                  disabled={!selectedPlaybook || (missingSources.length > 0 && initials.trim().length === 0)}
                  className="font-semibold"
                >
                  Deploy Skeleton <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </motion.div>
          </div>
        )}
        </AnimatePresence>,
        document.body
      )}
    </>
  )
}
