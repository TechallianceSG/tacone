import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env vars: .env.development / .env.staging / .env.production
  const env = loadEnv(mode, process.cwd(), '')
  const portalPort = env.VITE_PORTAL_PORT || '3000'
  const authPort = env.VITE_AUTH_PORT || '3001'

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
        // User Admin (auth, users, roles, permissions) — per-environment
        '/api/auth': {
          target: `http://127.0.0.1:${authPort}`,
          changeOrigin: true,
        },
        '/api/public': {
          target: `http://127.0.0.1:${authPort}`,
          changeOrigin: true,
        },
        '/api/users': {
          target: `http://127.0.0.1:${authPort}`,
          changeOrigin: true,
        },
        '/api/roles': {
          target: `http://127.0.0.1:${authPort}`,
          changeOrigin: true,
        },
        '/api/permissions': {
          target: `http://127.0.0.1:${authPort}`,
          changeOrigin: true,
        },
        '/api/audit-logs': {
          target: `http://127.0.0.1:${authPort}`,
          changeOrigin: true,
        },
        '/api/login-sessions': {
          target: `http://127.0.0.1:${authPort}`,
          changeOrigin: true,
        },
        '/api/dashboard': {
          target: `http://127.0.0.1:${authPort}`,
          changeOrigin: true,
        },
        // Portal — per-environment
        '/api/portal': {
          target: `http://127.0.0.1:${portalPort}`,
          changeOrigin: true,
        },
        // Shared services (fixed ports across all environments)
        '/api/employees': {
          target: 'http://127.0.0.1:8004',
          changeOrigin: true,
        },
        '/api/masterdata': {
          target: 'http://127.0.0.1:8007',
          changeOrigin: true,
        },
        '/api/messages': {
          target: 'http://127.0.0.1:8012',
          changeOrigin: true,
        },
        '/api/payroll': {
          target: 'http://127.0.0.1:8016',
          changeOrigin: true,
        },
        '/api/salary': {
          target: 'http://127.0.0.1:8016',
          changeOrigin: true,
        },
        '/api/timesheet': {
          target: 'http://127.0.0.1:8002',
          changeOrigin: true,
        },
        '/api/expense': {
          target: 'http://127.0.0.1:8003',
          changeOrigin: true,
        },
        '/api/selfservice': {
          target: 'http://127.0.0.1:8018',
          changeOrigin: true,
        },
      },
    },
  }
})
