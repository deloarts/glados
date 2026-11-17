import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeDemandItemResponse } from '@/test-utils/factories'
import { useLoadingBarStore } from '@/core/stores/loadingBarStore'

import type { BoughtItemDemandResponse } from '@/features/bought-items'
import type { ProjectResponse } from '../../types/projectResponse'

const pushMock = vi.fn<(to: string) => void>()

// Partial mock: the component only needs useRouter(); keep everything else
// (RouterLink, etc.) real in case a sibling import chain touches it.
vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRouter: () => ({ push: pushMock }),
}))

const getDemandsMock =
  vi.fn<
    (params?: { project_id: number; skip: number; limit: number }) => Promise<{ items: BoughtItemDemandResponse[] }>
  >()

// Only getDemands is mocked; formatUnit (also used by the SUT) stays real.
vi.mock('@/features/bought-items', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/bought-items')>()),
  getDemands: (params?: { project_id: number; skip: number; limit: number }) => getDemandsMock(params),
}))

import ProjectItemsDialog from '../ProjectItemsDialog.vue'

function makeProject(overrides: Partial<ProjectResponse> = {}): ProjectResponse {
  return {
    id: 7,
    public_id: 'dddddddd-0000-0000-0000-000000000007',
    project_number: 'PRJ-007',
    customer_id: null,
    customer: null,
    product_id: null,
    product: null,
    description: null,
    status: 'active',
    designated_user_id: 1,
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by: null,
    creator_id: 1,
    creator: null,
    production_time_budget: null,
    required_delivery_date_made: null,
    required_delivery_date_bought: null,
    edit_version: 0,
    actions: [],
    live_work: null,
    ...overrides,
  }
}

function makeDemand(overrides: Partial<BoughtItemDemandResponse> = {}): BoughtItemDemandResponse {
  return makeDemandItemResponse({
    quantity: 1,
    unit: 'pcs',
    item_article_name: 'Bracket',
    item: {} as never,
    project_id: 7,
    project_number: 'PRJ-007',
    project_customer: '',
    project_description: '',
    ...overrides,
  })
}

function mountDialog(props: Record<string, unknown>) {
  return mountWithApp(ProjectItemsDialog, {
    attachTo: document.body,
    props: { visible: true, project: makeProject(), ...props },
  })
}

describe('ProjectItemsDialog', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    pushMock.mockReset()
    getDemandsMock.mockReset()
    getDemandsMock.mockResolvedValue({ items: [] })
  })

  it('fetches demands scoped to the project and renders them aggregated by item', async () => {
    getDemandsMock.mockResolvedValue({
      items: [
        makeDemand({ item_id: 1, quantity: 3, status: 'open' }),
        makeDemand({ item_id: 1, quantity: 2, status: 'fulfilled' }),
        makeDemand({
          id: 2,
          item_id: 2,
          item_article_name: 'Screw',
          item_order_code_1: 'OC-2',
          quantity: 10,
          status: 'ordered',
        }),
      ],
    })

    // Mirrors real usage: the dialog is mounted once (closed) and later
    // toggled open, which is what the watch on `visible` reacts to. It
    // does not run on an already-true initial prop.
    const wrapper = mountDialog({ visible: false, project: makeProject({ id: 7 }) })
    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(getDemandsMock).toHaveBeenCalledWith({ project_id: 7, skip: 0, limit: 500 })

    // The dialog is teleported to document.body, so assert against that
    // rather than wrapper.text() (which only sees wrapper.element's subtree).
    const text = document.body.textContent ?? ''
    expect(text).toContain('Bracket')
    expect(text).toContain('Screw')
    // Bracket's two demands (3 + 2) are summed into a single row's demanded
    // quantity, but only the fulfilled one counts toward fulfilled quantity.
    expect(text).toMatch(/Bracket[\s\S]*5[\s\S]*2/)

    wrapper.unmount()
  })

  it('shows the empty message when the project has no demands', async () => {
    getDemandsMock.mockResolvedValue({ items: [] })

    const wrapper = mountDialog({})
    await flushPromises()

    expect(document.body.textContent).toContain('No items found for this project.')

    wrapper.unmount()
  })

  it('does not fetch when closed, and fetches once opened', async () => {
    const wrapper = mountDialog({ visible: false })
    await flushPromises()

    expect(getDemandsMock).not.toHaveBeenCalled()

    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(getDemandsMock).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('turns on the shared loading bar while the fetch is in flight', async () => {
    let resolveDemands!: (value: { items: BoughtItemDemandResponse[] }) => void
    getDemandsMock.mockReturnValue(
      new Promise((resolve) => {
        resolveDemands = resolve
      }),
    )

    const pinia = createPinia()
    setActivePinia(pinia)
    const loadingBarStore = useLoadingBarStore()

    const wrapper = mountWithApp(ProjectItemsDialog, {
      pinia,
      attachTo: document.body,
      props: { visible: false, project: makeProject() },
    })
    await wrapper.setProps({ visible: true })
    await flushPromises()

    expect(loadingBarStore.isLoading).toBe(true)

    resolveDemands({ items: [] })
    await flushPromises()

    wrapper.unmount()
  })

  it('places the open-project button before Close and navigates to the project detail route, closing the dialog', async () => {
    const wrapper = mountDialog({ project: makeProject({ id: 42 }) })
    await flushPromises()

    // Dialog content is teleported out of wrapper.element, so raw DOM
    // selectors (wrapper.find) can't see it; findAllComponents walks the
    // component tree instead, which still reaches teleported children.
    const allButtons = wrapper.findAllComponents({ name: 'Button' })
    const openButton = allButtons.find((b) => b.props('label') === 'Project Details')
    const closeButton = allButtons.find((b) => b.props('label') === 'Close')
    expect(openButton).toBeTruthy()
    expect(closeButton).toBeTruthy()
    expect(allButtons.indexOf(openButton!)).toBeLessThan(allButtons.indexOf(closeButton!))

    await openButton!.trigger('click')

    expect(pushMock).toHaveBeenCalledWith('/workspace/projects/42')
    expect(wrapper.emitted('update:visible')).toBeTruthy()
    expect(wrapper.emitted('update:visible')![0]).toEqual([false])

    wrapper.unmount()
  })

  it('disables the open-project button when there is no project', async () => {
    const wrapper = mountDialog({ project: null })
    await flushPromises()

    const openButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Project Details')
    expect(openButton!.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('closes via the Close button without navigating', async () => {
    const wrapper = mountDialog({})
    await flushPromises()

    const closeButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Close')
    await closeButton!.trigger('click')

    expect(pushMock).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:visible')![0]).toEqual([false])

    wrapper.unmount()
  })
})
