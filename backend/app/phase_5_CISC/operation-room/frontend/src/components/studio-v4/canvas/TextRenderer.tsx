'use client'

import { cn } from '@operation-room/lib/utils'
import { Extension } from '@tiptap/core'
import { Color } from '@tiptap/extension-color'
import { Placeholder } from '@tiptap/extension-placeholder'
import { TextAlign } from '@tiptap/extension-text-align'
import { TextStyle } from '@tiptap/extension-text-style'
import { Underline } from '@tiptap/extension-underline'
import { EditorContent, useEditor } from '@tiptap/react'
import { BubbleMenu } from '@tiptap/react/menus'
import StarterKit from '@tiptap/starter-kit'
import { AlignCenter, AlignLeft, AlignRight, Baseline, Bold, Italic, Strikethrough, Underline as UnderlineIcon, X } from 'lucide-react'
import React from 'react'
import { CanvasElement, useStudioStore } from '../store/useStudioStore'

// Phase 4: AI Writer Slash Command Extension
const AISlashCommand = Extension.create({
  name: 'aiSlashCommand',

  addKeyboardShortcuts() {
    return {
      '/': () => {
        const { editor } = this
        const { state } = editor
        const { selection } = state
        const { $from } = selection

        // Check if on empty line or right after start of line
        if ($from.parent.textContent === '/') {
          // This is a simplified frontend mock-up of the /ai command.
          // Since it's a real-time collaborative env, in a real implementation we would open a frosted-glass popup UI.
          const text = prompt("AI Writer: Describe what you want the AI to analyze and stream...")
          if (text) {
            // Remove the slash
            editor.commands.deleteRange({ from: $from.pos - 1, to: $from.pos })

            // Mock SSE stream typing
            let i = 0
            const responseText = " [AI streamed response for: " + text + "] "
            const interval = setInterval(() => {
              if (i < responseText.length) {
                editor.commands.insertContent(responseText[i])
                i++
              } else {
                clearInterval(interval)
              }
            }, 50)
            return true
          }
        }
        return false
      }
    }
  }
})

export const TextRenderer = ({
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
  const { updateElement, deleteElements, selectedElementIds, setSelectedElements } = useStudioStore()
  const isSelected = selectedElementIds.includes(element.id)
  const [dragPosition, setDragPosition] = React.useState<{ x: number; y: number } | null>(null)

  const handleSelect = (e: React.MouseEvent) => {
    e.stopPropagation()
    setSelectedElements([element.id])
  }

  // Pure textual Editor completely isolated to this bounding box
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3, 4] },
      }),
      TextStyle,
      Color,
      Underline,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Placeholder.configure({
        placeholder: element.data.textType === 'heading' ? 'Heading...' : 'Type "/" for AI commands...',
        emptyEditorClass: 'is-editor-empty before:content-[attr(data-placeholder)] before:text-muted-foreground before:opacity-50 before:float-left before:pointer-events-none',
      }),
      AISlashCommand,
    ],
    content: element.data.content || '<p></p>',
    onUpdate: ({ editor }) => {
      updateElement(pageIndex, element.id, {
        data: {
          ...element.data,
          content: editor.getHTML()
        }
      })
    },
    editable: true // Text is directly editable inside the RND box
  })

  // Prevent drag events when actively typing inside TipTap
  const isTyping = editor?.isFocused

  return (
    <div
      onClick={handleSelect}
      className={cn(
        "group relative w-full transition-shadow rounded-md border border-transparent",
        isSelected ? "ring-2 ring-sky-500/50 shadow-md z-10" : "hover:ring-1 hover:ring-sky-500/30"
      )}
    >
      {/* Widget Header & Controls (Hidden until hovered or selected) */}
      <div
        className={cn(
          "absolute -top-7 left-0 h-6 bg-white dark:bg-[#111] shadow border rounded-md flex items-center justify-between px-1 transition-all z-20",
          isSelected ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1 group-hover:opacity-100 group-hover:translate-y-0"
        )}
      >
        <button
          onClick={(e) => { e.stopPropagation(); deleteElements(pageIndex, [element.id]); }}
          className="p-0.5 hover:bg-red-500/10 hover:text-red-500 rounded text-muted-foreground transition-colors"
        >
          <X className="h-3 w-3" />
        </button>
      </div>

      {/* Editor Body */}
      <div
        className={cn(
          "w-full h-full min-h-[40px] px-2 py-1 overflow-hidden relative",
          element.data.style === 'heading'
            ? 'font-sans text-2xl font-black tracking-tighter text-slate-800 dark:text-slate-100 antialiased'
            : 'font-serif text-base leading-relaxed text-slate-700 dark:text-slate-300 antialiased prose prose-slate dark:prose-invert prose-p:my-1'
        )}
      >
        {editor && (
          <BubbleMenu
            editor={editor}

            className="flex flex-row items-center gap-1 p-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl rounded-md z-[99999]"
          >
            {/* Format Buttons */}
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); editor.chain().focus().toggleBold().run() }}
              className={cn("p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800", editor.isActive('bold') && "bg-slate-100 dark:bg-slate-800 text-sky-600")}
              title="Bold"
            >
              <Bold className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); editor.chain().focus().toggleItalic().run() }}
              className={cn("p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800", editor.isActive('italic') && "bg-slate-100 dark:bg-slate-800 text-sky-600")}
              title="Italic"
            >
              <Italic className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); editor.chain().focus().toggleUnderline().run() }}
              className={cn("p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800", editor.isActive('underline') && "bg-slate-100 dark:bg-slate-800 text-sky-600")}
              title="Underline"
            >
              <UnderlineIcon className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); editor.chain().focus().toggleStrike().run() }}
              className={cn("p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800", editor.isActive('strike') && "bg-slate-100 dark:bg-slate-800 text-sky-600")}
              title="Strikethrough"
            >
              <Strikethrough className="h-3.5 w-3.5" />
            </button>

            <div className="w-px h-4 bg-slate-200 dark:bg-slate-700 mx-1" />

            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); editor.chain().focus().toggleHeading({ level: 1 }).run() }}
              className={cn("p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 font-bold font-sans text-xs", editor.isActive('heading', { level: 1 }) && "bg-slate-100 dark:bg-slate-800 text-sky-600")}
              title="Heading 1"
            >
              H1
            </button>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); editor.chain().focus().toggleHeading({ level: 2 }).run() }}
              className={cn("p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 font-bold font-sans text-xs", editor.isActive('heading', { level: 2 }) && "bg-slate-100 dark:bg-slate-800 text-sky-600")}
              title="Heading 2"
            >
              H2
            </button>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); editor.chain().focus().setParagraph().run() }}
              className={cn("p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-serif", editor.isActive('paragraph') && "bg-slate-100 dark:bg-slate-800 text-sky-600")}
              title="Paragraph"
            >
              P
            </button>

            <div className="w-px h-4 bg-slate-200 dark:bg-slate-700 mx-1" />

            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); editor.chain().focus().setTextAlign('left').run() }}
              className={cn("p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800", editor.isActive({ textAlign: 'left' }) && "bg-slate-100 dark:bg-slate-800 text-sky-600")}
              title="Align Left"
            >
              <AlignLeft className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); editor.chain().focus().setTextAlign('center').run() }}
              className={cn("p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800", editor.isActive({ textAlign: 'center' }) && "bg-slate-100 dark:bg-slate-800 text-sky-600")}
              title="Align Center"
            >
              <AlignCenter className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => { e.preventDefault(); e.stopPropagation(); editor.chain().focus().setTextAlign('right').run() }}
              className={cn("p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800", editor.isActive({ textAlign: 'right' }) && "bg-slate-100 dark:bg-slate-800 text-sky-600")}
              title="Align Right"
            >
              <AlignRight className="h-3.5 w-3.5" />
            </button>

            <div className="w-px h-4 bg-slate-200 dark:bg-slate-700 mx-1" />

            <div className="flex items-center gap-1 group/color pl-1 cursor-pointer">
              <Baseline className="h-3.5 w-3.5 text-slate-500" />
              <input
                type="color"
                onInput={(e) => editor.chain().focus().setColor(e.currentTarget.value).run()}
                value={editor.getAttributes('textStyle').color || '#000000'}
                className="w-5 h-5 rounded cursor-pointer border-0 bg-transparent p-0"
                onClick={(e) => e.stopPropagation()}
              />
            </div>

          </BubbleMenu>
        )}
        <EditorContent editor={editor} className="outline-none min-h-full cursor-text" />
      </div>
    </div>
  )
}
