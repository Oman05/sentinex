import axios from 'axios';
import type {
  AccessLogItem,
  AuditLogListResponse,
  ChainOfCustodyResponse,
  EvidenceIntegrityResult,
  EvidenceItem,
  EvidenceListResponse,
  EvidenceProvenanceResponse,
  EvidenceRelationship,
  EvidenceStats,
  EvidenceTimelineResponse,
  ExportRecord,
  RetentionPolicy,
} from '../types/evidence';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: BASE_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sentinex_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface EvidenceSearchParams {
  case_id?: number;
  camera_id?: number;
  evidence_type?: string;
  status?: string;
  classification?: string;
  match_event_id?: number;
  alert_id?: number;
  date_from?: string;
  date_to?: string;
  q?: string;
  page?: number;
  page_size?: number;
}

export interface AuditSearchParams {
  user?: string;
  action?: string;
  resource_type?: string;
  resource_id?: string;
  date_from?: string;
  date_to?: string;
  result?: string;
  page?: number;
  page_size?: number;
}

export const getEvidenceStats = async (): Promise<EvidenceStats> => {
  const response = await api.get('/evidence/stats');
  return response.data;
};

export const listEvidence = async (params?: EvidenceSearchParams): Promise<EvidenceListResponse> => {
  const response = await api.get('/evidence', { params });
  return response.data;
};

export const getEvidence = async (evidenceId: string, reason?: string): Promise<EvidenceItem> => {
  const response = await api.get(`/evidence/${evidenceId}`, {
    params: reason ? { reason } : undefined,
  });
  return response.data;
};

export const downloadEvidenceContent = async (evidenceId: string, reason: string): Promise<Blob> => {
  const response = await api.get(`/evidence/${evidenceId}/content`, {
    params: { reason },
    responseType: 'blob',
  });
  return response.data;
};

export const getEvidenceAccessLogs = async (evidenceId: string): Promise<AccessLogItem[]> => {
  const response = await api.get(`/evidence/${evidenceId}/access`);
  return response.data;
};

export const verifyEvidenceIntegrity = async (evidenceId: string): Promise<EvidenceIntegrityResult> => {
  const response = await api.get(`/evidence/${evidenceId}/integrity`);
  return response.data;
};

export const getEvidenceTimeline = async (evidenceId: string): Promise<EvidenceTimelineResponse> => {
  const response = await api.get(`/evidence/${evidenceId}/timeline`);
  return response.data;
};

export const getChainOfCustody = async (evidenceId: string): Promise<ChainOfCustodyResponse> => {
  const response = await api.get(`/evidence/${evidenceId}/custody`);
  return response.data;
};

export const getEvidenceProvenance = async (evidenceId: string): Promise<EvidenceProvenanceResponse> => {
  const response = await api.get(`/evidence/${evidenceId}/provenance`);
  return response.data;
};

export const updateEvidence = async (
  evidenceId: string,
  payload: {
    description?: string;
    tags?: string;
    classification?: string;
    retention_policy_id?: number;
    version_notes?: string;
  }
): Promise<EvidenceItem> => {
  const response = await api.put(`/evidence/${evidenceId}`, payload);
  return response.data;
};

export const finalizeEvidence = async (
  evidenceId: string,
  reason: string,
  notes?: string
): Promise<EvidenceItem> => {
  const response = await api.post(`/evidence/${evidenceId}/finalize`, { reason, notes });
  return response.data;
};

export const archiveEvidence = async (evidenceId: string, reason: string): Promise<EvidenceItem> => {
  const response = await api.post(`/evidence/${evidenceId}/archive`, { reason });
  return response.data;
};

export const deleteEvidence = async (
  evidenceId: string,
  reason: string,
  force = false
): Promise<{ status: string; evidence_id: string; message: string }> => {
  const response = await api.delete(`/evidence/${evidenceId}`, {
    data: { reason, force },
  });
  return response.data;
};

export const createEvidence = async (formData: FormData): Promise<EvidenceItem> => {
  const response = await api.post('/evidence', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const createEvidenceVersion = async (
  evidenceId: string,
  formData: FormData
): Promise<EvidenceItem> => {
  const response = await api.post(`/evidence/${evidenceId}/version`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const exportEvidence = async (
  evidenceId: string,
  payload: { export_type: string; reason: string; destination?: string }
): Promise<ExportRecord> => {
  const response = await api.post(`/evidence/${evidenceId}/export`, payload);
  return response.data;
};

export const createCCTVClip = async (formData: FormData): Promise<EvidenceItem> => {
  const response = await api.post('/evidence/cctv-clip', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const getEvidenceRelationships = async (evidenceId: string): Promise<EvidenceRelationship[]> => {
  const response = await api.get(`/evidence/${evidenceId}/relationships`);
  return response.data;
};

export const listRetentionPolicies = async (): Promise<RetentionPolicy[]> => {
  const response = await api.get('/evidence/retention/policies');
  return response.data;
};

export const processExpiredRetention = async (): Promise<{
  processed_count: number;
  expired_evidence_ids: string[];
  message: string;
}> => {
  const response = await api.post('/evidence/retention/process-expired');
  return response.data;
};

export const listAuditLogs = async (params?: AuditSearchParams): Promise<AuditLogListResponse> => {
  const response = await api.get('/audit', { params });
  return response.data;
};

export const getResourceAuditHistory = async (
  resourceType: string,
  resourceId: string,
  page = 1,
  pageSize = 50
): Promise<AuditLogListResponse> => {
  const response = await api.get(`/audit/${resourceType}/${resourceId}`, {
    params: { page, page_size: pageSize },
  });
  return response.data;
};
