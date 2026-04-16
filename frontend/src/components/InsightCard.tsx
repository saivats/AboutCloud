import { motion } from 'framer-motion';

interface InsightCardProps {
  summary: string;
  severity?: string;
  dominantType?: string | null;
  affectedMetrics?: string[];
  recommendation?: string | null;
}

const severityConfig: Record<string, { border: string; glow: string; badge: string }> = {
  critical: {
    border: 'border-red-500/20',
    glow: 'shadow-[0_0_20px_rgba(255,68,68,0.08)]',
    badge: 'score-critical',
  },
  warning: {
    border: 'border-orange-500/20',
    glow: 'shadow-[0_0_20px_rgba(255,107,53,0.06)]',
    badge: 'score-warning',
  },
  low: {
    border: 'border-emerald-500/15',
    glow: '',
    badge: 'score-healthy',
  },
};

export default function InsightCard({
  summary,
  severity = 'low',
  dominantType,
  affectedMetrics = [],
  recommendation,
}: InsightCardProps) {
  const config = severityConfig[severity] || severityConfig.low;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`insight-card ${config.glow}`}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-cyan-400 flex-shrink-0 mt-0.5">
            <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="currentColor" fillOpacity="0.6" />
          </svg>
          <p className="text-white/80 text-xs leading-relaxed flex-1">{summary}</p>
        </div>
        {severity !== 'low' && (
          <span className={`score-badge text-[9px] flex-shrink-0 ${config.badge}`}>
            {severity}
          </span>
        )}
      </div>

      {dominantType && (
        <div className="flex items-center gap-2 mt-2">
          <span className="text-white/25 text-[10px] uppercase tracking-wider">Pattern:</span>
          <span className={`score-badge text-[9px] label-${dominantType}`}>
            {dominantType}
          </span>
        </div>
      )}

      {affectedMetrics.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {affectedMetrics.map((m) => (
            <span key={m} className="text-[9px] px-2 py-0.5 rounded-full bg-white/[0.04] text-white/40 border border-white/[0.06]">
              {m}
            </span>
          ))}
        </div>
      )}

      {recommendation && (
        <p className="text-white/30 text-[10px] mt-3 leading-relaxed italic pl-3 border-l border-white/[0.06]">
          💡 {recommendation}
        </p>
      )}
    </motion.div>
  );
}
