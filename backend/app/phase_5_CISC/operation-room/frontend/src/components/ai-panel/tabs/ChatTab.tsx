/**
 * Chat Tab - Main chat interface with AI
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useInvestigationStore } from '@operation-room/stores/investigationStore';
import { useWebSocket } from '@operation-room/hooks/useWebSocket';
import { useParams } from 'next/navigation';
import ChatMessage from '../messages/ChatMessage';

export default function ChatTab() {
  const params = useParams();
  const routeCaseId = params?.id as string || '';
  const { chatMessages, investigationId, scenario, caseId, setPlan } = useInvestigationStore();
  const { connected, sendChatMessage } = useWebSocket(investigationId);
  const [inputValue, setInputValue] = useState('');
  const [isInitialSetup, setIsInitialSetup] = useState(!scenario);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  useEffect(() => {
    if (scenario || investigationId) {
      setIsInitialSetup(false);
    }
  }, [scenario, investigationId]);
  
  const handleSend = () => {
    if (!inputValue.trim()) return;
    
    if (isInitialSetup) {
      // First message - start investigation
      handleStartInvestigation(inputValue);
    } else {
      // Normal chat message
      sendChatMessage(inputValue);
      
      // Add user message to UI immediately
      useInvestigationStore.getState().addChatMessage({
        id: `user-${Date.now()}`,
        sender: 'user',
        content: inputValue,
        type: 'text',
        timestamp: new Date().toISOString(),
      });
    }
    
    setInputValue('');
  };
  
  const handleStartInvestigation = async (scenario: string) => {
    try {
      const effectiveCaseId = caseId || routeCaseId || `case-${Date.now()}`;

      // Call API to start investigation
      const response = await fetch('/api/deep-research/orchestrator/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: effectiveCaseId,
          scenario: scenario,
          objectives: [
            'Establish complete timeline of events',
            'Identify all artifacts and evidence',
            'Correlate cross-device activities',
            'Generate detailed forensic report',
          ],
          mode: 'focused',
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to start investigation (${response.status})`);
      }
      
      const data = await response.json();
      
      // Set investigation ID in store
      useInvestigationStore.getState().setInvestigationId(
        data.investigation_id,
        data.case_id || effectiveCaseId,
        scenario
      );

      if (data.plan) {
        setPlan(data.plan);
      }
      
      setIsInitialSetup(false);
      
      // Add user message
      useInvestigationStore.getState().addChatMessage({
        id: `user-${Date.now()}`,
        sender: 'user',
        content: scenario,
        type: 'text',
        timestamp: new Date().toISOString(),
      });
      
    } catch (error) {
      console.error('Failed to start investigation:', error);
      useInvestigationStore.getState().addChatMessage({
        id: `error-${Date.now()}`,
        sender: 'system',
        content: `❌ Failed to start investigation: ${error}`,
        type: 'error',
        timestamp: new Date().toISOString(),
      });
    }
  };
  
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
  
  return (
    <div className="flex flex-col h-full bg-white">
      {/* Connection status */}
      {investigationId && (
        <div className={`px-4 py-2 text-xs flex items-center gap-2 ${
          connected ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
        }`}>
          <div className={`w-2 h-2 rounded-full ${
            connected ? 'bg-green-500' : 'bg-red-500'
          }`} />
          {connected ? 'Connected to AI Assistant' : 'Disconnected - Reconnecting...'}
        </div>
      )}
      
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {chatMessages.length === 0 && isInitialSetup && (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">🤖</div>
            <h3 className="text-lg font-semibold text-gray-800 mb-2">
              AI Investigation Assistant
            </h3>
            <p className="text-gray-600 mb-6 max-w-md mx-auto">
              Describe your investigation scenario and I'll help you analyze the evidence, 
              generate hypotheses, and create a comprehensive forensic report.
            </p>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-left max-w-md mx-auto">
              <div className="font-semibold text-blue-900 mb-2">💡 Example scenarios:</div>
              <ul className="text-sm text-gray-700 space-y-1">
                <li>• Data exfiltration via USB, Bluetooth, and email</li>
                <li>• Unauthorized access to confidential files</li>
                <li>• Timeline reconstruction of security incident</li>
                <li>• Network intrusion investigation</li>
              </ul>
            </div>
          </div>
        )}
        
        {chatMessages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* Input area */}
      <div className="border-t bg-gray-50 p-4">
        <div className="flex gap-2">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={
              isInitialSetup 
                ? "Describe your investigation scenario..." 
                : "Type your message or answer..."
            }
            rows={3}
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
          <button
            onClick={handleSend}
            disabled={!inputValue.trim()}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium self-end"
          >
            {isInitialSetup ? 'Start Investigation' : 'Send'}
          </button>
        </div>
        <div className="text-xs text-gray-500 mt-2">
          Press Enter to send, Shift+Enter for new line
        </div>
      </div>
    </div>
  );
}
