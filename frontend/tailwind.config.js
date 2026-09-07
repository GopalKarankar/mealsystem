/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}"
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          white: '#FFFFFF',
          black: '#1A1A1A',
          gray: '#F5F5F5',
          border: '#E0E0E0'
        },
        accent: {
          protein: '#F97316',
          carbs: '#3B82F6',
          fats: '#D97706',
          green: '#A8B8A8',
          beige: '#F5E6D3'
        },
        status: {
          success: '#2E7D32',
          warning: '#F97316',
          error: '#D32F2F',
          info: '#3B82F6'
        }
      },
      borderRadius: {
        xs: '4px',
        sm: '8px',
        md: '12px',
        lg: '16px'
      },
      boxShadow: {
        sm: '0 2px 8px rgba(0, 0, 0, 0.08)',
        md: '0 4px 12px rgba(0, 0, 0, 0.12)',
        lg: '0 8px 24px rgba(0, 0, 0, 0.15)',
        xl: '0 12px 32px rgba(0, 0, 0, 0.18)'
      }
    }
  },
  plugins: []
}
