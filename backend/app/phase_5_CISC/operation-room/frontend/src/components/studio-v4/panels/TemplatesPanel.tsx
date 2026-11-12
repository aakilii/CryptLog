'use client'

import React, { useEffect, useMemo, useState } from 'react'
import {
  FileText,
  FileCode,
  LayoutTemplate,
  Shield,
  Activity,
  Server,
  Terminal,
  Search,
  CheckCircle2,
  ChevronRight
} from 'lucide-react'
import { PanelContent } from '../ExpandablePanel'
import { Input } from '@operation-room/components/ui/input'
import { Button } from '@operation-room/components/ui/button'
import { Badge } from '@operation-room/components/ui/badge'
import { api } from '@operation-room/lib/api'

// Template Categories
const TEMPLATE_CATEGORIES = [
  { id: 'all', label: 'All' },
  { id: 'ir', label: 'Incident Response' },
  { id: 'malware', label: 'Malware Analysis' },
  { id: 'network', label: 'Network Forensic' },
  { id: 'insider', label: 'Insider Threat' }
]

type TemplateItem = {
  id: string
  name: string
  description?: string
  category?: string
  color?: string
  required_modules?: string[]
}

interface TemplatesPanelProps {
  caseId: string
  onApplyTemplate?: (templateId: string) => void
}

export const TemplatesPanel = ({ caseId, onApplyTemplate }: TemplatesPanelProps) => {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCategory, setActiveCategory] = useState('all')
  const [templates, setTemplates] = useState<TemplateItem[]>([])

  useEffect(() => {
    api.get(`/v4/studio/cases/${caseId}/templates`)
      .then((data) => setTemplates((data?.templates || []) as TemplateItem[]))
      .catch((err) => {
        console.error('Failed to load templates', err)
        setTemplates([])
      })
  }, [caseId])

  const filteredTemplates = useMemo(() => templates.filter((tpl) => {
    const matchesSearch = tpl.name.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          (tpl.description || '').toLowerCase().includes(searchQuery.toLowerCase())
    const matchesCategory = activeCategory === 'all' || (tpl.category || 'ir') === activeCategory
    return matchesSearch && matchesCategory
  }), [templates, searchQuery, activeCategory])

  const iconForCategory = (category?: string) => {
    switch (category) {
      case 'ir':
        return Shield
      case 'malware':
        return FileCode
      case 'network':
        return Server
      case 'insider':
        return Terminal
      default:
        return Activity
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="p-4 border-b">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search templates..."
            className="pl-9 bg-muted/50 border-none font-ui text-sm h-9"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        
        <div className="flex items-center gap-1 mt-3 overflow-x-auto pb-1 scrollbar-none">
          {TEMPLATE_CATEGORIES.map((cat) => (
            <Badge
              key={cat.id}
              variant={activeCategory === cat.id ? 'default' : 'secondary'}
              className="cursor-pointer whitespace-nowrap"
              onClick={() => setActiveCategory(cat.id)}
            >
              {cat.label}
            </Badge>
          ))}
        </div>
      </div>

      <PanelContent className="p-4">
        <div className="space-y-3">
          {filteredTemplates.length > 0 ? (
            filteredTemplates.map((tpl) => (
              <div
                key={tpl.id}
                className="group flex gap-3 p-3 rounded-lg border bg-card hover:border-primary/50 hover:shadow-md transition-all cursor-pointer"
                onClick={() => onApplyTemplate?.(tpl.id)}
              >
                <div 
                  className="mt-1 flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-md bg-opacity-10"
                  style={{ backgroundColor: `${tpl.color}15`, color: tpl.color }}
                >
                  {React.createElement(iconForCategory(tpl.category), { className: 'w-5 h-5' })}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between">
                    <h4 className="font-geist text-sm font-semibold truncate pb-1">{tpl.name}</h4>
                    <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity">
                      <ChevronRight className="h-4 w-4 text-primary" />
                    </Button>
                  </div>
                  <p className="font-ui text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                    {tpl.description}
                  </p>
                  <div className="flex items-center gap-1.5 mt-2">
                    {(tpl.required_modules || []).slice(0, 3).map((tag, i) => (
                      <span key={i} className="text-[9px] uppercase tracking-wider font-semibold text-slate-500 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="flex flex-col items-center justify-center py-10 text-center text-muted-foreground">
              <LayoutTemplate className="h-8 w-8 mb-3 opacity-20" />
              <p className="text-sm">No templates match your search.</p>
            </div>
          )}
        </div>
      </PanelContent>
    </div>
  )
}
