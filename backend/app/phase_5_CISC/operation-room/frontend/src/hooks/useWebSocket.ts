/**
 * WebSocket hook for real-time investigation updates
 */

import { useInvestigationStore } from '@operation-room/stores/investigationStore';
import type { Finding, ProgressUpdate } from '@operation-room/types/investigation';
import { useCallback, useEffect, useRef, useState } from 'react';

const normalizeProgress = (value: unknown): number => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 0;
  }
  if (value > 0 && value <= 1) {
    return Math.round(value * 100);
  }
  return Math.max(0, Math.min(100, Math.round(value)));
};

const normalizeFindingPayload = (data: any): Finding => {
  const payload = data?.finding && typeof data.finding === 'object' ? data.finding : data;
  const nestedData = payload?.data && typeof payload.data === 'object' ? payload.data : payload;

  const confidenceValue = typeof payload?.confidence === 'number'
    ? payload.confidence
    : typeof payload?.confidence_score === 'number'
      ? payload.confidence_score
      : typeof nestedData?.confidence === 'number'
        ? nestedData.confidence
        : undefined;

  const summary = payload?.summary
    || nestedData?.summary
    || nestedData?.statement
    || nestedData?.title
    || data?.message
    || 'Finding update';

  const verdictRaw = payload?.verdict || nestedData?.verdict;
  const verdict = typeof verdictRaw === 'string'
    ? verdictRaw.toLowerCase()
    : 'inconclusive';

  return {
    id: payload?.id || nestedData?.id,
    type: payload?.type || nestedData?.type || data?.type || 'finding',
    tool_id: data?.tool_id || payload?.tool_id || nestedData?.tool_id,
    hypothesis_id: payload?.hypothesis_id || nestedData?.hypothesis_id || payload?.id || nestedData?.id,
    hypothesis_name: payload?.hypothesis_name || nestedData?.hypothesis_name || nestedData?.statement || nestedData?.title,
    verdict: verdict === 'confirmed' || verdict === 'rejected' || verdict === 'pending' ? verdict : 'inconclusive',
    confidence: confidenceValue,
    confidence_score: confidenceValue,
    evidence_for: Array.isArray(payload?.evidence_for) ? payload.evidence_for : [],
    evidence_against: Array.isArray(payload?.evidence_against) ? payload.evidence_against : [],
    summary,
    details: payload?.details || nestedData,
    timestamp: payload?.timestamp || data?.timestamp || new Date().toISOString(),
    data: nestedData,
  };
};

export function useWebSocket(investigationId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const reconnectAttempts = useRef(0);
  const [connected, setConnected] = useState(false);

  const {
    addChatMessage,
    updateProgress,
    setPlan,
    addFinding,
    addEvidence,
    setReportProgress,
    addVersion,
    markQuestionAnswered,
  } = useInvestigationStore();

  const connect = useCallback(() => {
    if (!investigationId) return;

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    const pageProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const configuredApi = (process.env.NEXT_PUBLIC_API_URL || window.location.origin).replace(/\/api\/?$/, '');

    let wsBase = '';
    if (configuredApi.startsWith('ws://') || configuredApi.startsWith('wss://')) {
      wsBase = configuredApi;
    } else if (configuredApi.startsWith('https://')) {
      wsBase = `wss://${configuredApi.slice('https://'.length)}`;
    } else if (configuredApi.startsWith('http://')) {
      wsBase = `ws://${configuredApi.slice('http://'.length)}`;
    } else {
      wsBase = `${pageProtocol}//${configuredApi}`;
    }

    const wsUrl = `${wsBase.replace(/\/$/, '')}/deep-research/investigations/${investigationId}/ws`;

    console.log('Connecting to WebSocket:', wsUrl);

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('WebSocket connected');
      reconnectAttempts.current = 0;
      setConnected(true);

      addChatMessage({
        id: `system-${Date.now()}`,
        sender: 'system',
        content: '🔗 Connected to AI Assistant',
        type: 'text',
        timestamp: new Date().toISOString(),
      });
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      wsRef.current = null;
      setConnected(false);

      // Attempt to reconnect with exponential backoff
      if (reconnectAttempts.current < 5) {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
        reconnectAttempts.current++;

        reconnectTimeoutRef.current = setTimeout(() => {
          console.log(`Reconnecting... (attempt ${reconnectAttempts.current})`);
          connect();
        }, delay);
      } else {
        addChatMessage({
          id: `system-error-${Date.now()}`,
          sender: 'system',
          content: '❌ Connection lost. Please refresh the page.',
          type: 'error',
          timestamp: new Date().toISOString(),
        });
      }
    };
  }, [investigationId, addChatMessage]);

  const handleMessage = (data: any) => {
    console.log('WebSocket message:', data.type, data);

    switch (data.type) {
      case 'connected':
        console.log('Connection confirmed:', data.investigation_id);
        break;

      case 'chat_message':
        addChatMessage({
          id: data.id || `msg-${Date.now()}`,
          sender: data.sender,
          content: data.content,
          type: data.message_type || 'text',
          timestamp: data.timestamp,
          metadata: data.metadata,
        });
        break;

      case 'progress_update':
      case 'progress':
        const progressValue = normalizeProgress(data.progress);
        const progressUpdate: ProgressUpdate = {
          phase: data.phase,
          progress: progressValue,
          message: data.message || `${data.phase || 'investigation'} in progress`,
          current_task: data.current_task,
          estimated_time_remaining: data.estimated_time_remaining,
          sub_tasks: data.sub_tasks,
        };

        updateProgress(progressUpdate);

        // Also add to chat as visual update
        addChatMessage({
          id: `progress-${Date.now()}`,
          sender: 'system',
          content: data.message || `${data.phase || 'Investigation'} progress: ${progressValue}%`,
          type: 'progress',
          timestamp: data.timestamp,
          metadata: progressUpdate,
        });
        break;

      case 'question':
        addChatMessage({
          id: data.question_id,
          sender: 'ai',
          content: data.question,
          type: 'question',
          timestamp: data.timestamp,
          metadata: {
            priority: data.priority,
            choices: data.choices || data.options,
            allowFreeform: data.allow_freeform,
            answered: false,
          },
        });
        break;

      case 'plan_generated':
      case 'plan_update':
        if (data.plan) {
          setPlan(data.plan);
        } else if (data.data?.plan) {
          setPlan(data.data.plan);
        }

        if (data.type === 'plan_generated' && data.plan) {
          const hypothesisCount = Array.isArray(data.plan.alternative_hypotheses)
            ? data.plan.alternative_hypotheses.length
            : 0;

          addChatMessage({
            id: `plan-${Date.now()}`,
            sender: 'ai',
            content: `📋 I've created an investigation plan with ${hypothesisCount} hypotheses. Please review and approve in the Plan tab.`,
            type: 'text',
            timestamp: data.timestamp,
            metadata: { requiresApproval: true },
          });
        }
        break;

      case 'finding_discovered':
      case 'finding':
        const finding: Finding = normalizeFindingPayload(data);
        addFinding(finding);

        const verdict = finding.verdict || 'inconclusive';
        const emoji = verdict === 'confirmed' ? '✅' :
          verdict === 'rejected' ? '❌' : '⚠️';
        const findingTitle = finding.hypothesis_name || finding.summary || 'Finding update';
        const confidenceValue = typeof finding.confidence === 'number' ? finding.confidence : finding.confidence_score;
        const confidenceText = typeof confidenceValue === 'number'
          ? ` (${(confidenceValue * 100).toFixed(0)}% confidence)`
          : '';

        addChatMessage({
          id: `finding-${finding.hypothesis_id || Date.now()}`,
          sender: 'ai',
          content: `${emoji} **${verdict.toUpperCase()}**: ${findingTitle}${confidenceText}`,
          type: 'finding',
          timestamp: data.timestamp,
          metadata: finding,
        });
        break;

      case 'evidence_found':
      case 'evidence':
        addEvidence(data.evidence || data);
        break;

      case 'report_progress':
        if (data.progress && typeof data.progress === 'object') {
          setReportProgress(data.progress);
        } else {
          setReportProgress(data);
        }
        break;

      case 'version_created':
        if (!data.version) {
          break;
        }

        addVersion(data.version);

        addChatMessage({
          id: `version-${data.version.version_id}`,
          sender: 'system',
          content: `📝 Version ${data.version.version_id}: ${data.version.commit_message || data.version.message || 'New checkpoint'}`,
          type: 'text',
          timestamp: data.timestamp,
        });
        break;

      case 'question_answered':
        if (data.question_id) {
          markQuestionAnswered(data.question_id, data.answer || 'Answered', Boolean(data.skipped));
        }
        addChatMessage({
          id: `question-answered-${Date.now()}`,
          sender: 'system',
          content: '✅ Answer recorded. Investigation continuing.',
          type: 'text',
          timestamp: data.timestamp,
        });
        break;

      case 'plan_approved':
        addChatMessage({
          id: `plan-approved-${Date.now()}`,
          sender: 'system',
          content: '✅ Plan approved. Investigation is moving forward.',
          type: 'text',
          timestamp: data.timestamp,
        });
        break;

      case 'error':
        addChatMessage({
          id: `error-${Date.now()}`,
          sender: 'system',
          content: `❌ Error: ${data.message}`,
          type: 'error',
          timestamp: data.timestamp,
        });
        break;

      default:
        console.log('Unknown message type:', data.type);
    }
  };

  const sendMessage = useCallback((type: string, payload: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, ...payload }));
      return true;
    }
    console.error('WebSocket not connected');
    return false;
  }, []);

  const answerQuestion = useCallback((questionId: string, answer: string) => {
    return sendMessage('answer_question', { question_id: questionId, answer });
  }, [sendMessage]);

  const approvePlan = useCallback((comments?: string) => {
    return sendMessage('approve_plan', { comments });
  }, [sendMessage]);

  const sendChatMessage = useCallback((message: string) => {
    return sendMessage('send_message', { message });
  }, [sendMessage]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    connected,
    answerQuestion,
    approvePlan,
    sendChatMessage,
  };
}
