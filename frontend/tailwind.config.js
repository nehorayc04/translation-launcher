/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          yellow: "#fff700",
          cyan:   "#00ffe0",
          ink:    "#0a0a14",
        },
      },
      fontFamily: {
        display: ['Orbitron', 'system-ui', 'sans-serif'],
        hebrew:  ['Heebo', 'system-ui', 'sans-serif'],
        body:    ['Heebo', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        'fade-in':   { '0%': { opacity: 0, transform: 'translateY(8px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        'scale-in':  { '0%': { opacity: 0, transform: 'scale(0.95)'    }, '100%': { opacity: 1, transform: 'scale(1)'      } },
        'pulse-dot': { '0%, 100%': { opacity: 1 }, '50%': { opacity: 0.4 } },
        // Premium motion set (WeMod/Steam-style).
        'rise':      { '0%': { opacity: 0, transform: 'translateY(18px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        'shimmer':   { '0%': { backgroundPosition: '200% 0' }, '100%': { backgroundPosition: '-200% 0' } },
        'sheen':     { '0%': { transform: 'translateX(-150%) skewX(-18deg)' }, '60%,100%': { transform: 'translateX(250%) skewX(-18deg)' } },
        'float':     { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-10px)' } },
        'gradient-pan': { '0%,100%': { backgroundPosition: '0% 50%' }, '50%': { backgroundPosition: '100% 50%' } },
        'glow-pulse':{ '0%,100%': { opacity: 0.35 }, '50%': { opacity: 0.7 } },
      },
      animation: {
        'fade-in':   'fade-in 0.35s ease-out both',
        'scale-in':  'scale-in 0.25s ease-out both',
        'pulse-dot': 'pulse-dot 1.4s ease-in-out infinite',
        'rise':         'rise 0.5s cubic-bezier(0.22,1,0.36,1) both',
        'shimmer':      'shimmer 2.4s linear infinite',
        'sheen':        'sheen 1.1s ease-out',
        'float':        'float 6s ease-in-out infinite',
        'gradient-pan': 'gradient-pan 8s ease-in-out infinite',
        'glow-pulse':   'glow-pulse 3s ease-in-out infinite',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
