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
      },
      animation: {
        'fade-in':   'fade-in 0.35s ease-out both',
        'scale-in':  'scale-in 0.25s ease-out both',
        'pulse-dot': 'pulse-dot 1.4s ease-in-out infinite',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
