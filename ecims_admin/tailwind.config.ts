import type { Config } from 'tailwindcss';

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: {
          900: '#0b1220',
          800: '#111a2e',
          700: '#19243c'
        }
      },
      boxShadow: {
        soft: '0 8px 24px rgba(2, 6, 23, 0.25)'
      }
    }
  },
  plugins: []
} satisfies Config;
