import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuthStore, useUIStore } from '@/stores';
import { authApi } from '@/api/client';

export default function LoginPage() {
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const setAuth = useAuthStore((s) => s.setAuth);
  const addToast = useUIStore((s) => s.addToast);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;

    setLoading(true);
    try {
      const response = await authApi.login(apiKey.trim());
      const { access_token } = response.data;

      const payload = JSON.parse(atob(access_token.split('.')[1]));
      const tenantId = payload.sub || '';
      const tenantName = payload.tenant_name || 'Tenant';

      setAuth(access_token, tenantId, tenantName);
      addToast('Authenticated successfully', 'success');
      navigate('/dashboard');
    } catch {
      addToast('Invalid API key', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      <div className="absolute inset-0 bg-surface" />

      <div className="ambient-glow w-[500px] h-[500px] bg-primary/[0.04] top-[10%] left-[15%]" />
      <div className="ambient-glow w-[400px] h-[400px] bg-tertiary/[0.04] bottom-[15%] right-[10%]" />
      <div className="ambient-glow w-[300px] h-[300px] bg-primary-container/[0.03] top-[50%] right-[30%]" />

      <div className="absolute inset-0 opacity-[0.015]"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, rgba(255,255,255,0.3) 1px, transparent 0)`,
          backgroundSize: '40px 40px',
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 40, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}
        className="relative z-10 w-full max-w-md px-4"
      >
        <div className="glass-modal p-10">
          <div className="text-center mb-10">
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ delay: 0.2, type: 'spring', stiffness: 180, damping: 15 }}
              className="inline-flex items-center justify-center w-20 h-20 rounded-3xl bg-gradient-to-br from-primary/10 to-tertiary/10 flex-shrink-0 relative mb-5"
            >
              <div className="absolute inset-0 rounded-3xl animate-pulse-glow" />
              <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
                <circle cx="18" cy="18" r="14" stroke="url(#logo-grad)" strokeWidth="2" strokeDasharray="6 3" />
                <circle cx="18" cy="18" r="8" fill="url(#logo-grad)" fillOpacity="0.15" />
                <circle cx="18" cy="18" r="4" fill="url(#logo-grad)" />
                <defs>
                  <linearGradient id="logo-grad" x1="4" y1="4" x2="32" y2="32">
                    <stop stopColor="var(--primary)" />
                    <stop offset="1" stopColor="var(--tertiary)" />
                  </linearGradient>
                </defs>
              </svg>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 }}
              className="text-4xl font-display font-bold tracking-tight gradient-text mb-2"
            >
              AboutCloud
            </motion.h1>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.45 }}
              className="text-slate-400 text-sm font-medium"
            >
              Cloud Anomaly Analytics Platform
            </motion.p>
          </div>

          <motion.form
            onSubmit={handleSubmit}
            className="space-y-6"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <div>
              <label htmlFor="api-key-input" className="block text-[10px] font-semibold text-slate-400 mb-2.5 uppercase tracking-widest">
                API Key
              </label>
              <input
                id="api-key-input"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your API key"
                className="w-full px-5 py-4 bg-surface-container-high/40 rounded-xl text-slate-200 
                           placeholder-slate-500 text-sm font-medium transition-all duration-200"
                autoFocus
              />
            </div>

            <motion.button
              type="submit"
              disabled={loading || !apiKey.trim()}
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.98 }}
              className="w-full py-3.5 btn-primary text-sm rounded-xl"
            >
              {loading ? (
                <span className="inline-flex items-center gap-2">
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                    className="inline-block w-4 h-4 border-2 border-[#06080f]/30 border-t-[#06080f] rounded-full"
                  />
                  Authenticating...
                </span>
              ) : (
                'Sign In'
              )}
            </motion.button>
          </motion.form>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.7 }}
            className="flex items-center justify-center gap-2 mt-8"
          >
            <div className="w-1.5 h-1.5 rounded-full bg-anomaly-normal animate-pulse-dot" />
            <p className="text-slate-400 text-[11px] font-medium">Secure multi-tenant authentication</p>
          </motion.div>
        </div>
      </motion.div>
    </div>
  );
}
