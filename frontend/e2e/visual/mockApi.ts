/**
 * Answers every backend request of a screenshot test from fixtures, so the
 * tests need no running backend and render the same data every time. A
 * request no handler matches gets a 404 and is recorded; `unmatched()` lists
 * them so a test can fail loudly instead of screenshotting an error toast.
 */
import type { Page, Route } from '@playwright/test'

export interface MockHandler {
  method?: string
  /** Matched against the path after `/api/v1`, query string excluded. */
  path: string | RegExp
  status?: number
  body?: unknown | ((url: URL) => unknown)
}

export interface MockedApi {
  unmatched(): string[]
}

function matches(handler: MockHandler, method: string, path: string): boolean {
  if (handler.method && handler.method !== method) return false
  return typeof handler.path === 'string' ? handler.path === path : handler.path.test(path)
}

export async function mockApi(page: Page, handlers: MockHandler[]): Promise<MockedApi> {
  const missed: string[] = []

  // A predicate, not a glob: Vite serves source modules such as
  // /src/features/x/api/y.ts, which a `**/api/**` glob would swallow.
  await page.route((url) => url.pathname.startsWith('/api/'), async (route: Route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace(/^\/api\/v1/, '')
    const method = request.method()
    // Later handlers win, so a test can override a default by appending.
    const handler = [...handlers].reverse().find((h) => matches(h, method, path))
    if (!handler) {
      missed.push(`${method} ${path}`)
      await route.fulfill({ status: 404, json: { detail: 'Not mocked', code: 'NotFoundError' } })
      return
    }
    const body = typeof handler.body === 'function' ? handler.body(url) : handler.body
    if (url.pathname.endsWith('/stream') || request.headers()['accept'] === 'text/event-stream') {
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' })
      return
    }
    await route.fulfill({ status: handler.status ?? 200, json: body ?? null })
  })

  return { unmatched: () => [...new Set(missed)] }
}
