'use client';

import './ReportEditor.css';
import React, { useCallback, useEffect, useState, useRef, useMemo } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import { StarterKit } from '@tiptap/starter-kit';
import { Underline } from '@tiptap/extension-underline';
import { TextAlign } from '@tiptap/extension-text-align';
import { Highlight } from '@tiptap/extension-highlight';
import { Image } from '@tiptap/extension-image';
import { Table } from '@tiptap/extension-table';
import { TableRow } from '@tiptap/extension-table-row';
import { TableCell } from '@tiptap/extension-table-cell';
import { TableHeader } from '@tiptap/extension-table-header';
import { Placeholder } from '@tiptap/extension-placeholder';
import { TextStyle } from '@tiptap/extension-text-style';
import { Color } from '@tiptap/extension-color';
import { Highlighter, Image as ImageIcon, Redo2, Table2, Undo2 } from 'lucide-react';

/* ── Collaboration (Yjs) — lazy loaded when needed ──── */
let Collaboration, CollaborationCursor, WebsocketProvider, Y;
try {
  Collaboration = require('@tiptap/extension-collaboration').default;
  CollaborationCursor = require('@tiptap/extension-collaboration-cursor').default;
  WebsocketProvider = require('y-websocket').WebsocketProvider;
  Y = require('yjs');
} catch (e) {
  // Collaboration packages not installed — solo mode only
}

const CURSOR_COLORS = [
  '#2563eb', '#059669', '#d97706', '#dc2626', '#7c3aed',
  '#0891b2', '#be185d', '#4f46e5', '#ca8a04', '#0d9488',
];

/* ═══════════════════════════════════════════════════════════════════
   Toolbar Button Component
   ═══════════════════════════════════════════════════════════════════ */
function TBtn({ onClick, active, disabled, title, children }) {
  return (
    <button
      onMouseDown={(e) => { e.preventDefault(); onClick?.(); }}
      disabled={disabled}
      title={title}
      style={{
        width: 32, height: 32, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        borderRadius: 6, border: 'none', cursor: disabled ? 'default' : 'pointer',
        background: active ? 'rgba(37,99,235,0.10)' : 'transparent',
        color: active ? '#2563eb' : disabled ? '#cbd5e1' : '#475569',
        fontSize: 14, fontWeight: 600, transition: 'all 0.15s',
        opacity: disabled ? 0.4 : 1,
      }}
    >
      {children}
    </button>
  );
}

function Divider() {
  return <div style={{ width: 1, height: 20, background: '#e2e8f0', margin: '0 4px' }} />;
}

/* ═══════════════════════════════════════════════════════════════════
   Toolbar Component
   ═══════════════════════════════════════════════════════════════════ */
function EditorToolbar({ editor }) {
  if (!editor) return null;

  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 2,
      padding: '8px 12px', borderBottom: '1px solid #e2e8f0',
      background: '#fafbfc', position: 'sticky', top: 0, zIndex: 10,
    }}>
      {/* ── Text Formatting ────────────────── */}
      <TBtn onClick={() => editor.chain().focus().toggleBold().run()} active={editor.isActive('bold')} title="Bold (Ctrl+B)">
        <b>B</b>
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().toggleItalic().run()} active={editor.isActive('italic')} title="Italic (Ctrl+I)">
        <i>I</i>
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().toggleUnderline().run()} active={editor.isActive('underline')} title="Underline (Ctrl+U)">
        <u>U</u>
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().toggleStrike().run()} active={editor.isActive('strike')} title="Strikethrough">
        <s>S</s>
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().toggleHighlight().run()} active={editor.isActive('highlight')} title="Highlight">
        <Highlighter size={14} />
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().toggleCode().run()} active={editor.isActive('code')} title="Inline Code">
        {'</>'}
      </TBtn>

      <Divider />

      {/* ── Headings ────────────────────────── */}
      <TBtn onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} active={editor.isActive('heading', { level: 1 })} title="Heading 1">
        H1
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} active={editor.isActive('heading', { level: 2 })} title="Heading 2">
        H2
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} active={editor.isActive('heading', { level: 3 })} title="Heading 3">
        H3
      </TBtn>

      <Divider />

      {/* ── Lists ───────────────────────────── */}
      <TBtn onClick={() => editor.chain().focus().toggleBulletList().run()} active={editor.isActive('bulletList')} title="Bullet List">
        •≡
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().toggleOrderedList().run()} active={editor.isActive('orderedList')} title="Numbered List">
        1.
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().toggleBlockquote().run()} active={editor.isActive('blockquote')} title="Blockquote">
        "
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().toggleCodeBlock().run()} active={editor.isActive('codeBlock')} title="Code Block">
        {'{ }'}
      </TBtn>

      <Divider />

      {/* ── Alignment ──────────────────────── */}
      <TBtn onClick={() => editor.chain().focus().setTextAlign('left').run()} active={editor.isActive({ textAlign: 'left' })} title="Align Left">
        ≡←
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().setTextAlign('center').run()} active={editor.isActive({ textAlign: 'center' })} title="Align Center">
        ≡↔
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().setTextAlign('right').run()} active={editor.isActive({ textAlign: 'right' })} title="Align Right">
        →≡
      </TBtn>

      <Divider />

      {/* ── Insert ─────────────────────────── */}
      <TBtn onClick={() => editor.chain().focus().setHorizontalRule().run()} title="Horizontal Rule">
        ──
      </TBtn>
      <TBtn onClick={() => {
        editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
      }} title="Insert Table">
        <Table2 size={14} />
      </TBtn>
      <TBtn onClick={() => {
        const url = window.prompt('Image URL:');
        if (url) editor.chain().focus().setImage({ src: url }).run();
      }} title="Insert Image">
        <ImageIcon size={14} />
      </TBtn>

      <Divider />

      {/* ── History ─────────────────────────── */}
      <TBtn onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()} title="Undo (Ctrl+Z)">
        <Undo2 size={14} />
      </TBtn>
      <TBtn onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()} title="Redo (Ctrl+Shift+Z)">
        <Redo2 size={14} />
      </TBtn>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════
   Main TipTap Editor Component
   ═══════════════════════════════════════════════════════════════════ */
export default function ReportEditor({
  initialContent, onSave, onContentChange, readOnly = false,
  collaborative = false, docId = null, userName = 'Investigator',
}) {
  const [wordCount, setWordCount] = useState(0);
  const [charCount, setCharCount] = useState(0);
  const [connectedUsers, setConnectedUsers] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const saveTimer = useRef(null);
  const ydocRef = useRef(null);
  const providerRef = useRef(null);

  // Yjs setup (memoised to prevent re-creation)
  const collabExtensions = useMemo(() => {
    if (!collaborative || !docId || !Collaboration || !Y) return [];

    const ydoc = new Y.Doc();
    ydocRef.current = ydoc;

    // Connect to y-websocket server
    const wsUrl = typeof window !== 'undefined'
      ? `ws://${window.location.hostname}:4001`
      : 'ws://localhost:4001';

    const provider = new WebsocketProvider(wsUrl, `studio-${docId}`, ydoc);
    providerRef.current = provider;

    provider.on('status', ({ status }) => {
      setWsConnected(status === 'connected');
    });

    // Track connected users
    const awareness = provider.awareness;
    const userColor = CURSOR_COLORS[Math.floor(Math.random() * CURSOR_COLORS.length)];
    awareness.setLocalStateField('user', { name: userName, color: userColor });

    const updateUsers = () => {
      const users = [];
      awareness.getStates().forEach((state, clientId) => {
        if (state.user && clientId !== awareness.clientID) {
          users.push(state.user);
        }
      });
      setConnectedUsers(users);
    };
    awareness.on('change', updateUsers);

    const extensions = [
      Collaboration.configure({ document: ydoc }),
    ];

    if (CollaborationCursor) {
      extensions.push(
        CollaborationCursor.configure({
          provider,
          user: { name: userName, color: userColor },
        })
      );
    }

    return extensions;
  }, [collaborative, docId, userName]);

  // Cleanup Yjs on unmount
  useEffect(() => {
    return () => {
      providerRef.current?.destroy();
      ydocRef.current?.destroy();
    };
  }, []);

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3, 4] },
        codeBlock: { HTMLAttributes: { class: 'studio-code-block' } },
        ...(collaborative ? { history: false } : {}),  // Disable history in collab mode (Yjs handles undo)
      }),
      Underline,
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Highlight.configure({ multicolor: true }),
      Image.configure({ inline: false, allowBase64: true }),
      Table.configure({ resizable: true }),
      TableRow,
      TableCell,
      TableHeader,
      Placeholder.configure({ placeholder: 'Start writing your forensic report...' }),
      TextStyle,
      Color,
      ...collabExtensions,
    ],
    content: collaborative ? undefined : (initialContent || { type: 'doc', content: [{ type: 'paragraph' }] }),
    editable: !readOnly,
    onUpdate: ({ editor }) => {
      const text = editor.getText();
      setWordCount(text.split(/\s+/).filter(Boolean).length);
      setCharCount(text.length);

      // Debounced autosave
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => {
        const json = editor.getJSON();
        onContentChange?.(json);
        onSave?.(json);
      }, 2000);
    },
    editorProps: {
      attributes: {
        class: 'studio-editor-content',
        spellcheck: 'true',
      },
    },
  });

  // Update content when initialContent changes externally
  useEffect(() => {
    if (editor && initialContent && !editor.isFocused) {
      const currentJSON = JSON.stringify(editor.getJSON());
      const newJSON = JSON.stringify(initialContent);
      if (currentJSON !== newJSON) {
        editor.commands.setContent(initialContent);
      }
    }
  }, [initialContent, editor]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, []);

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      border: '1px solid #e2e8f0', borderRadius: 10,
      background: '#ffffff', overflow: 'hidden',
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
    }}>
      {/* Toolbar */}
      {!readOnly && <EditorToolbar editor={editor} />}

      {/* Editor Canvas */}
      <div style={{
        flex: 1, minHeight: 500, maxHeight: 'calc(100vh - 280px)',
        overflow: 'auto', padding: '40px 60px',
        background: '#ffffff',
      }}>
        <EditorContent editor={editor} />
      </div>

      {/* Status Bar */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '6px 16px', borderTop: '1px solid #e2e8f0',
        background: '#fafbfc', fontSize: 11, color: '#94a3b8',
        fontFamily: "'JetBrains Mono', monospace",
      }}>
        <span>{wordCount} words · {charCount} characters</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* Collaboration presence */}
          {collaborative && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: wsConnected ? '#059669' : '#dc2626',
                display: 'inline-block',
              }} />
              <span>{wsConnected ? 'Connected' : 'Connecting…'}</span>
              {connectedUsers.length > 0 && (
                <span style={{ color: '#475569' }}>
                  · {connectedUsers.length + 1} editors
                  {connectedUsers.map((u, i) => (
                    <span key={i} style={{
                      display: 'inline-block', width: 16, height: 16,
                      borderRadius: '50%', background: u.color || '#2563eb',
                      marginLeft: 3, verticalAlign: 'middle',
                      fontSize: 8, lineHeight: '16px', textAlign: 'center',
                      color: '#fff', fontWeight: 700,
                    }}>
                      {u.name?.[0] || '?'}
                    </span>
                  ))}
                </span>
              )}
            </div>
          )}
          <span>Report Studio v2</span>
        </div>
      </div>
    </div>
  );
}


