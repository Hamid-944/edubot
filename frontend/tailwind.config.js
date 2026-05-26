/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        dark: { 950: '#07070f', 900: '#0e0e1a', 800: '#16162a', 700: '#1e1e38' },
      },
      animation: {
        'blob':        'blob 12s ease-in-out infinite',
        'blob-slow':   'blob 18s ease-in-out infinite',
        'shimmer':     'shimmer 2s linear infinite',
        'fade-up':     'fadeUp 0.4s ease-out',
        'spin-slow':   'spin 8s linear infinite',
        'pulse-glow':  'pulseGlow 2s ease-in-out infinite',
        'bar-fill':    'barFill 0.8s ease-out forwards',
        'cursor-blink':'cursorBlink 1s step-end infinite',
      },
      keyframes: {
        blob: {
          '0%,100%': { transform: 'translate(0,0) scale(1)' },
          '33%':     { transform: 'translate(40px,-30px) scale(1.1)' },
          '66%':     { transform: 'translate(-20px,20px) scale(0.9)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% center' },
          '100%': { backgroundPosition:  '200% center' },
        },
        fadeUp: {
          '0%':   { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%,100%': { boxShadow: '0 0 8px 2px currentColor' },
          '50%':     { boxShadow: '0 0 24px 6px currentColor' },
        },
        barFill: {
          '0%':   { width: '0%' },
          '100%': { width: 'var(--bar-width)' },
        },
        cursorBlink: {
          '0%,100%': { opacity: '1' },
          '50%':     { opacity: '0' },
        },
      },
      backdropBlur: { xs: '2px' },
      boxShadow: {
        'glow-amber':   '0 0 20px 4px rgba(245,158,11,0.25)',
        'glow-emerald': '0 0 20px 4px rgba(16,185,129,0.25)',
        'glow-blue':    '0 0 20px 4px rgba(59,130,246,0.25)',
        'glow-violet':  '0 0 20px 4px rgba(139,92,246,0.25)',
        'glow-indigo':  '0 0 20px 4px rgba(99,102,241,0.25)',
      },
    },
  },
  plugins: [],
}
