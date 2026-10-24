import { defineConfig } from '@playwright/test'
import path from 'node:path'
const python = process.env.ASTRA_A_PYTHON
if (!python) throw new Error('ASTRA_A_PYTHON must point to the locked A validation environment.')
export default defineConfig({
  testDir: './e2e-integration',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  reporter: 'list',
  outputDir: 'test-results-integration',
  use: { baseURL: 'https://localhost:4175', ignoreHTTPSErrors: true, trace: 'retain-on-failure' },
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
      command: `"${python}" ../../server/tests/a_line/web_harness.py`,
      url: 'http://127.0.0.1:8011/health',
      reuseExistingServer: false,
    },
    {
      command: 'pnpm dev --port 4175 --strictPort',
      url: 'https://localhost:4175',
      ignoreHTTPSErrors: true,
      reuseExistingServer: false,
      env: {
        VITE_API_PROXY_TARGET: 'http://127.0.0.1:8011',
        ASTRA_TEST_TLS: path.resolve('../../.local/a-browser-tls'),
      },
    },
  ],
})
