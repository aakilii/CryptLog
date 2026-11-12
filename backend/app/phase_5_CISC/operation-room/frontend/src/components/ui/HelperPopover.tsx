'use client'

import React, { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Info, HelpCircle, AlertCircle } from 'lucide-react'

export interface HelperPopoverProps {
  title: string
  description: string
  codeSnippet?: string
  icon?: 'info' | 'help' | 'alert'
  side?: 'top' | 'bottom' | 'left' | 'right'
  children?: React.ReactNode
}

export function HelperPopover({ title, description, codeSnippet, icon = 'info', side = 'top', children }: HelperPopoverProps) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLDivElement>(null)
  const [coords, setCoords] = useState({ x: 0, y: 0 })

  const Icon = icon === 'alert' ? AlertCircle : icon === 'help' ? HelpCircle : Info
  const colorToken = icon === 'alert' ? 'text-amber-400' : 'text-sky-400'

  useEffect(() => {
    if (open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect()
      let x = rect.left + rect.width / 2
      let y = rect.top

      if (side === 'bottom') {
        y = rect.bottom
      } else if (side === 'left') {
        x = rect.left
        y = rect.top + rect.height / 2
      } else if (side === 'right') {
        x = rect.right
        y = rect.top + rect.height / 2
      }

      setCoords({ x, y })
    }
  }, [open, side])

  const popupClasses = "fixed bg-slate-900/95 backdrop-blur-xl border border-slate-700 shadow-2xl p-4 rounded-xl z-[9999] text-left pointer-events-none w-72"

  const initialY = side === 'top' ? 5 : side === 'bottom' ? -5 : 0
  const initialX = side === 'left' ? 5 : side === 'right' ? -5 : 0

  let xTransform = "-50%"
  const yTransform = side === 'top' ? "-100%" : side === 'bottom' ? "0%" : "-50%"

  if (side === 'left') {
    xTransform = "-100%"
  } else if (side === 'right') {
    xTransform = "0%"
  }

  const mt = side === 'bottom' ? 8 : 0
  const mb = side === 'top' ? 8 : 0
  const ml = side === 'right' ? 8 : 0
  const mr = side === 'left' ? 8 : 0

  let portalContent = null
  if (open) {
    const portalElement = document.body
    if (portalElement) {
      portalContent = createPortal(
        <AnimatePresence>
          <motion.div
             initial={{ opacity: 0, y: initialY, x: initialX, scale: 0.95 }}
             animate={{ opacity: 1, y: 0, x: 0, scale: 1 }}
             exit={{ opacity: 0, y: initialY, x: initialX, scale: 0.95 }}
             transition={{ duration: 0.15 }}
             className={popupClasses}
             style={{
               left: coords.x,
               top: coords.y,
               transform: `translate(${xTransform}, ${yTransform})`,
               marginTop: mt,
               marginBottom: mb,
               marginLeft: ml,
               marginRight: mr
             }}
          >
            <div className={`font-semibold mb-2 flex items-center gap-2 text-[13px] ${colorToken}`}>
               <Icon className="w-4 h-4" /> {title}
            </div>
            <div className="text-slate-300 text-xs leading-relaxed">
              {description}
            </div>
            {codeSnippet && (
              <div className="mt-3 bg-black/80 px-3 py-2 rounded-lg border border-slate-800 font-mono text-[11px] text-emerald-400 overflow-x-auto whitespace-pre-wrap">
                {codeSnippet}
              </div>
            )}
          </motion.div>
        </AnimatePresence>,
        portalElement
      )
    }
  }

  return (
    <div
      ref={triggerRef}
      className="relative inline-flex items-center justify-center align-middle leading-none z-20 group cursor-help"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      {children || (
        <span className="text-slate-400 hover:text-sky-400 transition-colors cursor-help p-1 rounded-full hover:bg-slate-800">
          <Icon className="w-4 h-4" />
        </span>
      )}
      {typeof window !== 'undefined' && portalContent}
    </div>
  )
} 