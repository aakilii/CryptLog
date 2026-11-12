/**
 * ThoughtNode Component
 * 
 * Individual thought node with detailed view.
 */

import React from 'react';

const CONFIDENCE_LABELS = {
  0.95: { label: 'Very High', color: 'bg-green-600' },
  0.82: { label: 'High', color: 'bg-green-500' },
  0.62: { label: 'Moderate', color: 'bg-yellow-500' },
  0.37: { label: 'Low', color: 'bg-orange-500' },
  0.15: { label: 'Very Low', color: 'bg-red-500' },
};

function getConfidenceLabel(confidence) {
  if (confidence >= 0.9) return CONFIDENCE_LABELS[0.95];
  if (confidence >= 0.75) return CONFIDENCE_LABELS[0.82];
  if (confidence >= 0.5) return CONFIDENCE_LABELS[0.62];
  if (confidence >= 0.25) return CONFIDENCE_LABELS[0.37];
  return CONFIDENCE_LABELS[0.15];
}

export function ThoughtNode({ 
  thought,
  isSelected = false,
  onSelect,
  onViewEvidence,
  className = '',
}) {
  if (!thought) return null;
  
  const confidenceInfo = thought.confidence 
    ? getConfidenceLabel(thought.confidence)
    : null;
  
  return (
    <div 
      className={`
        p-4 rounded-lg border-2 cursor-pointer transition-all
        ${isSelected ? 'border-blue-500 shadow-lg' : 'border-gray-200 hover:border-gray-300'}
        ${className}
      `}
      onClick={() => onSelect?.(thought)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-2">
        <div>
          <h4 className="font-semibold text-gray-900">{thought.title}</h4>
          <span className="text-xs text-gray-500 capitalize">
            {thought.thought_type?.replace(/_/g, ' ')}
          </span>
        </div>
        
        {/* Status Badge */}
        <span className={`
          px-2 py-1 text-xs rounded-full capitalize
          ${thought.status === 'completed' ? 'bg-green-100 text-green-700' : ''}
          ${thought.status === 'in_progress' ? 'bg-blue-100 text-blue-700' : ''}
          ${thought.status === 'pending' ? 'bg-gray-100 text-gray-700' : ''}
          ${thought.status === 'failed' ? 'bg-red-100 text-red-700' : ''}
          ${thought.status === 'blocked' ? 'bg-yellow-100 text-yellow-700' : ''}
        `}>
          {thought.status}
        </span>
      </div>
      
      {/* Content */}
      <div className="text-sm text-gray-700 mb-3 whitespace-pre-wrap">
        {thought.content}
      </div>
      
      {/* Confidence Bar */}
      {confidenceInfo && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-500">Confidence</span>
            <span className="font-medium">{confidenceInfo.label} ({(thought.confidence * 100).toFixed(0)}%)</span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className={`h-full ${confidenceInfo.color} transition-all duration-300`}
              style={{ width: `${thought.confidence * 100}%` }}
            />
          </div>
        </div>
      )}
      
      {/* Evidence References */}
      {thought.evidence_refs && thought.evidence_refs.length > 0 && (
        <div className="mb-3">
          <h5 className="text-xs font-medium text-gray-500 mb-1">Evidence</h5>
          <div className="flex flex-wrap gap-1">
            {thought.evidence_refs.map((ref, i) => (
              <button
                key={i}
                onClick={(e) => {
                  e.stopPropagation();
                  onViewEvidence?.(ref);
                }}
                className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded hover:bg-purple-200"
              >
                📎 {typeof ref === 'string' ? ref.substring(0, 12) : ref}...
              </button>
            ))}
          </div>
        </div>
      )}
      
      {/* Result */}
      {thought.result && (
        <div className="p-2 bg-green-50 border border-green-200 rounded text-sm text-green-700">
          <span className="font-medium">Result:</span> {thought.result}
        </div>
      )}
      
      {/* Error */}
      {thought.error && (
        <div className="p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          <span className="font-medium">Error:</span> {thought.error}
        </div>
      )}
      
      {/* Metadata */}
      <div className="mt-3 flex items-center justify-between text-xs text-gray-400">
        <span>ID: {thought.id?.substring(0, 8)}</span>
        {thought.duration_ms && (
          <span>{thought.duration_ms}ms</span>
        )}
        {thought.module_source && (
          <span>Module: {thought.module_source}</span>
        )}
      </div>
    </div>
  );
}

export default ThoughtNode;
