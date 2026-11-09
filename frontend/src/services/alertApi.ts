import axios from 'axios';
import type {
  AlertDashboardStats,
  AlertDetail,
  AlertFilters,
  AlertListResponse,
  AlertNotification,
  AlertTimeline,
} from '../types/alert';

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

export const getAlertDashboardStats = async (): Promise<AlertDashboardStats> => {
  const response = await api.get('/alerts/dashboard/stats');
  return response.data;
};

export const listAlerts = async (
  filters?: AlertFilters,
  page = 1,
  pageSize = 20
): Promise<AlertListResponse> => {
  const response = await api.get('/alerts', {
    params: {
      ...filters,
      page,
      page_size: pageSize,
    },
  });
  return response.data;
};

export const getAlertDetail = async (alertId: number): Promise<AlertDetail> => {
  const response = await api.get(`/alerts/${alertId}`);
  return response.data;
};

export const acknowledgeAlert = async (alertId: number, notes?: string): Promise<AlertDetail> => {
  const response = await api.post(`/alerts/${alertId}/acknowledge`, { notes });
  return response.data;
};

export const updateAlertStatus = async (
  alertId: number,
  status: string,
  notes?: string
): Promise<AlertDetail> => {
  const response = await api.post(`/alerts/${alertId}/status`, { status, notes });
  return response.data;
};

export const getAlertTimeline = async (alertId: number): Promise<AlertTimeline[]> => {
  const response = await api.get(`/alerts/${alertId}/timeline`);
  return response.data;
};

export const getAlertNotifications = async (alertId: number): Promise<AlertNotification[]> => {
  const response = await api.get(`/alerts/${alertId}/notifications`);
  return response.data;
};

export const retryAlertNotifications = async (
  alertId: number,
  notificationId?: number
): Promise<AlertNotification[]> => {
  const response = await api.post(`/alerts/${alertId}/retry`, { notification_id: notificationId });
  return response.data;
};
