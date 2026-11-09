export interface AdminDashboardMetrics {
  total_users: number;
  active_departments: number;
  registered_cameras: number;
  online_cameras: number;
  offline_cameras: number;
  active_cases: number;
  pending_human_reviews: number;
  confirmed_for_action_events: number;
  active_alerts: number;
  system_health: string;
  ai_model_status: string;
  database_status: string;
  storage_status: string;
  worker_status: string;
  recent_security_events: Array<{
    id: number;
    action: string;
    resource_type: string;
    resource_id?: number | string;
    details?: string;
    timestamp: string;
  }>;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  department_id?: number | null;
  created_at: string;
  updated_at: string;
  last_login_at?: string | null;
}

export interface AdminDepartment {
  id: number;
  department_name: string;
  department_type: string;
  location?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DepartmentStats {
  department_id: number;
  department_name: string;
  total_users: number;
  total_cameras: number;
  online_cameras: number;
  total_cases: number;
  total_alerts_dispatched: number;
  total_alerts_received: number;
}

export interface AdminCamera {
  id: number;
  camera_code: string;
  camera_name: string;
  department_id: number;
  location_name?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  jurisdiction?: string | null;
  stream_type: string;
  status: string;
  is_active: boolean;
  processing_enabled: boolean;
  sample_fps: number;
  sampling_interval: number;
  created_at: string;
  updated_at: string;
  last_seen_at?: string | null;
  last_error?: string | null;
}

export interface SystemConfigItem {
  id: number;
  category: string;
  key: string;
  value: string | number | boolean | any;
  value_type: string;
  description?: string | null;
  is_secret: boolean;
  requires_restart: boolean;
  updated_at: string;
}

export interface SystemConfigAuditItem {
  id: number;
  category: string;
  key: string;
  old_value?: string | null;
  new_value: string;
  changed_by_user_id?: number | null;
  changed_at: string;
  reason?: string | null;
}

export interface WorkerStatusItem {
  worker_name: string;
  display_name: string;
  status: string;
  current_job?: string | null;
  queue_size: number;
  jobs_processed: number;
  jobs_failed: number;
  avg_processing_time_ms: number;
  last_heartbeat: string;
  last_error?: string | null;
}

export interface BackupItem {
  id: number;
  backup_id: string;
  filename: string;
  filepath: string;
  backup_type: string;
  size_bytes: number;
  duration_seconds: number;
  status: string;
  checksum_sha256: string;
  verification_status: string;
  created_at: string;
  notes?: string | null;
}

export interface BackupVerifyResponse {
  backup_id: string;
  is_valid: boolean;
  status: string;
  checksum_sha256: string;
  details: string;
}

export interface AdminAuditEntry {
  id: number;
  user_id: number;
  action: string;
  resource_type: string;
  resource_id?: number | string | null;
  timestamp: string;
  ip_address?: string | null;
  details?: string | null;
}

export interface SystemHealthData {
  status: string;
  timestamp: string;
  database: {
    connected: boolean;
    latency_ms: number;
    type: string;
  };
  workers: {
    total: number;
    errors: number;
    list: WorkerStatusItem[];
  };
  storage: {
    evidence_dir: string;
    writable: boolean;
  };
  ai_pipeline: {
    status: string;
    active_models_count: number;
  };
}
