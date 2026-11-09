/**
 * Module 11 – Analytics & Evaluation TypeScript Types
 * ====================================================
 * All analytics metrics are aggregated statistics.
 * No personal data, biometric data, or PII is included.
 */

export type TimeRange = 'today' | '7d' | '30d' | 'custom';
export type ModelStatus = 'TESTING' | 'ACTIVE' | 'RETIRED';
export type DatasetCategory = 'TRAINING' | 'VALIDATION' | 'TEST';
export type EvalRunStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
export type DriftSeverity = 'INFO' | 'WARNING' | 'CRITICAL';

// ─── System Health ──────────────────────────────────────────────────────────

export interface SystemHealthResponse {
  cameras_online: number;
  cameras_offline: number;
  cameras_error: number;
  frames_received: number;
  frames_processed: number;
  frames_dropped: number;
  avg_fps: number | null;
  avg_latency_ms: number | null;
  api_response_time_ms: number | null;
  queue_size: number | null;
  db_healthy: boolean;
}

// ─── Camera Analytics ────────────────────────────────────────────────────────

export interface CameraAnalyticsItem {
  camera_id: number;
  camera_name: string;
  frames_received: number;
  frames_processed: number;
  frames_dropped: number;
  avg_fps: number | null;
  avg_latency_ms: number | null;
  detections: number;
  face_candidates: number;
  stream_uptime_pct: number | null;
  error_count: number;
}

// ─── Pipeline ────────────────────────────────────────────────────────────────

export interface PipelineStageMetrics {
  stage_name: string;
  input_count: number;
  successful_count: number;
  failed_count: number;
  avg_latency_ms: number | null;
  error_count: number;
}

// ─── Face Quality ────────────────────────────────────────────────────────────

export interface FaceQualityBreakdown {
  faces_received: number;
  faces_passed: number;
  faces_rejected: number;
  avg_quality_score: number | null;
  avg_processing_time_ms: number | null;
  rejection_reasons: Record<string, number>;
}

// ─── Matching ────────────────────────────────────────────────────────────────

export interface MatchingMetricsResponse {
  queries_processed: number;
  candidates_retrieved: number;
  possible_matches: number;
  no_candidate_results: number;
  avg_search_latency_ms: number | null;
  top1_accuracy: number | null;
  top5_retrieval_rate: number | null;
  fmr: number | null;
  fnmr: number | null;
}

// ─── Reviews ─────────────────────────────────────────────────────────────────

export interface ReviewMetricsResponse {
  reviews_created: number;
  reviews_completed: number;
  pending_reviews: number;
  confirmed_for_action: number;
  rejected: number;
  need_more_evidence: number;
  avg_review_time_seconds: number | null;
}

// ─── Alerts ──────────────────────────────────────────────────────────────────

export interface AlertMetricsResponse {
  alerts_created: number;
  alerts_acknowledged: number;
  alerts_in_progress: number;
  alerts_resolved: number;
  alerts_failed: number;
  avg_acknowledgment_time_seconds: number | null;
  avg_notification_latency_ms: number | null;
  notification_failures: number;
}

// ─── Evidence ────────────────────────────────────────────────────────────────

export interface EvidenceMetricsResponse {
  evidence_created: number;
  images: number;
  videos: number;
  documents: number;
  integrity_checks: number;
  integrity_failures: number;
  evidence_access_events: number;
  evidence_exports: number;
  archived_evidence: number;
  total_size_bytes: number;
}

// ─── Overview ────────────────────────────────────────────────────────────────

export interface OverviewResponse {
  system: SystemHealthResponse;
  pipeline: PipelineStageMetrics[];
  matching: MatchingMetricsResponse;
  reviews: ReviewMetricsResponse;
  alerts: AlertMetricsResponse;
  evidence: EvidenceMetricsResponse;
  time_range: string;
  generated_at: string;
}

// ─── Model Registry ──────────────────────────────────────────────────────────

export interface ModelRegistryItem {
  id: number;
  model_name: string;
  model_type: string;
  version: string;
  framework: string | null;
  checksum: string | null;
  dataset_version: string | null;
  status: ModelStatus;
  configuration_json: string | null;
  notes: string | null;
  created_at: string;
  deployed_at: string | null;
  retired_at: string | null;
}

export interface ModelRegistryCreate {
  model_name: string;
  model_type: string;
  version: string;
  framework?: string;
  checksum?: string;
  dataset_version?: string;
  configuration_json?: string;
  notes?: string;
}

// ─── Dataset Registry ────────────────────────────────────────────────────────

export interface DatasetRegistryItem {
  id: number;
  dataset_name: string;
  dataset_version: string;
  category: DatasetCategory;
  source_type: string;
  sample_count: number | null;
  notes: string | null;
  creation_date: string | null;
  registered_at: string;
}

export interface DatasetRegistryCreate {
  dataset_name: string;
  dataset_version: string;
  category: DatasetCategory;
  source_type: string;
  sample_count?: number;
  notes?: string;
  creation_date?: string;
}

// ─── Evaluation Runs ─────────────────────────────────────────────────────────

export interface EvaluationRunItem {
  id: number;
  run_id: string;
  run_name: string | null;
  model_name: string;
  model_version: string;
  dataset_name: string;
  dataset_version: string;
  threshold: number | null;
  status: EvalRunStatus;
  notes: string | null;
  justification: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface EvaluationRunCreate {
  run_name?: string;
  model_name: string;
  model_version: string;
  dataset_name: string;
  dataset_version: string;
  threshold?: number;
  notes?: string;
  justification?: string;
  dataset_registry_id?: number;
  model_registry_id?: number;
}

// ─── Evaluation Results ──────────────────────────────────────────────────────

export interface EvaluationResultItem {
  id: number;
  run_id: string;
  true_positives: number;
  false_positives: number;
  true_negatives: number;
  false_negatives: number;
  precision: number | null;
  recall: number | null;
  f1_score: number | null;
  false_match_rate: number | null;
  false_non_match_rate: number | null;
  top1_accuracy: number | null;
  top5_retrieval_rate: number | null;
  average_similarity_score: number | null;
  average_latency_ms: number | null;
  evaluated_at: string;
  disclaimer: string;
}

// ─── Threshold Evaluation ────────────────────────────────────────────────────

export interface ThresholdEvaluationResult {
  threshold: number;
  time_range: string;
  total_matches_evaluated: number;
  above_threshold: number;
  below_threshold: number;
  confirmed_above: number;
  rejected_above: number;
  confirmed_below: number;
  rejected_below: number;
  estimated_fmr: number | null;
  estimated_fnmr: number | null;
  estimated_precision: number | null;
  estimated_recall: number | null;
}

// ─── Drift Events ────────────────────────────────────────────────────────────

export interface DriftEventItem {
  id: number;
  event_type: string;
  metric_name: string;
  baseline_value: number | null;
  current_value: number | null;
  deviation: number | null;
  severity: DriftSeverity;
  description: string | null;
  is_acknowledged: boolean;
  detected_at: string;
  acknowledged_at: string | null;
}

// ─── Analytics Alerts (Technical) ───────────────────────────────────────────

export interface AnalyticsAlertItem {
  id: number;
  alert_type: string;
  severity: string;
  title: string;
  description: string | null;
  is_resolved: boolean;
  is_acknowledged: boolean;
  detected_at: string;
  resolved_at: string | null;
  acknowledged_at: string | null;
}

// ─── Score Distribution ──────────────────────────────────────────────────────

export interface ScoreDistributionResponse {
  genuine_scores: number[];
  non_match_scores: number[];
  threshold: number;
  total_genuine: number;
  total_non_match: number;
  avg_genuine_score: number | null;
  avg_non_match_score: number | null;
}
