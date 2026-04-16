import { motion, AnimatePresence } from 'framer-motion';
import { useUIStore } from '@/stores';

const iconMap = {
  error: '✕',
  success: '✓',
  info: 'ℹ',
};

export default function ToastContainer() {
  const toasts = useUIStore((s) => s.toasts);
  const removeToast = useUIStore((s) => s.removeToast);

  const colorMap = {
    error: 'border-red-500/25 bg-gradient-to-r from-red-500/10 to-red-500/5 text-red-300',
    success: 'border-emerald-500/25 bg-gradient-to-r from-emerald-500/10 to-emerald-500/5 text-emerald-300',
    info: 'border-cyan-400/25 bg-gradient-to-r from-cyan-400/10 to-cyan-400/5 text-cyan-300',
  };

  const iconColor = {
    error: 'bg-red-500/20 text-red-400',
    success: 'bg-emerald-500/20 text-emerald-400',
    info: 'bg-cyan-400/20 text-cyan-400',
  };

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, x: 80, scale: 0.9, filter: 'blur(4px)' }}
            animate={{ opacity: 1, x: 0, scale: 1, filter: 'blur(0px)' }}
            exit={{ opacity: 0, x: 80, scale: 0.9, filter: 'blur(4px)' }}
            transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
            className={`glass-card px-4 py-3 border cursor-pointer flex items-center gap-3 ${colorMap[toast.type]}`}
            onClick={() => removeToast(toast.id)}
          >
            <span className={`w-6 h-6 rounded-lg flex items-center justify-center text-xs font-bold ${iconColor[toast.type]}`}>
              {iconMap[toast.type]}
            </span>
            <p className="text-sm font-medium flex-1">{toast.message}</p>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
