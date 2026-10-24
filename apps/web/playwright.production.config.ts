import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e-production',
  outputDir: 'test-results-production',
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:4174' },
  webServer: {
    command: 'pnpm preview --port 4174 --strictPort',
    url: 'http://127.0.0.1:4174',
    reuseExistingServer: false,
  },
})
