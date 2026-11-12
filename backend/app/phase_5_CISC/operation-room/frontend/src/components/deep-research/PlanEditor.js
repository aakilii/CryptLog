/**
 * PlanEditor Component
 * 
 * Interactive investigation plan editor with:
 * - Phase/step hierarchy
 * - Drag-and-drop reordering
 * - Inline editing
 * - Approval workflow
 */

import React, { useState, useCallback } from 'react';

const STEP_TYPE_ICONS = {
  analysis: '🔍',
  query: '🔎',
  hypothesis: '🔬',
  synthesis: '🧩',
  report: '📝',
  clarification: '💬',
  manual: '👤',
  verification: '✓',
};

const STATUS_COLORS = {
  draft: 'bg-gray-100 border-gray-300',
  pending_approval: 'bg-yellow-100 border-yellow-300',
  approved: 'bg-blue-100 border-blue-300',
  in_progress: 'bg-blue-200 border-blue-400',
  completed: 'bg-green-100 border-green-300',
  cancelled: 'bg-red-100 border-red-300',
};

function StepItem({ 
  step, 
  phaseId,
  onEdit, 
  onDelete, 
  onDragStart,
  onDragOver,
  onDrop,
  isDragging,
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(step.title);
  
  const icon = STEP_TYPE_ICONS[step.step_type] || '📋';
  const statusColor = STATUS_COLORS[step.status] || STATUS_COLORS.draft;
  
  const handleSave = () => {
    onEdit(phaseId, step.id, { title: editTitle });
    setIsEditing(false);
  };
  
  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, 'step', { phaseId, stepId: step.id })}
      onDragOver={(e) => {
        e.preventDefault();
        onDragOver(e, 'step');
      }}
      onDrop={(e) => onDrop(e, 'step', { phaseId, stepId: step.id })}
      className={`
        flex items-center gap-2 p-2 rounded border cursor-move
        ${statusColor}
        ${isDragging ? 'opacity-50' : ''}
        hover:shadow-sm transition-shadow
      `}
    >
      <span className="text-sm">{icon}</span>
      
      {isEditing ? (
        <input
          type="text"
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          onBlur={handleSave}
          onKeyDown={(e) => e.key === 'Enter' && handleSave()}
          className="flex-1 text-sm p-1 border rounded"
          autoFocus
        />
      ) : (
        <span 
          className="flex-1 text-sm text-gray-800"
          onDoubleClick={() => setIsEditing(true)}
        >
          {step.title}
        </span>
      )}
      
      {step.module && (
        <span className="text-xs bg-white/50 px-1 rounded">
          {step.module}
        </span>
      )}
      
      {/* Progress */}
      {step.status === 'in_progress' && (
        <div className="w-16 h-2 bg-white/50 rounded-full overflow-hidden">
          <div 
            className="h-full bg-blue-500"
            style={{ width: `${step.progress * 100}%` }}
          />
        </div>
      )}
      
      <button
        onClick={() => onDelete(phaseId, step.id)}
        className="text-xs text-gray-500 hover:text-red-500"
      >
        ×
      </button>
    </div>
  );
}

function PhaseItem({
  phase,
  onEditPhase,
  onEditStep,
  onDeletePhase,
  onDeleteStep,
  onAddStep,
  onDragStart,
  onDragOver,
  onDrop,
  isExpanded,
  onToggleExpand,
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(phase.title);
  
  const statusColor = STATUS_COLORS[phase.status] || STATUS_COLORS.draft;
  const completedSteps = phase.steps?.filter(s => s.status === 'completed').length || 0;
  const totalSteps = phase.steps?.length || 0;
  
  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, 'phase', { phaseId: phase.id })}
      onDragOver={(e) => {
        e.preventDefault();
        onDragOver(e, 'phase');
      }}
      onDrop={(e) => onDrop(e, 'phase', { phaseId: phase.id })}
      className={`border-2 rounded-lg overflow-hidden ${statusColor}`}
    >
      {/* Phase Header */}
      <div 
        className="flex items-center gap-2 p-3 cursor-pointer"
        onClick={onToggleExpand}
      >
        <span className="text-gray-500">
          {isExpanded ? '▼' : '▶'}
        </span>
        
        {isEditing ? (
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onBlur={() => {
              onEditPhase(phase.id, { title: editTitle });
              setIsEditing(false);
            }}
            onClick={(e) => e.stopPropagation()}
            className="flex-1 p-1 border rounded"
            autoFocus
          />
        ) : (
          <h4 
            className="flex-1 font-medium text-gray-900"
            onDoubleClick={(e) => {
              e.stopPropagation();
              setIsEditing(true);
            }}
          >
            {phase.title}
          </h4>
        )}
        
        {/* Progress */}
        <span className="text-sm text-gray-600">
          {completedSteps}/{totalSteps}
        </span>
        
        {/* Status Badge */}
        <span className={`
          px-2 py-0.5 text-xs rounded capitalize
          ${phase.status === 'completed' ? 'bg-green-200 text-green-800' : ''}
          ${phase.status === 'in_progress' ? 'bg-blue-200 text-blue-800' : ''}
          ${phase.status === 'approved' ? 'bg-blue-100 text-blue-700' : ''}
          ${phase.status === 'draft' ? 'bg-gray-200 text-gray-700' : ''}
        `}>
          {phase.status?.replace(/_/g, ' ')}
        </span>
        
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDeletePhase(phase.id);
          }}
          className="text-gray-500 hover:text-red-500"
        >
          ×
        </button>
      </div>
      
      {/* Phase Content */}
      {isExpanded && (
        <div className="p-3 pt-0 space-y-2">
          {/* Objective */}
          {phase.objective && (
            <p className="text-sm text-gray-600 italic">
              {phase.objective}
            </p>
          )}
          
          {/* Steps */}
          {phase.steps?.map(step => (
            <StepItem
              key={step.id}
              step={step}
              phaseId={phase.id}
              onEdit={onEditStep}
              onDelete={onDeleteStep}
              onDragStart={onDragStart}
              onDragOver={onDragOver}
              onDrop={onDrop}
            />
          ))}
          
          {/* Add Step Button */}
          <button
            onClick={() => onAddStep(phase.id)}
            className="w-full p-2 text-sm text-gray-500 border border-dashed rounded hover:border-gray-400 hover:text-gray-700"
          >
            + Add Step
          </button>
          
          {/* Hypotheses */}
          {phase.hypothesis_ids?.length > 0 && (
            <div className="mt-2 pt-2 border-t">
              <span className="text-xs font-medium text-gray-500">
                Hypotheses to test: {phase.hypothesis_ids.length}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function PlanEditor({
  plan,
  onUpdatePlan,
  onApprovePlan,
  readOnly = false,
  className = '',
}) {
  const [expandedPhases, setExpandedPhases] = useState(new Set());
  const [dragData, setDragData] = useState(null);
  
  // Initialize all phases expanded
  React.useEffect(() => {
    if (plan?.phases) {
      setExpandedPhases(new Set(plan.phases.map(p => p.id)));
    }
  }, [plan]);
  
  const handleDragStart = useCallback((e, type, data) => {
    setDragData({ type, data });
    e.dataTransfer.effectAllowed = 'move';
  }, []);
  
  const handleDragOver = useCallback((e, type) => {
    e.preventDefault();
  }, []);
  
  const handleDrop = useCallback((e, targetType, targetData) => {
    e.preventDefault();
    if (!dragData) return;
    
    // Handle reordering
    onUpdatePlan?.({
      type: 'reorder',
      source: dragData,
      target: { type: targetType, data: targetData },
    });
    
    setDragData(null);
  }, [dragData, onUpdatePlan]);
  
  const handleEditPhase = useCallback((phaseId, data) => {
    onUpdatePlan?.({
      type: 'edit_phase',
      phaseId,
      data,
    });
  }, [onUpdatePlan]);
  
  const handleEditStep = useCallback((phaseId, stepId, data) => {
    onUpdatePlan?.({
      type: 'edit_step',
      phaseId,
      stepId,
      data,
    });
  }, [onUpdatePlan]);
  
  const handleDeletePhase = useCallback((phaseId) => {
    if (window.confirm('Delete this phase?')) {
      onUpdatePlan?.({
        type: 'delete_phase',
        phaseId,
      });
    }
  }, [onUpdatePlan]);
  
  const handleDeleteStep = useCallback((phaseId, stepId) => {
    onUpdatePlan?.({
      type: 'delete_step',
      phaseId,
      stepId,
    });
  }, [onUpdatePlan]);
  
  const handleAddPhase = useCallback(() => {
    onUpdatePlan?.({
      type: 'add_phase',
      data: {
        title: 'New Phase',
        objective: '',
        steps: [],
      },
    });
  }, [onUpdatePlan]);
  
  const handleAddStep = useCallback((phaseId) => {
    onUpdatePlan?.({
      type: 'add_step',
      phaseId,
      data: {
        title: 'New Step',
        step_type: 'analysis',
      },
    });
  }, [onUpdatePlan]);
  
  const togglePhaseExpand = useCallback((phaseId) => {
    setExpandedPhases(prev => {
      const next = new Set(prev);
      if (next.has(phaseId)) {
        next.delete(phaseId);
      } else {
        next.add(phaseId);
      }
      return next;
    });
  }, []);
  
  if (!plan) {
    return (
      <div className={`p-8 text-center text-gray-500 ${className}`}>
        No plan available
      </div>
    );
  }
  
  const isApproved = plan.status === 'approved' || plan.status === 'in_progress';
  
  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div>
          <h3 className="font-semibold text-gray-900">{plan.title || 'Investigation Plan'}</h3>
          <p className="text-sm text-gray-500">
            {plan.phases?.length || 0} phases • v{plan.version}
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          {/* Status */}
          <span className={`
            px-3 py-1 text-sm rounded-full capitalize
            ${plan.status === 'approved' ? 'bg-green-100 text-green-700' : ''}
            ${plan.status === 'draft' ? 'bg-gray-100 text-gray-700' : ''}
            ${plan.status === 'pending_approval' ? 'bg-yellow-100 text-yellow-700' : ''}
          `}>
            {plan.status?.replace(/_/g, ' ')}
          </span>
          
          {/* Approve Button */}
          {!isApproved && !readOnly && (
            <button
              onClick={() => onApprovePlan?.()}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              Approve Plan
            </button>
          )}
        </div>
      </div>
      
      {/* Hypotheses Summary */}
      <div className="px-4 py-2 bg-gray-50 border-b">
        <div className="text-sm">
          <span className="font-medium text-gray-700">Null Hypothesis:</span>
          <span className="ml-2 text-gray-600">{plan.null_hypothesis || 'Not defined'}</span>
        </div>
        {plan.alternative_hypotheses?.length > 0 && (
          <div className="text-sm mt-1">
            <span className="font-medium text-gray-700">Alternatives:</span>
            <span className="ml-2 text-gray-600">
              {plan.alternative_hypotheses.join(', ')}
            </span>
          </div>
        )}
      </div>
      
      {/* Phases */}
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {plan.phases?.map(phase => (
          <PhaseItem
            key={phase.id}
            phase={phase}
            onEditPhase={handleEditPhase}
            onEditStep={handleEditStep}
            onDeletePhase={handleDeletePhase}
            onDeleteStep={handleDeleteStep}
            onAddStep={handleAddStep}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            isExpanded={expandedPhases.has(phase.id)}
            onToggleExpand={() => togglePhaseExpand(phase.id)}
          />
        ))}
        
        {/* Add Phase Button */}
        {!readOnly && (
          <button
            onClick={handleAddPhase}
            className="w-full p-4 text-gray-500 border-2 border-dashed rounded-lg hover:border-gray-400 hover:text-gray-700"
          >
            + Add Phase
          </button>
        )}
      </div>
      
      {/* Progress Footer */}
      <div className="px-4 py-2 border-t bg-gray-50">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">
            Overall Progress: {((plan.progress || 0) * 100).toFixed(0)}%
          </span>
          <div className="w-48 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className="h-full bg-blue-500"
              style={{ width: `${(plan.progress || 0) * 100}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default PlanEditor;
