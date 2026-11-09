/**
 * Module 11 – Analytics API Service
 * ==================================
 * Client for all /api/analytics, /api/evaluation, and /api/models endpoints.
 * 
 * Privacy note: All endpoints return aggregated statistics only.
 * No personal data, biometric data, or PII is fetched or stored here.
 */

import axios from 'axios';
import type {
  AnalyticsAlertItem,
  CameraAnalyticsItem,
  DatasetRegistryCreate,
  DatasetRegistryItem,
  DriftEventItem,
  EvaluationResultItem,
  EvaluationRunCreate,
  EvaluationRunItem,
  FaceQualityBreakdown,
  MatchingMetricsResponse,
  ModelRegistryCreate,
  ModelRegistryItem,
  OverviewResponse,
  PipelineStageMetrics,
  ReviewMetricsResponse,
  AlertMetricsResponse,
  ScoreDistributionResponse,
  SystemHealthResponse,
  ThresholdEvaluationResult,
  TimeRange,
} from '../types/analytics';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sentinex_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ─── Time range helpers ──────────────────────────────────────────────────────

interface TimeRangeParams {
  time_range: TimeRange;
  start_date?: string;
  end_date?: string;
}

function buildParams(timeRange: TimeRange, startDate?: string, endDate?: string): TimeRangeParams {
  const params: TimeRangeParams = { time_range: timeRange };
  if (timeRange === 'custom') {
    params.start_date = startDate;
    params.end_date = endDate;
  }
  return params;
}

// ─── Analytics Endpoints ─────────────────────────────────────────────────────

export const getOverview = async (
  timeRange: TimeRange = '7d',
  startDate?: string,
  endDate?: string
): Promise<OverviewResponse> => {
  const { data } = await api.get('/analytics/overview', {
    params: buildParams(timeRange, startDate, endDate),
  });
  return data;
};

export const getSystemHealth = async (): Promise<SystemHealthResponse> => {
  const { data } = await api.get('/analytics/system');
  return data;
};

export const getCameraAnalytics = async (
  timeRange: TimeRange = '7d',
  startDate?: string,
  endDate?: string
): Promise<CameraAnalyticsItem[]> => {
  const { data } = await api.get('/analytics/cameras', {
    params: buildParams(timeRange, startDate, endDate),
  });
  return data;
};

export const getPipelineMetrics = async (
  timeRange: TimeRange = '7d',
  startDate?: string,
  endDate?: string
): Promise<PipelineStageMetrics[]> => {
  const { data } = await api.get('/analytics/pipeline', {
    params: buildParams(timeRange, startDate, endDate),
  });
  return data;
};

export const getFaceQualityBreakdown = async (
  timeRange: TimeRange = '7d',
  startDate?: string,
  endDate?: string
): Promise<FaceQualityBreakdown> => {
  const { data } = await api.get('/analytics/quality', {
    params: buildParams(timeRange, startDate, endDate),
  });
  return data;
};

export const getMatchingMetrics = async (
  timeRange: TimeRange = '7d',
  startDate?: string,
  endDate?: string
): Promise<MatchingMetricsResponse> => {
  const { data } = await api.get('/analytics/matching', {
    params: buildParams(timeRange, startDate, endDate),
  });
  return data;
};

export const getReviewMetrics = async (
  timeRange: TimeRange = '7d',
  startDate?: string,
  endDate?: string
): Promise<ReviewMetricsResponse> => {
  const { data } = await api.get('/analytics/reviews', {
    params: buildParams(timeRange, startDate, endDate),
  });
  return data;
};

export const getAlertMetrics = async (
  timeRange: TimeRange = '7d',
  startDate?: string,
  endDate?: string
): Promise<AlertMetricsResponse> => {
  const { data } = await api.get('/analytics/alerts', {
    params: buildParams(timeRange, startDate, endDate),
  });
  return data;
};

export const getDriftEvents = async (limit = 50): Promise<DriftEventItem[]> => {
  const { data } = await api.get('/analytics/drift', { params: { limit } });
  return data;
};

export const runDriftCheck = async (): Promise<DriftEventItem[]> => {
  const { data } = await api.post('/analytics/drift/check');
  return data;
};

export const acknowledgeDriftEvent = async (eventId: number): Promise<DriftEventItem> => {
  const { data } = await api.post(`/analytics/drift/${eventId}/acknowledge`);
  return data;
};

export const getTechnicalAlerts = async (resolved = false): Promise<AnalyticsAlertItem[]> => {
  const { data } = await api.get('/analytics/alerts/technical', { params: { resolved } });
  return data;
};

export const acknowledgeTechnicalAlert = async (alertId: number): Promise<AnalyticsAlertItem> => {
  const { data } = await api.post(`/analytics/alerts/technical/${alertId}/acknowledge`);
  return data;
};

export const resolveTechnicalAlert = async (alertId: number): Promise<AnalyticsAlertItem> => {
  const { data } = await api.post(`/analytics/alerts/technical/${alertId}/resolve`);
  return data;
};

export const getScoreDistribution = async (
  timeRange: TimeRange = '30d',
  startDate?: string,
  endDate?: string
): Promise<ScoreDistributionResponse> => {
  const { data } = await api.get('/analytics/scores/distribution', {
    params: buildParams(timeRange, startDate, endDate),
  });
  return data;
};

// ─── Export ──────────────────────────────────────────────────────────────────

export const exportAnalyticsCSV = async (timeRange: TimeRange = '7d'): Promise<Blob> => {
  const response = await api.get('/analytics/export/csv', {
    params: { time_range: timeRange },
    responseType: 'blob',
  });
  return response.data;
};

export const exportAnalyticsJSON = async (timeRange: TimeRange = '7d'): Promise<object> => {
  const { data } = await api.get('/analytics/export/json', {
    params: { time_range: timeRange },
  });
  return data;
};

export const generateResearchReport = async (runId: string): Promise<object> => {
  const { data } = await api.get('/analytics/report/research', {
    params: { run_id: runId },
  });
  return data;
};

// ─── Evaluation Endpoints ─────────────────────────────────────────────────────

export const createEvaluationRun = async (data: EvaluationRunCreate): Promise<EvaluationRunItem> => {
  const { data: result } = await api.post('/evaluation/run', data);
  return result;
};

export const listEvaluationRuns = async (): Promise<EvaluationRunItem[]> => {
  const { data } = await api.get('/evaluation/runs');
  return data;
};

export const getEvaluationRun = async (runId: string): Promise<EvaluationRunItem> => {
  const { data } = await api.get(`/evaluation/runs/${runId}`);
  return data;
};

export const executeEvaluationRun = async (runId: string): Promise<EvaluationResultItem> => {
  const { data } = await api.post(`/evaluation/runs/${runId}/execute`);
  return data;
};

export const getEvaluationResults = async (runId: string): Promise<EvaluationResultItem> => {
  const { data } = await api.get(`/evaluation/runs/${runId}/results`);
  return data;
};

export const evaluateThreshold = async (
  threshold: number,
  timeRange: TimeRange = '30d'
): Promise<ThresholdEvaluationResult> => {
  const { data } = await api.post('/evaluation/threshold', {
    threshold,
    time_range: timeRange,
  });
  return data;
};

// ─── Model Registry ──────────────────────────────────────────────────────────

export const registerModel = async (modelData: ModelRegistryCreate): Promise<ModelRegistryItem> => {
  const { data } = await api.post('/models/registry', modelData);
  return data;
};

export const listModels = async (): Promise<ModelRegistryItem[]> => {
  const { data } = await api.get('/models/registry');
  return data;
};

export const getModel = async (modelId: number): Promise<ModelRegistryItem> => {
  const { data } = await api.get(`/models/registry/${modelId}`);
  return data;
};

export const activateModel = async (modelId: number): Promise<ModelRegistryItem> => {
  const { data } = await api.post(`/models/registry/${modelId}/activate`);
  return data;
};

export const retireModel = async (modelId: number): Promise<ModelRegistryItem> => {
  const { data } = await api.post(`/models/registry/${modelId}/retire`);
  return data;
};

export const registerDataset = async (datasetData: DatasetRegistryCreate): Promise<DatasetRegistryItem> => {
  const { data } = await api.post('/models/datasets', datasetData);
  return data;
};

export const listDatasets = async (): Promise<DatasetRegistryItem[]> => {
  const { data } = await api.get('/models/datasets');
  return data;
};
