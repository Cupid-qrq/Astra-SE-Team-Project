import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'

export default defineConfig(({ mode, command }) => ({
  plugins: [react()],
  publicDir: command === 'serve' && mode === 'mock' ? 'public' : false,
  define: { __MOCK__: JSON.stringify(command === 'serve' && mode === 'mock') },
  server: {
    host: '127.0.0.1',
    ...(process.env.ASTRA_TEST_TLS
      ? {
          https: {
            cert: readFileSync(`${process.env.ASTRA_TEST_TLS}/cert.pem`),
            key: readFileSync(`${process.env.ASTRA_TEST_TLS}/key.pem`),
          },
        }
      : {}),
    proxy: { '/api': { target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000' } },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
}))
