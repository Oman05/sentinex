export type EvidenceType =
  | 'CCTV_FRAME'
  | 'FACE_CROP'
  | 'REFERENCE_IMAGE'
  | 'REVIEWER_SNAPSHOT'
  | 'EVIDENCE_SNAPSHOT'
  | 'CCTV_CLIP'
  | 'INVESTIGATION_CLIP'
  | 'AI_DETECTION_METADATA'
  | 'AI_TRACKING_METADATA'
  | 'AI_FEATURE_ANALYSIS'
  | 'AI_CANDIDATE_RANKING'
  | 'AI_MODEL_VERSION'
  | 'REVIEW_RECORD'
  | 'REVIEW_NOTE'
  | 'EVIDENCE_REQUEST'
  | 'ALERT_RECORD'
  | 'NOTIFICATION_RECORD'
  | 'ACKNOWLEDGMENT_RECORD'
  | 'CASE_DOCUMENT'
  | 'INVESTIGATION_NOTE'
  | 'AUTHORIZED_REPORT';

export type EvidenceStatus =
  | 'CAPTURED'
  | 'UPLOADED'
  | 'PROCESSING'
  | 'AVAILABLE'
  | 'RESTRICTED'
  | 'FINALIZED'
  | 'ARCHIVED'
  | 'EXPIRED'
  | 'DELETED'
  | 'INTEGRITY_FAILED';

export type EvidenceClassification =
  | 'INTERNAL'
  | 'RESTRICTED'
  | 'SENSITIVE'
  | 'HIGHLY_RESTRICTED';

export type IntegrityStatusType =
  | 'NOT_VERIFIED'
  | 'VERIFIED'
  | 'FAILED'
  | 'PENDING';

export interface EvidenceItem {
  id: number;
  evidence_id: string;
  evidence_type: EvidenceType;
  classification: EvidenceClassification;
  status: EvidenceStatus;
  integrity_status: IntegrityStatusType;
  case_id?: number | null;
  case_number?: string | null;
  match_event_id?: number | null;
  review_event_id?: number | null;
  alert_id?: number | null;
  camera_id?: number | null;
  department_id?: number | null;
  file_name?: string | null;
  file_size?: number | null;
  mime_type?: string | null;
  hash_algorithm: string;
  file_hash?: string | null;
  storage_backend: string;
  captured_at?: string | null;
  uploaded_at?: string | null;
  created_at: string;
  track_id?: string | null;
  camera_location?: string | null;
  clip_start_time?: string | null;
  clip_end_time?: string | null;
  clip_duration_seconds?: number | null;
  clip_generation_method?: string | null;
  version_number: number;
  parent_evidence_id?: number | null;
  version_notes?: string | null;
  description?: string | null;
  tags?: string | null;
  retention_policy_id?: number | null;
  retention_expires_at?: string | null;
  last_integrity_check_at?: string | null;
}

export interface EvidenceListResponse {
  items: EvidenceItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface EvidenceStats {
  total_evidence: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  by_classification: Record<string, number>;
  integrity_verified: number;
  integrity_failed: number;
  integrity_pending: number;
  recent_accesses: number;
  unauthorized_attempts: number;
  storage_size_bytes: number;
}

export interface EvidenceIntegrityResult {
  evidence_id: string;
  integrity_status: IntegrityStatusType;
  stored_hash?: string | null;
  computed_hash?: string | null;
  hash_algorithm: string;
  verified_at: string;
  match: boolean;
  message: string;
}

export interface AccessLogItem {
  id: number;
  evidence_id: number;
  actor_username?: string | null;
  action: string;
  access_granted: boolean;
  denial_reason?: string | null;
  reason?: string | null;
  ip_address?: string | null;
  timestamp: string;
}

export interface TimelineEntry {
  timestamp: string;
  actor?: string | null;
  action: string;
  description: string;
  resource_type: string;
  resource_id?: string | null;
}

export interface EvidenceTimelineResponse {
  evidence_id: string;
  case_number?: string | null;
  entries: TimelineEntry[];
}

export interface CustodyEvent {
  timestamp: string;
  actor?: string | null;
  action: string;
  source?: string | null;
  destination?: string | null;
  reason?: string | null;
  integrity_info?: string | null;
}

export interface ChainOfCustodyResponse {
  evidence_id: string;
  evidence_type: string;
  case_number?: string | null;
  chain: CustodyEvent[];
  disclaimer: string;
}

export interface ProvenanceStep {
  stage: string;
  identifier: string;
  label: string;
  timestamp?: string | null;
  metadata: Record<string, any>;
}

export interface EvidenceProvenanceResponse {
  evidence_id: string;
  evidence_type: string;
  case_id?: number | null;
  case_number?: string | null;
  camera_id?: number | null;
  track_id?: string | null;
  match_event_id?: number | null;
  review_event_id?: number | null;
  alert_id?: number | null;
  chain_of_events: ProvenanceStep[];
  explanation: string;
}

export interface EvidenceRelationship {
  id: number;
  source_evidence_id: number;
  target_evidence_id: number;
  relationship_type: string;
  description?: string | null;
  created_at: string;
}

export interface RetentionPolicy {
  id: number;
  policy_name: string;
  evidence_type?: string | null;
  retention_days: number;
  action_on_expiry: string;
  requires_manual_review: boolean;
  description?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface AuditLogItem {
  id: number;
  event_id: string;
  actor_username?: string | null;
  department_id?: number | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  resource_label?: string | null;
  timestamp: string;
  ip_address?: string | null;
  reason?: string | null;
  result: string;
  metadata_json?: string | null;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ExportRecord {
  id: number;
  export_id: string;
  evidence_id: number;
  actor_username?: string | null;
  export_type: string;
  reason: string;
  destination?: string | null;
  file_hash_at_export?: string | null;
  created_at: string;
}
