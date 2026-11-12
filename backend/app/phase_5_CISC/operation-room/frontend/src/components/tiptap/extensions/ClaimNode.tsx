import { Node, mergeAttributes } from '@tiptap/core'
import { ReactNodeViewRenderer, NodeViewWrapper } from '@tiptap/react'
import React, { useEffect, useRef, useState } from 'react'
import { useStudioStore, EvidenceCard } from '@operation-room/components/studio-v4/store/useStudioStore'
import { HelperPopover } from '@operation-room/components/ui/HelperPopover'

const ClaimComponent = ({ node, updateAttributes }: any) => {
  const { evidenceCards, focusMode } = useStudioStore((state) => ({ evidenceCards: state.evidenceCards, focusMode: state.focusMode }))
  const caseId = typeof window !== 'undefined' ? window.location.pathname.split('/')[2] : 'default'
  const evidenceCardIds = node.attrs.evidenceCardIds || []
  const status = node.attrs.status || 'draft'
  const text = node.attrs.text || 'Empty Claim'
  
  const connectedCards = evidenceCards.filter((c: EvidenceCard) => evidenceCardIds.includes(c.id))
  
  const bgColor = status === 'approved' ? 'bg-green-100 text-green-800 border-green-200' 
                : status === 'disputed' ? 'bg-red-100 text-red-800 border-red-200'
                : 'bg-yellow-100 text-yellow-800 border-yellow-200'

  const ref = useRef<HTMLSpanElement>(null)
  
  const [contextMenu, setContextMenu] = useState<{x: number, y: number} | null>(null)
  const [disputeMode, setDisputeMode] = useState(false)
  const [disputeReason, setDisputeReason] = useState('')

  useEffect(() => {
    if (ref.current) {
      const p = ref.current.closest('p')
      if (p) {
        // Clear previous status classes
        p.classList.remove('bg-yellow-50', 'border-yellow-400', 'bg-green-50', 'border-green-400', 'bg-red-50', 'border-red-400', '!border-l-4', 'px-2')
        
        if (status === 'draft') {
          p.classList.add('bg-yellow-50', 'border-yellow-400', '!border-l-4', 'px-2')
        } else if (status === 'approved') {
          p.classList.add('bg-green-50', 'border-green-400', '!border-l-4', 'px-2')
        } else if (status === 'disputed') {
          p.classList.add('bg-red-50', 'border-red-400', '!border-l-4', 'px-2')
        }
      }
    }
  }, [status])

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    setContextMenu({ x: e.clientX, y: e.clientY })
    setDisputeMode(false)
  }

  const updateClaimStatus = async (newStatus: string, reason?: string) => {
    try {
      const claimId = `claim-${Date.now()}` // Ideally fetched from attrs
      
      await fetch(`/api/cases/${caseId}/claims/${claimId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Role': 'LEAD_INVESTIGATOR'
        },
        body: JSON.stringify({ status: newStatus, reason: reason || undefined })
      })

      updateAttributes({ status: newStatus })
      setContextMenu(null)
      setDisputeMode(false)
      setDisputeReason('')
    } catch (err) {
      console.error("Failed to update claim status", err)
    }
  }

  // Close context menu on external clicks
  useEffect(() => {
    const handleClick = () => setContextMenu(null)
    window.addEventListener('click', handleClick)
    return () => window.removeEventListener('click', handleClick)
  }, [])

  return (
    <NodeViewWrapper className="inline-block relative">
      <span 
        ref={ref}
        onContextMenu={handleContextMenu}
        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono border cursor-pointer select-none mx-1 relative group ${bgColor} shadow-[0_0_8px_rgba(0,0,0,0.1)]`} 
        style={{ boxShadow: focusMode === 'Review' && status !== 'approved' ? (status === 'disputed' ? '0 0 20px 4px rgba(239, 68, 68, 0.8)' : '0 0 20px 4px rgba(234, 179, 8, 0.8)') : (status === 'approved' ? '0 0 10px rgba(34, 197, 94, 0.4)' : status === 'disputed' ? '0 0 10px rgba(239, 68, 68, 0.4)' : '0 0 10px rgba(234, 179, 8, 0.4)'), opacity: focusMode === 'Review' && status === 'approved' ? 0.3 : 1, filter: focusMode === 'Review' && status === 'approved' ? 'grayscale(100%)' : 'none' }}

      >
        <HelperPopover
          title={`Claim Status: ${status.toUpperCase()}`}
          description={connectedCards.length > 0 ? 'Evidence backing this claim.' : '⚠️ Unbacked Claim! (No Evidence Linked. This will block PDF exports.)'}
          icon={status === 'approved' ? 'info' : 'alert'}
          codeSnippet={connectedCards.length > 0 ? connectedCards.map((c: any) => `[${c.evidence_ref.table}] ${c.title}\nID: ${c.id}\nRowHash: ${c.evidence_ref.rowHashes?.[0]?.slice(0, 16) || 'None'}\nEvents: ${c.evidence_ref.pointers.length}`).join('\n\n') : undefined}
        >
          {text}
        </HelperPopover>
      </span>

      {/* Collaboration State Machine Context Menu */}
      {contextMenu && (
        <div 
          className="fixed z-[100] bg-slate-800 border border-slate-700 rounded shadow-xl py-1 px-1 flex flex-col gap-1 w-48 text-sm"
          style={{ top: contextMenu.y, left: contextMenu.x }}
          onClick={(e) => e.stopPropagation()} // Keep popup from closing itself
        >
          {!disputeMode ? (
            <>
              <div className="px-2 py-1 text-xs text-slate-400 font-semibold border-b border-slate-700 mb-1">Claim Actions</div>
              <button 
                onClick={() => updateClaimStatus('approved')}
                className="text-left px-2 py-1 hover:bg-slate-700 text-green-400 rounded flex w-full"
              >
                ✅ Approve Claim
              </button>
              <button 
                onClick={() => setDisputeMode(true)}
                className="text-left px-2 py-1 hover:bg-slate-700 text-red-400 rounded flex w-full"
              >
                🛑 Dispute Claim
              </button>
              <button 
                onClick={() => updateClaimStatus('draft')}
                className="text-left px-2 py-1 hover:bg-slate-700 text-yellow-400 rounded flex w-full mt-1 border-t border-slate-700 tabular-nums"
              >
                ↩ Revert to Draft
              </button>
            </>
          ) : (
            <div className="p-2">
               <div className="text-xs text-red-400 font-semibold mb-2">Dispute Reason</div>
               <textarea
                 className="w-full bg-slate-900 border border-slate-700 rounded text-slate-300 text-xs p-1 h-16 outline-none"
                 placeholder="Why is this claim incorrect?"
                 value={disputeReason}
                 onChange={(e) => setDisputeReason(e.target.value)}
                 autoFocus
               />
               <div className="flex gap-2 mt-2">
                 <button 
                   onClick={() => updateClaimStatus('disputed', disputeReason)}
                   className="bg-red-600 hover:bg-red-500 text-white text-xs px-2 py-1 rounded w-full"
                 >
                   Submit
                 </button>
                 <button 
                   onClick={() => setDisputeMode(false)}
                   className="bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs px-2 py-1 rounded"
                 >
                   Cancel
                 </button>
               </div>
            </div>
          )}
        </div>
      )}
    </NodeViewWrapper>
  )
}

export const ClaimNode = Node.create({
  name: 'claim',
  group: 'inline',
  inline: true,
  selectable: true,
  atom: true,

  addAttributes() {
    return {
      evidenceCardIds: {
        default: [],
      },
      status: {
        default: 'draft',
      },
      text: {
        default: 'Empty Claim',
      }
    }
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-claim]',
        getAttrs: (node) => {
          if (typeof node === 'string') return {}
          const evidenceCardIds = node.getAttribute('data-evidence-ids')
          return {
            evidenceCardIds: evidenceCardIds ? JSON.parse(evidenceCardIds) : [],
            status: node.getAttribute('data-status') || 'draft',
            text: node.getAttribute('data-text') || 'Empty Claim',
          }
        },
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return ['span', mergeAttributes(HTMLAttributes, { 
      'data-claim': 'true',
      'data-status': HTMLAttributes.status,
      'data-evidence-ids': JSON.stringify(HTMLAttributes.evidenceCardIds),
      'data-text': HTMLAttributes.text
    }), HTMLAttributes.text]
  },

  addNodeView() {
    return ReactNodeViewRenderer(ClaimComponent)
  },
})


