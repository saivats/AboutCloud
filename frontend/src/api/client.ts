import axios from 'axios';
import { useAuthStore, useUIStore, useAnomalyStore } from '@/stores';

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const message = error.response?.data?.detail || error.response?.data?.error || error.message;

    if (status === 401) {
      useAuthStore.getState().clearAuth();
      window.location.href = '/login';
    } else {
      useUIStore.getState().addToast(message || 'An error occurred', 'error');
    }

    return Promise.reject(error);
  }
);

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export const authApi = {
  login: async (apiKey: string) => {
    const dummyPayload = btoa(JSON.stringify({ sub: "tenant-1", tenant_name: "Demo Environment", exp: 9999999999 }));
    return { data: { access_token: `header.${dummyPayload}.sig`, token_type: 'bearer', expires_in: 3600 } };
  },
};

export interface MetricPoint {
  timestamp: string;
  value: number;
}

export interface MetricQueryResponse {
  data: MetricPoint[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

export const metricsApi = {
  query: async (params: any) => ({
    data: {
      data: Array.from({ length: 60 }).map((_, i) => ({ timestamp: new Date(Date.now() - (60 - i) * 60000).toISOString(), value: Math.random() * 100 })),
      total: 60, page: 1, page_size: 60, has_next: false
    }
  }),
  ingest: async (data: any) => ({ data: {} }),
};

export interface AnomalyInsightResponse {
  summary: string;
  baseline_value: number | null;
  observed_value: number | null;
  deviation_factor: number | null;
  pattern_description: string | null;
  recommendation: string | null;
}

export interface AnomalyResult {
  id: string;
  tenant_id: string;
  cluster_id: string;
  node_id: string;
  metric_name: string;
  window_start: string;
  window_end: string;
  anomaly_score: number;
  anomaly_label: string;
  confidence: number | null;
  magnitude: number | null;
  explanation: string | null;
  insight: AnomalyInsightResponse | null;
  detected_at: string | null;
}

export interface AnomalyQueryResponse {
  data: AnomalyResult[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

const MOCK_ANOMALIES = Array.from({ length: 15 }).map((_, i) => ({
  id: `mock-${i}`,
  tenant_id: 'tenant-1',
  cluster_id: 'frontend-cluster-prod',
  node_id: `node-${Math.floor(Math.random() * 5)}`,
  metric_name: ['cpu_usage', 'memory_usage', 'latency'][Math.floor(Math.random() * 3)],
  window_start: new Date(Date.now() - (15 - i) * 60000).toISOString(),
  window_end: new Date(Date.now() - (14 - i) * 60000).toISOString(),
  anomaly_score: 0.5 + Math.random() * 0.49,
  anomaly_label: ['spike', 'trend', 'seasonal'][Math.floor(Math.random() * 3)],
  confidence: 0.7 + Math.random() * 0.28,
  magnitude: Math.random() * 5,
  explanation: 'Detected anomalous deviation from baseline model.',
  insight: {
    summary: 'Spike exceeds standard deviation by 3x.',
    baseline_value: 40,
    observed_value: 120,
    deviation_factor: 3,
    pattern_description: 'Rapid increase over short window',
    recommendation: 'Check corresponding node queue depths.'
  },
  detected_at: new Date(Date.now() - (15 - i) * 60000).toISOString(),
}));

export const anomaliesApi = {
  query: async (params: any) => ({
    data: {
      data: MOCK_ANOMALIES,
      total: 15, page: 1, page_size: 50, has_next: false
    }
  }),
};

export interface ClusterInsightResponse {
  cluster_id: string;
  summary: string;
  dominant_anomaly_type: string | null;
  affected_metrics: string[];
  severity: string;
}

export interface HealthResponse {
  tenant_id: string;
  clusters: {
    cluster_id: string;
    health_score: number;
    top_anomalous_nodes: { node_id: string; score: number; rank: number }[];
    last_updated: string | null;
  }[];
  insights: ClusterInsightResponse[];
}

export const healthApi = {
  get: async () => ({
    data: {
      tenant_id: 'tenant-1',
      clusters: [{
        cluster_id: 'frontend-cluster-prod',
        health_score: 0.82,
        top_anomalous_nodes: [
          { node_id: 'node-2', score: 0.91, rank: 1 },
          { node_id: 'node-0', score: 0.65, rank: 2 },
          { node_id: 'node-4', score: 0.42, rank: 3 },
        ],
        last_updated: new Date().toISOString()
      }],
      insights: [{
        cluster_id: 'frontend-cluster-prod',
        summary: 'Cluster healthy but experiencing periodic latency spikes.',
        dominant_anomaly_type: 'spike',
        affected_metrics: ['latency', 'cpu_usage'],
        severity: 'medium'
      }]
    }
  }),
};

export interface DetectResponse {
  job_id: string;
  status: string;
}

export const adminApi = {
  detect: async (data: any) => ({ data: { job_id: 'mock-job', status: 'queued' } }),
};

let wsInstance: WebSocket | null = null;
let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function connectWebSocket() {
  const token = useAuthStore.getState().token;
  if (!token || wsInstance?.readyState === WebSocket.OPEN) return;

  // We are bypassing WebSockets with mock data, so just fake connection
  useUIStore.getState().setWsConnected(true);
  
  // Fake periodic WebSocket messages for demo
  wsReconnectTimer = setInterval(() => {
    const isAnomaly = Math.random() > 0.7;
    if (isAnomaly) {
      const p = {
        tenant_id: 'tenant-1',
        cluster_id: 'frontend-cluster-prod',
        node_id: `node-${Math.floor(Math.random() * 5)}`,
        metric_name: ['cpu_usage', 'memory_usage', 'latency'][Math.floor(Math.random() * 3)],
        anomaly_score: 0.6 + Math.random() * 0.3,
        anomaly_label: ['spike', 'trend'][Math.floor(Math.random() * 2)],
        confidence: 0.85,
        explanation: 'Real-time WebSocket mock anomaly detected.',
      };
      const event = {
        type: 'anomaly_detected',
        payload: p
      };
      
      useUIStore.getState().setWsEvent(event);
      useAnomalyStore.getState().appendAnomalies([{
        id: `ws-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        tenant_id: p.tenant_id,
        cluster_id: p.cluster_id,
        node_id: p.node_id,
        metric_name: p.metric_name,
        window_start: new Date().toISOString(),
        window_end: new Date().toISOString(),
        anomaly_score: p.anomaly_score,
        anomaly_label: p.anomaly_label,
        confidence: p.confidence,
        magnitude: null,
        explanation: p.explanation,
        insight: null,
        detected_at: new Date().toISOString(),
      }]);
    } else {
      useUIStore.getState().setWsEvent({ type: 'health_updated', payload: { cluster_id: 'frontend-cluster-prod',  score: 0.8 + Math.random() * 0.1 }});
    }
  }, 4000) as any;
}

export function disconnectWebSocket() {
  if (wsReconnectTimer) clearInterval(wsReconnectTimer);
  wsInstance?.close();
  wsInstance = null;
  useUIStore.getState().setWsConnected(false);
}

export default apiClient;
