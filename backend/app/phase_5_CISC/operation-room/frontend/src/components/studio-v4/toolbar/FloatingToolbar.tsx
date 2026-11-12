'use client'

import React, { useEffect, useRef, useState, useCallback } from 'react'
import type { Editor } from '@tiptap/core'
import {
  Bold, Italic, Underline, Strikethrough, Code,
  Heading1, Heading2, Heading3,
  AlignLeft, AlignCenter, AlignRight,
  Link2, Highlighter, Sparkles,
  ChevronDown, Type,
} from 'lucide-react'
import { cn } from '@operation-room/lib/utils'
import { Button } from '@operation-room/components/ui/button'
import { Toggle } from '@operation-room/components/ui/toggle'
import { Separator } from '@operation-room/components/ui/separator'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@operation-room/components/ui/popover'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@operation-room/components/ui/dropdown-menu'
import { ActionTooltip } from '@operation-room/components/ui/ActionTooltip'
import { ShieldCheck } from 'lucide-react'

// ── Color Presets ────────────────────────────────────────────────────────
const TEXT_COLORS = [
  { name: 'Default', value: '#1e293b' },
  { name: 'Red', value: '#dc2626' },
  { name: 'Orange', value: '#ea580c' },
  { name: 'Green', value: '#16a34a' },
  { name: 'Blue', value: '#2563eb' },
  { name: 'Purple', value: '#9333ea' },
  { name: 'Gray', value: '#64748b' },
]

const HIGHLIGHT_COLORS = [
  { name: 'None', value: 'transparent' },
  { name: 'Yellow', value: '#fef08a' },
  { name: 'Green', value: '#bbf7d0' },
  { name: 'Blue', value: '#bfdbfe' },
  { name: 'Purple', value: '#e9d5ff' },
  { name: 'Pink', value: '#fbcfe8' },
]

// ── Toolbar Button ──────────────────────────────────────────────────────
const Btn = ({ active, onClick, children, title }: {
  active?: boolean; onClick: () => void; children: React.ReactNode; title?: string
}) => (
  <Toggle
    pressed={active}
    onPressedChange={() => onClick()}
    size="sm"
    className={cn("h-7 w-7 p-0 rounded-lg", active && "bg-white/20 text-white")}
    title={title}
  >
    {children}
  </Toggle>
)

// ── Main Floating Toolbar ───────────────────────────────────────────────
interface FloatingToolbarProps {
  editor: Editor | null
  onAIAssist?: () => void
}

export const FloatingToolbar = ({ editor, onAIAssist }: FloatingToolbarProps) => {
  const toolbarRef = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  const [coords, setCoords] = useState({ top: 0, left: 0 })

  const updatePosition = useCallback(() => {
    if (!editor) return

    const { state } = editor
    const { from, to, empty } = state.selection

    // Don't show for empty selections or within evidence blocks
    if (empty || editor.isActive('evidenceBlock')) {
      setVisible(false)
      return
    }

    // Get the DOM coordinates of the selection
    const view = editor.view
    const start = view.coordsAtPos(from)
    const end = view.coordsAtPos(to)

    // Position above the selection, centered
    const centerX = (start.left + end.left) / 2
    const topY = Math.min(start.top, end.top)

    // Offset for toolbar height
    const toolbarHeight = toolbarRef.current?.offsetHeight || 40
    const toolbarWidth = toolbarRef.current?.offsetWidth || 500

    setCoords({
      top: topY - toolbarHeight - 12 + window.scrollY,
      left: Math.max(8, centerX - toolbarWidth / 2),
    })
    setVisible(true)
  }, [editor])

  useEffect(() => {
    if (!editor) return

    const onSelectionUpdate = () => {
      // Micro-delay to let the DOM settle
      requestAnimationFrame(updatePosition)
    }

    const onBlur = () => {
      // Small delay so clicking toolbar buttons doesn't dismiss
      setTimeout(() => setVisible(false), 200)
    }

    editor.on('selectionUpdate', onSelectionUpdate)
    editor.on('blur', onBlur)

    return () => {
      editor.off('selectionUpdate', onSelectionUpdate)
      editor.off('blur', onBlur)
    }
  }, [editor, updatePosition])

  if (!editor || !visible) return null

  return (
    <div
      ref={toolbarRef}
      className="fixed z-[60] pointer-events-auto"
      style={{ top: coords.top, left: coords.left }}
      onMouseDown={(e) => {
        // Prevent blur when clicking toolbar buttons
        e.preventDefault()
      }}
    >
      <div className={cn(
        "flex items-center gap-0.5 px-2 py-1.5 rounded-2xl",
        "bg-slate-900/95 dark:bg-zinc-800/95 backdrop-blur-xl",
        "shadow-[0_8px_40px_-12px_rgba(0,0,0,0.5)] dark:shadow-[0_8px_40px_-12px_rgba(0,0,0,0.8)]",
        "border border-white/10",
        "text-slate-200",
        "animate-in fade-in-0 zoom-in-95 duration-200"
      )}>
        {/* Heading dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="h-7 px-1.5 gap-0.5 text-slate-200 hover:text-white hover:bg-white/10 rounded-lg">
              <Type className="h-3.5 w-3.5" />
              <ChevronDown className="h-2.5 w-2.5 opacity-60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="min-w-[140px]" side="top" sideOffset={8}>
            <DropdownMenuItem onClick={() => editor.chain().focus().setParagraph().run()}>
              <span className="text-sm">Paragraph</span>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}>
              <Heading1 className="h-4 w-4 mr-2" /><span className="text-base font-bold">Heading 1</span>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>
              <Heading2 className="h-4 w-4 mr-2" /><span className="text-sm font-semibold">Heading 2</span>
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}>
              <Heading3 className="h-4 w-4 mr-2" /><span className="text-sm font-medium">Heading 3</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Separator orientation="vertical" className="h-4 mx-0.5 bg-white/15" />

        {/* Highlight Assist (Turn into Claim) - Phase 3 UX */}
        <ActionTooltip label="Tether this fact to an Evidence Card to survive cross-examination." delay={100}>
          <Button
            size="sm"
            variant="ghost"
            className="flex items-center gap-1.5 h-7 px-2 font-semibold text-emerald-400 hover:text-emerald-300 hover:bg-emerald-400/10 rounded-xl whitespace-nowrap"
            onClick={() => {
              if (editor) {
                const { from, to } = editor.state.selection
                const text = editor.state.doc.textBetween(from, to, ' ')
                if (!text) return
                editor.chain().focus()
                  .setNode('claim', { status: 'draft', text: text, evidenceCardIds: [] })
                  .run()
              }
            }}
          >
            <ShieldCheck className="h-3.5 w-3.5" /> Turn to Claim
          </Button>
        </ActionTooltip>

        <Separator orientation="vertical" className="h-4 mx-0.5 bg-white/15" />

        {/* Text formatting */}
        <Btn active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()} title="Bold">
          <Bold className="h-3.5 w-3.5" />
        </Btn>
        <Btn active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()} title="Italic">
          <Italic className="h-3.5 w-3.5" />
        </Btn>
        <Btn active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()} title="Underline">
          <Underline className="h-3.5 w-3.5" />
        </Btn>
        <Btn active={editor.isActive('strike')} onClick={() => editor.chain().focus().toggleStrike().run()} title="Strikethrough">
          <Strikethrough className="h-3.5 w-3.5" />
        </Btn>
        <Btn active={editor.isActive('code')} onClick={() => editor.chain().focus().toggleCode().run()} title="Code">
          <Code className="h-3.5 w-3.5" />
        </Btn>

        <Separator orientation="vertical" className="h-4 mx-0.5 bg-white/15" />

        {/* Alignment */}
        <Btn active={editor.isActive({ textAlign: 'left' })} onClick={() => editor.chain().focus().setTextAlign('left').run()} title="Align left">
          <AlignLeft className="h-3.5 w-3.5" />
        </Btn>
        <Btn active={editor.isActive({ textAlign: 'center' })} onClick={() => editor.chain().focus().setTextAlign('center').run()} title="Align center">
          <AlignCenter className="h-3.5 w-3.5" />
        </Btn>
        <Btn active={editor.isActive({ textAlign: 'right' })} onClick={() => editor.chain().focus().setTextAlign('right').run()} title="Align right">
          <AlignRight className="h-3.5 w-3.5" />
        </Btn>

        <Separator orientation="vertical" className="h-4 mx-0.5 bg-white/15" />

        {/* Text color */}
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-200 hover:text-white hover:bg-white/10 rounded-lg">
              <div className="flex flex-col items-center">
                <Type className="h-3 w-3" />
                <div className="w-3 h-0.5 mt-px rounded-sm bg-current" />
              </div>
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-2" side="top" sideOffset={8}>
            <div className="flex gap-1">
              {TEXT_COLORS.map(c => (
                <button
                  key={c.value}
                  className="w-6 h-6 rounded-full border-2 border-transparent hover:border-primary/50 transition-all hover:scale-110"
                  style={{ backgroundColor: c.value }}
                  title={c.name}
                  onClick={() => editor.chain().focus().setColor(c.value).run()}
                />
              ))}
            </div>
          </PopoverContent>
        </Popover>

        {/* Highlight */}
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7 text-slate-200 hover:text-white hover:bg-white/10 rounded-lg">
              <Highlighter className="h-3.5 w-3.5" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-2" side="top" sideOffset={8}>
            <div className="flex gap-1">
              {HIGHLIGHT_COLORS.map(c => (
                <button
                  key={c.value}
                  className={cn(
                    "w-6 h-6 rounded-full border-2 border-transparent hover:border-primary/50 transition-all hover:scale-110",
                    c.value === 'transparent' && "border-dashed border-muted-foreground/30"
                  )}
                  style={{ backgroundColor: c.value === 'transparent' ? '#fff' : c.value }}
                  title={c.name}
                  onClick={() => {
                    if (c.value === 'transparent') {
                      editor.chain().focus().unsetHighlight().run()
                    } else {
                      editor.chain().focus().toggleHighlight({ color: c.value }).run()
                    }
                  }}
                />
              ))}
            </div>
          </PopoverContent>
        </Popover>

        {/* Link */}
        <Btn
          active={editor.isActive('link')}
          onClick={() => {
            const url = window.prompt('URL:')
            if (url) editor.chain().focus().setLink({ href: url }).run()
          }}
          title="Link"
        >
          <Link2 className="h-3.5 w-3.5" />
        </Btn>

        <Separator orientation="vertical" className="h-4 mx-0.5 bg-white/15" />

        {/* AI Assist */}
        {onAIAssist && (
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 px-2 rounded-lg text-xs font-medium bg-gradient-to-r from-sky-500/20 to-indigo-500/20 text-sky-300 hover:text-white hover:from-sky-500/30 hover:to-indigo-500/30"
            onClick={onAIAssist}
          >
            <Sparkles className="h-3 w-3" />
            AI
          </Button>
        )}
      </div>
    </div>
  )
}
