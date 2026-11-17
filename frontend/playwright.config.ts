/**
 * Screenshot tests of the key screens against committed baselines. They run
 * inside the pinned Playwright image (`npm run test:visual`) so fonts and
 * rendering match on every machine, against the Vite dev server with the API
 * mocked per test (e2e/visual/mockApi.ts). They are run on demand, not in CI.
 */
import { defineConfig, devices } from '@playwright/test'

const PORT = 5199

export default defineConfig({
  testDir: './e2e/visual',
  snapshotPathTemplate: '{testDir}/baselines/{testFilePath}/{arg}{ext}',
  fullyParallel: true,
  forbidOnly: true,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  outputDir: 'test-results',
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.002, animations: 'disabled', caret: 'hide' },
  },
  use: {
    ...devices['Desktop Chrome'],
    baseURL: `http://127.0.0.1:${PORT}`,
    viewport: { width: 1440, height: 900 },
    locale: 'en-GB',
    timezoneId: 'Europe/Vienna',
    colorScheme: 'light',
  },
  webServer: {
    // A production build, so no dev-only overlay such as the Vue devtools
    // button ends up in a screenshot.
    command: `npx vite build --outDir node_modules/.visual-dist --emptyOutDir --logLevel error && npx vite preview --outDir node_modules/.visual-dist --port ${PORT} --strictPort --host 127.0.0.1`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
