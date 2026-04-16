import { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine,
} from 'recharts';
import { anomaliesApi, healthApi, AnomalyResult } from '@/api/client';
import LoadingSpinner from '@/components/LoadingSpinner';
import ErrorBoundary from '@/components/ErrorBoundary';
import EmptyState from '@/components/EmptyState';
import InsightCard from '@/components/InsightCard';
import Skeleton from '@/components/Skeleton';

interface NodeScore {
  node_id: string;
  score: number;
  rank: number;
}

interface TimelinePoint {
  time: string;
  score: number;
}

function HealthRingSmall({ score, size = 44 }: { score: number; size?: number }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const filled = c * score;
  const color = score > 0.7 ? '#ff4444' : score > 0.4 ? '#ff6b35' : '#00ff88';

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="3" />
        <motion.circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c - filled }}
          transition={{ duration: 1, ease: [0.25, 0.46, 0.45, 0.94] }}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ filter: `drop-shadow(0 0 4px ${color}40)` }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="stat-value text-[10px]" style={{ color }}>{(score * 100).toFixed(0)}</span>
      </div>
    </div>
  );
}

export default function ClusterPage() {
  const { clusterId } = useParams<{ clusterId: string }>();
  const navigate = useNavigate();

  const [nodes, setNodes] = useState<NodeScore[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyResult[]>([]);
  const [clusterScore, setClusterScore] = useState(0);
  const [loading, setLoading] = useState(true);
  const [clusterInsight, setClusterInsight] = useState<{ summary: string; severity: string; dominant_anomaly_type: string | null; affected_metrics: string[] } | null>(null);

  const fetchData = useCallback(async () => {
    if (!clusterId) return;
    setLoading(true);
    try {
      const [healthRes, anomalyRes] = await Promise.all([
        healthApi.get(),
        anomaliesApi.query({ cluster_id: clusterId, page_size: 200 }),
      ]);

      const cluster = healthRes.data.clusters.find((c) => c.cluster_id === clusterId);
      if (cluster) {
        setClusterScore(cluster.health_score);
        setNodes(cluster.top_anomalous_nodes);
      }

      const insight = healthRes.data.insights?.find((i) => i.cluster_id === clusterId);
      if (insight) {
        setClusterInsight(insight);
      }

      setAnomalies(anomalyRes.data.data);
    } catch {
      /* handled by interceptor */
    } finally {
      setLoading(false);
    }
  }, [clusterId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const timelineData = useMemo<TimelinePoint[]>(() =>
    anomalies
      .filter((a) => a.detected_at)
      .sort((a, b) => new Date(a.detected_at!).getTime() - new Date(b.detected_at!).getTime())
      .reduce<TimelinePoint[]>((acc, a) => {
        const time = new Date(a.detected_at!).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const existing = acc.find((p) => p.time === time);
        if (existing) {
          existing.score = Math.max(existing.score, a.anomaly_score);
        } else {
          acc.push({ time, score: a.anomaly_score });
        }
        return acc;
      }, []),
  [anomalies]);

  const scoreColor = clusterScore > 0.7 ? 'text-red-400' : clusterScore > 0.4 ? 'text-orange-400' : 'text-emerald-400';

  const labelClass: Record<string, string> = {
    spike: 'label-spike',
    trend: 'label-trend',
    seasonal: 'label-seasonal',
    normal: 'label-normal',
  };

  const anomalyBreakdown = useMemo(() => {
    const counts: Record<string, number> = { spike: 0, trend: 0, seasonal: 0, normal: 0 };
    anomalies.forEach((a) => { counts[a.anomaly_label] = (counts[a.anomaly_label] || 0) + 1; });
    return counts;
  }, [anomalies]);

  if (loading) return <div className="min-h-screen bg-[#06080f]"><LoadingSpinner label="Loading cluster data..." /></div>;

  return (
    <div className="min-h-screen bg-[#06080f] relative">
      <div className="ambient-glow w-[400px] h-[400px] bg-cyan-400/[0.015] top-0 right-[20%]" />

      <header className="h-14 border-b border-white/[0.04] flex items-center px-6 gap-4 bg-[#06080f]/80 backdrop-blur-md sticky top-0 z-20">
        <button
          onClick={() => navigate('/dashboard')}
          className="text-white/35 hover:text-white text-xs transition-colors font-medium flex items-center gap-1"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
          Dashboard
        </button>
        <div className="w-px h-5 bg-white/[0.06]" />
        <div className="flex-1 flex items-center gap-3">
          <h1 className="text-white font-semibold text-sm">
            Cluster <span className="font-mono text-cyan-400">{clusterId?.slice(0, 14)}</span>
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <HealthRingSmall score={clusterScore} size={36} />
          <span className={`stat-value text-lg ${scoreColor}`}>
            {(clusterScore * 100).toFixed(0)}%
          </span>
        </div>
      </header>

      <div className="p-6 space-y-6">
        <ErrorBoundary>
          {clusterInsight && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <InsightCard
                summary={clusterInsight.summary}
                severity={clusterInsight.severity}
                dominantType={clusterInsight.dominant_anomaly_type}
                affectedMetrics={clusterInsight.affected_metrics}
              />
            </motion.div>
          )}

          <div className="grid grid-cols-4 gap-3">
            {Object.entries(anomalyBreakdown).map(([label, count], i) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="glass-card p-4 text-center"
              >
                <span className={`score-badge text-[9px] mb-2 inline-flex ${labelClass[label]}`}>{label}</span>
                <p className="stat-value text-white/80 text-lg mt-1">{count}</p>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-6"
          >
            <h2 className="text-white/35 text-[10px] uppercase tracking-[0.15em] font-semibold mb-4">Health Timeline</h2>
            {timelineData.length === 0 ? (
              <EmptyState message="No timeline data" icon="📈" />
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={timelineData}>
                  <defs>
                    <linearGradient id="clusterScoreGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00d4ff" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#00d4ff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                  <XAxis dataKey="time" tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9 }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 1]} tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 9 }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      background: 'rgba(6, 8, 15, 0.95)',
                      border: '1px solid rgba(255,255,255,0.08)',
                      borderRadius: '12px',
                      fontSize: '11px',
                      color: '#e2e8f0',
                      backdropFilter: 'blur(20px)',
                    }}
                    formatter={(value: number) => [`${(value * 100).toFixed(0)}%`, 'Score']}
                  />
                  <ReferenceLine y={0.7} stroke="rgba(255,68,68,0.3)" strokeDasharray="4 4" />
                  <ReferenceLine y={0.4} stroke="rgba(255,107,53,0.2)" strokeDasharray="4 4" />
                  <Area
                    type="monotone" dataKey="score" stroke="#00d4ff" strokeWidth={2}
                    fill="url(#clusterScoreGrad)" animationDuration={800}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="glass-card p-6"
          >
            <h2 className="text-white/35 text-[10px] uppercase tracking-[0.15em] font-semibold mb-4">Node Rankings</h2>
            {nodes.length === 0 ? (
              <EmptyState message="No node data" icon="🖥️" />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-white/25 uppercase tracking-wider text-[10px] border-b border-white/[0.04]">
                      <th className="text-left py-3 px-3 font-semibold">Rank</th>
                      <th className="text-left py-3 px-3 font-semibold">Node</th>
                      <th className="text-center py-3 px-3 font-semibold">Health</th>
                      <th className="text-right py-3 px-3 font-semibold">Score</th>
                      <th className="text-right py-3 px-3 font-semibold">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nodes.map((node, idx) => {
                      const nodeAnomalies = anomalies.filter((a) => a.node_id === node.node_id);
                      const topMetric = nodeAnomalies.sort((a, b) => b.anomaly_score - a.anomaly_score)[0] || null;
                      const nodeScoreColor = node.score > 0.7 ? 'text-red-400' : node.score > 0.4 ? 'text-orange-400' : 'text-emerald-400';
                      const barColor = node.score > 0.7 ? 'bg-red-400' : node.score > 0.4 ? 'bg-orange-400' : 'bg-emerald-400';

                      return (
                        <motion.tr
                          key={node.node_id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: idx * 0.04 }}
                          className="table-row-interactive cursor-pointer"
                          onClick={() => navigate(`/nodes/${node.node_id}`)}
                        >
                          <td className="py-3 px-3 text-white/30 stat-value">#{node.rank}</td>
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-2">
                              <span className="text-white/75 font-mono text-[11px]">{node.node_id.slice(0, 14)}</span>
                              {topMetric && (
                                <span className="text-white/25 text-[10px]">{topMetric.metric_name}</span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-3">
                            <div className="flex justify-center">
                              <div className="w-20 h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                                <motion.div
                                  className={`h-full rounded-full ${barColor}`}
                                  initial={{ width: 0 }}
                                  animate={{ width: `${node.score * 100}%` }}
                                  transition={{ duration: 0.8, delay: 0.2 + idx * 0.05 }}
                                />
                              </div>
                            </div>
                          </td>
                          <td className={`py-3 px-3 text-right stat-value ${nodeScoreColor}`}>
                            {(node.score * 100).toFixed(0)}%
                          </td>
                          <td className="py-3 px-3 text-right">
                            <button
                              onClick={(e) => { e.stopPropagation(); navigate(`/nodes/${node.node_id}`); }}
                              className="text-cyan-400/50 hover:text-cyan-400 transition-colors text-[11px] font-medium"
                            >
                              View →
                            </button>
                          </td>
                        </motion.tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        </ErrorBoundary>
      </div>
    </div>
  );
}
