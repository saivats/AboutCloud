import { motion } from 'framer-motion';

export default function LoadingSpinner({ size = 48, label }: { size?: number; label?: string }) {
  const r = (size - 6) / 2;
  const circumference = 2 * Math.PI * r;

  return (
    <div className="flex flex-col items-center justify-center w-full h-full min-h-[200px] gap-4">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="animate-spin-slow">
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke="rgba(0, 212, 255, 0.08)"
            strokeWidth="3"
          />
        </svg>
        <svg
          width={size} height={size}
          viewBox={`0 0 ${size} ${size}`}
          className="absolute inset-0"
          style={{ animation: 'orbit 1.2s linear infinite' }}
        >
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke="url(#spinner-gradient)"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={`${circumference * 0.3} ${circumference * 0.7}`}
          />
          <defs>
            <linearGradient id="spinner-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#00d4ff" stopOpacity="1" />
              <stop offset="100%" stopColor="#a855f7" stopOpacity="0.3" />
            </linearGradient>
          </defs>
        </svg>
      </div>
      {label && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-white/30 text-xs font-medium"
        >
          {label}
        </motion.p>
      )}
    </div>
  );
}
