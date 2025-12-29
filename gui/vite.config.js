import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      // Proxy these specific endpoints directly to backend root if not under /api
      '/health': 'http://localhost:8000',
      '/status': 'http://localhost:8000',
      '/test-connection': 'http://localhost:8000',
      '/single-mapping': 'http://localhost:8000',
      '/bulk-mapping': 'http://localhost:8000',
      '/map-subnet': 'http://localhost:8000',
      '/stop-mapping': 'http://localhost:8000',
      '/emergency-stop': 'http://localhost:8000',
      '/get-logs': 'http://localhost:8000',
      '/progress': 'http://localhost:8000',
      '/update-tags': 'http://localhost:8000',
      '/update-ip-tags': 'http://localhost:8000',
      '/cert-status': 'http://localhost:8000',
      '/generate-pki': 'http://localhost:8000',
      '/upload-certs': 'http://localhost:8000',
      '/download-cert': 'http://localhost:8000',
    }
  }
})
