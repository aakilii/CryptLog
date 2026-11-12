/**
 * ThoughtTree Component
 * 
 * Displays chain-of-thought as a collapsible tree with:
 * - Hierarchical structure
 * - Expand/collapse nodes
 * - Status indicators
 * - Progress visualization
 */

import React, { useState, useCallback } from 'react';

const THOUGHT_TYPE_COLORS = {
  planning: 'border-purple-500 bg-purple-50',
  hypothesis: 'border-orange-500 bg-orange-50',
  analysis: 'border-blue-500 bg-blue-50',
  synthesis: 'border-green-500 bg-green-50',
  conclusion: 'border-emerald-500 bg-emerald-50',
  query: 'border-cyan-500 bg-cyan-50',
  verification: 'border-teal-500 bg-teal-50',
  question: 'border-yellow-500 bg-yellow-50',
  evidence_found: 'border-indigo-500 bg-indigo-50',
  evidence_missing: 'border-red-500 bg-red-50',
};

const STATUS_ICONS = {
  pending: '○',
  in_progress: '◐',
  completed: '●',
  failed: '✕',
  blocked: '⊘',
};

function TreeNode({ 
  node, 
  nodes, 
  depth = 0,
  expandedIds,
  onToggle,
  onNodeClick,
  onAnswerQuestion,
}) {
  const isExpanded = expandedIds.has(node.id);
  const hasChildren = node.children_ids && node.children_ids.length > 0;
  const children = hasChildren 
    ? node.children_ids.map(id => nodes[id]).filter(Boolean)
    : [];
  
  const typeColor = THOUGHT_TYPE_COLORS[node.thought_type] || 'border-gray-500 bg-gray-50';
  const statusIcon = STATUS_ICONS[node.status] || '○';
  
  return (
    <div className="select-none">
      {/* Node Header */}
      <div 
        className={`
          flex items-start gap-2 p-2 rounded-lg border-l-4 mb-1 cursor-pointer
          hover:shadow-sm transition-shadow
          ${typeColor}
        `}
        style={{ marginLeft: `${depth * 24}px` }}
        onClick={() => onNodeClick?.(node)}
      >
        {/* Expand/Collapse Toggle */}
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggle(node.id);
            }}
            className="w-5 h-5 flex items-center justify-center text-gray-500 hover:text-gray-700"
          >
            {isExpanded ? '▼' : '▶'}
          </button>
        ) : (
          <span className="w-5 h-5 flex items-center justify-center text-gray-400">
            •
          </span>
        )}
        
        {/* Status Icon */}
        <span className={`
          w-4 h-4 flex items-center justify-center text-sm
          ${node.status === 'in_progress' ? 'animate-spin text-blue-500' : ''}
          ${node.status === 'completed' ? 'text-green-500' : ''}
          ${node.status === 'failed' ? 'text-red-500' : ''}
          ${node.status === 'blocked' ? 'text-yellow-500' : ''}
        `}>
          {node.status === 'in_progress' ? '⟳' : statusIcon}
        </span>
        
        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-gray-900 truncate">
              {node.title}
            </span>
            {node.confidence !== undefined && node.confidence !== null && (
              <span className={`
                text-xs px-1.5 py-0.5 rounded
                ${node.confidence >= 0.8 ? 'bg-green-200 text-green-800' : ''}
                ${node.confidence >= 0.5 && node.confidence < 0.8 ? 'bg-yellow-200 text-yellow-800' : ''}
                ${node.confidence < 0.5 ? 'bg-red-200 text-red-800' : ''}
              `}>
                {(node.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
          
          {isExpanded && node.content && (
            <p className="text-sm text-gray-600 mt-1 whitespace-pre-wrap">
              {node.content}
            </p>
          )}
          
          {/* Evidence References */}
          {isExpanded && node.evidence_refs && node.evidence_refs.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {node.evidence_refs.map((ref, i) => (
                <span 
                  key={i}
                  className="text-xs bg-purple-200 text-purple-800 px-2 py-0.5 rounded"
                >
                  📎 {typeof ref === 'string' ? ref.substring(0, 8) : ref}
                </span>
              ))}
            </div>
          )}
          
          {/* Question Answer UI */}
          {node.status === 'blocked' && node.data?.question && (
            <div className="mt-2 p-2 bg-yellow-100 rounded border border-yellow-300">
              <p className="text-sm font-medium text-yellow-800">
                ❓ {node.data.question}
              </p>
              {node.data.options ? (
                <div className="flex flex-wrap gap-2 mt-2">
                  {node.data.options.map((option, i) => (
                    <button
                      key={i}
                      onClick={(e) => {
                        e.stopPropagation();
                        onAnswerQuestion?.(node.id, option);
                      }}
                      className="text-xs px-3 py-1 bg-white border border-yellow-400 rounded hover:bg-yellow-50"
                    >
                      {option}
                    </button>
                  ))}
                </div>
              ) : (
                <input
                  type="text"
                  placeholder="Type your answer..."
                  className="mt-2 w-full text-sm p-1 border rounded"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      onAnswerQuestion?.(node.id, e.target.value);
                    }
                  }}
                  onClick={(e) => e.stopPropagation()}
                />
              )}
            </div>
          )}
          
          {/* Error Display */}
          {node.error && (
            <div className="mt-2 text-xs text-red-600 bg-red-100 p-1 rounded">
              ⚠️ {node.error}
            </div>
          )}
          
          {/* Result Display */}
          {node.result && (
            <div className="mt-2 text-xs text-green-700 bg-green-100 p-1 rounded">
              ✓ {node.result}
            </div>
          )}
        </div>
        
        {/* Timing */}
        {node.duration_ms && (
          <span className="text-xs text-gray-400">
            {node.duration_ms}ms
          </span>
        )}
      </div>
      
      {/* Children */}
      {isExpanded && children.map(child => (
        <TreeNode
          key={child.id}
          node={child}
          nodes={nodes}
          depth={depth + 1}
          expandedIds={expandedIds}
          onToggle={onToggle}
          onNodeClick={onNodeClick}
          onAnswerQuestion={onAnswerQuestion}
        />
      ))}
    </div>
  );
}

export function ThoughtTree({
  treeData,
  onNodeClick,
  onAnswerQuestion,
  className = '',
}) {
  const [expandedIds, setExpandedIds] = useState(new Set());
  
  // Initialize with all nodes expanded
  React.useEffect(() => {
    if (treeData?.nodes) {
      setExpandedIds(new Set(Object.keys(treeData.nodes)));
    }
  }, [treeData]);
  
  const handleToggle = useCallback((nodeId) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);
  
  const expandAll = useCallback(() => {
    if (treeData?.nodes) {
      setExpandedIds(new Set(Object.keys(treeData.nodes)));
    }
  }, [treeData]);
  
  const collapseAll = useCallback(() => {
    setExpandedIds(new Set());
  }, []);
  
  if (!treeData || !treeData.nodes) {
    return (
      <div className={`p-4 text-center text-gray-500 ${className}`}>
        No thought tree data
      </div>
    );
  }
  
  const { nodes, root_ids, summary } = treeData;
  const rootNodes = root_ids.map(id => nodes[id]).filter(Boolean);
  
  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header with Controls */}
      <div className="flex items-center justify-between px-4 py-2 border-b bg-gray-50">
        <h3 className="font-semibold text-gray-900">Thought Tree</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={expandAll}
            className="text-xs px-2 py-1 text-gray-600 hover:bg-gray-200 rounded"
          >
            Expand All
          </button>
          <button
            onClick={collapseAll}
            className="text-xs px-2 py-1 text-gray-600 hover:bg-gray-200 rounded"
          >
            Collapse All
          </button>
        </div>
      </div>
      
      {/* Summary Stats */}
      {summary && (
        <div className="px-4 py-2 border-b bg-gray-50 flex items-center gap-4 text-xs text-gray-600">
          <span>Total: {summary.total_nodes}</span>
          <span>Progress: {(summary.progress * 100).toFixed(0)}%</span>
          {summary.by_status && (
            <>
              {summary.by_status.completed > 0 && (
                <span className="text-green-600">✓ {summary.by_status.completed}</span>
              )}
              {summary.by_status.in_progress > 0 && (
                <span className="text-blue-600">⟳ {summary.by_status.in_progress}</span>
              )}
              {summary.by_status.blocked > 0 && (
                <span className="text-yellow-600">⊘ {summary.by_status.blocked}</span>
              )}
            </>
          )}
        </div>
      )}
      
      {/* Tree Content */}
      <div className="flex-1 overflow-auto p-4">
        {rootNodes.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            <p>No thoughts yet.</p>
          </div>
        ) : (
          rootNodes.map(node => (
            <TreeNode
              key={node.id}
              node={node}
              nodes={nodes}
              depth={0}
              expandedIds={expandedIds}
              onToggle={handleToggle}
              onNodeClick={onNodeClick}
              onAnswerQuestion={onAnswerQuestion}
            />
          ))
        )}
      </div>
    </div>
  );
}

export default ThoughtTree;
