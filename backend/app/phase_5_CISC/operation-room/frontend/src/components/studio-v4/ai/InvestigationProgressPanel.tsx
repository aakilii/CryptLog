'use client';

/**
 * Investigation Progress Panel
 * 
 * Real-time visualization of an ongoing investigation.
 * Shows:
 * - Current phase and progress
 * - Hypotheses with verdicts
 * - Findings as they stream in
 * - Confidence scores
 * - Module execution status
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Badge } from '@operation-room/components/ui/badge';
import { Progress } from '@operation-room/components/ui/progress';
import { ScrollArea } from '@operation-room/components/ui/scroll-area';
import { Separator } from '@operation-room/components/ui/separator';
import { Button } from '@operation-room/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@operation-room/components/ui/collapsible';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@operation-room/components/ui/tooltip';
import {
  Play,
  Pause,
  Square,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  ChevronDown,
  ChevronRight,
  Brain,
  Loader2,
  Activity,
  Shield,
  FileText,
  Sparkles,
  TrendingUp,
  Target,
} from 'lucide-react';

// Types
interface Hypothesis {
  id: string;
  statement: string;
  type?: string;
  verdict?: 'CONFIRMED' | 'LIKELY' | 'INCONCLUSIVE' | 'UNLIKELY' | 'DISCONFIRMED' | 'PENDING';
  confidence?: number;
}

interface Finding {
  id: string;
  type: string;
  tool_id?: string;
  title?: string;
  description?: string;
  severity?: 'critical' | 'high' | 'medium' | 'low' | 'info';
  timestamp: string;
}

interface ModuleStatus {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'complete' | 'error';
  findingsCount?: number;
  duration?: number;
}

interface InvestigationProgressProps {
  investigationId?: string;
  phase: string;
  progress: number;
  hypotheses: Hypothesis[];
  findings: Finding[];
  moduleStatuses: ModuleStatus[];
  overallConfidence?: number;
  isRunning: boolean;
  onStop?: () => void;
  onPause?: () => void;
  onResume?: () => void;
}

// Phase display configuration
const PHASES = [
  { id: 'intake', label: 'Intake', icon: FileText },
  { id: 'hypothesis_generation', label: 'Hypotheses', icon: Brain },
  { id: 'planning', label: 'Planning', icon: Target },
  { id: 'execution', label: 'Execution', icon: Activity },
  { id: 'hypothesis_testing', label: 'Testing', icon: Sparkles },
  { id: 'confidence_scoring', label: 'Confidence', icon: Shield },
  { id: 'reporting', label: 'Reporting', icon: FileText },
  { id: 'complete', label: 'Complete', icon: CheckCircle2 },
];

// Verdict styling
const VERDICT_STYLES: Record<string, { bg: string; text: string; icon: typeof CheckCircle2 }> = {
  CONFIRMED: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', icon: CheckCircle2 },
  LIKELY: { bg: 'bg-blue-500/20', text: 'text-blue-400', icon: TrendingUp },
  INCONCLUSIVE: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', icon: AlertTriangle },
  UNLIKELY: { bg: 'bg-orange-500/20', text: 'text-orange-400', icon: AlertTriangle },
  DISCONFIRMED: { bg: 'bg-red-500/20', text: 'text-red-400', icon: XCircle },
  PENDING: { bg: 'bg-slate-500/20', text: 'text-slate-400', icon: Clock },
};

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  info: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

export function InvestigationProgressPanel({
  investigationId,
  phase,
  progress,
  hypotheses,
  findings,
  moduleStatuses,
  overallConfidence = 0,
  isRunning,
  onStop,
  onPause,
  onResume,
}: InvestigationProgressProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['hypotheses', 'findings'])
  );
  const findingsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to new findings
  useEffect(() => {
    if (findings.length > 0) {
      findingsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [findings.length]);

  const toggleSection = useCallback((section: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  }, []);

  // Current phase index
  const currentPhaseIndex = PHASES.findIndex(p => p.id === phase);

  return (
    <div className="h-full flex flex-col bg-slate-900 text-white">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-700 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-emerald-400" />
            <span className="font-semibold">Investigation</span>
            {investigationId && (
              <Badge variant="outline" className="text-xs font-mono">
                {investigationId.slice(0, 12)}
              </Badge>
            )}
          </div>
          
          {/* Controls */}
          <div className="flex items-center gap-1">
            {isRunning && onPause && (
              <Button size="icon" variant="ghost" onClick={onPause}>
                <Pause className="h-4 w-4" />
              </Button>
            )}
            {!isRunning && onResume && (
              <Button size="icon" variant="ghost" onClick={onResume}>
                <Play className="h-4 w-4" />
              </Button>
            )}
            {onStop && (
              <Button size="icon" variant="ghost" onClick={onStop} className="text-red-400 hover:text-red-300">
                <Square className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        {/* Progress */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-400">Progress</span>
            <span className="font-mono">{progress.toFixed(0)}%</span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        {/* Phase indicators */}
        <div className="flex items-center gap-1 overflow-x-auto pb-1">
          {PHASES.map((p, idx) => {
            const Icon = p.icon;
            const isActive = p.id === phase;
            const isComplete = idx < currentPhaseIndex;
            
            return (
              <TooltipProvider key={p.id}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div
                      className={`flex items-center justify-center w-8 h-8 rounded-full shrink-0 transition-all ${
                        isActive
                          ? 'bg-emerald-500/30 text-emerald-400 ring-2 ring-emerald-500/50'
                          : isComplete
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : 'bg-slate-700/50 text-slate-500'
                      }`}
                    >
                      {isComplete ? (
                        <CheckCircle2 className="h-4 w-4" />
                      ) : isActive && isRunning ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Icon className="h-4 w-4" />
                      )}
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{p.label}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-4">
          {/* Overall Confidence */}
          {overallConfidence > 0 && (
            <div className="p-3 rounded-lg bg-slate-800/50 border border-slate-700">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-slate-400">Overall Confidence</span>
                <Badge
                  variant="outline"
                  className={
                    overallConfidence >= 0.75
                      ? 'border-emerald-500/50 text-emerald-400'
                      : overallConfidence >= 0.5
                      ? 'border-yellow-500/50 text-yellow-400'
                      : 'border-red-500/50 text-red-400'
                  }
                >
                  {(overallConfidence * 100).toFixed(0)}%
                </Badge>
              </div>
              <Progress value={overallConfidence * 100} className="h-2" />
            </div>
          )}

          {/* Hypotheses Section */}
          <Collapsible
            open={expandedSections.has('hypotheses')}
            onOpenChange={() => toggleSection('hypotheses')}
          >
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-between p-2 hover:bg-slate-800"
              >
                <span className="flex items-center gap-2">
                  <Brain className="h-4 w-4 text-purple-400" />
                  Hypotheses
                  <Badge variant="secondary" className="text-xs">
                    {hypotheses.length}
                  </Badge>
                </span>
                {expandedSections.has('hypotheses') ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-2 pt-2">
              {hypotheses.length === 0 ? (
                <p className="text-sm text-slate-500 px-2">No hypotheses yet</p>
              ) : (
                hypotheses.map((hyp) => {
                  const verdictStyle = VERDICT_STYLES[hyp.verdict || 'PENDING'];
                  const VerdictIcon = verdictStyle.icon;
                  
                  return (
                    <div
                      key={hyp.id}
                      className={`p-3 rounded-lg border ${verdictStyle.bg} border-opacity-30`}
                    >
                      <div className="flex items-start gap-2">
                        <VerdictIcon className={`h-4 w-4 mt-0.5 shrink-0 ${verdictStyle.text}`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs text-slate-500">{hyp.id}</span>
                            {hyp.verdict && (
                              <Badge variant="outline" className={`text-xs ${verdictStyle.text}`}>
                                {hyp.verdict}
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm text-slate-300 mt-1">{hyp.statement}</p>
                          {hyp.confidence !== undefined && (
                            <div className="mt-2 flex items-center gap-2">
                              <Progress value={hyp.confidence * 100} className="h-1 flex-1" />
                              <span className="text-xs text-slate-500">
                                {(hyp.confidence * 100).toFixed(0)}%
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </CollapsibleContent>
          </Collapsible>

          <Separator className="bg-slate-700" />

          {/* Module Status */}
          <Collapsible
            open={expandedSections.has('modules')}
            onOpenChange={() => toggleSection('modules')}
          >
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-between p-2 hover:bg-slate-800"
              >
                <span className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-blue-400" />
                  Modules
                  <Badge variant="secondary" className="text-xs">
                    {moduleStatuses.filter(m => m.status === 'complete').length}/{moduleStatuses.length}
                  </Badge>
                </span>
                {expandedSections.has('modules') ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-2 pt-2">
              {moduleStatuses.map((mod) => (
                <div
                  key={mod.id}
                  className="flex items-center justify-between p-2 rounded bg-slate-800/50"
                >
                  <div className="flex items-center gap-2">
                    {mod.status === 'running' ? (
                      <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
                    ) : mod.status === 'complete' ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    ) : mod.status === 'error' ? (
                      <XCircle className="h-4 w-4 text-red-400" />
                    ) : (
                      <Clock className="h-4 w-4 text-slate-500" />
                    )}
                    <span className="text-sm">{mod.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {mod.findingsCount !== undefined && (
                      <Badge variant="outline" className="text-xs">
                        {mod.findingsCount} findings
                      </Badge>
                    )}
                    {mod.duration !== undefined && (
                      <span className="text-xs text-slate-500">
                        {(mod.duration / 1000).toFixed(1)}s
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </CollapsibleContent>
          </Collapsible>

          <Separator className="bg-slate-700" />

          {/* Findings Section */}
          <Collapsible
            open={expandedSections.has('findings')}
            onOpenChange={() => toggleSection('findings')}
          >
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="w-full justify-between p-2 hover:bg-slate-800"
              >
                <span className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-amber-400" />
                  Findings
                  <Badge variant="secondary" className="text-xs">
                    {findings.length}
                  </Badge>
                </span>
                {expandedSections.has('findings') ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-2 pt-2">
              {findings.length === 0 ? (
                <p className="text-sm text-slate-500 px-2">No findings yet</p>
              ) : (
                <>
                  {findings.slice(-20).map((finding, idx) => (
                    <div
                      key={finding.id || idx}
                      className={`p-2 rounded border ${
                        SEVERITY_STYLES[finding.severity || 'info']
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            {finding.tool_id && (
                              <Badge variant="outline" className="text-xs">
                                {finding.tool_id}
                              </Badge>
                            )}
                            {finding.severity && (
                              <Badge
                                variant="outline"
                                className={`text-xs ${SEVERITY_STYLES[finding.severity]}`}
                              >
                                {finding.severity}
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm mt-1">
                            {finding.title || finding.description || finding.type}
                          </p>
                        </div>
                        <span className="text-xs text-slate-500 shrink-0">
                          {new Date(finding.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  ))}
                  <div ref={findingsEndRef} />
                </>
              )}
            </CollapsibleContent>
          </Collapsible>
        </div>
      </ScrollArea>
    </div>
  );
}

export default InvestigationProgressPanel;
