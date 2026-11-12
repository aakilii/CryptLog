'use client';

/**
 * Investigation Config Dialog
 * 
 * A popup dialog that allows users to configure and start an investigation.
 * This is the entry point for the automated report generation flow.
 * 
 * Features:
 * - Scenario input (text area)
 * - LLM provider selection (Ollama/Gemini)
 * - Investigation options (traversal strategy, auto-answer timeout)
 * - Module selection (which tools to run)
 * - Start button that initiates SSE stream
 */

import React, { useState, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@operation-room/components/ui/dialog';
import { Button } from '@operation-room/components/ui/button';
import { Textarea } from '@operation-room/components/ui/textarea';
import { Label } from '@operation-room/components/ui/label';
import { Switch } from '@operation-room/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@operation-room/components/ui/select';
import { Slider } from '@operation-room/components/ui/slider';
import { Badge } from '@operation-room/components/ui/badge';
import { Progress } from '@operation-room/components/ui/progress';
import { Separator } from '@operation-room/components/ui/separator';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@operation-room/components/ui/collapsible';
import {
  Play,
  Settings,
  ChevronDown,
  Brain,
  Clock,
  Layers,
  Zap,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Network,
  Activity,
  Database,
  Shield,
  FileSearch,
  GitBranch,
} from 'lucide-react';

// Module configuration
const MODULES = [
  { id: 'timeline', name: 'Timeline', icon: Clock, description: 'Build unified event timeline' },
  { id: 'anomaly', name: 'Anomaly', icon: Activity, description: 'Detect statistical anomalies' },
  { id: 'correlation', name: 'Correlation', icon: Network, description: 'Entity relationship mapping' },
  { id: 'network', name: 'Network', icon: GitBranch, description: 'Network flow analysis' },
  { id: 'crud', name: 'CRUD', icon: Database, description: 'Data access patterns' },
  { id: 'depth', name: 'Impact', icon: Shield, description: 'Blast radius assessment' },
  { id: 'vault', name: 'Evidence', icon: FileSearch, description: 'Evidence vault integration' },
];

interface InvestigationConfigProps {
  caseId: string;
  onStart: (config: InvestigationConfig) => void;
  isRunning?: boolean;
  progress?: number;
  currentPhase?: string;
  trigger?: React.ReactNode;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export interface InvestigationConfig {
  caseId: string;
  scenario: string;
  objectives: string[];
  modules: string[];
  hypotheses: string[];
  options: {
    llmProvider: 'ollama' | 'gemini';
    ollamaModel?: string;
    traversalStrategy: 'bfs' | 'dfs' | 'bfs_then_dfs';
    autoAnswerTimeout: number;
    enabledModules: string[];
    generateHypotheses: boolean;
    computeConfidence: boolean;
    generateReport: boolean;
  };
}

export function InvestigationConfigDialog({
  caseId,
  onStart,
  isRunning = false,
  progress = 0,
  currentPhase = 'idle',
  trigger,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: InvestigationConfigProps) {
  const [internalOpen, setInternalOpen] = useState(false);
  
  // Use controlled or internal state
  const open = controlledOpen !== undefined ? controlledOpen : internalOpen;
  const setOpen = controlledOnOpenChange || setInternalOpen;
  
  const [scenario, setScenario] = useState('');
  const [objectives, setObjectives] = useState<string[]>([]);
  const [hypotheses, setHypotheses] = useState<string[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Options state
  const [llmProvider, setLlmProvider] = useState<'ollama' | 'gemini'>('gemini');
  const [ollamaModel, setOllamaModel] = useState('qwen3:8b');
  const [traversalStrategy, setTraversalStrategy] = useState<'bfs' | 'dfs' | 'bfs_then_dfs'>('bfs_then_dfs');
  const [autoAnswerTimeout, setAutoAnswerTimeout] = useState(60);
  const [enabledModules, setEnabledModules] = useState<string[]>(MODULES.map(m => m.id));
  const [generateHypotheses, setGenerateHypotheses] = useState(true);
  const [computeConfidence, setComputeConfidence] = useState(true);
  const [generateReport, setGenerateReport] = useState(true);

  // Toggle module
  const toggleModule = useCallback((moduleId: string) => {
    setEnabledModules(prev => 
      prev.includes(moduleId) 
        ? prev.filter(id => id !== moduleId)
        : [...prev, moduleId]
    );
  }, []);

  // Handle start
  const handleStart = useCallback(() => {
    const config: InvestigationConfig = {
      caseId,
      scenario,
      objectives,
      modules: enabledModules,
      hypotheses,
      options: {
        llmProvider,
        ollamaModel: llmProvider === 'ollama' ? ollamaModel : undefined,
        traversalStrategy,
        autoAnswerTimeout,
        enabledModules,
        generateHypotheses,
        computeConfidence,
        generateReport,
      },
    };

    onStart(config);
    setOpen(false);
  }, [
    caseId,
    scenario,
    objectives,
    hypotheses,
    llmProvider,
    ollamaModel,
    traversalStrategy,
    autoAnswerTimeout,
    enabledModules,
    generateHypotheses,
    computeConfidence,
    generateReport,
    onStart,
    setOpen,
  ]);

  const canStart = scenario.trim().length > 10 && enabledModules.length > 0;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {trigger || (
          <Button
            variant="default"
            size="lg"
            className="gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700"
          >
            <Zap className="h-5 w-5" />
            Start Investigation
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-emerald-500" />
            Configure Investigation
          </DialogTitle>
          <DialogDescription>
            Describe your investigation scenario and configure the AI-powered analysis.
          </DialogDescription>
        </DialogHeader>

        {/* Running indicator */}
        {isRunning && (
          <div className="bg-emerald-900/20 border border-emerald-500/30 rounded-lg p-4 space-y-2">
            <div className="flex items-center gap-2 text-emerald-400">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="font-medium">Investigation in progress...</span>
            </div>
            <Progress value={progress} className="h-2" />
            <div className="flex justify-between text-xs text-slate-400">
              <span>Phase: {currentPhase}</span>
              <span>{progress.toFixed(0)}%</span>
            </div>
          </div>
        )}

        <div className="space-y-6">
          {/* Scenario Input */}
          <div className="space-y-2">
            <Label htmlFor="scenario" className="flex items-center gap-2">
              Investigation Scenario
              <Badge variant="secondary" className="text-xs">Required</Badge>
            </Label>
            <Textarea
              id="scenario"
              placeholder="Describe the investigation scenario in detail. For example:

A computer (Windows) and a mobile phone (Android) have been seized. The computer was used by the suspect but owned by the organization. The mobile phone was owned by the suspect involved in transferring confidential files from the office computer to his mobile phone through various channels like USB, Bluetooth and email. Create timeline of file transfers with IP addresses."
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              className="min-h-[120px] resize-none"
              disabled={isRunning}
            />
            <p className="text-xs text-slate-500">
              {scenario.length} characters • Minimum 10 required
            </p>
          </div>

          {/* LLM Provider Selection */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>LLM Provider</Label>
              <Select
                value={llmProvider}
                onValueChange={(v) => setLlmProvider(v as 'ollama' | 'gemini')}
                disabled={isRunning}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gemini">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-gradient-to-r from-blue-500 to-purple-500" />
                      Gemini API
                    </div>
                  </SelectItem>
                  <SelectItem value="ollama">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-gradient-to-r from-orange-500 to-red-500" />
                      Ollama (Local)
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            {llmProvider === 'ollama' && (
              <div className="space-y-2">
                <Label>Ollama Model</Label>
                <Select
                  value={ollamaModel}
                  onValueChange={setOllamaModel}
                  disabled={isRunning}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="qwen3:8b">Qwen3 8B</SelectItem>
                    <SelectItem value="qwen3:32b">Qwen3 32B</SelectItem>
                    <SelectItem value="llama3:8b">Llama 3 8B</SelectItem>
                    <SelectItem value="mistral:7b">Mistral 7B</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>

          {/* Module Selection */}
          <div className="space-y-3">
            <Label className="flex items-center justify-between">
              <span>Analysis Modules</span>
              <span className="text-xs text-slate-500">
                {enabledModules.length} of {MODULES.length} selected
              </span>
            </Label>
            <div className="grid grid-cols-2 gap-2">
              {MODULES.map((module) => {
                const Icon = module.icon;
                const isEnabled = enabledModules.includes(module.id);
                
                return (
                  <button
                    key={module.id}
                    onClick={() => toggleModule(module.id)}
                    disabled={isRunning}
                    className={`flex items-center gap-3 p-3 rounded-lg border text-left transition-all ${
                      isEnabled
                        ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-400'
                        : 'border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-600'
                    } ${isRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <Icon className="h-4 w-4" />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm">{module.name}</div>
                      <div className="text-xs text-slate-500 truncate">{module.description}</div>
                    </div>
                    {isEnabled && <CheckCircle2 className="h-4 w-4 shrink-0" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Advanced Options */}
          <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" className="w-full justify-between">
                <span className="flex items-center gap-2">
                  <Settings className="h-4 w-4" />
                  Advanced Options
                </span>
                <ChevronDown className={`h-4 w-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-4 pt-4">
              <Separator />

              {/* Traversal Strategy */}
              <div className="space-y-2">
                <Label>Traversal Strategy</Label>
                <Select
                  value={traversalStrategy}
                  onValueChange={(v) => setTraversalStrategy(v as typeof traversalStrategy)}
                  disabled={isRunning}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="bfs">BFS (Breadth-First) - Comprehensive</SelectItem>
                    <SelectItem value="dfs">DFS (Depth-First) - Focused</SelectItem>
                    <SelectItem value="bfs_then_dfs">BFS then DFS (Recommended)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-slate-500">
                  BFS explores all hypotheses broadly first, then DFS deep-dives into promising leads.
                </p>
              </div>

              {/* Auto-answer timeout */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>Auto-Answer Timeout</Label>
                  <span className="text-sm text-slate-400">{autoAnswerTimeout}s</span>
                </div>
                <Slider
                  value={[autoAnswerTimeout]}
                  onValueChange={([v]) => setAutoAnswerTimeout(v)}
                  min={30}
                  max={300}
                  step={10}
                  disabled={isRunning}
                />
                <p className="text-xs text-slate-500">
                  If you don&apos;t answer a question within this time, the AI will use its best recommendation.
                </p>
              </div>

              {/* Feature toggles */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Generate Hypotheses</Label>
                    <p className="text-xs text-slate-500">Automatically generate investigation hypotheses</p>
                  </div>
                  <Switch
                    checked={generateHypotheses}
                    onCheckedChange={setGenerateHypotheses}
                    disabled={isRunning}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Compute Confidence</Label>
                    <p className="text-xs text-slate-500">6-factor confidence scoring (ODNI ICD 203)</p>
                  </div>
                  <Switch
                    checked={computeConfidence}
                    onCheckedChange={setComputeConfidence}
                    disabled={isRunning}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Generate Report</Label>
                    <p className="text-xs text-slate-500">Automatically generate full investigation report</p>
                  </div>
                  <Switch
                    checked={generateReport}
                    onCheckedChange={setGenerateReport}
                    disabled={isRunning}
                  />
                </div>
              </div>
            </CollapsibleContent>
          </Collapsible>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={() => setOpen(false)} disabled={isRunning}>
            Cancel
          </Button>
          <Button
            onClick={handleStart}
            disabled={!canStart || isRunning}
            className="gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700"
          >
            {isRunning ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                Start Investigation
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default InvestigationConfigDialog;
