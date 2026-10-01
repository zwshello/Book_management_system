import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')

  return {
    plugins: [vue()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        '/api/v1/auth': env.VITE_USER_SERVICE_TARGET || 'http://127.0.0.1:8001',
        '/api/v1/users': env.VITE_USER_SERVICE_TARGET || 'http://127.0.0.1:8001',
        '/api/v1/books': env.VITE_BOOK_SERVICE_TARGET || 'http://127.0.0.1:8002',
        '/api/v1/categories': env.VITE_BOOK_SERVICE_TARGET || 'http://127.0.0.1:8002',
        '/api/v1/borrows': env.VITE_BORROW_SERVICE_TARGET || 'http://127.0.0.1:8003',
        '/api/v1/statistics': env.VITE_STATISTICS_SERVICE_TARGET || 'http://127.0.0.1:8004',
      },
    },
  }
})
