import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      // jsdom sends a request no spec mocked for real, to its own origin.
      // The default, http://localhost:3000, is where the dev backend
      // listens, and its answers would land in later tests. The reserved
      // .invalid domain never resolves, so such a request fails the same
      // way on every machine.
      environmentOptions: { jsdom: { url: 'http://glados.invalid/' } },
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      setupFiles: ['./vitest.setup.ts'],
      // `npm run test:coverage` runs the suite with coverage, and CI's unit
      // test step uses it, so the thresholds below fail the build.
      coverage: {
        provider: 'v8',
        include: ['src/**/*.{ts,vue}'],
        exclude: [
          'src/**/__tests__/**',
          'src/**/*.d.ts',
          'src/test-utils/**',
          'src/core/api/generated/**',
          'src/core/i18n/locales/**',
        ],
        reporter: ['text-summary', 'lcov'],
        // About one point below what the suite covered when they were set, so
        // a change that drops coverage noticeably fails. Raise them as
        // coverage grows, never lower them to let a change through.
        thresholds: {
          lines: 74,
          statements: 73,
          branches: 66,
          functions: 60,
        },
      },
      // Before each test, `restoreMocks` puts back every method that
      // `vi.spyOn` replaced, and `clearMocks` empties the call history of
      // every mock, so a spy or a module-level `vi.fn()` never carries calls
      // or a replaced method into the next test. `mockReset` stays off: it
      // would also drop the implementations a spec gives its mocks once at
      // module scope or in a `vi.mock` factory (and the matchMedia stub in
      // vitest.setup.ts), which those specs rely on by design. A
      // `mockReturnValue` set inside a test therefore still lasts until the
      // spec overrides it, so each spec sets those in its own `beforeEach`.
      restoreMocks: true,
      clearMocks: true,
    },
  }),
)
