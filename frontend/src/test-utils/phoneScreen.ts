import { vi } from 'vitest'

import { PHONE_MEDIA_QUERY } from '@/core/composables/usePhoneLayout'

/**
 * Stubs matchMedia so the phone breakpoint matches, or not, and every other
 * query does not. It replaces the always-false stub of vitest.setup.ts, so a
 * spec calls it before mounting.
 */
export function stubPhoneScreen(phone: boolean): void {
  vi.stubGlobal(
    'matchMedia',
    vi.fn<(query: string) => unknown>().mockImplementation((query: string) => ({
      matches: phone && query === PHONE_MEDIA_QUERY,
      media: query,
      onchange: null,
      addListener: vi.fn<() => void>(),
      removeListener: vi.fn<() => void>(),
      addEventListener: vi.fn<() => void>(),
      removeEventListener: vi.fn<() => void>(),
      dispatchEvent: vi.fn<() => void>(),
    })),
  )
}
