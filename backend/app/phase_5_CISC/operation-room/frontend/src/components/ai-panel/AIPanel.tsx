/**
 * AI Panel - Main container for AI assistant interface
 */

'use client';

import { useStudioStore } from '@operation-room/components/studio-v4/store/useStudioStore';
import { useConfirmedFindings, useInvestigationStore, useUnreadQuestions } from '@operation-room/stores/investigationStore';
import { useParams } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import NotificationToast from './NotificationToast';
import ChatTab from './tabs/ChatTab';
import EvidenceTab from './tabs/EvidenceTab';
import FindingsTab from './tabs/FindingsTab';
import HistoryTab from './tabs/HistoryTab';
import PlanTab from './tabs/PlanTab';
import ProgressTab from './tabs/ProgressTab';
import ReportTab from './tabs/ReportTab';

interface LLMProvider {
  type: 'gemini' | 'ollama';
  model: string;
  is_available: boolean;
  is_current: boolean;
}

interface OllamaModel {
  name: string;
  size: string;
  modified_at: string;
}

const DEEP_RESEARCH_API = '/api/deep-research';

export default function AIPanel() {
  const params = useParams();
  const caseId = params?.id as string || '';
  const {
    activeTab,
    setActiveTab,
    panelState,
    setPanelState,
    investigationId,
    setInvestigationId,
    setPlan,
    reset,
  } = useInvestigationStore();
  const setAiPanelOpen = useStudioStore((state) => state.setAiPanelOpen);
  const unreadQuestions = useUnreadQuestions();
  const confirmedFindings = useConfirmedFindings();

  const [llmProvider, setLlmProvider] = useState<'gemini' | 'ollama'>('ollama');
  const [selectedModel, setSelectedModel] = useState<string>('qwen3:8b');
  const [isStarting, setIsStarting] = useState(false);
  const [availableModels, setAvailableModels] = useState<LLMProvider[]>([]);
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelSwitchStatus, setModelSwitchStatus] = useState<string>('');

  // Load LLM providers on mount
  useEffect(() => {
    const loadProviders = async () => {
      try {
        const res = await fetch(`${DEEP_RESEARCH_API}/llm/providers`);
        const data = await res.json();
        setAvailableModels(data.providers || []);
        const current = data.providers.find((p: LLMProvider) => p.is_current);
        if (current) {
          setLlmProvider(current.type);
          setSelectedModel(current.model);
        }
      } catch (error) {
        console.error('Failed to load LLM providers:', error);
      }
    };
    loadProviders();
  }, []);

  // Load Ollama models when provider is Ollama
  const loadOllamaModels = useCallback(async () => {
    if (llmProvider !== 'ollama') return;
    setIsLoadingModels(true);
    try {
      const res = await fetch(`${DEEP_RESEARCH_API}/llm/ollama-models`);
      const data = await res.json();
      setOllamaModels(data.models || []);
    } catch (error) {
      console.error('Failed to load Ollama models:', error);
      setOllamaModels([]);
    } finally {
      setIsLoadingModels(false);
    }
  }, [llmProvider]);

  useEffect(() => {
    if (llmProvider === 'ollama') {
      loadOllamaModels();
    }
  }, [llmProvider, loadOllamaModels]);

  const switchProvider = async (provider: 'gemini' | 'ollama', model?: string) => {
    setModelSwitchStatus('Switching...');
    try {
      const modelParam = model ? `&model=${encodeURIComponent(model)}` : '';
      const res = await fetch(`${DEEP_RESEARCH_API}/llm/switch?provider=${provider}${modelParam}`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setLlmProvider(provider);
        setSelectedModel(data.model || model || 'qwen3:8b');
        setModelSwitchStatus(`✓ Switched to ${provider}${model ? ` (${model})` : ''}`);
        setTimeout(() => setModelSwitchStatus(''), 2000);
      } else {
        setModelSwitchStatus('❌ Switch failed');
        setTimeout(() => setModelSwitchStatus(''), 3000);
      }
    } catch (error) {
      console.error('Failed to switch provider:', error);
      setModelSwitchStatus('❌ Connection error');
      setTimeout(() => setModelSwitchStatus(''), 3000);
    }
  };

  const handleModelChange = (model: string) => {
    setSelectedModel(model);
    switchProvider(llmProvider, model);
  };

  const startInvestigation = async () => {
    if (!caseId || isStarting) return;

    setIsStarting(true);
    const scenario = 'Analyze all available logs and evidence for this case to create a comprehensive forensic report';

    try {
      const res = await fetch(`${DEEP_RESEARCH_API}/orchestrator/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseId,
          scenario,
          objectives: [
            'Establish complete timeline of events',
            'Identify all artifacts and evidence',
            'Correlate cross-device activities',
            'Generate detailed forensic report'
          ],
          mode: 'focused'
        })
      });

      if (!res.ok) {
        throw new Error(`Failed to start investigation (${res.status})`);
      }

      const data = await res.json();
      if (data.investigation_id || data.tree_id) {
        setInvestigationId(data.investigation_id || data.tree_id, caseId, scenario);
        if (data.plan) {
          setPlan(data.plan);
        }
        setActiveTab('chat');
      }
    } catch (error) {
      console.error('Failed to start investigation:', error);
    } finally {
      setIsStarting(false);
    }
  };

  const stopInvestigation = async () => {
    const confirmed = window.confirm('End the current AI investigation session? This will clear panel investigation state.');
    if (!confirmed) {
      return;
    }

    if (investigationId) {
      try {
        await fetch(`${DEEP_RESEARCH_API}/investigations/${investigationId}/stop`, {
          method: 'POST',
        });
      } catch (error) {
        console.error('Failed to stop investigation session:', error);
      }
    }

    reset();
    setModelSwitchStatus('Session ended');
    setTimeout(() => setModelSwitchStatus(''), 2000);
  };

  const tabs = [
    { id: 'chat' as const, label: 'Chat', icon: '💬', badge: unreadQuestions },
    { id: 'progress' as const, label: 'Progress', icon: '📊' },
    { id: 'plan' as const, label: 'Plan', icon: '📋', badge: 0 },
    { id: 'evidence' as const, label: 'Evidence', icon: '🔍' },
    { id: 'findings' as const, label: 'Findings', icon: '📝', badge: confirmedFindings },
    { id: 'report' as const, label: 'Report', icon: '📄' },
    { id: 'history' as const, label: 'History', icon: '🕐' },
  ];

  return (
    <div className="flex flex-col h-full bg-white border-l border-gray-200">
      {/* Model Selector Bar - Prominent at top */}
      <div className="bg-gradient-to-r from-slate-900 to-slate-800 px-4 py-2 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">AI Model</span>

            {/* Provider Toggle */}
            <div className="flex items-center bg-slate-700/50 rounded-lg p-0.5">
              <button
                onClick={() => switchProvider('ollama')}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${llmProvider === 'ollama'
                  ? 'bg-green-500 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
                  }`}
              >
                🦙 Ollama
              </button>
              <button
                onClick={() => switchProvider('gemini')}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${llmProvider === 'gemini'
                  ? 'bg-blue-500 text-white shadow-lg'
                  : 'text-slate-400 hover:text-white'
                  }`}
              >
                ✨ Gemini
              </button>
            </div>

            {/* Model Selector for Ollama */}
            {llmProvider === 'ollama' && (
              <select
                value={selectedModel}
                onChange={(e) => handleModelChange(e.target.value)}
                className="px-2 py-1 text-xs bg-slate-700 text-white border border-slate-600 rounded-md hover:bg-slate-600 transition-colors cursor-pointer"
                title="Select Ollama Model"
              >
                {ollamaModels.length > 0 ? (
                  ollamaModels.map((model) => (
                    <option key={model.name} value={model.name}>
                      {model.name} ({model.size})
                    </option>
                  ))
                ) : (
                  <>
                    <option value="qwen3:8b">qwen3:8b</option>
                    <option value="llama3:8b">llama3:8b</option>
                    <option value="mistral:7b">mistral:7b</option>
                  </>
                )}
              </select>
            )}

            {/* Refresh models button */}
            {llmProvider === 'ollama' && (
              <button
                onClick={loadOllamaModels}
                disabled={isLoadingModels}
                className="p-1 text-slate-400 hover:text-white transition-colors"
                title="Refresh available models"
              >
                {isLoadingModels ? '⏳' : '🔄'}
              </button>
            )}
          </div>

          {/* Model status */}
          <div className="flex items-center gap-2">
            {modelSwitchStatus && (
              <span className="text-xs text-green-400 animate-pulse">{modelSwitchStatus}</span>
            )}
            <span className={`w-2 h-2 rounded-full ${availableModels.find(m => m.type === llmProvider)?.is_available
              ? 'bg-green-500'
              : 'bg-red-500'
              }`} title={llmProvider === 'ollama' ? 'Ollama Status' : 'Gemini Status'} />
          </div>
        </div>
      </div>

      {/* Header with controls */}
      <div className="border-b border-gray-200 bg-gradient-to-r from-blue-600 to-blue-700 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🤖</span>
            <h2 className="font-semibold text-white">AI Investigation Assistant</h2>
          </div>

          <div className="flex items-center gap-2">
            {/* Start Investigation Button */}
            {!investigationId ? (
              <button
                onClick={startInvestigation}
                disabled={isStarting || !caseId}
                className="px-4 py-1.5 text-sm bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
                title="Start AI Investigation"
              >
                {isStarting ? '🔄 Starting...' : '▶️ Start Investigation'}
              </button>
            ) : (
              <button
                onClick={stopInvestigation}
                className="px-4 py-1.5 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors font-medium"
                title="End AI Investigation Session"
              >
                ⏹ End Session
              </button>
            )}

            {/* Panel controls */}
            <button
              onClick={() => setPanelState(
                panelState === 'expanded' ? 'normal' : 'expanded'
              )}
              className="p-2 hover:bg-white/20 rounded transition-colors text-white"
              title={panelState === 'expanded' ? 'Normal width' : 'Expand panel'}
            >
              {panelState === 'expanded' ? '◀' : '▶'}
            </button>
            <button
              onClick={() => {
                setPanelState('collapsed');
                setAiPanelOpen(false);
              }}
              className="p-2 hover:bg-white/20 rounded transition-colors text-white"
              title="Close panel"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Investigation Status */}
        {investigationId && (
          <div className="mt-2 text-xs text-white/80 flex items-center gap-2">
            <span className="inline-block w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
            Investigation ID: {investigationId.substring(0, 8)}...
          </div>
        )}
      </div>

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 bg-white overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 transition-colors whitespace-nowrap relative ${activeTab === tab.id
              ? 'border-blue-600 text-blue-600 bg-blue-50'
              : 'border-transparent text-gray-600 hover:text-gray-800 hover:bg-gray-50'
              }`}
          >
            <span className="text-lg">{tab.icon}</span>
            <span className="text-sm font-medium">{tab.label}</span>

            {/* Badge for notifications */}
            {tab.badge !== undefined && tab.badge > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-semibold">
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'chat' && <ChatTab />}
        {activeTab === 'progress' && <ProgressTab />}
        {activeTab === 'plan' && <PlanTab />}
        {activeTab === 'evidence' && <EvidenceTab />}
        {activeTab === 'findings' && <FindingsTab />}
        {activeTab === 'report' && <ReportTab />}
        {activeTab === 'history' && <HistoryTab />}
      </div>

      {/* Notification Toast */}
      <NotificationToast />
    </div>
  );
}
