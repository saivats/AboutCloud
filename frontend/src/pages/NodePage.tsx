import { useEffect, useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  Brush, ReferenceArea, ReferenceLine, Legend,
} from 'recharts';
import { anomaliesApi, AnomalyResult } from '@/api/client';
import LoadingSpinner from '@/components/LoadingSpinner';
import ErrorBoundary from '@/components/ErrorBoundary';
import EmptyState from '@/components/EmptyState';
import Skeleton from '@/components/Skeleton';

interface ChartDataPoint {
  time: string;
  timestamp: number;
  value: number;
  anomalyScore?: number;
  anomalyLabel?: string;
}

function MetricChart({
  metricName,
  data,
  anomalies,
}: {
  metricName: string;
  data: ChartDataPoint[];
  anomalies: AnomalyResult[];
}) {
  const [showAnomalies, setShowAnomalies] = useState(true);

  const anomalyWindows = useMemo(() =>
    anomalies
      .filter((a) => a.anomaly_label !== 'normal' && a.metric_name === metricName)
      .map((a) => ({
        start: new Date(a.window_start).getTime(),
        end: new Date(a.window_end).getTime(),
        label: a.anomaly_label,
        score: a.anomaly_score,
      })),
  [anomalies, metricName]);

  const windowColors: Record<string, string> = {
    spike: 'rgba(255, 68, 68, 0.06)',
    trend: 'rgba(255, 107, 53, 0.06)',
    seasonal: 'rgba(168, 85, 247, 0.06)',
  };

  const metricAnomalyCount = anomalies.filter((a) => a.metric_name === metricName && a.anomaly_label !== 'normal').length;
  const maxScore = anomalies.filter((a) => a.metric_name === metricName).reduce((m, a) => Math.max(m, a.anomaly_score), 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-6 mb-4"
    >
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <h3 className="text-white font-semibold text-sm">{metricName}</h3>
          {metricAnomalyCount > 0 && (
            <span className="text-[9px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/15 stat-value">
              {metricAnomalyCount} anomalies
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {maxScore > 0 && (
            <span className={`stat-value text-[11px] ${maxScore > 0.7 ? 'text-red-400' : maxScore > 0.4 ? 'text-orange-400' : 'text-emerald-400'}`}>
              Peak: {(maxScore * 100).toFixed(0)}%
            </span>
          )}
          <button
            onClick={() => setShowAnomalies(!showAnomalies)}
            className={`btn-ghost text-[10px] ${showAnomalies ? 'border-cyan-400/20 text-cyan-400 bg-cyan-400/5' : ''}`}
          >
            {showAnomalies ? '◉' : '○'} Anomalies
          </button>
        </div>
      </div>

      {data.length === 0 ? (
        <EmptyState message={`No data for ${metricName}`} icon="📊" />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={data}>
            <defs>
              <linearGradient id={`line-${metricName}`} x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#00d4ff" />
                <stop offset="100%" stopColor="#a855f7" />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
            <XAxis
              dataKey="time"
              tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 9 }}
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 9 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: 'rgba(6, 8, 15, 0.95)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '12px',
                fontSize: '11px',
                color: '#e2e8f0',
                backdropFilter: 'blur(20px)',
                boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
              }}
              formatter={(value: number, name: string) => {
                if (name === 'value') return [value.toFixed(2), 'Value'];
                if (name === 'anomalyScore') return [`${(value * 100).toFixed(0)}%`, 'Anomaly'];
                return [value, name];
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: '10px', color: 'rgba(255,255,255,0.3)' }}
            />

            {showAnomalies && anomalyWindows.map((w, i) => (
              <ReferenceArea
                key={`window-${i}`}
                x1={data.find((d) => d.timestamp >= w.start)?.time}
                x2={data.find((d) => d.timestamp >= w.end)?.time || data[data.length - 1]?.time}
                fill={windowColors[w.label] || 'rgba(255,255,255,0.02)'}
                strokeOpacity={0}
              />
            ))}

            <Line
              type="monotone"
              dataKey="value"
              stroke={`url(#line-${metricName})`}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#00d4ff', stroke: '#06080f', strokeWidth: 2 }}
              animationDuration={600}
              name="Value"
            />

            {showAnomalies && (
              <Line
                type="monotone"
                dataKey="anomalyScore"
                stroke="#ff6b35"
                strokeWidth={1}
                strokeDasharray="4 3"
                dot={false}
                animationDuration={600}
                name="Anomaly Score"
              />
            )}

            <Brush
              dataKey="time"
              height={22}
              stroke="rgba(0, 212, 255, 0.2)"
              fill="rgba(255,255,255,0.01)"
              tickFormatter={() => ''}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </motion.div>
  );
}

function InsightPanel({ anomaly }: { anomaly: AnomalyResult }) {
  if (!anomaly.insight && !anomaly.explanation) return null;

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="insight-card mt-2 text-[11px]"
    >
      {anomaly.insight?.summary && (
        <p className="text-white/70 leading-relaxed mb-2">{anomaly.insight.summary}</p>
      )}
      {anomaly.insight?.pattern_description && (
        <p className="text-white/40 text-[10px] mb-1">
          <span className="text-white/25 uppercase tracking-wider text-[9px]">Pattern: </span>
          {anomaly.insight.pattern_description}
        </p>
      )}
      {anomaly.insight?.recommendation && (
        <p className="text-cyan-400/50 text-[10px] mt-2 italic">
          💡 {anomaly.insight.recommendation}
        </p>
      )}
      {!anomaly.insight && anomaly.explanation && (
        <p className="text-white/50 leading-relaxed">{anomaly.explanation}</p>
      )}
    </motion.div>
  );
}

export default function NodePage() {
  const { nodeId } = useParams<{ nodeId: string }>();
  const navigate = useNavigate();

  const [anomalies, setAnomalies] = useState<AnomalyResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!nodeId) return;
    setLoading(true);
    try {
      const anomalyRes = await anomaliesApi.query({ node_id: nodeId, page_size: 500 });
      setAnomalies(anomalyRes.data.data);
    } catch {
      /* handled by interceptor */
    } finally {
      setLoading(false);
    }
  }, [nodeId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const metricNames = useMemo(() => [...new Set(anomalies.map((a) => a.metric_name))], [anomalies]);

  const buildChartData = useCallback((metricName: string): ChartDataPoint[] => {
    return anomalies
      .filter((a) => a.metric_name === metricName)
      .sort((a, b) => new Date(a.window_start).getTime() - new Date(b.window_start).getTime())
      .map((a) => ({
        time: new Date(a.window_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        timestamp: new Date(a.window_start).getTime(),
        value: a.magnitude !== null ? a.magnitude * 100 : a.anomaly_score * 100,
        anomalyScore: a.anomaly_score,
        anomalyLabel: a.anomaly_label,
      }));
  }, [anomalies]);

  const labelClass: Record<string, string> = {
    spike: 'label-spike',
    trend: 'label-trend',
    seasonal: 'label-seasonal',
    normal: 'label-normal',
  };

  const totalAnomalous = anomalies.filter((a) => a.anomaly_label !== 'normal').length;
  const avgScore = anomalies.length > 0 ? anomalies.reduce((s, a) => s + a.anomaly_score, 0) / anomalies.length : 0;
  const avgConfidence = anomalies.filter((a) => a.confidence).reduce((s, a) => s + (a.confidence || 0), 0) /
    (anomalies.filter((a) => a.confidence).length || 1);

  if (loading) return <div className="min-h-screen bg-[#06080f]"><LoadingSpinner label="Loading node metrics..." /></div>;

  return (
    <div className="min-h-screen bg-[#06080f] relative">
      <div className="ambient-glow w-[400px] h-[400px] bg-purple-500/[0.015] top-[10%] right-0" />

      <header className="h-14 border-b border-white/[0.04] flex items-center px-6 gap-4 bg-[#06080f]/80 backdrop-blur-md sticky top-0 z-20">
        <button
          onClick={() => navigate(-1)}
          className="text-white/35 hover:text-white text-xs transition-colors font-medium flex items-center gap-1"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
          Back
        </button>
        <div className="w-px h-5 bg-white/[0.06]" />
        <h1 className="text-white font-semibold text-sm">
          Node <span className="font-mono text-cyan-400">{nodeId?.slice(0, 14)}</span>
        </h1>
        <div className="flex-1" />
        <div className="flex items-center gap-4">
          <div className="text-center">
            <p className="stat-value text-white/70 text-sm">{metricNames.length}</p>
            <p className="text-white/25 text-[9px]">Metrics</p>
          </div>
          <div className="w-px h-6 bg-white/[0.06]" />
          <div className="text-center">
            <p className={`stat-value text-sm ${totalAnomalous > 0 ? 'text-orange-400' : 'text-emerald-400'}`}>{totalAnomalous}</p>
            <p className="text-white/25 text-[9px]">Anomalies</p>
          </div>
          <div className="w-px h-6 bg-white/[0.06]" />
          <div className="text-center">
            <p className="stat-value text-cyan-400 text-sm">{(avgConfidence * 100).toFixed(0)}%</p>
            <p className="text-white/25 text-[9px]">Confidence</p>
          </div>
        </div>
      </header>

      <div className="p-6">
        <ErrorBoundary>
          {metricNames.length === 0 ? (
            <EmptyState message="No metric data for this node" icon="📡" />
          ) : (
            <div className="space-y-4">
              {metricNames.map((metricName) => (
                <MetricChart
                  key={metricName}
                  metricName={metricName}
                  data={buildChartData(metricName)}
                  anomalies={anomalies}
                />
              ))}
            </div>
          )}

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-6 mt-6"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-white/35 text-[10px] uppercase tracking-[0.15em] font-semibold">Anomaly Details</h2>
              <span className="text-white/20 text-[10px] stat-value">{anomalies.length} total</span>
            </div>
            {anomalies.length === 0 ? (
              <EmptyState message="No anomalies detected" icon="✅" />
            ) : (
              <div className="overflow-x-auto max-h-[450px] overflow-y-auto">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-[#06080f] z-10">
                    <tr className="text-white/25 uppercase tracking-wider text-[10px] border-b border-white/[0.04]">
                      <th className="text-left py-3 px-3 font-semibold">Metric</th>
                      <th className="text-left py-3 px-3 font-semibold">Label</th>
                      <th className="text-right py-3 px-3 font-semibold">Score</th>
                      <th className="text-right py-3 px-3 font-semibold">Confidence</th>
                      <th className="text-left py-3 px-3 font-semibold">Window</th>
                      <th className="text-left py-3 px-3 font-semibold">Explanation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {anomalies
                      .sort((a, b) => b.anomaly_score - a.anomaly_score)
                      .slice(0, 100)
                      .map((a, idx) => {
                        const rowId = a.id || String(idx);
                        const isExpanded = expandedRow === rowId;
                        return (
                          <motion.tr
                            key={rowId}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: Math.min(idx * 0.01, 0.5) }}
                            className="table-row-interactive cursor-pointer"
                            onClick={() => setExpandedRow(isExpanded ? null : rowId)}
                          >
                            <td className="py-2.5 px-3 text-white/55">{a.metric_name}</td>
                            <td className="py-2.5 px-3">
                              <span className={`score-badge text-[9px] ${labelClass[a.anomaly_label] || ''}`}>
                                {a.anomaly_label}
                              </span>
                            </td>
                            <td className={`py-2.5 px-3 text-right stat-value ${
                              a.anomaly_score > 0.7 ? 'text-red-400' : a.anomaly_score > 0.4 ? 'text-orange-400' : 'text-emerald-400'
                            }`}>
                              {(a.anomaly_score * 100).toFixed(0)}%
                            </td>
                            <td className="py-2.5 px-3 text-right">
                              {a.confidence !== null && a.confidence !== undefined ? (
                                <div className="flex items-center justify-end gap-2">
                                  <div className="w-10 h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                                    <div
                                      className="h-full rounded-full"
                                      style={{
                                        width: `${(a.confidence || 0) * 100}%`,
                                        background: 'linear-gradient(90deg, #00d4ff, #a855f7)',
                                      }}
                                    />
                                  </div>
                                  <span className="text-white/40 stat-value text-[10px]">
                                    {((a.confidence || 0) * 100).toFixed(0)}%
                                  </span>
                                </div>
                              ) : (
                                <span className="text-white/15">—</span>
                              )}
                            </td>
                            <td className="py-2.5 px-3 text-white/25 stat-value text-[10px]">
                              {new Date(a.window_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </td>
                            <td className="py-2.5 px-3 text-white/35 max-w-[280px]">
                              <p className="truncate text-[11px]">{a.explanation || '—'}</p>
                              <AnimatePresence>
                                {isExpanded && <InsightPanel anomaly={a} />}
                              </AnimatePresence>
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
