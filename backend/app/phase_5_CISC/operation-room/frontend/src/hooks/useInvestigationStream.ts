'use client';

/**
 * useInvestigationStream Hook
 * 
 * Manages SSE connection to the investigation API for real-time updates.
 * Handles:
 * - Starting investigations with configuration
 * - Streaming events (phases, findings, visualizations)
 * - State management for investigation progress
 */

import { useCallback, useEffect, useRef, useState } from 'react';

const INVESTIGATION_API_BASE = '/api/investigation';

const normalizeProgress = (value: unknown, fallback: number): number => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return fallback;
  }
  if (value > 0 && value <= 1) {
    return Math.max(0, Math.min(100, Math.round(value * 100)));
  }
  return Math.max(0, Math.min(100, Math.round(value)));
};

const normalizeStreamType = (rawType: unknown): EventType => {
  const value = typeof rawType === 'string' ? rawType : '';
  if (value === 'progress_update') {
    return 'progress';
  }
  if (
    value === 'phase_start'
    || value === 'phase_complete'
    || value === 'finding'
    || value === 'visualization'
    || value === 'hypothesis'
    || value === 'hypothesis_verdict'
    || value === 'confidence'
    || value === 'progress'
    || value === 'error'
    || value === 'complete'
  ) {
    return value;
  }
  return 'progress';
};

// Event types from the investigation stream
export type EventType =
  | 'phase_start'
  | 'phase_complete'
  | 'finding'
  | 'visualization'
  | 'hypothesis'
  | 'hypothesis_verdict'
  | 'confidence'
  | 'progress'
  | 'error'
  | 'complete';

// Phase enumeration
export type InvestigationPhase =
  | 'intake'
  | 'hypothesis'
  | 'planning'
  | 'execution'
  | 'testing'
  | 'confidence'
  | 'reporting';

// Finding from any tool
export interface Finding {
  id: string;
  type: string;
  tool_id?: string;
  timestamp: string;
  data: Record<string, any>;
}

// Visualization data
export interface Visualization {
  id: string;
  type: 'chart' | 'graph' | 'table' | 'heatmap' | 'timeline';
  tool_id: string;
  title?: string;
  data: Record<string, any>;
}

// Hypothesis state
export interface Hypothesis {
  id: string;
  statement: string;
  prior_confidence: number;
  verdict?: 'confirmed' | 'rejected' | 'inconclusive';
  posterior_confidence?: number;
  evidence_for?: string[];
  evidence_against?: string[];
}

// Stream event wrapper
export interface StreamEvent {
  type: EventType;
  phase?: InvestigationPhase;
  data: Record<string, any>;
  timestamp: string;
}

// Investigation configuration
export interface InvestigationConfig {
  scenario: string;
  caseId: string;
  objectives?: string[];
  timeRange?: { start: string; end: string };
  modules?: string[];
  hypotheses?: string[];
  options?: {
    llmProvider?: 'ollama' | 'gemini';
    ollamaModel?: string;
    traversalStrategy?: 'bfs' | 'dfs' | 'bfs_then_dfs';
    autoAnswerTimeout?: number;
    enabledModules?: string[];
    generateHypotheses?: boolean;
    computeConfidence?: boolean;
    generateReport?: boolean;
  };
}

// Investigation state
export interface InvestigationState {
  isRunning: boolean;
  currentPhase: InvestigationPhase | null;
  progress: number;
  findings: Finding[];
  visualizations: Visualization[];
  hypotheses: Hypothesis[];
  errors: string[];
  planSummary?: { phases: number; totalSteps: number };
  overallConfidence?: { level: string; score: number };
}

const initialState: InvestigationState = {
  isRunning: false,
  currentPhase: null,
  progress: 0,
  findings: [],
  visualizations: [],
  hypotheses: [],
  errors: [],
};

export function useInvestigationStream() {
  const [state, setState] = useState<InvestigationState>(initialState);
  const [investigationId, setInvestigationId] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Start investigation
  const startInvestigation = useCallback(async (config: InvestigationConfig) => {
    // Reset state
    setState({
      ...initialState,
      isRunning: true,
    });

    try {
      // Create abort controller for fetch
      abortControllerRef.current = new AbortController();

      // Start investigation via POST
      const response = await fetch(`${INVESTIGATION_API_BASE}/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({
          case_id: config.caseId,
          scenario: config.scenario,
          options: {
            objectives: config.objectives || [],
            time_range: config.timeRange,
            modules_to_run: config.modules,
            initial_hypotheses: config.hypotheses,
            traversal: config.options?.traversalStrategy,
            auto_answer_timeout: config.options?.autoAnswerTimeout,
            llm_provider: config.options?.llmProvider,
            llm_model: config.options?.ollamaModel,
            enabled_modules: config.options?.enabledModules,
            generate_hypotheses: config.options?.generateHypotheses,
            compute_confidence: config.options?.computeConfidence,
            generate_report: config.options?.generateReport,
          },
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`Investigation failed: ${response.statusText}`);
      }

      // Get investigation ID from headers or parse first line
      const contentType = response.headers.get('content-type');

      if (contentType?.includes('text/event-stream')) {
        // Process SSE stream
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (reader) {
          let buffer = '';

          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              setState(prev => ({ ...prev, isRunning: false }));
              break;
            }

            buffer += decoder.decode(value, { stream: true });

            // Process complete events
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || '';

            for (const eventBlock of lines) {
              if (!eventBlock.trim()) continue;

              // Parse SSE format: "data: {...}"
              const dataLine = eventBlock.split('\n').find(l => l.startsWith('data:'));
              if (dataLine) {
                try {
                  const jsonStr = dataLine.replace('data:', '').trim();
                  const rawEvent = JSON.parse(jsonStr) as StreamEvent & {
                    event_type?: string;
                    investigation_id?: string;
                  };

                  const event: StreamEvent = {
                    type: normalizeStreamType(rawEvent.type || rawEvent.event_type),
                    phase: rawEvent.phase,
                    data: rawEvent.data && typeof rawEvent.data === 'object' ? rawEvent.data : {},
                    timestamp: rawEvent.timestamp || new Date().toISOString(),
                  };

                  const incomingInvestigationId = rawEvent.investigation_id || (event.data as any).investigation_id;
                  if (typeof incomingInvestigationId === 'string' && incomingInvestigationId.length > 0) {
                    setInvestigationId(incomingInvestigationId);
                  }

                  processEvent(event);
                } catch (e) {
                  console.error('Failed to parse event:', e);
                }
              }
            }
          }
        }
      } else {
        // Not a stream, handle as regular JSON response
        const data = await response.json();
        setInvestigationId(data.investigation_id);
      }
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        setState(prev => ({
          ...prev,
          isRunning: false,
          errors: [...prev.errors, error.message],
        }));
      }
    }
  }, []);

  // Process incoming event
  const processEvent = useCallback((event: StreamEvent) => {
    switch (event.type) {
      case 'phase_start':
        setState(prev => ({
          ...prev,
          currentPhase: (event.phase || event.data?.phase || null) as InvestigationPhase | null,
        }));
        break;

      case 'phase_complete':
        setState(prev => ({
          ...prev,
          progress: Math.min(prev.progress + 14, 100), // ~7 phases
        }));
        break;

      case 'finding': {
        const findingType = event.data.type || event.data.finding?.type || 'generic';

        if (findingType === 'hypothesis') {
          setState(prev => ({
            ...prev,
            hypotheses: [...prev.hypotheses, {
              id: event.data.id || `hyp-${Date.now()}`,
              statement: event.data.statement,
              prior_confidence: event.data.prior_confidence || 0.5,
            }],
            findings: [...prev.findings, {
              id: event.data.id || `finding-${Date.now()}`,
              type: findingType,
              tool_id: event.data.tool_id,
              timestamp: event.timestamp,
              data: event.data,
            }],
          }));
          break;
        }

        if (findingType === 'hypothesis_verdict') {
          setState(prev => ({
            ...prev,
            hypotheses: prev.hypotheses.map(h =>
              h.id === event.data.hypothesis_id
                ? {
                  ...h,
                  verdict: event.data.verdict,
                  posterior_confidence: event.data.confidence,
                  evidence_for: event.data.evidence_for,
                  evidence_against: event.data.evidence_against,
                }
                : h
            ),
            findings: [...prev.findings, {
              id: event.data.id || `finding-${Date.now()}`,
              type: findingType,
              tool_id: event.data.tool_id,
              timestamp: event.timestamp,
              data: event.data,
            }],
          }));
          break;
        }

        if (findingType === 'overall_confidence') {
          setState(prev => ({
            ...prev,
            overallConfidence: {
              level: event.data.level,
              score: event.data.confidence,
            },
          }));
          break;
        }

        setState(prev => ({
          ...prev,
          findings: [...prev.findings, {
            id: event.data.id || event.data.finding?.id || `finding-${Date.now()}`,
            type: findingType,
            tool_id: event.data.tool_id,
            timestamp: event.timestamp,
            data: event.data,
          }],
        }));
        break;
      }

      case 'visualization': {
        const vizPayload = event.data.visualization || event.data;
        setState(prev => ({
          ...prev,
          visualizations: [...prev.visualizations, {
            id: vizPayload.id || `viz-${Date.now()}`,
            type: vizPayload.viz_type || vizPayload.type || 'chart',
            tool_id: event.data.tool_id || vizPayload.tool_id || 'unknown',
            title: vizPayload.title,
            data: vizPayload.data || vizPayload,
          }],
        }));
        break;
      }

      case 'hypothesis':
        setState(prev => ({
          ...prev,
          hypotheses: [...prev.hypotheses, {
            id: event.data.id || `hyp-${Date.now()}`,
            statement: event.data.statement,
            prior_confidence: event.data.prior_confidence || 0.5,
          }],
        }));
        break;

      case 'hypothesis_verdict':
        setState(prev => ({
          ...prev,
          hypotheses: prev.hypotheses.map(h =>
            h.id === event.data.hypothesis_id
              ? {
                ...h,
                verdict: event.data.verdict,
                posterior_confidence: event.data.confidence,
                evidence_for: event.data.evidence_for,
                evidence_against: event.data.evidence_against,
              }
              : h
          ),
        }));
        break;

      case 'confidence':
        setState(prev => ({
          ...prev,
          overallConfidence: {
            level: event.data.level,
            score: event.data.confidence,
          },
        }));
        break;

      case 'progress':
        setState(prev => ({
          ...prev,
          progress: normalizeProgress(event.data.progress, prev.progress),
          planSummary: event.data.plan_summary || prev.planSummary,
        }));
        break;

      case 'error':
        setState(prev => ({
          ...prev,
          errors: [...prev.errors, event.data.message || event.data.error || 'Unknown error'],
          isRunning: false,
        }));
        break;

      case 'complete':
        setState(prev => ({
          ...prev,
          isRunning: false,
          progress: 100,
        }));
        break;
    }
  }, []);

  // Stop investigation
  const stopInvestigation = useCallback(async () => {
    // Abort fetch if running
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    // Close EventSource if using
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    // Call stop API if we have an investigation ID
    if (investigationId) {
      try {
        await fetch(`${INVESTIGATION_API_BASE}/${investigationId}/stop`, {
          method: 'POST',
        });
      } catch (e) {
        console.error('Failed to stop investigation:', e);
      }
    }

    setState(prev => ({
      ...prev,
      isRunning: false,
    }));
  }, [investigationId]);

  // Clear state
  const clearState = useCallback(() => {
    setState(initialState);
    setInvestigationId(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return {
    // State
    ...state,
    investigationId,

    // Actions
    startInvestigation,
    stopInvestigation,
    clearState,
  };
}

export type UseInvestigationStreamReturn = ReturnType<typeof useInvestigationStream>;
