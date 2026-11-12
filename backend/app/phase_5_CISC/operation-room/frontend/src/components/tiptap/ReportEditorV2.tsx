'use client'

import React, { useEffect, useState, useRef, forwardRef, useImperativeHandle } from 'react'
import { useEditor, EditorContent, type Editor } from '@tiptap/react'
import { StarterKit } from '@tiptap/starter-kit'
import { Underline } from '@tiptap/extension-underline'
import { TextAlign } from '@tiptap/extension-text-align'
import { Highlight } from '@tiptap/extension-highlight'
import { Image } from '@tiptap/extension-image'
import { Table } from '@tiptap/extension-table'
import { TableRow } from '@tiptap/extension-table-row'
import { TableCell } from '@tiptap/extension-table-cell'
import { TableHeader } from '@tiptap/extension-table-header'
import { Placeholder } from '@tiptap/extension-placeholder'
import { TextStyle } from '@tiptap/extension-text-style'
import { Color } from '@tiptap/extension-color'
import { cn } from '@operation-room/lib/utils'
import { useStudioStore } from '@operation-room/components/studio-v4/store/useStudioStore'
import { EvidenceBlockNode,
      type EvidenceBlockAttrs } from '@operation-room/components/tiptap'
import { ClaimNode } from '@operation-room/components/tiptap/extensions/ClaimNode'
import { FloatingToolbar } from '@operation-room/components/studio-v4/toolbar/FloatingToolbar'
import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { Decoration, DecorationSet } from '@tiptap/pm/view'

const ExecutiveFilterExtension = Extension.create({
  name: 'executiveFilter',
  
  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('executiveFilter'),
        state: {
          init(_, { doc }) {
            return getNoiseDecorations(doc);
          },
          apply(tr, old) {
            if (tr.docChanged) return getNoiseDecorations(tr.doc);
            return old.map(tr.mapping, tr.doc);
          },
        },
        props: {
          decorations(state) {
            return this.getState(state);
          },
        },
      }),
    ]
  },
})

function getNoiseDecorations(doc: any) {
  const decorations: Decoration[] = [];
  // Regex for long hex strings (hashes), IPv4 addresses, and file paths
  const noiseRegex = /\b([0-9a-fA-F]{32,64}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b|((?:\/[a-zA-Z0-9_.-]+)+)\b|\b([A-Za-z]:\\[a-zA-Z0-9_.-]+)\b/g;

  doc.descendants((node: any, pos: number) => {
    if (node.isText && node.text) {
      let match;
      while ((match = noiseRegex.exec(node.text)) !== null) {
        decorations.push(
          Decoration.inline(pos + match.index, pos + match.index + match[0].length, {
            class: 'technical-noise',
          })
        );
      }
    }
  });

  return DecorationSet.create(doc, decorations);
}

const AISlashCommand = Extension.create({
  name: 'aiSlashCommand',
  addKeyboardShortcuts() {
    return {
      '/': () => {
        const { editor } = this
        const { selection } = editor.state
        const { $from } = selection
        if ($from.parent.textContent === '/') {
          const text = prompt('AI Writer: Describe what you want the AI to analyze and stream...')
          if (text) {
            editor.commands.deleteRange({ from: $from.pos - 1, to: $from.pos })
            let i = 0
            const responseText = ' [AI streamed response for: ' + text + '] '
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



// Old static EditorToolbar removed — text formatting now uses FloatingToolbar

// ═══════════════════════════════════════════════════════════════════════════
// Editor Ref Interface
// ═══════════════════════════════════════════════════════════════════════════

export interface ReportEditorRef {
  getContent: () => any
  setContent: (content: any) => void
  insertContent: (content: string | any) => void
  insertEvidenceBlock: (attrs: Partial<EvidenceBlockAttrs>) => void
  focus: () => void
  getWordCount: () => number
  getEditor: () => Editor | null
}

// ═══════════════════════════════════════════════════════════════════════════
// Main Editor Component
// ═══════════════════════════════════════════════════════════════════════════

export interface ReportEditorV2Props {
  initialContent?: any
  onContentChange?: (content: any) => void
  onSave?: (content: any) => void
  onWordCountChange?: (count: number) => void
  readOnly?: boolean
  placeholder?: string
  className?: string
  hideChrome?: boolean
  onAIAssist?: () => void
  onDropComponent?: (componentId: string, config?: Record<string, unknown>) => void
}

export const ReportEditorV2 = forwardRef<ReportEditorRef, ReportEditorV2Props>(({
  initialContent,
  onContentChange,
  onSave,
  onWordCountChange,
  readOnly = false,
  placeholder = 'Start writing your forensic report...',
  className,
  hideChrome = false,
  onAIAssist,
  onDropComponent,
}, ref) => {
  const [wordCount, setWordCount] = useState(0)
  const [charCount, setCharCount] = useState(0)
  const saveTimer = useRef<NodeJS.Timeout | null>(null)
  
  // Track last selection to insert components at the correct place after focus loss
  const lastSelection = useRef<{ from: number, to: number } | null>(null)

    const { focusMode } = useStudioStore()

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3, 4] },
        codeBlock: { HTMLAttributes: { class: 'prose-code-block' } },
      }),
      Underline,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Highlight.configure({ multicolor: true }),
      Image.configure({ inline: false, allowBase64: true }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
      Placeholder.configure({ placeholder }),
      TextStyle,
      Color,
      EvidenceBlockNode,
      ClaimNode,
      AISlashCommand,
        ExecutiveFilterExtension,
    ],
    content: initialContent || { type: 'doc', content: [{ type: 'paragraph' }] },
    editable: !readOnly,
    immediatelyRender: false,
    
    // Store selection before the blur happens (e.g. clicking sidebar)
    onSelectionUpdate: ({ editor }) => {
      const { from, to } = editor.state.selection
      lastSelection.current = { from, to }
    },
    onBlur: ({ editor }) => {
      // Ensure we keep the last known good position
      const { from, to } = editor.state.selection
      if (from !== undefined) {
        lastSelection.current = { from, to }
      }
    },
    onUpdate: ({ editor }) => {
      const text = editor.getText()
      const words = text.split(/\s+/).filter(Boolean).length
      setWordCount(words)
      setCharCount(text.length)
      onWordCountChange?.(words)

      // Debounced save
      if (saveTimer.current) clearTimeout(saveTimer.current)
      saveTimer.current = setTimeout(() => {
        const json = editor.getJSON()
        onContentChange?.(json)
        onSave?.(json)
      }, 1500)
    },
    editorProps: {
      attributes: {
        class: cn(
          'prose md:prose-lg prose-slate dark:prose-invert max-w-none w-full outline-none font-geist',
          'prose-headings:font-bold prose-headings:tracking-tight prose-headings:text-slate-900 dark:prose-headings:text-slate-100',
          'prose-h1:text-4xl prose-h1:mb-6 prose-h2:text-2xl prose-h2:mt-10 prose-h2:mb-4',
          'prose-p:leading-relaxed prose-p:text-slate-700 dark:prose-p:text-slate-300 prose-p:tracking-normal',
          'prose-a:text-sky-600 dark:prose-a:text-sky-400 prose-a:no-underline hover:prose-a:underline',
          'prose-code:bg-slate-100 dark:prose-code:bg-slate-800 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:font-geist-mono prose-code:text-sm',
          'prose-pre:bg-slate-950 dark:prose-pre:bg-black/50 prose-pre:border prose-pre:border-slate-800',
          'prose-blockquote:border-l-sky-500 prose-blockquote:bg-sky-50 dark:prose-blockquote:bg-sky-950/20 prose-blockquote:px-4 prose-blockquote:py-1 prose-blockquote:my-6 prose-blockquote:not-italic prose-blockquote:text-slate-700 dark:prose-blockquote:text-slate-300 prose-blockquote:rounded-r-lg',
          'prose-table:border-collapse prose-td:border prose-td:border-slate-200 dark:prose-td:border-slate-800 prose-th:border prose-th:border-slate-200 dark:prose-th:border-slate-800 prose-th:bg-slate-50 dark:prose-th:bg-slate-900',
          'focus:outline-none min-h-[400px]',
          !hideChrome && 'p-8'
        ),
      },
      handleDrop: (view, event, _slice, _moved) => {
        if (!event.dataTransfer) return false
        try {
          const data = event.dataTransfer.getData('application/json')
          if (!data) return false
          
          const payload = JSON.parse(data)
          if (payload.type === 'component' && payload.componentId && onDropComponent) {
            event.preventDefault()
            
            // Position cursor at drop location
            const coordinates = view.posAtCoords({ left: event.clientX, top: event.clientY })
            if (coordinates && editor) {
              editor.chain().focus().setTextSelection(coordinates.pos).run()
            } else if (editor) {
              // Fallback: insert at end of document
              editor.chain().focus().setTextSelection(editor.state.doc.content.size - 1).run()
            }
            
            onDropComponent(payload.componentId, { module: payload.module })
            return true
          }
        } catch (e) {
          // Ignore parse errors from non-JSON drop events
        }
        return false
      }
    },
  })

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    getContent: () => editor?.getJSON(),
    setContent: (content) => editor?.commands.setContent(content),
    insertContent: (content) => editor?.commands.insertContent(content),
    insertEvidenceBlock: (attrs) => {
      if (editor) {
        let chain = editor.chain()
        
        // If we lost focus, restore the last known cursor position
        if (!editor.isFocused && lastSelection.current) {
          chain = chain.setTextSelection(lastSelection.current)
        }
        
        chain.focus().insertEvidenceBlock(attrs).run()
      }
    },
    focus: () => editor?.commands.focus(),
    getWordCount: () => wordCount,
    getEditor: () => editor,
  }), [editor, wordCount])

  // Update content when initialContent changes
  useEffect(() => {
    if (editor && initialContent && !editor.isFocused) {
      const currentJSON = JSON.stringify(editor.getJSON())
      const newJSON = JSON.stringify(initialContent)
      if (currentJSON !== newJSON) {
        editor.commands.setContent(initialContent)
      }
    }
  }, [initialContent, editor])

  // Cleanup
  useEffect(() => {
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current)
    }
  }, [])

  return (
    <div 
      className={cn(
        "flex flex-col bg-transparent overflow-hidden transition-colors relative",
        !hideChrome && "border rounded-lg shadow-sm bg-card",
        className
      )}
      onDragOver={(e) => {
        // Accept component drops from the sidebar
        if (e.dataTransfer.types.includes('application/json')) {
          e.preventDefault()
          e.dataTransfer.dropEffect = 'copy'
        }
      }}
    >
      {/* Floating Context Toolbar — appears only on text selection */}
      {!readOnly && editor && <FloatingToolbar editor={editor} onAIAssist={onAIAssist} />}

      {/* Editor Content */}
      <div className={cn("flex-1 overflow-auto", hideChrome && "h-full")}>
        <EditorContent data-focus-mode={focusMode} editor={editor} className="h-full" />
      </div>

      {/* Status Bar */}
      {!hideChrome && (
        <div className="flex items-center justify-between px-4 py-2 border-t bg-muted/30 text-xs text-muted-foreground w-full">
          <div className="flex items-center gap-4">
            <span>{wordCount.toLocaleString()} words</span>
            <span>{charCount.toLocaleString()} characters</span>
          </div>
          <div className="flex items-center gap-2">
            {readOnly && (
              <span className="px-1.5 py-0.5 bg-muted rounded text-[10px] font-medium uppercase tracking-wider">
                Read Only
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
})

ReportEditorV2.displayName = 'ReportEditorV2'

export default ReportEditorV2





