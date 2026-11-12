'use client'

import React, { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useStudioStore, CanvasElement } from './store/useStudioStore'
import { Button } from '@operation-room/components/ui/button'
import { CheckCircle, XCircle, ShieldAlert } from 'lucide-react'

// Helper to recurse TipTap JSON AST to find claims
function findClaimsInNode(node: any, results: any[] = []) {
  if (node.type === 'claim') {
    results.push(node)
  }
  if (node.content && Array.isArray(node.content)) {
    node.content.forEach((child: any) => findClaimsInNode(child, results))
  }
  return results
}

export function ClaimReviewDrawer({ caseId }: { caseId: string }) {
  const pages = useStudioStore(state => state.pages)
  const updateElement = useStudioStore(state => state.updateElement)
  const [isAdminMode, setIsAdminMode] = useState(false)
  
  // Parse active AST
  const activeClaims = useMemo(() => {
    const claimsFound: { elementId: string; pageIndex: number; claimNode: any; text: string; status: string }[] = []
    
    pages.forEach((page, pageIndex) => {
      page.elements.forEach(el => {
        if (el.type === 'text' && el.config?.content) {
          const doc = typeof el.config.content === 'string' ? JSON.parse(el.config.content) : el.config.content
          const claims = findClaimsInNode(doc)
          
          claims.forEach(c => {
            claimsFound.push({
              elementId: el.id,
              pageIndex,
              claimNode: c,
              text: c.attrs?.text || 'Empty Claim',
              status: c.attrs?.status || 'draft'
            })
          })
        }
      })
    })
    
    return claimsFound
  }, [pages])

  const draftCount = activeClaims.filter(c => c.status === 'draft').length
  
  const handleApproveAll = async () => {
    // Attempt backend sync first to enforce RBAC
    try {
      const res = await fetch(`/api/cases/${caseId}/claims/approve-all`, {
        method: 'PATCH',
        headers: { 
          'Content-Type': 'application/json',
          'X-User-Role': isAdminMode ? 'LEAD_INVESTIGATOR' : 'JUNIOR_ANALYST'
        }
      })

      if (!res.ok) {
        if (res.status === 403) {
            alert('Access Denied: Only users with LEAD_INVESTIGATOR role can approve claims.')
            return
        }
        throw new Error('Failed to approve claims')
      }
      
      // Update local AST state if backend passes
      pages.forEach((page, pageIndex) => {
        page.elements.forEach(el => {
          if (el.type === 'text' && el.config?.content) {
            const doc = typeof el.config.content === 'string' ? JSON.parse(el.config.content) : JSON.parse(JSON.stringify(el.config.content))
            
            let modified = false
            // Local mutator
            const approveClaims = (node: any) => {
              if (node.type === 'claim' && node.attrs?.status === 'draft') {
                node.attrs.status = 'approved'
                modified = true
              }
              if (node.content && Array.isArray(node.content)) {
                  node.content.forEach((child: any) => approveClaims(child))
              }
            }
            
            approveClaims(doc)
            if (modified) {
               updateElement(pageIndex, el.id, { config: { ...el.config, content: doc } })
            }
          }
        })
      })
    } catch (e: any) {
        console.error(e)
        alert('Approvals failed.')
    }
  }

  const handleApproveSingle = async (pageIndex: number, elementId: string, nodeAST: any) => {
      // In a real app we would PATCH individual claim via /api/cases/{caseId}/claims/{claimId} 
      // but here we are doing a simpler RBAC test
      try {
        const claimId = nodeAST.attrs?.claimId || 'unknown'
        const res = await fetch(`/api/cases/${caseId}/claims/${claimId}`, {
          method: 'PATCH',
          headers: { 
            'Content-Type': 'application/json',
            'X-User-Role': isAdminMode ? 'LEAD_INVESTIGATOR' : 'JUNIOR_ANALYST'  
          }
        })
  
        if (!res.ok) {
          if (res.status === 403) {
              alert('Access Denied: Only LEAD_INVESTIGATOR can approve claims.')
              return
          }
          throw new Error('Failed to approve claim')
        }
        
        const page = pages[pageIndex]
        const el = page?.elements.find(e => e.id === elementId)
        if (el && el.config?.content) {
            const doc = typeof el.config.content === 'string' ? JSON.parse(el.config.content) : JSON.parse(JSON.stringify(el.config.content))
            const approveClaimRecurse = (node: any) => {
              // strict equality won't work on parsed JSON, but checking text and ids usually matches
              if (node.type === 'claim' && node.attrs?.text === nodeAST.attrs?.text) {
                node.attrs.status = 'approved'
              }
              if (node.content && Array.isArray(node.content)) {
                  node.content.forEach((child: any) => approveClaimRecurse(child))
              }
            }
            
            approveClaimRecurse(doc)
            updateElement(pageIndex, el.id, { config: { ...el.config, content: doc } })
        }
      } catch (e) {
          console.error(e)
          alert('Approval failed.')
      }
  }

  if (activeClaims.length === 0) return null

  return (
    <motion.div
      initial={{ x: 300, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 300, opacity: 0 }}
      className="absolute right-0 top-12 bottom-0 w-80 bg-background border-l shadow-xl flex flex-col z-40"
    >
      <div className="p-4 border-b bg-muted/30">
        <div className="flex items-center justify-between">
            <h2 className="font-semibold text-sm">Review & Approval Cockpit</h2>
            <Button
              variant={isAdminMode ? "default" : "outline"}
              size="sm"
              className={isAdminMode ? "bg-indigo-600 hover:bg-indigo-700 text-[10px] h-6 px-2" : "text-[10px] h-6 px-2"}
              onClick={() => setIsAdminMode(!isAdminMode)}
            >
              <ShieldAlert className="w-3 h-3 mr-1" />
              {isAdminMode ? 'Lead Auth Active' : 'Sudo Mode'}
            </Button>
        </div>
        <div className="flex items-center justify-between mt-2">
            <span className="text-xs text-muted-foreground">{draftCount} Claims pending review</span>
            {draftCount > 0 && (
                <Button size="sm" onClick={handleApproveAll} className="bg-green-600 hover:bg-green-700 text-white shadow-sm shadow-green-900/20 text-xs py-1 h-7">
                    <CheckCircle className="w-3 h-3 mr-1" />
                    Approve All
                </Button>
            )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {activeClaims.map((c, i) => (
            <div key={i} className={`p-3 rounded-md border text-sm ${c.status === 'approved' ? 'bg-green-50/50 border-green-200' : 'bg-yellow-50/50 border-yellow-200'}`}>
                <div className="font-medium mb-1 line-clamp-2">"{c.text}"</div>
                <div className="flex items-center justify-between mt-3">
                    <span className={`text-[10px] uppercase font-bold tracking-wider ${c.status === 'approved' ? 'text-green-600' : 'text-yellow-600'}`}>
                        {c.status}
                    </span>
                    {c.status === 'draft' && (
                        <div className="flex items-center gap-1">
                            <Button size="icon" variant="ghost" onClick={() => handleApproveSingle(c.pageIndex, c.elementId, c.claimNode)} className="h-6 w-6 text-green-600 hover:bg-green-100 hover:text-green-700">
                                <CheckCircle className="w-4 h-4" />
                            </Button>
                            <Button size="icon" variant="ghost" className="h-6 w-6 text-red-600 hover:bg-red-100 hover:text-red-700">
                                <XCircle className="w-4 h-4" />
                            </Button>
                        </div>
                    )}
                </div>
            </div>
        ))}
      </div>
    </motion.div>
  )
}