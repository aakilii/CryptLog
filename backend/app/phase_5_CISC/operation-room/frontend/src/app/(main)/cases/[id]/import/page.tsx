'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import { MagicQueryPage } from '@operation-room/components/magic-query/MagicQueryPage'

export default function CaseMagicQueryPage() {
  const params = useParams()
  const id = params?.id as string

  return (
    <>
      <div className="page-header animate-in">
        <div>
          <h1>Magic Query</h1>
          <p className="text-muted-foreground" style={{ fontSize: 13 }}>
            NL → SQL → committed logs (audit from main app: <code className="hash-value">csic_active_audit_id</code>)
          </p>
        </div>
        <Link href={`/cases/${id}`} className="btn btn-ghost">
          <ArrowLeft size={14} />
          Back to Case
        </Link>
      </div>

      <div
        className="glass-card-static animate-in animate-in-delay-1"
        style={{ padding: 0, overflow: 'hidden', minHeight: '70vh' }}
      >
        <MagicQueryPage embedded caseId={id} />
      </div>
    </>
  )
}
