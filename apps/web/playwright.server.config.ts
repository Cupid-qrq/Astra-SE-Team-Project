import { defineConfig } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import path from 'node:path'

const python = process.env.ASTRA_SERVER_PYTHON
if (!python) throw new Error('ASTRA_SERVER_PYTHON must point to the locked formal environment.')
const run = process.env.ASTRA_BROWSER_RUN || randomUUID().replaceAll('-', '')
process.env.ASTRA_BROWSER_RUN = run
export default defineConfig({
  testDir: './e2e-integration',
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  retries: 0,
  forbidOnly: !!process.env.CI,
  reporter: 'list',
  outputDir: 'test-results/server',
  globalTeardown: './scripts/server-browser-teardown.ts',
  use: {
    baseURL: 'https://localhost:4175',
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 10_000,
  },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1366, height: 768 } } },
    { name: 'wide', use: { viewport: { width: 1440, height: 900 } } },
    {
      name: 'mobile',
      use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
  ],
  webServer: [
    {
      command: `"${python}" ../../server/tests/shared/web_harness.py`,
      url: 'http://127.0.0.1:8012/health/live',
      reuseExistingServer: false,
      env: { ASTRA_BROWSER_RUN: run },
    },
    {
      command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 4175 --strictPort',
      url: 'https://localhost:4175',
      ignoreHTTPSErrors: true,
      reuseExistingServer: false,
      env: {
        VITE_API_PROXY_TARGET: 'http://127.0.0.1:8012',
        ASTRA_TEST_TLS: path.resolve('../../.local/b-browser-tls'),
      },
    },
  ],
})
