import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev: `npm run dev` with `campus serve` running; /api/* is proxied to the backend.
// Build: served by the backend at /ui/, calling the API on the same origin.
export default defineConfig({
  base: '/ui/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: process.env.CAMPUS_API ?? 'http://127.0.0.1:8765',
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
