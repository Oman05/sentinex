import axios from 'axios';
import type {
  AdminDashboardMetrics,
  AdminUser,
  AdminDepartment,
  DepartmentStats,
  AdminCamera,
  SystemConfigItem,
  SystemConfigAuditItem,
  WorkerStatusItem,
  BackupItem,
  BackupVerifyResponse,
  AdminAuditEntry,
  SystemHealthData,
} from '../types/admin';

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

// Dashboard
export const getAdminDashboard = async (): Promise<AdminDashboardMetrics> => {
  const res = await api.get('/admin/dashboard');
  return res.data;
};

// Users
export const listAdminUsers = async (params?: { role?: string; department_id?: number }): Promise<AdminUser[]> => {
  const res = await api.get('/admin/users', { params });
  return res.data;
};

export const createAdminUser = async (data: {
  username: string;
  email: string;
  password: string;
  role: string;
  department_id?: number | null;
}): Promise<AdminUser> => {
  const res = await api.post('/admin/users', null, { params: data });
  return res.data;
};

export const updateAdminUser = async (
  userId: number,
  data: { email?: string; role?: string; department_id?: number | null; is_active?: boolean }
): Promise<AdminUser> => {
  const res = await api.put(`/admin/users/${userId}`, data);
  return res.data;
};

export const updateAdminUserStatus = async (userId: number, is_active: boolean): Promise<AdminUser> => {
  const res = await api.patch(`/admin/users/${userId}/status`, null, { params: { is_active } });
  return res.data;
};

export const resetUserPassword = async (userId: number, new_password: string, reason?: string) => {
  const res = await api.post(`/admin/users/${userId}/reset-password`, { new_password, reason });
  return res.data;
};

// Departments
export const listAdminDepartments = async (is_active?: boolean): Promise<AdminDepartment[]> => {
  const res = await api.get('/admin/departments', { params: { is_active } });
  return res.data;
};

export const createAdminDepartment = async (data: {
  department_name: string;
  department_type: string;
  location?: string;
}): Promise<AdminDepartment> => {
  const res = await api.post('/admin/departments', data);
  return res.data;
};

export const updateAdminDepartment = async (
  deptId: number,
  data: { department_name?: string; department_type?: string; location?: string }
): Promise<AdminDepartment> => {
  const res = await api.put(`/admin/departments/${deptId}`, data);
  return res.data;
};

export const updateAdminDepartmentStatus = async (deptId: number, is_active: boolean): Promise<AdminDepartment> => {
  const res = await api.patch(`/admin/departments/${deptId}/status`, { is_active });
  return res.data;
};

export const getDepartmentStats = async (deptId: number): Promise<DepartmentStats> => {
  const res = await api.get(`/admin/departments/${deptId}/stats`);
  return res.data;
};

// Cameras
export const listAdminCameras = async (params?: { department_id?: number; status_filter?: string }): Promise<AdminCamera[]> => {
  const res = await api.get('/admin/cameras', { params });
  return res.data;
};

export const createAdminCamera = async (data: any): Promise<AdminCamera> => {
  const res = await api.post('/admin/cameras', data);
  return res.data;
};

export const updateAdminCamera = async (cameraId: number, data: any): Promise<AdminCamera> => {
  const res = await api.put(`/admin/cameras/${cameraId}`, data);
  return res.data;
};

export const deleteAdminCamera = async (cameraId: number): Promise<{ message: string }> => {
  const res = await api.delete(`/admin/cameras/${cameraId}`);
  return res.data;
};

export const testCameraConnection = async (cameraId: number) => {
  const res = await api.post(`/admin/cameras/${cameraId}/test`);
  return res.data;
};

// Configurations
export const getSystemConfigs = async (category?: string): Promise<SystemConfigItem[]> => {
  const res = await api.get('/admin/config', { params: { category } });
  return res.data;
};

export const updateSystemConfigs = async (updates: Array<{ key: string; value: any; reason: string }>) => {
  const res = await api.put('/admin/config', { updates, confirmation: true });
  return res.data;
};

export const getConfigAuditHistory = async (limit = 50, category?: string): Promise<SystemConfigAuditItem[]> => {
  const res = await api.get('/admin/config/audit', { params: { limit, category } });
  return res.data;
};

// Workers
export const getWorkerStatus = async (): Promise<WorkerStatusItem[]> => {
  const res = await api.get('/admin/workers');
  return res.data;
};

export const restartWorker = async (workerName: string) => {
  const res = await api.post(`/admin/workers/${workerName}/restart`);
  return res.data;
};

// System Health
export const getAdminSystemHealth = async (): Promise<SystemHealthData> => {
  const res = await api.get('/admin/system-health');
  return res.data;
};

// Backups
export const createBackup = async (backup_type = 'FULL', notes?: string): Promise<BackupItem> => {
  const res = await api.post('/admin/backups', { backup_type, notes });
  return res.data;
};

export const listBackups = async (limit = 50): Promise<BackupItem[]> => {
  const res = await api.get('/admin/backups', { params: { limit } });
  return res.data;
};

export const verifyBackup = async (backupId: string): Promise<BackupVerifyResponse> => {
  const res = await api.post(`/admin/backups/${backupId}/verify`);
  return res.data;
};

export const restoreBackup = async (backupId: string, confirmation_code = 'CONFIRM_RESTORE') => {
  const res = await api.post(`/admin/backups/${backupId}/restore`, { confirmation_code });
  return res.data;
};

// Audit Logs
export const listAdminAuditLogs = async (params?: { user_id?: number; action?: string; resource_type?: string }): Promise<AdminAuditEntry[]> => {
  const res = await api.get('/admin/audit', { params });
  return res.data;
};

// Camera stream control (used by Live Camera Demo page)
export const startCameraStream = async (cameraId: number): Promise<{ message: string; status: string }> => {
  const res = await api.post(`/admin/cameras/${cameraId}/start`);
  return res.data;
};

export const stopCameraStream = async (cameraId: number): Promise<{ message: string; status: string }> => {
  const res = await api.post(`/admin/cameras/${cameraId}/stop`);
  return res.data;
};

export const getCameraStreamStatus = async (cameraId: number) => {
  const res = await api.get(`/cameras/${cameraId}/stream-status`);
  return res.data;
};
