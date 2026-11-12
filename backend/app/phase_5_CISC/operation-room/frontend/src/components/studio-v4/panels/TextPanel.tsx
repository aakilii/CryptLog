'use client'

import React from 'react'
import {
  Heading1,
  Heading2,
  Heading3,
  AlignLeft,
  Quote,
  List,
  Code,
  SquareAsterisk
} from 'lucide-react'
import {
  PanelContent,
  PanelSection,
} from '../ExpandablePanel'

// Text Element Types
const TEXT_BLOCKS = [
  {
    id: 'text-h1',
    name: 'Add a heading',
    type: 'heading',
    level: 1,
    icon: Heading1,
    className: 'text-xl font-bold font-geist tracking-tight'
  },
  {
    id: 'text-h2',
    name: 'Add a subheading',
    type: 'heading',
    level: 2,
    icon: Heading2,
    className: 'text-lg font-semibold font-geist tracking-tight'
  },
  {
    id: 'text-body',
    name: 'Add a little bit of body text',
    type: 'paragraph',
    icon: AlignLeft,
    className: 'text-sm font-ui text-muted-foreground'
  },
  {
    id: 'text-quote',
    name: 'Add a blockquote',
    type: 'blockquote',
    icon: Quote,
    className: 'text-sm font-ui border-l-2 pl-2 italic text-muted-foreground'
  },
  {
    id: 'text-list',
    name: 'Add a bulleted list',
    type: 'bulletList',
    icon: List,
    className: 'text-sm font-ui flex items-center gap-2'
  },
  {
    id: 'text-code',
    name: 'Add a code block',
    type: 'codeBlock',
    icon: Code,
    className: 'text-xs font-geist-mono bg-muted p-2 rounded'
  }
]

interface TextPanelProps {
  onInsertText?: (blockDef: any) => void
}

export const TextPanel = ({ onInsertText }: TextPanelProps) => {
  return (
    <div className="flex flex-col h-full overflow-hidden bg-muted/10">
      <PanelContent className="p-4 space-y-6">
        <div>
          <h3 className="font-geist text-sm font-semibold mb-3">Default Text Styles</h3>
          <div className="flex flex-col gap-2">
            {TEXT_BLOCKS.slice(0, 3).map((block) => (
              <div
                key={block.id}
                className="p-3 rounded-lg border bg-card hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer flex flex-col justify-center min-h-[48px]"
                onClick={() => onInsertText?.(block)}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('application/json', JSON.stringify({
                    type: 'text-block',
                    content: block.type,
                    level: block.level
                  }))
                }}
              >
                <span className={block.className}>{block.name}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
           <h3 className="font-geist text-sm font-semibold mb-3">Formatting Blocks</h3>
           <div className="grid grid-cols-2 gap-2">
            {TEXT_BLOCKS.slice(3).map((block) => (
              <div
                key={block.id}
                className="p-3 rounded-lg border bg-card flex flex-col items-center justify-center gap-2 hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer aspect-square"
                onClick={() => onInsertText?.(block)}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('application/json', JSON.stringify({
                    type: 'text-block',
                    content: block.type,
                  }))
                }}
              >
                <block.icon className="w-8 h-8 text-muted-foreground" />
                <span className="text-xs font-ui text-center">{block.name}</span>
              </div>
            ))}
           </div>
        </div>

      </PanelContent>
    </div>
  )
}
