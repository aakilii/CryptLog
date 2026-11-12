'use client'

import React from 'react'
import {
  Square,
  Circle,
  Triangle,
  Minus,
  ArrowRight,
  Sticker,
  PenTool,
  Stamp,
  Tag,
  AlertOctagon,
  Image as ImageIcon,
} from 'lucide-react'
import {
  PanelContent,
} from '../ExpandablePanel'

// Canvas Shapes and Elements
const ELEMENTS = [
  { id: 'el-square', name: 'Square', icon: Square, type: 'shape' },
  { id: 'el-circle', name: 'Circle', icon: Circle, type: 'shape' },
  { id: 'el-triangle', name: 'Triangle', icon: Triangle, type: 'shape' },
  { id: 'el-line', name: 'Line', icon: Minus, type: 'line' },
  { id: 'el-arrow', name: 'Arrow', icon: ArrowRight, type: 'line' },
]

const ANNOTATIONS = [
  { id: 'an-sticker', name: 'Sticker', icon: Sticker },
  { id: 'an-draw', name: 'Freehand', icon: PenTool },
  { id: 'an-stamp', name: 'Approved Stamp', icon: Stamp },
  { id: 'an-confidential', name: 'Confidential', icon: AlertOctagon },
  { id: 'an-tag', name: 'Highlight Tag', icon: Tag },
]

interface ElementsPanelProps {
  onInsertElement?: (elementConfig: any) => void
}

export const ElementsPanel = ({ onInsertElement }: ElementsPanelProps) => {
  return (
    <div className="flex flex-col h-full overflow-hidden bg-muted/10">
      <PanelContent className="p-4 space-y-6">
        
        {/* Shapes Library */}
        <div>
          <h3 className="font-geist text-sm font-semibold mb-3">Shapes & Lines</h3>
          <div className="grid grid-cols-3 gap-2">
            {ELEMENTS.map((el) => (
              <div
                key={el.id}
                className="group p-3 rounded-lg border bg-card flex flex-col items-center justify-center gap-2 hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer aspect-square"
                onClick={() => onInsertElement?.(el)}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('application/json', JSON.stringify({
                    type: 'canvas-element',
                    elementId: el.id
                  }))
                }}
              >
                <el.icon className="w-6 h-6 text-muted-foreground group-hover:text-primary transition-colors" />
                <span className="text-[10px] font-ui text-center text-muted-foreground">{el.name}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Annotations */}
        <div>
          <h3 className="font-geist text-sm font-semibold mb-3">Stamps & Annotations</h3>
          <div className="grid grid-cols-2 gap-2">
            {ANNOTATIONS.map((an) => (
              <div
                key={an.id}
                className="group p-3 rounded-lg border bg-card flex items-center justify-center gap-2 hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer h-12"
                onClick={() => onInsertElement?.(an)}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('application/json', JSON.stringify({
                    type: 'annotation',
                    elementId: an.id
                  }))
                }}
              >
                <an.icon className="w-4 h-4 text-primary opacity-70 group-hover:opacity-100" />
                <span className="text-xs font-ui font-medium truncate">{an.name}</span>
              </div>
            ))}
          </div>
        </div>

      </PanelContent>
    </div>
  )
}
