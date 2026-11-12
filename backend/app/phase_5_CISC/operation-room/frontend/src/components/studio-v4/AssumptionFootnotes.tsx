import React from 'react'

export const AssumptionFootnotes = ({ elements }: { elements: any[] }) => {
  // Scan all elements and find correlation widgets containing edges with confidence_score < 0.5
  const lowConfidenceEdges: any[] = []
  
  elements.forEach((item) => {
    const el = item.el
    if (el.data?.type === 'correlation-graph' || el.data?.data?.edges) {
      const edges = el.data?.data?.edges || []
      edges.forEach((edge: any) => {
        if (edge.confidence_score !== undefined && edge.confidence_score < 0.5) {
          lowConfidenceEdges.push({
            sourceLabel: edge.source_label || edge.source,
            targetLabel: edge.target_label || edge.target,
            reason: edge.join_reason || 'Temporal proximity or heuristic match',
            confidence: edge.confidence_score
          })
        }
      })
    }
  })

  // Deduplicate
  const uniqueEdges = lowConfidenceEdges.filter((v, i, a) => a.findIndex(t => (t.sourceLabel === v.sourceLabel && t.targetLabel === v.targetLabel)) === i)

  if (uniqueEdges.length === 0) return null

  return (
    <div className="mt-16">
      <h2 className="text-xl font-bold mb-2 text-amber-700 flex items-center gap-2">
        <span>⚠️</span> Assumption Footnotes: Heuristic Inferences
      </h2>
      <p className="text-sm text-slate-500 mb-8 border-b pb-4">
        The chart(s) generated above utilise machine-learning heuristics which are mathematically probable, but not cryptographically deterministic. Adhere to institutional guidelines before executing responses based solely on these temporal or probability-based edges.
      </p>
      
      <table className="w-full text-sm text-left border-collapse border border-slate-200">
        <thead className="bg-amber-50 text-amber-900 uppercase text-[10px] tracking-wider">
          <tr>
            <th className="px-4 py-3 border border-slate-200 font-medium">Source Node</th>
            <th className="px-4 py-3 border border-slate-200 font-medium">Target Node</th>
            <th className="px-4 py-3 border border-slate-200 font-medium">Confidence</th>
            <th className="px-4 py-3 border border-slate-200 font-medium">Inference Reason</th>
          </tr>
        </thead>
        <tbody>
          {uniqueEdges.map((edge, i) => (
            <tr key={i} className="border-b border-slate-200 bg-amber-50/10 hover:bg-amber-50/50">
              <td className="px-4 py-3 text-slate-700 font-semibold">{edge.sourceLabel}</td>
              <td className="px-4 py-3 text-slate-700 font-semibold">{edge.targetLabel}</td>
              <td className="px-4 py-3 font-mono text-[10px] text-amber-600">{(edge.confidence * 100).toFixed(1)}%</td>
              <td className="px-4 py-3 text-xs text-slate-600">{edge.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}