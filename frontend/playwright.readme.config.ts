/**
 * Captures the README pictures (e2e/readme) with the same build, viewport and
 * locale as the screenshot tests. One worker, since the walkthrough is a
 * single long run and the order of its frames matters.
 */
import { defineConfig } from '@playwright/test'

import visual from './playwright.config'

export default defineConfig({
  ...visual,
  testDir: './e2e/readme',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
})
