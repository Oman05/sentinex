import axios from 'axios';
import type {
  Filters,
  InvestigationTask,
  InvestigationTaskCreate,
  NotificationItem,
  ReviewDashboardStats,
  ReviewDecisionRequest,
  EvidenceRequestPayload,
  ReviewEventDetail,
  ReviewEventSummary,
  ReviewHistory,
  TrackHistory
} from '../types/review';

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

export const getDashboardStats = async (): Promise<ReviewDashboardStats> => {
  const response = await api.get('/dashboard/stats');
  return response.data;
};

export const listReviewEvents = async (filters?: Filters, limit = 50, offset = 0): Promise<ReviewEventSummary[]> => {
  const response = await api.get('/reviews', { params: { ...filters, limit, offset } });
  return response.data;
};

export const getReviewEvent = async (id: number): Promise<ReviewEventDetail> => {
  const response = await api.get(`/reviews/${id}`);
  return response.data;
};

export const startReview = async (id: number, notes?: string): Promise<ReviewEventDetail> => {
  const response = await api.post(`/reviews/${id}/start`, { notes });
  return response.data;
};

export const submitDecision = async (id: number, payload: ReviewDecisionRequest): Promise<ReviewEventDetail> => {
  const response = await api.post(`/reviews/${id}/decision`, payload);
  return response.data;
};

export const requestEvidence = async (id: number, payload: EvidenceRequestPayload): Promise<ReviewEventDetail> => {
  const response = await api.post(`/reviews/${id}/evidence`, payload);
  return response.data;
};

export const assignEvent = async (id: number, examiner_user_id: number, notes?: string): Promise<ReviewEventDetail> => {
  const response = await api.post(`/reviews/${id}/assign`, { examiner_user_id, notes });
  return response.data;
};

export const getReviewHistory = async (id: number): Promise<ReviewHistory> => {
  const response = await api.get(`/reviews/${id}/history`);
  return response.data;
};

export const listTasks = async (filters?: { status?: string; case_id?: number; assigned_to?: number }, limit = 50, offset = 0): Promise<InvestigationTask[]> => {
  const response = await api.get('/tasks', { params: { ...filters, limit, offset } });
  return response.data;
};

export const createTask = async (payload: InvestigationTaskCreate): Promise<InvestigationTask> => {
  const response = await api.post('/tasks', payload);
  return response.data;
};

export const updateTask = async (taskId: number, payload: { status?: string; assigned_to?: number; resolution_notes?: string; due_date?: string }): Promise<InvestigationTask> => {
  const response = await api.put(`/tasks/${taskId}`, payload);
  return response.data;
};

export const getTrackHistory = async (eventId: number): Promise<TrackHistory | null> => {
  const response = await api.get(`/reviews/${eventId}/tracks`);
  return response.data;
};

export const getNotifications = async (limit = 10): Promise<NotificationItem[]> => {
  const response = await api.get('/notifications', { params: { limit } });
  return response.data;
};

export const login = async (username: string, password: string): Promise<{ access_token: string; token_type: string }> => {
  const response = await api.post('/auth/login', { username, password });
  return response.data;
};
