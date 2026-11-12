/**
 * Plan Tab - Investigation plan viewer and editor
 */

'use client';

import { useInvestigationStore } from '@operation-room/stores/investigationStore';
import { useCallback, useEffect, useMemo, useState } from 'react';

type Priority = 'high' | 'medium' | 'low';

type NormalizedHypothesis = {
  id: string;
  name: string;
  description: string;
  priority: Priority;
  requiredEvidence: string[];
  confidenceThreshold: number;
  temporalConstraints?: string;
  actorConstraints?: string;
  targetConstraints?: string;
};

type NormalizedStep = {
  id: string;
  name: string;
  status: string;
};

type NormalizedPhase = {
  id: string;
  name: string;
  description: string;
  status: string;
  estimatedDuration?: string;
  steps: NormalizedStep[];
};

type NormalizedPlan = {
  title: string;
  status: string;
  nullHypothesis: string;
  alternativeHypotheses: NormalizedHypothesis[];
  phases: NormalizedPhase[];
  version?: number;
};

const APPROVED_PLAN_STATUSES = new Set([
  'approved',
  'executing',
  'in_progress',
  'complete',
  'completed',
]);

function normalizeHypothesis(raw: unknown, index: number): NormalizedHypothesis {
  if (typeof raw === 'string') {
    return {
      id: `hyp-${index + 1}`,
      name: raw,
      description: '',
      priority: 'medium',
      requiredEvidence: [],
      confidenceThreshold: 0.5,
    };
  }

  const value = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};

  const priorityRaw = typeof value.priority === 'string' ? value.priority.toLowerCase() : 'medium';
  const priority: Priority = priorityRaw === 'high' || priorityRaw === 'low' ? priorityRaw : 'medium';

  const requiredEvidence = Array.isArray(value.required_evidence)
    ? value.required_evidence.filter((item): item is string => typeof item === 'string')
    : [];

  const confidenceThreshold = typeof value.confidence_threshold === 'number'
    ? value.confidence_threshold
    : 0.5;

  return {
    id: typeof value.hypothesis_id === 'string' ? value.hypothesis_id : `hyp-${index + 1}`,
    name: typeof value.hypothesis_name === 'string' && value.hypothesis_name
      ? value.hypothesis_name
      : `Hypothesis ${index + 1}`,
    description: typeof value.description === 'string' ? value.description : '',
    priority,
    requiredEvidence,
    confidenceThreshold,
    temporalConstraints: typeof value.temporal_constraints === 'string' ? value.temporal_constraints : undefined,
    actorConstraints: typeof value.actor_constraints === 'string' ? value.actor_constraints : undefined,
    targetConstraints: typeof value.target_constraints === 'string' ? value.target_constraints : undefined,
  };
}

function normalizeNullHypothesis(raw: unknown): string {
  if (typeof raw === 'string' && raw.trim()) {
    return raw.trim();
  }

  if (raw && typeof raw === 'object') {
    const value = raw as Record<string, unknown>;
    if (typeof value.hypothesis_name === 'string' && value.hypothesis_name.trim()) {
      if (typeof value.description === 'string' && value.description.trim()) {
        return `${value.hypothesis_name.trim()} - ${value.description.trim()}`;
      }
      return value.hypothesis_name.trim();
    }
  }

  return 'No suspicious activity occurred.';
}

function normalizePlan(rawPlan: unknown): NormalizedPlan {
  const plan = rawPlan && typeof rawPlan === 'object' ? (rawPlan as Record<string, unknown>) : {};

  const title = typeof plan.title === 'string' && plan.title.trim()
    ? plan.title.trim()
    : 'Investigation Plan';

  const status = typeof plan.status === 'string' ? plan.status : 'draft';
  const nullHypothesis = normalizeNullHypothesis(plan.null_hypothesis);

  const alternativeHypothesesRaw = Array.isArray(plan.alternative_hypotheses)
    ? plan.alternative_hypotheses
    : [];

  const alternativeHypotheses = alternativeHypothesesRaw.map((hypothesis, index) =>
    normalizeHypothesis(hypothesis, index)
  );

  const phasesRaw = Array.isArray(plan.phases) ? plan.phases : [];
  const phases = phasesRaw.map((phaseRaw, phaseIndex) => {
    const phase = phaseRaw && typeof phaseRaw === 'object'
      ? (phaseRaw as Record<string, unknown>)
      : {};

    const phaseStepsRaw = Array.isArray(phase.steps) ? phase.steps : [];
    const steps = phaseStepsRaw.map((stepRaw, stepIndex) => {
      const step = stepRaw && typeof stepRaw === 'object'
        ? (stepRaw as Record<string, unknown>)
        : {};

      return {
        id: typeof step.step_id === 'string'
          ? step.step_id
          : (typeof step.id === 'string' ? step.id : `step-${phaseIndex + 1}-${stepIndex + 1}`),
        name: typeof step.name === 'string'
          ? step.name
          : (typeof step.title === 'string' ? step.title : `Step ${stepIndex + 1}`),
        status: typeof step.status === 'string' ? step.status : 'pending',
      };
    });

    return {
      id: typeof phase.phase_id === 'string'
        ? phase.phase_id
        : (typeof phase.id === 'string' ? phase.id : `phase-${phaseIndex + 1}`),
      name: typeof phase.name === 'string'
        ? phase.name
        : (typeof phase.title === 'string' ? phase.title : `Phase ${phaseIndex + 1}`),
      description: typeof phase.description === 'string'
        ? phase.description
        : (typeof phase.objective === 'string' ? phase.objective : ''),
      status: typeof phase.status === 'string' ? phase.status : 'pending',
      estimatedDuration: typeof phase.estimated_duration === 'string' ? phase.estimated_duration : undefined,
      steps,
    };
  });

  return {
    title,
    status,
    nullHypothesis,
    alternativeHypotheses,
    phases,
    version: typeof plan.version === 'number' ? plan.version : undefined,
  };
}

export default function PlanTab() {
  const {
    plan,
    planApproved,
    investigationId,
    approvePlan: approvePlanStore,
    setPlan,
  } = useInvestigationStore();

  const [editMode, setEditMode] = useState(false);
  const [approvalComments, setApprovalComments] = useState('');
  const [showApprovalDialog, setShowApprovalDialog] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [isLoadingPlan, setIsLoadingPlan] = useState(false);
  const [isApplyingModification, setIsApplyingModification] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [newHypothesis, setNewHypothesis] = useState('');
  const [newPhaseTitle, setNewPhaseTitle] = useState('');
  const [newPhaseObjective, setNewPhaseObjective] = useState('');

  const normalizedPlan = useMemo(() => (plan ? normalizePlan(plan) : null), [plan]);
  const effectivePlanApproved = planApproved || (normalizedPlan ? APPROVED_PLAN_STATUSES.has(normalizedPlan.status) : false);

  const addSystemMessage = useCallback((content: string, type: 'text' | 'error' = 'text') => {
    useInvestigationStore.getState().addChatMessage({
      id: `plan-msg-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
      sender: 'system',
      content,
      type,
      timestamp: new Date().toISOString(),
    });
  }, []);

  const loadPlan = useCallback(async () => {
    if (!investigationId) {
      return;
    }

    setIsLoadingPlan(true);
    setPlanError(null);

    try {
      const response = await fetch(`/api/deep-research/investigations/${investigationId}/plan`);
      if (!response.ok) {
        throw new Error(`Plan load failed (${response.status})`);
      }
      const data = await response.json();
      setPlan(data);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setPlanError(message);
    } finally {
      setIsLoadingPlan(false);
    }
  }, [investigationId, setPlan]);

  useEffect(() => {
    if (!investigationId || plan) {
      return;
    }
    loadPlan();
  }, [investigationId, plan, loadPlan]);

  const applyModification = useCallback(async (
    modificationType: string,
    data: Record<string, unknown>,
    targetId?: string,
  ) => {
    if (!investigationId || isApplyingModification) {
      return;
    }

    setIsApplyingModification(true);
    setPlanError(null);

    try {
      const response = await fetch(`/api/deep-research/investigations/${investigationId}/plan/modify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          modification_type: modificationType,
          target_id: targetId,
          data,
        }),
      });

      if (!response.ok) {
        throw new Error(`Modification failed (${response.status})`);
      }

      const payload = await response.json();
      if (payload.plan) {
        setPlan(payload.plan);
      } else {
        await loadPlan();
      }

      addSystemMessage(`✅ Plan updated: ${modificationType.replace(/_/g, ' ')}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setPlanError(message);
      addSystemMessage(`❌ Failed to update plan: ${message}`, 'error');
    } finally {
      setIsApplyingModification(false);
    }
  }, [addSystemMessage, investigationId, isApplyingModification, loadPlan, setPlan]);

  const handleApprove = async () => {
    if (!investigationId || isApproving) {
      return;
    }

    setIsApproving(true);

    try {
      const response = await fetch(`/api/deep-research/investigations/${investigationId}/plan/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approver: 'investigator',
          comments: approvalComments || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error(`Approval failed (${response.status})`);
      }

      approvePlanStore();
      setShowApprovalDialog(false);
      setEditMode(false);
      await loadPlan();

      addSystemMessage('✅ Plan approved! Investigation starting...');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      addSystemMessage(`❌ Failed to approve plan: ${message}`, 'error');
    } finally {
      setIsApproving(false);
    }
  };

  const handleAddHypothesis = () => {
    const hypothesis = newHypothesis.trim();
    if (!hypothesis) {
      return;
    }

    applyModification('add_hypothesis', { hypothesis }, 'plan');
    setNewHypothesis('');
  };

  const handleRemoveHypothesis = (hypothesis: string) => {
    applyModification('remove_hypothesis', { hypothesis }, 'plan');
  };

  const handleAddPhase = () => {
    const title = newPhaseTitle.trim();
    if (!title) {
      return;
    }

    applyModification('add_phase', {
      title,
      objective: newPhaseObjective.trim() || title,
      description: newPhaseObjective.trim() || '',
    }, 'plan');

    setNewPhaseTitle('');
    setNewPhaseObjective('');
  };

  const handleRemovePhase = (phaseId: string) => {
    applyModification('remove_phase', { phase_id: phaseId }, phaseId);
  };

  if (!normalizedPlan && isLoadingPlan) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50 p-8">
        <div className="text-center">
          <div className="text-4xl mb-3">⏳</div>
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Loading Plan</h3>
          <p className="text-gray-600 max-w-md">Fetching the latest investigation plan from the backend...</p>
        </div>
      </div>
    );
  }

  if (!normalizedPlan) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-50 p-8">
        <div className="text-center">
          <div className="text-6xl mb-4">📋</div>
          <h3 className="text-lg font-semibold text-gray-800 mb-2">
            No Investigation Plan Yet
          </h3>
          <p className="text-gray-600 max-w-md mb-4">
            The AI will generate an investigation plan after analyzing your scenario.
            You will be able to review and approve it here.
          </p>
          {investigationId && (
            <button
              onClick={loadPlan}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors"
            >
              Refresh Plan
            </button>
          )}
          {planError && (
            <div className="mt-3 text-sm text-red-600">{planError}</div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-gray-50">
      <div className={`p-6 border-b ${effectivePlanApproved
          ? 'bg-green-50 border-green-200'
          : 'bg-yellow-50 border-yellow-200'
        }`}>
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-800 mb-1">
              {normalizedPlan.title}
            </h3>
            <div className={`text-sm font-medium ${effectivePlanApproved ? 'text-green-700' : 'text-yellow-700'
              }`}>
              {effectivePlanApproved ? '✅ Approved & Executing' : '⏸️ Awaiting Your Approval'}
            </div>
            <div className="text-xs text-gray-600 mt-1">
              Status: <span className="font-medium capitalize">{normalizedPlan.status.replace(/_/g, ' ')}</span>
              {typeof normalizedPlan.version === 'number' && (
                <span> • Version {normalizedPlan.version}</span>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={loadPlan}
              disabled={isLoadingPlan}
              className="px-3 py-2 border border-gray-300 bg-white rounded-lg hover:bg-gray-50 transition-colors text-sm"
            >
              {isLoadingPlan ? '⏳ Refreshing...' : '🔄 Refresh'}
            </button>

            {!effectivePlanApproved && (
              <>
                <button
                  onClick={() => setShowApprovalDialog(true)}
                  disabled={isApplyingModification}
                  className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-green-400 transition-colors font-medium"
                >
                  ✅ Approve & Execute
                </button>
                <button
                  onClick={() => setEditMode((value) => !value)}
                  className="px-4 py-2 border border-gray-300 bg-white rounded-lg hover:bg-gray-50 transition-colors"
                >
                  {editMode ? 'Done Editing' : '✏️ Modify Plan'}
                </button>
              </>
            )}
          </div>
        </div>

        {planError && (
          <div className="text-sm text-red-600">{planError}</div>
        )}
      </div>

      <div className="p-6 bg-white border-b border-gray-200">
        <h4 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <span className="text-lg">🎯</span>
          Null Hypothesis (H0)
        </h4>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-gray-800">
          {normalizedPlan.nullHypothesis}
        </div>
      </div>

      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-semibold text-gray-700 flex items-center gap-2">
            <span className="text-lg">💡</span>
            Alternative Hypotheses ({normalizedPlan.alternativeHypotheses.length})
          </h4>
        </div>

        {editMode && !effectivePlanApproved && (
          <div className="mb-4 bg-white border border-gray-200 rounded-lg p-3 flex gap-2">
            <input
              value={newHypothesis}
              onChange={(event) => setNewHypothesis(event.target.value)}
              placeholder="Add hypothesis statement..."
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              onClick={handleAddHypothesis}
              disabled={isApplyingModification || !newHypothesis.trim()}
              className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-300 transition-colors text-sm"
            >
              Add
            </button>
          </div>
        )}

        {normalizedPlan.alternativeHypotheses.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-lg p-4 text-sm text-gray-600">
            No alternative hypotheses were generated yet.
          </div>
        ) : (
          <div className="space-y-4">
            {normalizedPlan.alternativeHypotheses.map((hypothesis, index) => (
              <HypothesisCard
                key={hypothesis.id}
                hypothesis={hypothesis}
                index={index}
                editMode={editMode && !effectivePlanApproved}
                onRemove={() => handleRemoveHypothesis(hypothesis.name)}
              />
            ))}
          </div>
        )}
      </div>

      <div className="p-6 bg-white border-t border-gray-200">
        <h4 className="font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <span className="text-lg">⚙️</span>
          Execution Phases ({normalizedPlan.phases.length})
        </h4>

        {editMode && !effectivePlanApproved && (
          <div className="mb-4 bg-gray-50 border border-gray-200 rounded-lg p-3 space-y-2">
            <input
              value={newPhaseTitle}
              onChange={(event) => setNewPhaseTitle(event.target.value)}
              placeholder="New phase title"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <input
              value={newPhaseObjective}
              onChange={(event) => setNewPhaseObjective(event.target.value)}
              placeholder="Phase objective (optional)"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              onClick={handleAddPhase}
              disabled={isApplyingModification || !newPhaseTitle.trim()}
              className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-blue-300 transition-colors text-sm"
            >
              Add Phase
            </button>
          </div>
        )}

        {normalizedPlan.phases.length === 0 ? (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-600">
            No phases defined yet.
          </div>
        ) : (
          <div className="space-y-3">
            {normalizedPlan.phases.map((phase, index) => (
              <div key={phase.id} className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div>
                    <div className="font-medium text-gray-800">
                      Phase {index + 1}: {phase.name}
                    </div>
                    <div className="text-xs text-gray-500 capitalize mt-1">
                      Status: {phase.status.replace(/_/g, ' ')}
                      {phase.estimatedDuration && <span> • Est. {phase.estimatedDuration}</span>}
                    </div>
                  </div>

                  {editMode && !effectivePlanApproved && (
                    <button
                      onClick={() => handleRemovePhase(phase.id)}
                      className="text-xs px-2 py-1 border border-red-300 text-red-700 rounded hover:bg-red-50 transition-colors"
                    >
                      Remove
                    </button>
                  )}
                </div>

                {phase.description && (
                  <div className="text-sm text-gray-600 mb-3">{phase.description}</div>
                )}

                {phase.steps.length > 0 && (
                  <div className="pl-4 space-y-1">
                    {phase.steps.map((step) => (
                      <div key={step.id} className="text-sm text-gray-600 flex items-center gap-2">
                        <span className="text-gray-400">•</span>
                        <span>{step.name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {editMode && !effectivePlanApproved && (
        <div className="p-6 bg-white border-t border-gray-200">
          <div className="text-sm text-gray-600">
            Changes are applied immediately to the backend plan.
            {isApplyingModification && <span className="ml-2 text-blue-700">Saving...</span>}
          </div>
        </div>
      )}

      {showApprovalDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
            <div className="p-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">
                Approve Investigation Plan?
              </h3>

              <p className="text-gray-600 mb-4">
                Once approved, the AI will begin executing this investigation plan.
              </p>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Comments (optional)
                </label>
                <textarea
                  value={approvalComments}
                  onChange={(event) => setApprovalComments(event.target.value)}
                  placeholder="Any specific instructions or notes..."
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div className="flex gap-3">
                <button
                  onClick={handleApprove}
                  disabled={isApproving}
                  className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium disabled:bg-green-400"
                >
                  {isApproving ? '⏳ Approving...' : '✅ Approve & Start'}
                </button>
                <button
                  onClick={() => setShowApprovalDialog(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function HypothesisCard({
  hypothesis,
  index,
  editMode,
  onRemove,
}: {
  hypothesis: NormalizedHypothesis;
  index: number;
  editMode: boolean;
  onRemove: () => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getPriorityBadge = (priority: Priority) => {
    const colors = {
      high: 'bg-red-100 text-red-800 border-red-300',
      medium: 'bg-blue-100 text-blue-800 border-blue-300',
      low: 'bg-gray-100 text-gray-700 border-gray-300',
    };
    return colors[priority];
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className="font-semibold text-gray-800">
              H{index + 1}: {hypothesis.name}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${getPriorityBadge(hypothesis.priority)}`}>
              {hypothesis.priority.toUpperCase()}
            </span>
          </div>
          {hypothesis.description && (
            <div className="text-sm text-gray-600">
              {hypothesis.description}
            </div>
          )}
        </div>

        {editMode && (
          <div className="flex gap-2 ml-4">
            <button
              onClick={onRemove}
              className="text-red-600 hover:text-red-800 text-sm"
              title="Remove hypothesis"
            >
              🗑️
            </button>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-gray-600">Confidence Threshold:</span>
        <span className="text-sm font-semibold text-blue-700">
          {(hypothesis.confidenceThreshold * 100).toFixed(0)}%
        </span>
      </div>

      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1"
      >
        {isExpanded ? '▼' : '▶'}
        {isExpanded ? 'Hide' : 'Show'} Details
      </button>

      {isExpanded && (
        <div className="mt-3 pt-3 border-t border-gray-200 space-y-3">
          {hypothesis.requiredEvidence.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-700 mb-2">
                Required Evidence ({hypothesis.requiredEvidence.length})
              </div>
              <div className="flex flex-wrap gap-2">
                {hypothesis.requiredEvidence.map((evidence) => (
                  <span
                    key={evidence}
                    className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded border border-blue-200"
                  >
                    {evidence}
                  </span>
                ))}
              </div>
            </div>
          )}

          {(hypothesis.temporalConstraints || hypothesis.actorConstraints || hypothesis.targetConstraints) && (
            <div>
              <div className="text-xs font-semibold text-gray-700 mb-2">Constraints</div>
              <div className="space-y-1 text-xs text-gray-600">
                {hypothesis.temporalConstraints && <div>• Temporal: {hypothesis.temporalConstraints}</div>}
                {hypothesis.actorConstraints && <div>• Actor: {hypothesis.actorConstraints}</div>}
                {hypothesis.targetConstraints && <div>• Target: {hypothesis.targetConstraints}</div>}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}