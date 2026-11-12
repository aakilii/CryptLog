/**
 * ThoughtStream Component
 * 
 * Displays streaming chain-of-thought text with:
 * - Real-time text streaming
 * - Typing animation
 * - Status indicators
 * - Collapsible sections
 */

import React, { useState, useEffect, useRef } from 'react';

const THOUGHT_TYPE_ICONS = {
  planning: '📋',
  hypothesis: '🔬',
  analysis: '🔍',
  synthesis: '🧩',
  conclusion: '✅',
  query: '🔎',
  verification: '✓',
  comparison: '⚖️',
  correlation: '🔗',
  question: '❓',
  clarification: '💬',
  summary: '📝',
  evidence_found: '📎',
  evidence_missing: '⚠️',
  evidence_conflict: '❌',
};

const STATUS_COLORS = {
  pending: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-600',
  completed: 'bg-green-100 text-green-600',
  failed: 'bg-red-100 text-red-600',
  blocked: 'bg-yellow-100 text-yellow-600',
};

function ThoughtItem({ thought, isLatest }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const contentRef = useRef(null);
  
  const icon = THOUGHT_TYPE_ICONS[thought.thought_type] || '💭';
  const statusColor = STATUS_COLORS[thought.status] || STATUS_COLORS.pending;
  
  // Auto-scroll for latest thought
  useEffect(() => {
    if (isLatest && contentRef.current) {
      contentRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [thought.content, isLatest]);
  
  return (
    <div className={`border-l-2 ${thought.status === 'in_progress' ? 'border-blue-500' : 'border-gray-200'} pl-4 py-2`}>
      <div 
        className="flex items-center gap-2 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="text-lg">{icon}</span>
        <span className="font-medium text-gray-900">{thought.title}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor}`}>
          {thought.status}
        </span>
        {thought.confidence && (
          <span className="text-xs text-gray-500">
            Confidence: {(thought.confidence * 100).toFixed(0)}%
          </span>
        )}
        <span className="text-gray-400 ml-auto">
          {isExpanded ? '▼' : '▶'}
        </span>
      </div>
      
      {isExpanded && (
        <div ref={contentRef} className="mt-2 ml-6">
          <div className="text-sm text-gray-700 whitespace-pre-wrap">
            {thought.content}
            {thought.status === 'in_progress' && (
              <span className="inline-block w-2 h-4 bg-blue-500 ml-1 animate-pulse" />
            )}
          </div>
          
          {thought.evidence_refs.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {thought.evidence_refs.map((ref, i) => (
                <span 
                  key={i}
                  className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded"
                >
                  📎 {ref.substring(0, 8)}...
                </span>
              ))}
            </div>
          )}
          
          {thought.error && (
            <div className="mt-2 text-sm text-red-600 bg-red-50 p-2 rounded">
              ⚠️ {thought.error}
            </div>
          )}
          
          {thought.result && (
            <div className="mt-2 text-sm text-green-700 bg-green-50 p-2 rounded">
              ✓ {thought.result}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ThoughtStream({ 
  investigationId,
  thoughts = [],
  onThoughtClick,
  className = '',
}) {
  const [localThoughts, setLocalThoughts] = useState(thoughts);
  const [isConnected, setIsConnected] = useState(false);
  const containerRef = useRef(null);
  
  // Connect to SSE stream
  useEffect(() => {
    if (!investigationId) return;
    
    const eventSource = new EventSource(
      `/api/deep-research/investigations/${investigationId}/thoughts/stream`
    );
    
    eventSource.onopen = () => {
      setIsConnected(true);
    };
    
    eventSource.onerror = () => {
      setIsConnected(false);
    };
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        switch (data.event_type) {
          case 'tree_update':
            // Full tree update
            if (data.data.stream_format) {
              setLocalThoughts(data.data.stream_format);
            }
            break;
            
          case 'thought_start':
            // New thought started
            setLocalThoughts(prev => [...prev, {
              id: data.thought_id,
              title: data.data.title,
              thought_type: data.data.thought_type,
              status: 'in_progress',
              content: '',
              evidence_refs: [],
              depth: data.data.depth || 0,
            }]);
            break;
            
          case 'thought_content':
            // Content chunk
            setLocalThoughts(prev => prev.map(t => 
              t.id === data.thought_id
                ? { ...t, content: t.content + data.content }
                : t
            ));
            break;
            
          case 'thought_complete':
            // Thought finished
            setLocalThoughts(prev => prev.map(t =>
              t.id === data.thought_id
                ? { ...t, status: data.data.status }
                : t
            ));
            break;
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    };
    
    return () => {
      eventSource.close();
    };
  }, [investigationId]);
  
  // Update from props
  useEffect(() => {
    setLocalThoughts(thoughts);
  }, [thoughts]);
  
  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b">
        <h3 className="font-semibold text-gray-900">Chain of Thought</h3>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-xs text-gray-500">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>
      
      {/* Thought List */}
      <div ref={containerRef} className="flex-1 overflow-auto p-4 space-y-2">
        {localThoughts.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <p>No thoughts yet.</p>
            <p className="text-sm">Start an investigation to see the reasoning process.</p>
          </div>
        ) : (
          localThoughts.map((thought, index) => (
            <div 
              key={thought.id}
              style={{ marginLeft: `${(thought.depth || 0) * 20}px` }}
              onClick={() => onThoughtClick?.(thought)}
            >
              <ThoughtItem 
                thought={thought}
                isLatest={index === localThoughts.length - 1}
              />
            </div>
          ))
        )}
      </div>
      
      {/* Progress Footer */}
      <div className="px-4 py-2 border-t bg-gray-50">
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>{localThoughts.filter(t => t.status === 'completed').length} / {localThoughts.length} complete</span>
          <span>
            {localThoughts.filter(t => t.status === 'in_progress').length > 0 && (
              <span className="text-blue-600">Processing...</span>
            )}
          </span>
        </div>
      </div>
    </div>
  );
}

export default ThoughtStream;
