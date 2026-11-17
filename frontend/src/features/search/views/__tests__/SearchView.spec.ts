import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'

import type {
  GlobalSearchGroup,
  GlobalSearchHit,
  GlobalSearchResponse,
  SearchResource,
} from '../../types/globalSearchResponse'
import type { ResolvePublicIdResponse } from '@/features/scan'

// Mutable so each test can set a different `q` query value before mounting;
// vi.mock factories are hoisted, so this can't be a per-test local without
// living on a module-scope object like this.
const routeQuery: Record<string, unknown> = {}

const pushMock = vi.fn<(to: string) => void>()
const replaceMock = vi.fn<(to: string) => void>()

// Partial mock (importOriginal): SearchResultGroup pulls in
// useOrderFormatters/lotStatusSeverity/productionOrderStatusSeverity plus
// the three ThumbnailCell components via their feature barrels, and those
// barrels' API modules import the shared api client, which
// imports currentUserStore, which imports src/router, a module-level
// `createRouter(...)` call. A full replacement mock has no createRouter to
// give it, so the real one has to be kept alongside the overrides below.
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ query: routeQuery }),
    useRouter: () => ({ push: pushMock, replace: replaceMock }),
    // SearchResultGroup's "show all" footer link. A minimal stand-in so the
    // template resolves it under the fully-mocked module above.
    RouterLink: {
      props: ['to'],
      template: '<a :href="to"><slot /></a>',
    },
  }
})

const globalSearchMock = vi.fn<() => Promise<GlobalSearchResponse>>()
vi.mock('../../api/globalSearch', () => ({
  globalSearch: (...args: unknown[]) =>
    (globalSearchMock as unknown as (...a: unknown[]) => Promise<GlobalSearchResponse>)(...args),
}))

const resolvePublicIdMock = vi.fn<() => Promise<ResolvePublicIdResponse>>()
vi.mock('@/features/scan/api/resolvePublicId', () => ({
  resolvePublicId: (...args: unknown[]) =>
    (resolvePublicIdMock as unknown as (...a: unknown[]) => Promise<ResolvePublicIdResponse>)(
      ...args,
    ),
}))

import SearchView from '../SearchView.vue'

const ALL_RESOURCES: SearchResource[] = [
  'products',
  'projects',
  'bought-items',
  'made-items',
  'source-items',
  'orders',
  'production-lots',
  'production-orders',
]

function emptyGroup(resource: SearchResource): GlobalSearchGroup {
  return { resource, total: 0, items: [] }
}

function makeResponse(overrides: Partial<Record<SearchResource, GlobalSearchGroup>> = {}) {
  const groups: GlobalSearchGroup[] = ALL_RESOURCES.map(
    (resource) => overrides[resource] ?? emptyGroup(resource),
  )
  return { query: 'term', groups }
}

function makeHit(overrides: Partial<GlobalSearchHit> = {}): GlobalSearchHit {
  return {
    resource: 'projects',
    id: 7,
    public_id: '9f3c1111-1111-1111-1111-111111111111',
    label: 'AX-2201',
    subtitle: 'Injection mold housing',
    details: null,
    match_kind: 'exact',
    via_kind: null,
    ...overrides,
  }
}

function axiosError(status: number): unknown {
  return { isAxiosError: true, response: { status } }
}

function mountSearchView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return { pinia, wrapper: mountWithApp(SearchView, { pinia }) }
}

describe('SearchView', () => {
  beforeEach(() => {
    for (const key of Object.keys(routeQuery)) delete routeQuery[key]
    pushMock.mockClear()
    replaceMock.mockClear()
    globalSearchMock.mockReset()
    resolvePublicIdMock.mockReset()
  })

  it('renders a card for each non-empty group', async () => {
    routeQuery.q = 'AX-22'
    globalSearchMock.mockResolvedValue(
      makeResponse({
        projects: { resource: 'projects', total: 12, items: [makeHit()] },
      }),
    )

    const { wrapper } = mountSearchView()
    await flushPromises()

    expect(wrapper.text()).toContain('AX-2201')
    expect(wrapper.text()).toContain('Injection mold housing')
  })

  it('shows the results-for text, hit count and duration in the info bar, and hides the summary panel once results render', async () => {
    routeQuery.q = 'AX-22'
    globalSearchMock.mockResolvedValue(
      makeResponse({
        projects: { resource: 'projects', total: 12, items: [makeHit()] },
      }),
    )

    const { wrapper } = mountSearchView()
    await flushPromises()

    // The identifier-style bold text and hit count live in the InfoBar, not
    // the hidden summary Panel.
    expect(wrapper.text()).toContain('Results for “AX-22”')
    expect(wrapper.text()).toContain('12 hits')
    expect(wrapper.text()).toMatch(/\d+ ms/)
    expect(wrapper.find('.search-summary').exists()).toBe(false)
  })

  it('hides empty groups', async () => {
    routeQuery.q = 'AX-22'
    globalSearchMock.mockResolvedValue(
      makeResponse({
        projects: { resource: 'projects', total: 12, items: [makeHit()] },
      }),
    )

    const { wrapper } = mountSearchView()
    await flushPromises()

    // Bought items stayed empty (total: 0), so its card (and title) never render.
    expect(wrapper.text()).not.toContain('Bought Items')
  })

  it('hides production lots and orders, and excludes them from the total, when production planning is disabled', async () => {
    routeQuery.q = 'lot'
    globalSearchMock.mockResolvedValue(
      makeResponse({
        projects: {
          resource: 'projects',
          total: 5,
          items: [makeHit({ id: 3, label: 'PRJ-1', subtitle: null })],
        },
        'production-lots': {
          resource: 'production-lots',
          total: 3,
          items: [
            makeHit({ resource: 'production-lots', id: 1, label: 'LOT-1', subtitle: 'in_progress' }),
          ],
        },
        'production-orders': {
          resource: 'production-orders',
          total: 2,
          items: [makeHit({ resource: 'production-orders', id: 2, label: 'PO-1', subtitle: 'queued' })],
        },
      }),
    )

    const { pinia, wrapper } = mountSearchView()
    useHostStore(pinia).productionPlanningEnabled = false
    await flushPromises()

    expect(wrapper.text()).not.toContain('LOT-1')
    expect(wrapper.text()).not.toContain('PO-1')
    expect(wrapper.text()).toContain('PRJ-1')
    // Total is counted over the groups actually shown: lots/production
    // orders' 3 + 2 must not be added on top of projects' 5.
    expect(wrapper.text()).toContain('5 hits')
    expect(wrapper.text()).not.toContain('10 hits')
  })

  it('pushes the resolved route when a result row is clicked', async () => {
    routeQuery.q = 'AX-22'
    globalSearchMock.mockResolvedValue(
      makeResponse({
        projects: { resource: 'projects', total: 1, items: [makeHit()] },
      }),
    )

    const { wrapper } = mountSearchView()
    await flushPromises()

    await wrapper.find('button.hit-row').trigger('click')

    expect(pushMock).toHaveBeenCalledWith('/workspace/projects/7')
  })

  it('shows an error message with a retry button when the search fails, and retries on click', async () => {
    routeQuery.q = 'AX-22'
    globalSearchMock.mockRejectedValueOnce(new Error('network error'))

    const { wrapper } = mountSearchView()
    await flushPromises()

    expect(wrapper.text()).toContain('Something went wrong while searching.')

    globalSearchMock.mockResolvedValueOnce(makeResponse())
    const retryButton = wrapper.findAll('button').find((button) => button.text() === 'Retry')
    expect(retryButton).toBeTruthy()

    await retryButton!.trigger('click')
    await flushPromises()

    expect(globalSearchMock).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('Something went wrong while searching.')
  })

  it('falls back to an empty query when q is not a string (e.g. repeated ?q=a&q=b)', async () => {
    routeQuery.q = ['a', 'b']

    const { wrapper } = mountSearchView()
    await flushPromises()

    expect(wrapper.text()).not.toContain('a,b')
    expect(globalSearchMock).not.toHaveBeenCalled()
    expect(resolvePublicIdMock).not.toHaveBeenCalled()
  })

  it('resolves a UUID query directly, stays in the looking-up state, and replaces with the resolved route', async () => {
    const uuid = '11111111-1111-1111-1111-111111111111'
    routeQuery.q = uuid
    resolvePublicIdMock.mockResolvedValue({ resource: 'projects', id: 7, public_id: uuid })

    const { wrapper } = mountSearchView()
    await flushPromises()

    expect(resolvePublicIdMock).toHaveBeenCalledWith(uuid)
    expect(replaceMock).toHaveBeenCalledWith('/workspace/projects/7')
    expect(globalSearchMock).not.toHaveBeenCalled()
    // Stays in "looking up" until the replace actually navigates away. It
    // must not flash the error branch in between.
    expect(wrapper.text()).toContain('Looking up')
    expect(wrapper.text()).not.toContain('Something went wrong while searching.')
  })

  it('shows "no record" and skips the text search when the UUID does not resolve', async () => {
    const uuid = '22222222-2222-2222-2222-222222222222'
    routeQuery.q = uuid
    resolvePublicIdMock.mockRejectedValue(axiosError(404))

    const { wrapper } = mountSearchView()
    await flushPromises()

    expect(wrapper.text()).toContain(uuid)
    expect(globalSearchMock).not.toHaveBeenCalled()
    expect(replaceMock).not.toHaveBeenCalled()
  })
})
