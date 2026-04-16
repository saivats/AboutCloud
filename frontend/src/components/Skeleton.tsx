import { motion } from 'framer-motion';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'card' | 'circle' | 'chart';
  count?: number;
}

function SkeletonLine({ className = '', delay = 0 }: { className?: string; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay }}
      className={`skeleton ${className}`}
    />
  );
}

export default function Skeleton({ className = '', variant = 'text', count = 1 }: SkeletonProps) {
  if (variant === 'card') {
    return (
      <div className="glass-card p-6 space-y-4">
        <div className="flex items-center justify-between">
          <SkeletonLine className="h-4 w-24" />
          <SkeletonLine className="h-10 w-10 rounded-full" delay={0.05} />
        </div>
        <SkeletonLine className="h-3 w-32" delay={0.1} />
        <div className="space-y-2 mt-4">
          <SkeletonLine className="h-3 w-full" delay={0.15} />
          <SkeletonLine className="h-3 w-3/4" delay={0.2} />
          <SkeletonLine className="h-3 w-1/2" delay={0.25} />
        </div>
      </div>
    );
  }

  if (variant === 'chart') {
    return (
      <div className="glass-card p-6">
        <SkeletonLine className="h-4 w-40 mb-4" />
        <div className="flex items-end gap-1 h-[200px]">
          {Array.from({ length: 20 }).map((_, i) => (
            <SkeletonLine
              key={i}
              className="flex-1"
              delay={i * 0.02}
            />
          ))}
        </div>
      </div>
    );
  }

  if (variant === 'circle') {
    return <SkeletonLine className={`rounded-full ${className}`} />;
  }

  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonLine
          key={i}
          className={`h-3 ${i === count - 1 ? 'w-2/3' : 'w-full'} ${className}`}
          delay={i * 0.05}
        />
      ))}
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.07 }}
        >
          <Skeleton variant="card" />
        </motion.div>
      ))}
    </div>
  );
}

export function FeedSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.04 }}
          className="glass-card p-3 space-y-2"
        >
          <div className="flex justify-between">
            <SkeletonLine className="h-3 w-16" />
            <SkeletonLine className="h-4 w-12 rounded-full" />
          </div>
          <SkeletonLine className="h-3 w-24" delay={0.05} />
        </motion.div>
      ))}
    </div>
  );
}
