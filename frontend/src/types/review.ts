// Module 8 – TypeScript Types for Human Verification & Investigation Dashboard
// AI Safety: Similarity scores are algorithmic signals ONLY. Never identity assertions.

export type ReviewStatus =
  | 'PENDING_REVIEW'
  | 'UNDER_REVIEW'
  | 'CONFIRMED_FOR_ACTION'
  | 'REJECTED'
  | 'NEED_MORE_EVIDENCE';

export type ReviewDecision =
  | 'CONFIRM_FOR_ACTION'
  | 'REJECTED'
  | 'NEED_MORE_EVIDENCE';

export type CaseCategory = 'MISSING' | 'WANTED';

export type TaskStatus = 'OPEN' | 'ASSIGNED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
export type TaskPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';
export type EvidenceRequestType =
  | 'ADDITIONAL_OBSERVATIONS'
  | 'ADDITIONAL_CAMERA_FOOTAGE'
  | 'DIFFERENT_TIME_INTERVAL'
  | 'ADDITIONAL_REFERENCE_IMAGE'
  | 'REASSIGN_REVIEWER';

export const SIMILARITY_DISCLAIMER =
  'This score is an algorithmic similarity signal and does not independently establish identity.';

export interface ReviewEventSummary {
  id: number;
  match_event_id: string;
  case_id: number;
  case_number: string;
  category: CaseCategory;
  similarity_score: number;
  candidate_ranking_score: number;
  rank: number | null;
  decision_state: string;
  status: ReviewStatus;
  assigned_to: number | null;
  camera_location: string | null;
  created_at: string;
  updated_at: string;
  similarity_score_disclaimer: string;
  priority: string | null;
  face_quality_label: string | null;
}

export interface ReviewEventDetail extends ReviewEventSummary {
  query_quality_score: number | null;
  camera_id: number | null;
  track_id: string | null;
  model_name: string | null;
  model_version: string | null;
  decision: ReviewDecision | null;
  decision_notes: string | null;
  evidence_request_notes: string | null;
  review_started_at: string | null;
  decision_at: string | null;
  module9_notified: boolean;
  observation_count: number | null;
  detection_quality_score: number | null;
}

export interface ReviewAuditEntry {
  id: number;
  review_event_id: number;
  actor_id: number;
  actor_username: string;
  action: string;
  previous_status: string | null;
  new_status: string | null;
  notes: string | null;
  ip_address: string | null;
  timestamp: string;
}

export interface ReviewHistory {
  review_event_id: number;
  match_event_id: string;
  case_number: string;
  entries: ReviewAuditEntry[];
}

export interface ReviewDashboardStats {
  total_events: number;
  pending_review: number;
  under_review: number;
  confirmed_for_action: number;
  rejected: number;
  need_more_evidence: number;
  missing_category_count: number;
  wanted_category_count: number;
  total_tasks: number;
  open_tasks: number;
  in_progress_tasks: number;
  completed_tasks: number;
  similarity_score_disclaimer: string;
}

export interface InvestigationTask {
  id: number;
  review_event_id: number;
  case_id: number;
  case_number: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  assigned_to: number | null;
  created_by: number;
  due_date: string | null;
  completed_at: string | null;
  resolution_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface NotificationItem {
  id: number;
  event_type: string;
  title: string;
  message: string;
  review_event_id: number | null;
  is_read: boolean;
  created_at: string;
}

export interface TrackObservation {
  observation_id: string;
  timestamp: string;
  quality_label: string;
  quality_score: number;
  frame_number: number | null;
}

export interface TrackHistory {
  track_id: string;
  observations: TrackObservation[];
  best_quality_observation_id: string | null;
}

export interface ReviewDecisionRequest {
  decision: ReviewDecision;
  notes?: string;
}

export interface EvidenceRequestPayload {
  notes: string;
  request_type?: EvidenceRequestType;
  reason?: string;
}

export interface InvestigationTaskCreate {
  review_event_id: number;
  title: string;
  description?: string;
  priority?: TaskPriority;
  assigned_to?: number;
  due_date?: string;
}

export interface Filters {
  status?: ReviewStatus | '';
  category?: CaseCategory | '';
  priority?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
  camera_id?: string;
  assigned_to?: string;
}
