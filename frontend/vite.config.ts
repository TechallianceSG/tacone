import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env vars: .env.development / .env.staging / .env.production
  const env = loadEnv(mode, process.cwd(), '')
  const portalPort = env.VITE_PORTAL_PORT || '3000'

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        // ── Unified API Gateway ──
        // All /api/* requests go to Portal (:3000), which forwards to
        // the appropriate internal backend service.
        '/api': {
          target: `http://127.0.0.1:${portalPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
