'use client'

import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export interface ActionTooltipProps {
  label: string
  children: React.ReactNode
  delay?: number
  isSvg?: boolean
}

export function ActionTooltip({ label, children, delay = 200, isSvg = false }: ActionTooltipProps) {
  const [open, setOpen] = useState(false)
  const [timer, setTimer] = useState<NodeJS.Timeout | null>(null)

  const handleMouseEnter = () => {
    const t = setTimeout(() => setOpen(true), delay)
    setTimer(t)
  }

  const handleMouseLeave = () => {
    if (timer) clearTimeout(timer)
    setOpen(false)
  }

  useEffect(() => {
    return () => {
      if (timer) clearTimeout(timer)
    }
  }, [timer])

  const tooltipElement = (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0, y: -4, scale: 0.9 }}
          animate={{ opacity: 1, y: -8, scale: 1 }}
          exit={{ opacity: 0, y: -4, scale: 0.9 }}
          transition={{ duration: 0.1, type: "spring", stiffness: 300, damping: 20 }}
          className="absolute bottom-full left-1/2 -translate-x-1/2 w-max max-w-[250px] px-2 py-1 bg-slate-800 text-slate-200 text-[10px] font-semibold rounded shadow-md z-[200] pointer-events-none tracking-wide text-center"
        >
          {label}
          {/* Tiny arrow */}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px w-0 h-0 border-l-[4px] border-r-[4px] border-t-[4px] border-l-transparent border-r-transparent border-t-slate-800"></div>
        </motion.div>
      )}
    </AnimatePresence>
  )

  if (isSvg) {
    return (
      <g
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        style={{ cursor: 'pointer' }}
      >
        {children}
        {open && (
           <foreignObject x="0" y="0" width="1" height="1" style={{ overflow: 'visible' }}>
             <div className="relative group inline-flex items-center justify-center pointer-events-none">
               {tooltipElement}
             </div>
           </foreignObject>
        )}
      </g>
    )
  }

  return (
    <div
      className="relative inline-flex items-center justify-center group"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      {tooltipElement}
    </div>
  )
}
