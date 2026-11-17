import { vi } from 'vitest'

// jsdom does not implement matchMedia; PrimeVue's Select (and several other
// components) call it in their mounted hook to bind a responsive-breakpoint
// listener. The stub lives here, via `test.setupFiles`, so every spec gets it
// without its own copy. A spec that needs matchMedia to behave statefully
// (e.g. simulating an OS dark-mode change) stubs its own on top of this one,
// see `core/stores/__tests__/layoutStore.spec.ts`.
vi.stubGlobal(
  'matchMedia',
  vi.fn<(query: string) => unknown>().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn<() => void>(),
    removeListener: vi.fn<() => void>(),
    addEventListener: vi.fn<() => void>(),
    removeEventListener: vi.fn<() => void>(),
    dispatchEvent: vi.fn<() => void>(),
  })),
)

// jsdom does not implement ResizeObserver; PrimeVue's Textarea (autoResize)
// and several other components call it in their mounted hook. Same
// consolidation as above - was duplicated verbatim across 45+ spec files.
class ResizeObserverMock {
  observe = vi.fn<() => void>()
  unobserve = vi.fn<() => void>()
  disconnect = vi.fn<() => void>()
}

vi.stubGlobal('ResizeObserver', ResizeObserverMock)
