import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// vite.config.js — Vite Build Tool Configuration
//
// What this file does:
// - Tells Vite which plugins to use (React + Tailwind)
// - Sets up a proxy so API calls to /api/* during development
//   are forwarded to the FastAPI backend at localhost:8000
//   This avoids CORS issues during development and means we
//   can write fetch('/api/health') instead of fetch('http://localhost:8000/api/health')

export default defineConfig({
  plugins: [
    react(),       // Enables JSX transformation and React Fast Refresh
    tailwindcss(), // Processes Tailwind utility classes
  ],

  server: {
    port: 5173, // React dev server port

    proxy: {
      // Any request starting with /api gets forwarded to the backend
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
