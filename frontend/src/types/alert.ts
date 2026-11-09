export type AlertPriority = 'LOW' | 'NORMAL' | 'HIGH' | 'CRITICAL';

export type AlertStatus =
  | 'CREATED'
  | 'QUEUED'
  | 'SENT'
  | 'DELIVERED'
  | 'ACKNOWLEDGED'
  | 'IN_PROGRESS'
  | 'RESOLVED'
  | 'CLOSED'
  | 'FAILED';

export type RecipientType =
  | 'ORIGINATING_DEPARTMENT'
  | 'NEAREST_AUTHORIZED_DEPARTMENT'
  | 'ESCALATION_RECIPIENT';

export type DeliveryChannel =
  | 'IN_APP'
  | 'EMAIL'
  | 'SMS'
  | 'PUSH_NOTIFICATION'
  | 'SECURE_INTERNAL_API';

export interface AlertRecipient {
  id: number;
  alert_id: number;
  department_id: number;
  department_name?: string;
  department_code?: string;
  recipient_type: RecipientType;
  delivery_channel: DeliveryChannel;
  destination_reference?: string;
  status: AlertStatus;
  sent_at?: string;
  delivered_at?: string;
  acknowledged_at?: string;
  acknowledged_by?: number;
}

export interface AlertNotification {
  id: number;
  alert_id: number;
  recipient_id: number;
  channel: DeliveryChannel;
  status: AlertStatus;
  attempt_count: number;
  sent_at?: string;
  delivered_at?: string;
  failed_at?: string;
  error_code?: string;
  error_message?: string;
  message_payload?: string;
  created_at: string;
}

export interface AlertTimeline {
  id: number;
  alert_id: number;
  timestamp: string;
  event_type: string;
  description: string;
  metadata_json?: string;
}

export interface AlertAuditLog {
  id: number;
  alert_id: number;
  user_id?: number;
  actor_username?: string;
  action: string;
  previous_status?: string;
  new_status?: string;
  timestamp: string;
  ip_address?: string;
  metadata_json?: string;
}

export interface AlertItem {
  id: number;
  alert_number: string;
  match_event_id: string;
  review_event_id: number;
  case_id: number;
  case_number: string;
  category: string;
  originating_department_id: number;
  originating_department_name?: string;
  detected_camera_id?: number;
  detected_camera_code?: string;
  detected_location?: string;
  nearest_department_id?: number;
  nearest_department_name?: string;
  routing_reason?: string;
  distance_km?: number;
  priority: AlertPriority;
  status: AlertStatus;
  observation_count: number;
  last_observation_at: string;
  created_at: string;
  acknowledged_at?: string;
  closed_at?: string;
}

export interface AlertDetail extends AlertItem {
  case_title?: string;
  person_identifier?: string;
  case_priority?: string;
  examiner_username?: string;
  decision_notes?: string;
  similarity_score?: number;
  similarity_disclaimer: string;
  recipients: AlertRecipient[];
  notifications: AlertNotification[];
  timeline: AlertTimeline[];
  audit_logs: AlertAuditLog[];
}

export interface AlertListResponse {
  items: AlertItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface AlertDashboardStats {
  total_alerts: number;
  pending: number;
  acknowledged: number;
  in_progress: number;
  resolved: number;
  closed: number;
  failed: number;
  duplicate_alerts_prevented: number;
  average_latency_seconds: number;
}

export interface AlertFilters {
  case_number?: string;
  category?: string;
  status?: string;
  priority?: string;
  department_id?: number;
  camera_id?: number;
}
