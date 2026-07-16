/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f7f0',
          100: '#dde8dd',
          200: '#bdd4bd',
          300: '#8ec88e',
          400: '#5db85a',
          500: '#407e3c',
          600: '#2d5c29',
          700: '#1a3c18',
          800: '#112610',
          900: '#0a160a',
        },
      },
    },
  },
  plugins: [],
};

