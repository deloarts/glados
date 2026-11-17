import { describe, it, expect, vi, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory, type Router } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { asyncTabStub } from '@/test-utils/asyncTabStub'

// Every tab panel is a heavyweight view in its own right (its own stores,
// api calls, gantt/kanban widgets); none of that is ProductionView's own
// concern, only which one is active and when it mounts. Each lazily loaded
// tab is therefore replaced with a trivial named stub.
vi.mock('@/features/production/lots/views/ProductionLotsListView.vue', () =>
  asyncTabStub('ProductionLotsListView', '<div class="lots-stub" />'),
)
vi.mock('@/features/production/queue/views/ProductionQueueView.vue', () =>
  asyncTabStub('ProductionQueueView', '<div class="queue-stub" />'),
)
vi.mock('@/features/production/planning/views/ProductionPlanningView.vue', () =>
  asyncTabStub('ProductionPlanningView', '<div class="planning-stub" />'),
)
vi.mock('@/features/production/wip/views/ProductionWipView.vue', () =>
  asyncTabStub('ProductionWipView', '<div class="wip-stub" />'),
)
vi.mock('@/features/production/planning/views/ProductionCapacityView.vue', () =>
  asyncTabStub('ProductionCapacityView', '<div class="capacity-stub" />'),
)
vi.mock('@/features/production-qa/views/ProductionQaView.vue', () =>
  asyncTabStub('ProductionQaView', '<div class="qa-stub" />'),
)
vi.mock('@/features/production/kpi/views/ProductionKpiView.vue', () =>
  asyncTabStub('ProductionKpiView', '<div class="kpi-stub" />'),
)

import ProductionView from '../ProductionView.vue'

function makeRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/production/:tab?', name: 'Production', component: ProductionView },
      {
        path: '/production/lots/timeline',
        name: 'ProductionLotsTimeline',
        component: ProductionView,
      },
    ],
  })
}

const mounted: VueWrapper[] = []

async function mountAt(path: string) {
  const router = makeRouter()
  await router.push(path)
  await router.isReady()

  const wrapper = mountWithApp(ProductionView, {
    global: { plugins: [router] },
  })
  mounted.push(wrapper)
  // The active tab's panel is an asyncTab()-wrapped dynamic import; even a
  // trivially-mocked target module resolves on a real microtask, so the
  // stub isn't in the DOM synchronously after mount().
  await flushPromises()
  return { wrapper, router }
}

describe('ProductionView', () => {
  afterEach(() => {
    for (const wrapper of mounted) wrapper.unmount()
    mounted.length = 0
  })

  it('renders every tab label regardless of permissions or capabilities', async () => {
    const { wrapper } = await mountAt('/production/queue')

    const labels = wrapper.findAllComponents({ name: 'Tab' }).map((t) => t.text())
    expect(labels).toEqual([
      'Lots',
      'Queue',
      'Planning',
      'WIP',
      'Exceptions',
      'Capacity',
      'QA',
      'KPIs',
    ])
  })

  it('defaults to the Queue tab for an unknown/missing tab param', async () => {
    const { wrapper } = await mountAt('/production')

    expect(wrapper.find('.queue-stub').exists()).toBe(true)
  })

  it('resolves the tab from the route param', async () => {
    const { wrapper } = await mountAt('/production/planning')

    expect(wrapper.find('.planning-stub').exists()).toBe(true)
    expect(wrapper.find('.queue-stub').exists()).toBe(false)
  })

  it('resolves the KPI tab from the route param', async () => {
    const { wrapper } = await mountAt('/production/kpi')

    expect(wrapper.find('.kpi-stub').exists()).toBe(true)
    expect(wrapper.find('.queue-stub').exists()).toBe(false)
  })

  it('resolves the Lots tab from either lots-list or lots-timeline route names, ignoring the tab param', async () => {
    const { wrapper } = await mountAt('/production/lots/timeline')

    expect(wrapper.find('.lots-stub').exists()).toBe(true)
  })

  it('mounts only the active tab panel - the rest stay unmounted, not just hidden', async () => {
    const { wrapper } = await mountAt('/production/qa')

    expect(wrapper.find('.qa-stub').exists()).toBe(true)
    expect(wrapper.find('.lots-stub').exists()).toBe(false)
    expect(wrapper.find('.queue-stub').exists()).toBe(false)
    expect(wrapper.find('.planning-stub').exists()).toBe(false)
    expect(wrapper.find('.wip-stub').exists()).toBe(false)
    expect(wrapper.find('.capacity-stub').exists()).toBe(false)
  })

  it('switching tabs unmounts the old panel and mounts the new one, and replaces the route', async () => {
    const { wrapper, router } = await mountAt('/production/queue')
    expect(wrapper.find('.queue-stub').exists()).toBe(true)

    const capacityTab = wrapper
      .findAllComponents({ name: 'Tab' })
      .find((t) => t.text() === 'Capacity')
    expect(capacityTab).toBeTruthy()
    await capacityTab!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.queue-stub').exists()).toBe(false)
    expect(wrapper.find('.capacity-stub').exists()).toBe(true)
    expect(router.currentRoute.value.path).toBe('/production/capacity')
  })

  it('syncs activeTab when the route changes externally (e.g. browser back)', async () => {
    const { wrapper, router } = await mountAt('/production/queue')
    expect(wrapper.find('.queue-stub').exists()).toBe(true)

    await router.push('/production/wip')
    await flushPromises()

    expect(wrapper.find('.wip-stub').exists()).toBe(true)
    expect(wrapper.find('.queue-stub').exists()).toBe(false)
  })
})
