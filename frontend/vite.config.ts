import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Same-origin in development, so the dashboard does not have to wait on
      // CORS during local work. Production still talks to the API origin
      // directly and relies on the allow-list in settings.
      '/auth': 'http://127.0.0.1:8000',
      '/users': 'http://127.0.0.1:8000',
      '/shipments': 'http://127.0.0.1:8000',
      '/warehouses': 'http://127.0.0.1:8000',
      '/tags': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
})
