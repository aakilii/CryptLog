/**
 * Investigation Store - Zustand state management for Deep Research
 */

import {
  ActiveTab,
  Evidence,
  Finding,
  InvestigationPlan,
  Message,
  PanelState,
  ProgressUpdate,
  ReportProgress,
  ReportVersion
} from '@operation-room/types/investigation';
import { create } from 'zustand';

interface InvestigationState {
  // Investigation data
  investigationId: string | null;
  caseId: string | null;
  scenario: string | null;

  // Current state
  phase: string;
  progress: number;

  // Chat & messaging
  chatMessages: Message[];
  pendingQuestions: string[];

  // Plan
  plan: InvestigationPlan | null;
  planApproved: boolean;

  // Results
  findings: Finding[];
  evidence: Evidence[];

  // Progress tracking
  progressUpdate: ProgressUpdate | null;

  // Report
  reportProgress: ReportProgress | null;

  // Version history
  versions: ReportVersion[];
  currentVersion: string | null;
  reportDocumentId: string | null;

  // UI state
  activeTab: ActiveTab;
  panelState: PanelState;
  panelWidth: number;

  // Actions
  setInvestigationId: (id: string, caseId?: string, scenario?: string) => void;
  addChatMessage: (message: Message) => void;
  updateProgress: (update: ProgressUpdate) => void;
  setPlan: (plan: InvestigationPlan) => void;
  approvePlan: () => void;
  addFinding: (finding: Finding) => void;
  addEvidence: (evidence: Evidence) => void;
  setReportProgress: (progress: ReportProgress) => void;
  addVersion: (version: ReportVersion) => void;
  setVersions: (versions: ReportVersion[]) => void;
  setReportDocumentId: (docId: string | null) => void;
  markQuestionAnswered: (messageId: string, answer: string, skipped?: boolean) => void;
  setActiveTab: (tab: ActiveTab) => void;
  setPanelState: (state: PanelState) => void;
  setPanelWidth: (width: number) => void;
  reset: () => void;
}

const APPROVED_PLAN_STATUSES = new Set([
  'approved',
  'executing',
  'in_progress',
  'complete',
  'completed',
]);

const sortVersionsByCreatedAt = (versions: ReportVersion[]): ReportVersion[] => {
  return [...versions].sort((a, b) => {
    const aTime = new Date(a.created_at || 0).getTime();
    const bTime = new Date(b.created_at || 0).getTime();
    return bTime - aTime;
  });
};

const normalizeVerdict = (value: unknown): Finding['verdict'] => {
  const normalized = typeof value === 'string' ? value.toLowerCase() : '';
  if (normalized === 'confirmed' || normalized === 'rejected' || normalized === 'inconclusive' || normalized === 'pending') {
    return normalized;
  }
  return 'inconclusive';
};

const normalizeStringList = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string' && item.length > 0);
};

const normalizeFinding = (finding: Finding): Finding => {
  const payload = finding.data && typeof finding.data === 'object'
    ? finding.data as Record<string, unknown>
    : {};

  const confidenceValue = typeof finding.confidence === 'number'
    ? finding.confidence
    : typeof finding.confidence_score === 'number'
      ? finding.confidence_score
      : typeof payload.confidence === 'number'
        ? payload.confidence
        : undefined;

  const hypothesisId = finding.hypothesis_id
    || (typeof payload.hypothesis_id === 'string' ? payload.hypothesis_id : undefined)
    || finding.id
    || `finding-${Date.now()}`;

  const summary = finding.summary
    || (typeof payload.summary === 'string' ? payload.summary : '')
    || (typeof payload.statement === 'string' ? payload.statement : '')
    || (typeof payload.title === 'string' ? payload.title : '')
    || 'Investigation finding update';

  return {
    ...finding,
    id: finding.id || (typeof payload.id === 'string' ? payload.id : undefined) || hypothesisId,
    type: finding.type || (typeof payload.type === 'string' ? payload.type : undefined) || 'finding',
    hypothesis_id: hypothesisId,
    hypothesis_name: finding.hypothesis_name
      || (typeof payload.hypothesis_name === 'string' ? payload.hypothesis_name : undefined)
      || (typeof payload.statement === 'string' ? payload.statement : undefined)
      || 'Hypothesis',
    verdict: normalizeVerdict(finding.verdict || payload.verdict),
    confidence: confidenceValue,
    confidence_score: confidenceValue,
    evidence_for: normalizeStringList(finding.evidence_for || payload.evidence_for),
    evidence_against: normalizeStringList(finding.evidence_against || payload.evidence_against),
    summary,
    details: finding.details || payload,
    timestamp: finding.timestamp || (typeof payload.timestamp === 'string' ? payload.timestamp : undefined) || new Date().toISOString(),
  };
};

const initialState = {
  investigationId: null,
  caseId: null,
  scenario: null,
  phase: 'idle',
  progress: 0,
  chatMessages: [],
  pendingQuestions: [],
  plan: null,
  planApproved: false,
  findings: [],
  evidence: [],
  progressUpdate: null,
  reportProgress: null,
  versions: [],
  currentVersion: null,
  reportDocumentId: null,
  activeTab: 'chat' as ActiveTab,
  panelState: 'normal' as PanelState,
  panelWidth: 40,
};

export const useInvestigationStore = create<InvestigationState>((set) => ({
  ...initialState,

  setInvestigationId: (id, caseId, scenario) => set({
    investigationId: id,
    caseId: caseId || null,
    scenario: scenario || null,
    phase: 'initializing',
  }),

  addChatMessage: (message) => set((state) => ({
    chatMessages: [...state.chatMessages, message],
  })),

  updateProgress: (update) => set({
    progressUpdate: update,
    progress: update.progress,
    phase: update.phase,
  }),

  setPlan: (plan) => set({
    plan,
    planApproved: APPROVED_PLAN_STATUSES.has((plan as any)?.status || ''),
  }),

  approvePlan: () => set({
    planApproved: true,
  }),

  addFinding: (finding) => set((state) => {
    const normalized = normalizeFinding(finding);
    const fingerprint = `${normalized.hypothesis_id || ''}:${normalized.timestamp || ''}:${normalized.verdict || ''}:${normalized.summary || ''}`;

    const exists = state.findings.some((item) => {
      const current = normalizeFinding(item);
      if (normalized.id && current.id && normalized.id === current.id) {
        return true;
      }
      const currentFingerprint = `${current.hypothesis_id || ''}:${current.timestamp || ''}:${current.verdict || ''}:${current.summary || ''}`;
      return currentFingerprint === fingerprint;
    });

    if (exists) {
      return state;
    }

    return {
      findings: [...state.findings, normalized],
    };
  }),

  addEvidence: (evidence) => set((state) => {
    const exists = state.evidence.some((item) => item.evidence_id === evidence.evidence_id);
    if (exists) {
      return state;
    }
    return {
      evidence: [...state.evidence, evidence],
    };
  }),

  setReportProgress: (progress) => set({
    reportProgress: progress,
  }),

  addVersion: (version) => set((state) => {
    const merged = [
      version,
      ...state.versions.filter((item) => item.version_id !== version.version_id),
    ];

    return {
      versions: sortVersionsByCreatedAt(merged),
      currentVersion: version.version_id,
      reportDocumentId: version.document_id || version.report_id || state.reportDocumentId,
    };
  }),

  setVersions: (versions) => set((state) => {
    const sorted = sortVersionsByCreatedAt(versions);
    return {
      versions: sorted,
      currentVersion: sorted.length > 0 ? sorted[0].version_id : state.currentVersion,
    };
  }),

  setReportDocumentId: (docId) => set({
    reportDocumentId: docId,
  }),

  markQuestionAnswered: (messageId, answer, skipped = false) => set((state) => ({
    chatMessages: state.chatMessages.map((message) => (
      message.id === messageId
        ? {
          ...message,
          metadata: {
            ...message.metadata,
            answered: true,
            answer,
            skipped,
          },
        }
        : message
    )),
  })),

  setActiveTab: (tab) => set({
    activeTab: tab,
  }),

  setPanelState: (state) => set({
    panelState: state,
  }),

  setPanelWidth: (width) => set({
    panelWidth: width,
  }),

  reset: () => set(initialState),
}));

// Selectors for derived state
export const useUnreadQuestions = () => useInvestigationStore(
  (state) => state.chatMessages.filter(
    msg => msg.type === 'question' && !msg.metadata?.answered
  ).length
);

export const useConfirmedFindings = () => useInvestigationStore(
  (state) => state.findings.filter(f => f.verdict === 'confirmed').length
);

export const useEvidenceCount = () => useInvestigationStore(
  (state) => state.evidence.length
);
