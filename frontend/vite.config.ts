import fs from 'node:fs'
import path from 'node:path'
import type { ProxyOptions } from 'vite'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const API = 'http://127.0.0.1:8000'

/** SPA routes that share prefixes with the API — browser GET (Accept: text/html) must not be proxied. */
function apiProxy(): ProxyOptions {
  return {
    target: API,
    bypass(req) {
      const accept = String(req.headers.accept || '')
      const htmlNav = accept.toLowerCase().includes('text/html')
      // #region agent log
      try {
        fs.appendFileSync(
          '/Users/jean.nascimento/Projetos/avs-management/.cursor/debug-718b43.log',
          JSON.stringify({
            sessionId: '718b43',
            runId: 'post-fix',
            hypothesisId: 'A',
            location: 'vite.config.ts:bypass',
            message: 'proxy decision',
            data: {
              url: req.url,
              method: req.method,
              htmlNav,
              accept: accept.slice(0, 80),
            },
            timestamp: Date.now(),
          }) + '\n',
        )
      } catch {
        /* ignore */
      }
      // #endregion
      if (htmlNav) return '/index.html'
      return undefined
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    proxy: {
      '/preview': API,
      '/integrar': API,
      '/inativar': apiProxy(),
      '/excluir': API,
      '/consulta': API,
      '/relatorio': API,
      '/stats': API,
      '/auth': API,
      '/orcamentos': apiProxy(),
      '/faturamento': apiProxy(),
      '/documentos': apiProxy(),
      '/health': API,
      '/static': API,
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
