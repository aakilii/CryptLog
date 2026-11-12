import React, { useMemo } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea
} from 'recharts'

export interface TimelineEvent {
  timestamp: string
  normalized_ts?: string
  utc_offset?: number // Extracted offset in minutes
  event_type: string
  source: string
}

export const TimelineWidget = ({ events }: { events: TimelineEvent[] }) => {
  // Phase 3: Ghost Timelines / Time Skew Mitigation
  const driftZones = useMemo(() => {
    // If UTC offset variance between adjacent chronological logs from disparate sources > 5 minutes, 
    // mark that temporal gap as an "Uncertainty Block".
    
    // Sort events chronologically to find adjacent anomalies
    const sorted = [...events].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    
    const zones: { start: string, end: string, variance: number }[] = []
    
    for (let i = 1; i < sorted.length; i++) {
        const prev = sorted[i - 1]
        const curr = sorted[i]
        
        // If sources differ and offsets are tracked
        if (prev.source !== curr.source && prev.utc_offset !== undefined && curr.utc_offset !== undefined) {
             const diff = Math.abs(prev.utc_offset - curr.utc_offset)
             if (diff > 5) {
                 zones.push({
                     start: prev.timestamp,
                     end: curr.timestamp,
                     variance: diff
                 })
             }
        }
    }
    return zones
  }, [events])

  const chartData = useMemo(() => {
     // Basic binning of events per hour
     const map: Record<string, number> = {}
     events.forEach(e => {
         const d = new Date(e.timestamp)
         // round to nearest hour
         d.setMinutes(0, 0, 0)
         const key = d.toISOString()
         map[key] = (map[key] || 0) + 1
     })
     return Object.keys(map).sort().map(k => ({
         time: k,
         formatted: new Date(k).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
         count: map[k]
     }))
  }, [events])

  return (
    <div className="w-full h-full p-4 bg-slate-900 border border-slate-700/50 rounded-lg relative overflow-hidden">
        <h3 className="text-slate-200 text-sm font-bold mb-4 font-mono">Forensic Timeline (Skews Detected: {driftZones.length})</h3>
        
        {driftZones.length > 0 && (
            <div className="absolute top-4 right-4 bg-amber-900/50 border border-amber-500/50 text-amber-500 text-[10px] px-2 py-1 rounded">
                ⚠️ Includes {driftZones.length} Uncertainty Block(s)
            </div>
        )}

        <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
               <AreaChart data={chartData}>
                  <defs>
                     <linearGradient id="eventColor" x1="0" y1="0" x2="0" y2="1">
                         <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.5} />
                         <stop offset="95%" stopColor="#38bdf8" stopOpacity={0} />
                     </linearGradient>
                  </defs>
                  <XAxis dataKey="formatted" stroke="#64748b" fontSize={10} tickMargin={8} />
                  <YAxis stroke="#64748b" fontSize={10} />
                  <CartesianGrid stroke="#334155" strokeDasharray="3 3" opacity={0.5} />
                  <Tooltip 
                     contentStyle={{ backgroundColor: '#1e293b', borderColor: '#475569', color: '#f8fafc' }}
                     itemStyle={{ color: '#38bdf8' }}
                  />
                  
                  {/* Render the Ghost Timelines (Uncertainty Blocks) dynamically */}
                  {driftZones.map((zone, idx) => (
                      <ReferenceArea 
                         key={idx} 
                         x1={new Date(zone.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} 
                         x2={new Date(zone.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} 
                         fill="url(#uncertaintyGradient)" 
                         strokeOpacity={0.3} 
                         fillOpacity={0.8}
                         stroke="#f59e0b"
                         strokeDasharray="3 3"
                         ifOverflow="extendDomain"
                      />
                  ))}

                  <defs>
                      <linearGradient id="uncertaintyGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#94a3b8" stopOpacity={0.4} />
                          <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.1} />
                      </linearGradient>
                  </defs>

                  <Area type="monotone" dataKey="count" stroke="#38bdf8" strokeWidth={2} fill="url(#eventColor)" />
               </AreaChart>
            </ResponsiveContainer>
        </div>
    </div>
  )
}