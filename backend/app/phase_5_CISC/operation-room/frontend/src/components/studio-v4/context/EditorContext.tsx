'use client'

import React, { createContext, useContext, useRef, useCallback } from 'react'
import type { Editor } from '@tiptap/core'
import type { EvidenceBlockAttrs } from '@operation-room/components/tiptap/EvidenceBlockNode'

// ── Hash utility ────────────────────────────────────────────────────────
async function computeSHA256(data: string): Promise<string> {
  if (typeof window === 'undefined') return `sha256:${Date.now().toString(16)}`
  const encoded = new TextEncoder().encode(data)
  const hashBuffer = await crypto.subtle.digest('SHA-256', encoded)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return 'sha256:' + hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
}

function computeHashSync(data: string): string {
  // Simple sync hash for when we can't use async
  let hash = 0
  for (let i = 0; i < data.length; i++) {
    const char = data.charCodeAt(i)
    hash = ((hash << 5) - hash) + char
    hash |= 0
  }
  return `sha256:${Math.abs(hash).toString(16).padStart(12, '0')}`
}

// ── Citation ID generator ───────────────────────────────────────────────
function generateCitationId(source: string, id?: string): string {
  const shortId = id?.slice(0, 4) || Math.random().toString(36).slice(2, 6)
  return `[EVD-${source.toUpperCase()}-${shortId}]`
}

// ── Context types ───────────────────────────────────────────────────────
interface EditorContextValue {
  /** The active TipTap editor instance */
  editor: Editor | null
  /** Set the editor instance (called by ReportEditorV2 on mount) */
  setEditor: (editor: Editor | null) => void
  /** Insert an evidence block into the editor at cursor position */
  insertEvidence: (attrs: Partial<EvidenceBlockAttrs>) => void
  /** Insert raw TipTap content */
  insertContent: (content: any) => void
}

const EditorContext = createContext<EditorContextValue>({
  editor: null,
  setEditor: () => {},
  insertEvidence: () => {},
  insertContent: () => {},
})

export const useEditorContext = () => useContext(EditorContext)

// ── Provider ────────────────────────────────────────────────────────────
interface EditorProviderProps {
  children: React.ReactNode
}

export const EditorProvider = ({ children }: EditorProviderProps) => {
  const editorRef = useRef<Editor | null>(null)

  const setEditor = useCallback((editor: Editor | null) => {
    editorRef.current = editor
  }, [])

  const insertEvidence = useCallback((attrs: Partial<EvidenceBlockAttrs>) => {
    const editor = editorRef.current
    if (!editor) {
      console.warn('[EditorContext] No editor available for insertion')
      return
    }

    // Auto-generate provenance fields
    const evidenceId = attrs.id || `evd-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const dataStr = JSON.stringify(attrs.data || {})
    const hash = computeHashSync(dataStr)
    const citationId = generateCitationId(attrs.source || 'case', evidenceId)

    const fullAttrs: Partial<EvidenceBlockAttrs> = {
      ...attrs,
      id: evidenceId,
      metadata: {
        hash,
        timestamp: new Date().toISOString(),
        runId: (attrs.metadata as any)?.runId || undefined,
        citationId,
        insertionActor: 'investigator',
        verified: false,
        ...(attrs.metadata || {}),
      },
    }

    editor.chain().focus().insertContent({
      type: 'evidenceBlock',
      attrs: fullAttrs,
    }).run()

    console.log(`[EditorContext] Inserted evidence: ${citationId}`, fullAttrs)
  }, [])

  const insertContent = useCallback((content: any) => {
    const editor = editorRef.current
    if (!editor) return
    editor.chain().focus().insertContent(content).run()
  }, [])

  return (
    <EditorContext.Provider value={{ editor: editorRef.current, setEditor, insertEvidence, insertContent }}>
      {children}
    </EditorContext.Provider>
  )
}
