/**
 * TypeScript types for Deep Research Investigation
 */

export interface Message {
  id: string;
  sender: 'user' | 'ai' | 'system';
  content: string;
  type: 'text' | 'question' | 'hypothesis' | 'progress' | 'finding' | 'error';
  timestamp: string;
  metadata?: any;
}

export interface Question {
  id: string;
  question: string;
  priority: 'high' | 'medium' | 'low';
  choices?: string[];
  allowFreeform?: boolean;
  answered?: boolean;
  answer?: string;
}

export interface Hypothesis {
  hypothesis_id?: string;
  hypothesis_name: string;
  description?: string;
  required_evidence?: string[];
  confidence_threshold?: number;
  priority: 'high' | 'medium' | 'low';
  temporal_constraints?: string;
  actor_constraints?: string;
  target_constraints?: string;
}

export type PlanHypothesis = Hypothesis | string;

export interface InvestigationPlan {
  investigation_id: string;
  title: string;
  null_hypothesis: PlanHypothesis;
  alternative_hypotheses: PlanHypothesis[];
  phases: PlanPhase[];
  status: 'draft' | 'pending_approval' | 'approved' | 'executing' | 'in_progress' | 'complete' | 'completed' | 'failed';
  id?: string;
  version?: number;
}

export interface PlanPhase {
  phase_id?: string;
  id?: string;
  name?: string;
  title?: string;
  description?: string;
  objective?: string;
  steps: PlanStep[];
  estimated_duration?: string;
  status: 'pending' | 'in_progress' | 'complete' | 'completed' | 'failed' | 'draft' | 'approved';
}

export interface PlanStep {
  step_id?: string;
  id?: string;
  name?: string;
  title?: string;
  description?: string;
  type: string;
  status: 'pending' | 'in_progress' | 'complete' | 'completed' | 'failed' | 'draft' | 'approved';
}

export interface Finding {
  id?: string;
  type?: string;
  tool_id?: string;
  hypothesis_id?: string;
  hypothesis_name?: string;
  verdict?: 'confirmed' | 'rejected' | 'inconclusive' | 'pending';
  confidence?: number;
  evidence_for?: string[];
  evidence_against?: string[];
  summary?: string;
  details?: any;
  timestamp?: string;
  confidence_score?: number;
  data?: Record<string, unknown>;
}

export interface Evidence {
  evidence_id: string;
  evidence_type: string;
  description: string;
  timestamp: string;
  source_log: string;
  hash: string;
  data: any;
  severity?: string;
  confidence_score?: number;
  verified?: boolean;
}

export interface ProgressUpdate {
  phase: string;
  progress: number;
  message: string;
  current_task?: string;
  estimated_time_remaining?: string;
  sub_tasks?: SubTaskProgress[];
}

export interface SubTaskProgress {
  task_id: string;
  name: string;
  progress: number;
  status: 'pending' | 'in_progress' | 'complete' | 'failed';
}

export interface ReportProgress {
  progress: number;
  current_page: number;
  total_pages: number;
  current_section: string;
  status: string;
  pages_complete: number;
  sections: ReportSection[] | Record<string, ReportSection>;
  alignment_score: number;
  completeness_score: number;
  branch?: string;
  changes?: string[];
  errors: any[];
  warnings: any[];
}

export interface ReportSection {
  id?: string;
  section_id: string;
  type: string;
  title: string;
  status: 'pending' | 'writing' | 'complete' | 'completed' | 'in_progress';
  progress?: number;
  pages?: number[];
  updated_at?: string;
  word_count?: number;
  page_count: number;
  evidence_count?: number;
}

export interface ReportVersion {
  version_id: string;
  report_id?: string;
  document_id?: string;
  parent_version?: string | null;
  created_at: string;
  created_by: string;
  message?: string;
  commit_message?: string;
  branch?: string;
  changes: Array<string | VersionChange>;
  quality_metrics?: {
    alignment_score: number;
    completeness_score: number;
  };
  alignment_score?: number;
  completeness_score?: number;
}

export interface VersionChange {
  change_type: string;
  target_element: string;
  before_value?: any;
  after_value?: any;
}

export type ActiveTab = 'chat' | 'progress' | 'plan' | 'evidence' | 'findings' | 'report' | 'history';

export type PanelState = 'collapsed' | 'normal' | 'expanded' | 'fullscreen';
