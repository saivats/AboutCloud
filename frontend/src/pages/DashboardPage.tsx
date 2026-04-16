import { useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuthStore, useClusterStore, useAnomalyStore, useUIStore, ClusterHealth } from '@/stores';
import { healthApi, anomaliesApi, connectWebSocket } from '@/api/client';
import LoadingSpinner from '@/components/LoadingSpinner';
import ErrorBoundary from '@/components/ErrorBoundary';
import EmptyState from '@/components/EmptyState';
import InsightCard from '@/components/InsightCard';
import { DashboardSkeleton, FeedSkeleton } from '@/components/Skeleton';

function HealthRing({ score, size = 72, strokeWidth = 4 }: { score: number; size?: number; strokeWidth?: number }) {
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = circumference * score;
  const color = score > 0.7 ? '#ff4444' : score > 0.4 ? '#ff6b35' : '#00ff88';
  const glowColor = score > 0.7 ? 'rgba(255,68,68,0.3)' : score > 0.4 ? 'rgba(255,107,53,0.2)' : 'rgba(0,255,136,0.2)';

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference - filled }}
          transition={{ duration: 1.2, ease: [0.25, 0.46, 0.45, 0.94], delay: 0.2 }}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ filter: `drop-shadow(0 0 6px ${glowColor})` }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <motion.span
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.6, duration: 0.4 }}
          className="stat-value text-sm"
          style={{ color }}
        >
          {(score * 100).toFixed(0)}
        </motion.span>
      </div>
    </div>
  );
}

function ClusterHealthCard({ cluster, index, onClick }: { cluster: ClusterHealth; index: number; onClick: () => void }) {
  const scoreStatus = cluster.health_score > 0.7 ? 'critical' : cluster.health_score > 0.4 ? 'warning' : 'healthy';
  const statusLabel = scoreStatus === 'critical' ? 'Critical' : scoreStatus === 'warning' ? 'Warning' : 'Healthy';
  const badgeClass = `score-${scoreStatus}`;

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.06, ease: [0.25, 0.46, 0.45, 0.94] }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      onClick={onClick}
      className="glass-card glass-card-hover p-6"
    >
      <div className="flex items-start justify-between mb-5">
        <div className="flex-1 min-w-0">
          <h3 className="text-white font-semibold text-sm mb-2 truncate font-mono">
            {cluster.cluster_id.slice(0, 12)}...
          </h3>
          <span className={`score-badge ${badgeClass}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${scoreStatus === 'critical' ? 'bg-red-400 animate-pulse-dot' : scoreStatus === 'warning' ? 'bg-orange-400' : 'bg-emerald-400'}`} />
            {statusLabel}
          </span>
        </div>
        <HealthRing score={cluster.health_score} size={64} />
      </div>

      <div className="space-y-1.5 mt-4">
        <p className="text-white/25 text-[10px] uppercase tracking-[0.15em] font-semibold mb-2">Top Anomalous Nodes</p>
        {cluster.top_anomalous_nodes.length === 0 ? (
          <p className="text-white/15 text-xs italic">No anomalies detected</p>
        ) : (
          cluster.top_anomalous_nodes.slice(0, 3).map((node, i) => {
            const nodeColor = node.score > 0.7 ? 'text-red-400' : node.score > 0.4 ? 'text-orange-400' : 'text-emerald-400';
            const barColor = node.score > 0.7 ? 'bg-red-400' : node.score > 0.4 ? 'bg-orange-400' : 'bg-emerald-400';
            return (
              <div key={node.node_id} className="flex items-center gap-2 text-xs">
                <span className="text-white/30 w-4 text-right">#{node.rank}</span>
                <span className="text-white/55 font-mono flex-1 truncate">{node.node_id.slice(0, 10)}</span>
                <div className="w-16 h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                  <motion.div
                    className={`h-full rounded-full ${barColor}`}
                    initial={{ width: 0 }}
                    animate={{ width: `${node.score * 100}%` }}
                    transition={{ duration: 0.8, delay: 0.3 + i * 0.1 }}
                  />
                </div>
                <span className={`stat-value text-[11px] w-8 text-right ${nodeColor}`}>
                  {(node.score * 100).toFixed(0)}
                </span>
              </div>
            );
          })
        )}
      </div>

      {cluster.last_updated && (
        <p className="text-white/15 text-[9px] mt-4 font-medium">
          Updated {new Date(cluster.last_updated).toLocaleTimeString()}
        </p>
      )}
    </motion.div>
  );
}

function LiveAnomalyFeed() {
  const anomalies = useAnomalyStore((s) => s.anomalies);
  const loading = useAnomalyStore((s) => s.loading);
  const wsConnected = useUIStore((s) => s.ws.connected);

  const labelClass: Record<string, string> = {
    spike: 'label-spike',
    trend: 'label-trend',
    seasonal: 'label-seasonal',
    normal: 'label-normal',
  };

  if (loading && anomalies.length === 0) return <FeedSkeleton />;

  return (
    <div className="space-y-2 max-h-[calc(100vh-220px)] overflow-y-auto pr-1">
      <div className="flex items-center justify-between mb-2">
        <span className={`live-indicator text-[10px] font-semibold uppercase tracking-wider ${wsConnected ? 'text-emerald-400/80' : 'text-white/25'}`}>
          {wsConnected ? 'Live' : 'Polling'}
        </span>
        <span className="text-white/20 text-[10px] stat-value">{anomalies.length}</span>
      </div>

      {anomalies.length === 0 ? (
        <EmptyState message="No anomalies detected" icon="✅" />
      ) : (
        <AnimatePresence initial={false}>
          {anomalies.slice(0, 50).map((a, idx) => (
            <motion.div
              key={a.id || idx}
              initial={{ opacity: 0, x: 24, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: -20, scale: 0.95 }}
              transition={{ duration: 0.25 }}
              className="glass-card p-3 text-xs space-y-1.5 group"
            >
              <div className="flex items-center justify-between">
                <span className="text-white/60 font-mono text-[11px]">{a.node_id.slice(0, 10)}</span>
                <span className={`score-badge text-[9px] ${labelClass[a.anomaly_label] || 'label-normal'}`}>
                  {a.anomaly_label}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-white/35">{a.metric_name}</span>
                <span className={`stat-value text-[11px] ${a.anomaly_score > 0.7 ? 'text-red-400' : a.anomaly_score > 0.4 ? 'text-orange-400' : 'text-emerald-400'}`}>
                  {(a.anomaly_score * 100).toFixed(0)}%
                </span>
              </div>
              {a.confidence !== null && a.confidence !== undefined && (
                <div className="confidence-bar mt-1">
                  <div
                    className="confidence-bar-fill"
                    style={{
                      width: `${a.confidence * 100}%`,
                      background: `linear-gradient(90deg, rgba(0,212,255,0.6), rgba(168,85,247,0.4))`,
                    }}
                  />
                </div>
              )}
              {a.insight?.summary && (
                <p className="text-white/25 text-[10px] leading-relaxed mt-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                  {a.insight.summary}
                </p>
              )}
              {a.detected_at && (
                <p className="text-white/15 text-[9px]">{new Date(a.detected_at).toLocaleString()}</p>
              )}
            </motion.div>
          ))}
        </AnimatePresence>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const { tenantName, clearAuth } = useAuthStore();
  const { clusters, insights, loading, setClusters, setInsights, setLoading } = useClusterStore();
  const { setAnomalies, setLoading: setAnomalyLoading } = useAnomalyStore();

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    try {
      const response = await healthApi.get();
      setClusters(response.data.clusters);
      setInsights(response.data.insights || []);
    } catch {
      /* toast handled by interceptor */
    } finally {
      setLoading(false);
    }
  }, [setClusters, setInsights, setLoading]);

  const fetchAnomalies = useCallback(async () => {
    setAnomalyLoading(true);
    try {
      const response = await anomaliesApi.query({ page_size: 50 });
      setAnomalies(response.data.data, response.data.total);
    } catch {
      /* toast handled by interceptor */
    } finally {
      setAnomalyLoading(false);
    }
  }, [setAnomalies, setAnomalyLoading]);

  useEffect(() => {
    fetchHealth();
    fetchAnomalies();
    connectWebSocket();

    const interval = setInterval(() => {
      fetchAnomalies();
    }, 10000);

    return () => clearInterval(interval);
  }, [fetchHealth, fetchAnomalies]);

  const overallHealth = useMemo(() => {
    if (clusters.length === 0) return 0;
    return clusters.reduce((sum, c) => sum + c.health_score, 0) / clusters.length;
  }, [clusters]);

  const totalAnomalies = useAnomalyStore((s) => s.total);
  const criticalClusters = clusters.filter((c) => c.health_score > 0.7).length;

  return (
    <div className="min-h-screen bg-[#06080f] flex">
      <div className="ambient-glow w-[600px] h-[600px] bg-cyan-400/[0.02] -top-[200px] -left-[200px]" />
      <div className="ambient-glow w-[500px] h-[500px] bg-purple-500/[0.015] bottom-0 right-0" />

      <aside className="w-64 border-r border-white/[0.04] p-4 flex flex-col relative z-10 bg-[#06080f]/80 backdrop-blur-xl">
        <div className="flex items-center gap-3 mb-8 px-2">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-cyan-400/20 to-purple-500/20 border border-cyan-400/15 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="10" stroke="url(#sb-grad)" strokeWidth="2" strokeDasharray="4 2" />
              <circle cx="16" cy="16" r="4" fill="url(#sb-grad)" />
              <defs>
                <linearGradient id="sb-grad" x1="6" y1="6" x2="26" y2="26">
                  <stop stopColor="#00d4ff" />
                  <stop offset="1" stopColor="#a855f7" />
                </linearGradient>
              </defs>
            </svg>
          </div>
          <span className="font-bold text-sm gradient-text">AboutCloud</span>
        </div>

        <div className="glass-card p-3 mb-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-white/30 text-[9px] uppercase tracking-[0.15em] font-semibold">Overall Health</span>
            <HealthRing score={overallHealth} size={36} strokeWidth={2.5} />
          </div>
          <div className="grid grid-cols-2 gap-2 mt-2">
            <div className="text-center">
              <p className="stat-value text-white/80 text-sm">{clusters.length}</p>
              <p className="text-white/25 text-[9px]">Clusters</p>
            </div>
            <div className="text-center">
              <p className={`stat-value text-sm ${criticalClusters > 0 ? 'text-red-400' : 'text-emerald-400'}`}>{criticalClusters}</p>
              <p className="text-white/25 text-[9px]">Critical</p>
            </div>
          </div>
        </div>

        <p className="text-white/25 text-[9px] uppercase tracking-[0.15em] font-semibold mb-2 px-2">Clusters</p>
        <div className="flex-1 space-y-0.5 overflow-y-auto">
          {clusters.map((cluster) => {
            const dotColor = cluster.health_score > 0.7 ? 'bg-red-400 animate-pulse-dot' : cluster.health_score > 0.4 ? 'bg-orange-400' : 'bg-emerald-400';
            return (
              <button
                key={cluster.cluster_id}
                onClick={() => navigate(`/clusters/${cluster.cluster_id}`)}
                className="sidebar-link w-full text-left"
              >
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`} />
                <span className="truncate font-mono text-[11px]">{cluster.cluster_id.slice(0, 14)}</span>
              </button>
            );
          })}
          {clusters.length === 0 && !loading && (
            <p className="text-white/15 text-xs px-3 italic">No clusters found</p>
          )}
        </div>

        <div className="mt-auto pt-4 border-t border-white/[0.04]">
          <div className="flex items-center justify-between px-2">
            <span className="text-white/30 text-xs truncate max-w-[140px]">{tenantName}</span>
            <button
              onClick={() => { clearAuth(); navigate('/login'); }}
              className="text-white/25 hover:text-red-400 text-[11px] transition-colors font-medium"
            >
              Logout
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 flex flex-col overflow-hidden relative z-10">
        <header className="h-14 border-b border-white/[0.04] flex items-center justify-between px-6 bg-[#06080f]/60 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <h1 className="text-white font-semibold text-sm">Dashboard</h1>
            {totalAnomalies > 0 && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-400/10 text-cyan-400 border border-cyan-400/15 stat-value"
              >
                {totalAnomalies} anomalies
              </motion.span>
            )}
          </div>
          <span className="text-white/20 text-[11px] stat-value">
            {new Date().toLocaleTimeString()}
          </span>
        </header>

        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 p-6 overflow-y-auto space-y-6">
            <ErrorBoundary>
              {insights.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-3"
                >
                  <h2 className="text-white/35 text-[10px] uppercase tracking-[0.15em] font-semibold">Intelligence Insights</h2>
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                    {insights.map((insight) => (
                      <InsightCard
                        key={insight.cluster_id}
                        summary={insight.summary}
                        severity={insight.severity}
                        dominantType={insight.dominant_anomaly_type}
                        affectedMetrics={insight.affected_metrics}
                      />
                    ))}
                  </div>
                </motion.div>
              )}

              {loading ? (
                <DashboardSkeleton />
              ) : clusters.length === 0 ? (
                <EmptyState message="No clusters found. Ingest metrics to get started." icon="🔍" />
              ) : (
                <>
                  <h2 className="text-white/35 text-[10px] uppercase tracking-[0.15em] font-semibold">Cluster Health</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                    {clusters.map((cluster, idx) => (
                      <ClusterHealthCard
                        key={cluster.cluster_id}
                        cluster={cluster}
                        index={idx}
                        onClick={() => navigate(`/clusters/${cluster.cluster_id}`)}
                      />
                    ))}
                  </div>
                </>
              )}
            </ErrorBoundary>
          </div>

          <aside className="w-80 border-l border-white/[0.04] p-4 overflow-hidden flex flex-col bg-[#06080f]/40 backdrop-blur-sm">
            <h2 className="text-white/35 text-[10px] uppercase tracking-[0.15em] font-semibold mb-4">
              Anomaly Feed
            </h2>
            <ErrorBoundary>
              <LiveAnomalyFeed />
            </ErrorBoundary>
          </aside>
        </div>
      </main>
    </div>
  );
}
