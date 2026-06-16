import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/preview': 'http://127.0.0.1:8000',
      '/integrar': 'http://127.0.0.1:8000',
      '/inativar': 'http://127.0.0.1:8000',
      '/excluir': 'http://127.0.0.1:8000',
      '/consulta': 'http://127.0.0.1:8000',
      '/relatorio': 'http://127.0.0.1:8000',
      '/stats': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
