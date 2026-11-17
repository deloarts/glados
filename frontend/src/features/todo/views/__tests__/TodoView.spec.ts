import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { useHostStore } from '@/core/host/stores/hostStore'

// A draft order with no items: buildTodoTasks pushes a `submit_order` task
// (todo.tasks.submitOrder) for it: procurement category, no due date, so it
// buckets into 'blockers' with important:false (not overdue/today,
// highPriority false). That makes it hidden by the "important only" default
// filter, which lets these specs exercise the hidden-count / show-all /
// category-toggle / permission-gating wiring without needing a more elaborate
// domain fixture.
function makeDraftOrder(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    order_number: 'ORD-1',
    status: 'draft',
    supplier_name: 'Acme',
    items: [],
    ...overrides,
  }
}

const getMock =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
  },
}))

let hasPermissionMock = (_permission: string) => true
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => hasPermissionMock(permission) }),
}))

import TodoView from '../TodoView.vue'

const TODO_SOURCES_URL = '/todo/sources'

function sources(overrides: Record<string, unknown[]> = {}) {
  return {
    data: {
      horizon: '2026-01-09',
      orders: [],
      bought_demands: [],
      made_demands: [],
      source_demands: [],
      lots: [],
      ...overrides,
    },
  }
}

function mockEmptyFeed(): void {
  getMock.mockImplementation(() => Promise.resolve(sources()))
}

function mockDraftOrderFeed(): void {
  getMock.mockImplementation(() => Promise.resolve(sources({ orders: [makeDraftOrder()] })))
}

function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  // Off, so the fetch/permission surface under test is just the four
  // procurement/demand endpoints; production planning's own lots/queue
  // fetches are exercised by ProductionPlanningView/ProductionQueueView's
  // own specs instead.
  useHostStore().productionPlanningEnabled = false

  return mount(TodoView, { global: { plugins: [pinia, i18n] } })
}

describe('TodoView', () => {
  beforeEach(() => {
    getMock.mockReset()
    hasPermissionMock = () => true
    mockEmptyFeed()
  })

  it('reads the task sources in one request on mount, without the lots while Production Planning is off', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(getMock).toHaveBeenCalledTimes(1)
    expect(getMock).toHaveBeenCalledWith(TODO_SOURCES_URL, {
      params: { include_lots: false },
    })

    wrapper.unmount()
  })

  it('shows a progress bar while the initial fetch is in flight', async () => {
    let resolveSources: (value: unknown) => void = () => {}
    getMock.mockImplementation(() => new Promise((resolve) => (resolveSources = resolve)))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(true)

    resolveSources(sources())
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ProgressBar' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('shows a load-error state with a Reload button that refetches', async () => {
    getMock.mockRejectedValue(new Error('network down'))

    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load tasks.')

    getMock.mockReset()
    mockEmptyFeed()
    const reloadButton = wrapper.findAll('button').find((b) => b.text() === 'Reload')
    expect(reloadButton).toBeTruthy()
    await reloadButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Failed to load tasks.')
    expect(wrapper.text()).toContain('Nothing to do right now.')

    wrapper.unmount()
  })

  it('shows the empty state when there is genuinely nothing to do', async () => {
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Nothing to do right now.')

    wrapper.unmount()
  })

  it('a not-yet-important task (draft order) is hidden by default behind "Show all"', async () => {
    mockDraftOrderFeed()

    const wrapper = mountView()
    await flushPromises()

    // Nothing urgent shown, but the task exists: the important-only empty
    // copy, not the genuinely-nothing-to-do copy.
    expect(wrapper.text()).toContain('Nothing urgent right now.')

    const showAllButton = wrapper.findAll('button').find((b) => b.text().includes('Show all'))
    expect(showAllButton).toBeTruthy()
    expect(showAllButton!.text()).toContain('+1')
    await showAllButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Submit order ORD-1')
    expect(wrapper.text()).not.toContain('Nothing urgent right now.')

    wrapper.unmount()
  })

  it('hides the task entirely when the user lacks its permission, regardless of Show all', async () => {
    hasPermissionMock = () => false
    mockDraftOrderFeed()

    const wrapper = mountView()
    await flushPromises()

    const showAllButton = wrapper.findAll('button').find((b) => b.text().includes('Show all'))
    expect(showAllButton!.text()).toContain('+0')
    await showAllButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Submit order ORD-1')
    expect(wrapper.text()).toContain('Nothing to do right now.')

    wrapper.unmount()
  })

  it('toggling off the task category filters the task out, without hiding the other categories', async () => {
    mockDraftOrderFeed()

    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text().includes('Show all'))!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Submit order ORD-1')

    const procurementButton = wrapper.findAll('button').find((b) => b.text().startsWith('Procurement'))
    expect(procurementButton).toBeTruthy()
    await procurementButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Submit order ORD-1')
    // Only that category was switched off, not every category, so the
    // "no categories selected" copy must not show, and the other two
    // category buttons stay selected (OpenVue's `text` prop is only true
    // for a *deselected* category button) rather than being switched off too.
    expect(wrapper.text()).not.toContain('No categories selected.')
    const categoryButton = (label: string) =>
      wrapper.findAllComponents({ name: 'Button' }).find((b) => (b.props('label') as string)?.startsWith(label))
    expect(categoryButton('Shop Floor')!.props('text')).toBe(false)
    expect(categoryButton('Planning')!.props('text')).toBe(false)

    wrapper.unmount()
  })

  it("shows the user's overdue meeting todo under Meetings without any permission", async () => {
    hasPermissionMock = () => false
    getMock.mockImplementation(() =>
      Promise.resolve(
        sources({
          meeting_todos: [
            {
              todo_id: 11,
              title: 'Send layout drawing rev. D',
              due_date: '2026-01-02',
              meeting_id: 21,
              meeting_number: 'MTG-26-0021',
              meeting_name: 'Design Review Gripper',
              card_id: 4,
              card_scope: 'Vacuum gripper',
              owner_kind: 'project',
              owner_id: 142,
            },
          ],
        }),
      ),
    )
    const wrapper = mountView()
    await flushPromises()

    expect(wrapper.text()).toContain('Meetings (1)')
    expect(wrapper.text()).toContain('Send layout drawing rev. D')
    expect(wrapper.text()).toContain('MTG-26-0021 Design Review Gripper · Vacuum gripper')

    wrapper.unmount()
  })

  it('shows "no categories selected" once every category is toggled off, with a reset button', async () => {
    const wrapper = mountView()
    await flushPromises()

    const categoryButtons = ['Procurement', 'Shop Floor', 'Planning', 'Meetings'].map(
      (label) => wrapper.findAll('button').find((b) => b.text().startsWith(label))!,
    )
    for (const button of categoryButtons) {
      await button.trigger('click')
      await flushPromises()
    }

    expect(wrapper.text()).toContain('No categories selected.')

    const resetButton = wrapper.findAll('button').find((b) => b.text() === 'Show all categories')
    expect(resetButton).toBeTruthy()
    await resetButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).not.toContain('No categories selected.')

    wrapper.unmount()
  })
})
