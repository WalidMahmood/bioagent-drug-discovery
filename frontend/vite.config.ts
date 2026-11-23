import react from '@vitejs/plugin-react'
import path from 'path'
import { defineConfig } from 'vite'
import { bioAgentApiPlugin } from './apiMiddleware.ts'

export default defineConfig({
  plugins: [react(), bioAgentApiPlugin()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    hmr: false,
  },
  preview: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
  },
})
