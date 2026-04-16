import { motion } from 'framer-motion';

interface EmptyStateProps {
  message?: string;
  icon?: string;
  action?: { label: string; onClick: () => void };
}

export default function EmptyState({
  message = 'No data available',
  icon = '📊',
  action,
}: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col items-center justify-center py-16 px-6"
    >
      <motion.div
        initial={{ scale: 0.8 }}
        animate={{ scale: 1 }}
        transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
        className="w-20 h-20 rounded-2xl bg-gradient-to-br from-white/[0.04] to-white/[0.02] border border-white/[0.06] flex items-center justify-center mb-5"
      >
        <span className="text-3xl">{icon}</span>
      </motion.div>
      <p className="text-white/35 text-sm font-medium text-center max-w-xs leading-relaxed">
        {message}
      </p>
      {action && (
        <motion.button
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          onClick={action.onClick}
          className="mt-5 btn-ghost text-xs"
        >
          {action.label}
        </motion.button>
      )}
    </motion.div>
  );
}
