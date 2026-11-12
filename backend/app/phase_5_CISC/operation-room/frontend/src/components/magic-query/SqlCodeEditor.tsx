"use client"

import { useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from "react"
import { highlightSQL } from "./sql-utils"

const LINE_HEIGHT_PX = 20

export function SqlCodeEditor({
  value,
  onChange,
  insertField,
}: {
  value: string
  onChange: (val: string) => void
  insertField: string | null
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const highlightRef = useRef<HTMLDivElement>(null)
  const [lineCount, setLineCount] = useState(1)

  useEffect(() => {
    setLineCount(Math.max(value.split("\n").length, 1))
  }, [value])

  useEffect(() => {
    if (insertField && textareaRef.current) {
      const ta = textareaRef.current
      const start = ta.selectionStart
      const end = ta.selectionEnd
      const before = value.slice(0, start)
      const after = value.slice(end)
      onChange(before + insertField + after)
      setTimeout(() => {
        ta.focus()
        ta.selectionStart = ta.selectionEnd = start + insertField.length
      }, 10)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- insert only when parent bumps insertField
  }, [insertField])

  const handleScroll = () => {
    if (textareaRef.current && highlightRef.current) {
      highlightRef.current.scrollTop = textareaRef.current.scrollTop
      highlightRef.current.scrollLeft = textareaRef.current.scrollLeft
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Tab") {
      e.preventDefault()
      const ta = textareaRef.current!
      const start = ta.selectionStart
      const end = ta.selectionEnd
      onChange(value.slice(0, start) + "  " + value.slice(end))
      setTimeout(() => {
        ta.selectionStart = ta.selectionEnd = start + 2
      }, 0)
    }
  }

  const lineNumberStyle: CSSProperties = { lineHeight: `${LINE_HEIGHT_PX}px` }
  const editorTextStyle: CSSProperties = {
    lineHeight: `${LINE_HEIGHT_PX}px`,
    tabSize: 2,
  }

  return (
    <div className="flex w-full min-w-0 items-stretch rounded-md border border-border bg-[#0d1117] font-mono text-[13px] shadow-inner overflow-hidden">
      {/* Dedicated gutter column — code lives only in the right column (fixes clipped first characters) */}
      <div
        className="shrink-0 w-12 select-none border-r border-slate-800 bg-[#0d1117] py-3 pl-1 pr-2 text-right text-[11px] text-slate-600"
        aria-hidden
      >
        {Array.from({ length: lineCount }, (_, i) => (
          <div key={i} style={lineNumberStyle}>
            {i + 1}
          </div>
        ))}
      </div>

      <div className="relative min-h-[min(520px,75vh)] min-w-0 flex-1 max-h-[75vh]">
        <div
          ref={highlightRef}
          className="absolute inset-0 z-0 overflow-auto whitespace-pre p-3 text-[13px] text-slate-300 [scrollbar-width:thin] pointer-events-none"
          style={editorTextStyle}
          aria-hidden
          dangerouslySetInnerHTML={{ __html: highlightSQL(value) + "\n" }}
        />

        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onScroll={handleScroll}
          onKeyDown={handleKeyDown}
          spellCheck={false}
          className="relative z-[1] box-border block min-h-[min(520px,75vh)] w-full min-w-0 max-h-[75vh] resize-y overflow-auto border-0 bg-transparent p-3 font-mono text-[13px] text-transparent caret-slate-300 outline-none"
          style={{ ...editorTextStyle, WebkitTextFillColor: "transparent" }}
        />
      </div>
    </div>
  )
}
