/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#0c1324',
          container: {
            lowest: '#070d1f',
            low: '#151b2d',
            DEFAULT: '#191f31',
            high: '#23293c',
            highest: '#2e3447',
          }
        },
        primary: {
          DEFAULT: '#8aebff',
          container: '#22d3ee',
        },
        tertiary: {
          DEFAULT: '#ecd3ff',
        },
        outline: {
          variant: '#3c494c',
        },
        navy: {
          900: '#0c1324',
          800: '#151b2d',
          700: '#23293c',
          600: '#2e3447',
        },
        cyan: {
          400: '#8aebff',
          500: '#22d3ee',
        },
        anomaly: {
          spike: '#ffb4ab',
          trend: '#ff8c5a',
          seasonal: '#ecd3ff',
          normal: '#a2eeff',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Manrope', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'monospace'],
      },
      backdropBlur: {
        '16': '16px',
        '20': '20px',
      },
      boxShadow: {
        'ambient': '0px 20px 40px rgba(0, 0, 0, 0.4)',
        'neon': '0 0 12px var(--primary)',
      },
      animation: {
        'pulse-cyan': 'pulse-cyan 2s ease-in-out infinite',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 0.3s ease-out',
        'spin-slow': 'spin 2s linear infinite',
        'orbit': 'orbit 1.2s linear infinite',
        'pulse-glow': 'pulse-glow 2.5s ease-in-out infinite',
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
        'float': 'float 4s ease-in-out infinite',
        'breathing': 'breathing 3s ease-in-out infinite',
      },
      keyframes: {
        'pulse-cyan': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'orbit': {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 8px rgba(138, 235, 255, 0.1)' },
          '50%': { boxShadow: '0 0 20px rgba(138, 235, 255, 0.3), 0 0 40px rgba(138, 235, 255, 0.1)' },
        },
        'pulse-dot': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.5', transform: 'scale(0.85)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        'breathing': {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '0.8' },
        },
      },
    },
  },
  plugins: [],
};
