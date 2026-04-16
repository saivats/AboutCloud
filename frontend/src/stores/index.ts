import { create } from 'zustand';

interface AuthState {
  token: string | null;
  tenantId: string | null;
  tenantName: string | null;
  setAuth: (token: string, tenantId: string, tenantName: string) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  tenantId: null,
  tenantName: null,
  setAuth: (token, tenantId, tenantName) => set({ token, tenantId, tenantName }),
  clearAuth: () => set({ token: null, tenantId: null, tenantName: null }),
  isAuthenticated: () => get().token !== null,
}));

export interface ClusterHealth {
  cluster_id: string;
  health_score: number;
  top_anomalous_nodes: { node_id: string; score: number; rank: number }[];
  last_updated: string | null;
}

export interface ClusterInsight {
  cluster_id: string;
  summary: string;
  dominant_anomaly_type: string | null;
  affected_metrics: string[];
  severity: string;
}

interface ClusterState {
  clusters: ClusterHealth[];
  insights: ClusterInsight[];
  selectedCluster: string | null;
  loading: boolean;
  setClusters: (clusters: ClusterHealth[]) => void;
  setInsights: (insights: ClusterInsight[]) => void;
  setSelectedCluster: (id: string | null) => void;
  setLoading: (loading: boolean) => void;
}

export const useClusterStore = create<ClusterState>((set) => ({
  clusters: [],
  insights: [],
  selectedCluster: null,
  loading: false,
  setClusters: (clusters) => set({ clusters }),
  setInsights: (insights) => set({ insights }),
  setSelectedCluster: (id) => set({ selectedCluster: id }),
  setLoading: (loading) => set({ loading }),
}));

export interface AnomalyInsight {
  summary: string;
  baseline_value: number | null;
  observed_value: number | null;
  deviation_factor: number | null;
  pattern_description: string | null;
  recommendation: string | null;
}

export interface AnomalyItem {
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
  insight: AnomalyInsight | null;
  detected_at: string | null;
}

interface AnomalyState {
  anomalies: AnomalyItem[];
  total: number;
  loading: boolean;
  setAnomalies: (anomalies: AnomalyItem[], total: number) => void;
  appendAnomalies: (anomalies: AnomalyItem[]) => void;
  setLoading: (loading: boolean) => void;
}

export const useAnomalyStore = create<AnomalyState>((set) => ({
  anomalies: [],
  total: 0,
  loading: false,
  setAnomalies: (anomalies, total) => set({ anomalies, total }),
  appendAnomalies: (newAnomalies) =>
    set((state) => ({
      anomalies: [...newAnomalies.filter(
        (n) => !state.anomalies.some((e) => e.id === n.id)
      ), ...state.anomalies].slice(0, 200),
      total: state.total + newAnomalies.length,
    })),
  setLoading: (loading) => set({ loading }),
}));

interface ToastItem {
  id: string;
  message: string;
  type: 'error' | 'success' | 'info';
}

interface WebSocketState {
  connected: boolean;
  lastEvent: Record<string, unknown> | null;
}

interface UIState {
  sidebarOpen: boolean;
  selectedTimeRange: string;
  toasts: ToastItem[];
  ws: WebSocketState;
  toggleSidebar: () => void;
  setTimeRange: (range: string) => void;
  addToast: (message: string, type: 'error' | 'success' | 'info') => void;
  removeToast: (id: string) => void;
  setWsConnected: (connected: boolean) => void;
  setWsEvent: (event: Record<string, unknown>) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  selectedTimeRange: '24h',
  toasts: [],
  ws: { connected: false, lastEvent: null },
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setTimeRange: (range) => set({ selectedTimeRange: range }),
  addToast: (message, type) => {
    const id = crypto.randomUUID();
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 4000);
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  setWsConnected: (connected) => set((s) => ({ ws: { ...s.ws, connected } })),
  setWsEvent: (event) => set((s) => ({ ws: { ...s.ws, lastEvent: event } })),
}));
