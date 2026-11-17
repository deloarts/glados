import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { PageResponse } from '@/core/api/types'
import type {
  ChecklistCreateRequest,
  ChecklistListParams,
  ChecklistResponse,
  ChecklistSummaryResponse,
} from '../../types/checklist'

const getChecklists = vi.fn<(p: ChecklistListParams) => Promise<PageResponse<ChecklistSummaryResponse>>>()
vi.mock('../../api/getChecklists', () => ({ getChecklists: (p: ChecklistListParams) => getChecklists(p) }))

const createChecklist = vi.fn<(body: ChecklistCreateRequest) => Promise<ChecklistResponse>>()
vi.mock('../../api/createChecklist', () => ({ createChecklist: (body: ChecklistCreateRequest) => createChecklist(body) }))

vi.mock('@/features/projects', () => ({
  getProjects: vi.fn<() => Promise<unknown>>(async () => ({
    items: [
      {
        id: 3,
        project_number: 'P-1001',
        customer: { name: 'ACME' },
        product: { product_number: 'PR-7' },
        designated_user_id: null,
      },
    ],
    total: 1,
  })),
}))
vi.mock('@/features/products', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/products')>()),
  getProducts: vi.fn<() => Promise<unknown>>(async () => ({
    items: [
      {
        id: 7,
        product_number: 'PR-7',
        customer: { name: 'ACME' },
        designated_user_id: null,
        designation: 'Press 12',
        legal_basis: 'regulation',
      },
    ],
    total: 1,
  })),
  useProductsStore: () => ({ items: [], loading: false, refresh: vi.fn<() => Promise<void>>() }),
}))
vi.mock('@/core/api/projects/searchProjects', () => ({
  searchProjects: vi.fn<() => Promise<{ items: never[]; total: number; limit: number; skip: number }>>(
    async () => ({ items: [], total: 0, limit: 50, skip: 0 }),
  ),
}))

import ChecklistsList from '../ChecklistsList.vue'
import ChecklistOwnerDialog from '../ChecklistOwnerDialog.vue'
import NewChecklistButton from '../NewChecklistButton.vue'
import ChecklistsView from '../../views/ChecklistsView.vue'
import { useChecklistsTableStores } from '../../stores/checklistsTableStores'
import { controlledDocumentFields } from '@/test-utils/controlledDocument'

function summary(overrides: Partial<ChecklistSummaryResponse> = {}): ChecklistSummaryResponse {
  return {
    designation: null,
    ...controlledDocumentFields(),
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-10-09T10:00:00Z',
    changed: '2026-10-09T10:00:00Z',
    type: 'hydraulics',
    title: 'Hydraulics checklist, P-1001',
    definition_version: 1,
    item_count: 4,
    answered_count: 2,
    finding_count: 1,
    verdict: 'failed',
    project_id: 3,
    project_number: 'P-1001',
    product_id: null,
    product_number: null,
    lineage: '22222222-2222-2222-2222-222222222222',
    revision: 'B',
    revision_reason: null,
    is_latest: true,
    superseded_at: null,
    release_required: true,
    read_only: false,
    finished: false,
    creator_id: 1,
    creator_full_name: 'Tester',
    released_at: null,
    released_by_id: null,
    released_by_full_name: null,
    ...overrides,
  }
}

async function mountList(
  props: Record<string, unknown>,
  component: typeof ChecklistsList | typeof ChecklistsView | typeof NewChecklistButton = ChecklistsList,
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { id: 1, permissions: ['write:checklists'], is_systemuser: false } as never
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/checklists/:id', name: 'ChecklistDetail', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  const wrapper = mountWithApp(component, {
    pinia,
    props,
    global: { plugins: [router, ConfirmationService], directives: { tooltip: Tooltip } },
  })
  await flushPromises()
  return { wrapper, router }
}

describe('ChecklistsList', () => {
  beforeEach(() => {
    getChecklists.mockReset()
    getChecklists.mockResolvedValue({ items: [summary()], total: 1, limit: 500, skip: 0 })
    createChecklist.mockReset()
  })

  it('lists the checklists of a project as a plain table with revision, result, status and row actions', async () => {
    const { wrapper } = await mountList({ projectId: 3 })

    expect(getChecklists).toHaveBeenCalledWith({ skip: 0, limit: 25, project_id: 3 })
    expect(wrapper.get('[data-testid="cl-revision-1"]').text()).toBe('Rev. B')
    expect(wrapper.text()).toContain('Failed')
    expect(wrapper.text()).toContain('50 %')
    expect(wrapper.find('[data-testid="cl-status-draft"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Belongs to')
    // The page around the tab offers New Checklist; the tab has no bars.
    expect(wrapper.find('[data-testid="cl-new"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="checklists-controls"]').exists()).toBe(false)
    const firstCell = wrapper.get('[data-testid="checklists-table"] tbody tr td')
    expect(firstCell.find('[data-testid="cl-row-actions-1"]').exists()).toBe(true)
    expect(firstCell.findAll('button').at(-1)?.attributes('disabled')).toBeUndefined()
  })

  it('shows the machine, completion and findings, and leaves document steps to the checklist page', async () => {
    getChecklists.mockResolvedValue({
      items: [
        summary({ designation: 'Press 12' }),
        summary({ id: 2, released_at: '2026-10-09T12:00:00Z', released_by_full_name: 'Reviewer', finding_count: 0 }),
      ],
      total: 2,
      limit: 25,
      skip: 0,
    })
    const { wrapper, router } = await mountList({ projectId: 3 })

    expect(wrapper.get('[data-testid="cl-designation-1"]').text()).toBe('Press 12')
    expect(wrapper.get('[data-testid="cl-completion-1"]').text()).toBe('50 %')
    expect(wrapper.get('[data-testid="cl-findings-1"]').text()).toBe('1')
    expect(wrapper.get('[data-testid="cl-findings-2"]').text()).toBe('0')
    expect(wrapper.get('[data-testid="cl-released-2"]').text()).toContain('Reviewer')

    await wrapper.findAll('[data-testid="checklists-table"] tbody tr')[0]!.trigger('contextmenu')
    await flushPromises()
    const edit = [...document.querySelectorAll<HTMLElement>('[data-testid="cl-row-menu"] li[role="menuitem"]')].find(
      (li) => li.textContent?.trim() === 'Edit',
    )
    expect(edit?.getAttribute('aria-disabled')).not.toBe('true')
    edit?.querySelector<HTMLElement>('a, div')?.click()
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/checklists/1?action=edit')
    wrapper.unmount()
  })

  it('lists a product with the checklists of its projects and shows what each belongs to', async () => {
    const { wrapper } = await mountList({ productId: 7, includeProductProjects: true })

    expect(getChecklists).toHaveBeenCalledWith({ skip: 0, limit: 25, related_product_id: 7 })
    expect(wrapper.text()).toContain('Belongs to')
    expect(wrapper.text()).toContain('Project P-1001')
  })

  it('ignores the filters, sort and grouping of the view stores on a project', async () => {
    const { wrapper } = await mountList({ projectId: 3 })
    const { filters, view } = useChecklistsTableStores('project')
    ;(filters.filters.verdict as { value: unknown }).value = 'failed'
    view.setSort('verdict', 'asc')
    view.setGroupBy('verdict')
    await flushPromises()

    expect(getChecklists.mock.calls.length).toBeGreaterThan(1)
    expect(getChecklists.mock.calls.at(-1)?.[0]).toEqual({ skip: 0, limit: 25, project_id: 3 })
    expect(wrapper.findAll('.group-header-label')).toHaveLength(0)
  })

  it('opens a checklist with a click anywhere on its row', async () => {
    const { wrapper, router } = await mountList({ projectId: 3 })

    await wrapper.get('[data-testid="checklists-table"] tbody tr').findAll('td').at(3)?.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/checklists/1')
  })

  it('pages on the server and sends the status, result and author filters on the page', async () => {
    await mountList({}, ChecklistsView)
    expect(getChecklists).toHaveBeenCalledWith({ skip: 0, limit: 25 })

    const { filters, view } = useChecklistsTableStores('page')
    ;(filters.filters.status as { value: unknown }).value = 'unreleased'
    ;(filters.filters.verdict as { value: unknown }).value = 'failed'
    ;(filters.filters.author as { value: unknown }).value = 'me'
    view.setSort('verdict', 'asc')
    await vi.waitFor(() =>
      expect(getChecklists.mock.calls.at(-1)?.[0]).toEqual({
        skip: 0,
        limit: 25,
        released: false,
        verdict: 'failed',
        mine: true,
        order_by: 'verdict',
        order_dir: 'asc',
      }),
    )
  })

  it('shows the row actions on the page only when asked to', async () => {
    const { wrapper } = await mountList({}, ChecklistsView)
    expect(wrapper.find('[data-testid="cl-row-actions-1"]').exists()).toBe(false)

    useChecklistsTableStores('page').view.toggleShowActions()
    await flushPromises()

    const firstCell = wrapper.get('[data-testid="checklists-table"] tbody tr td')
    expect(firstCell.find('[data-testid="cl-row-actions-1"]').exists()).toBe(true)
  })

  it('starts a checklist for the product New Checklist is offered on and opens it', async () => {
    createChecklist.mockResolvedValue({ ...summary({ id: 42 }), header: {}, answers: {}, remarks: {}, changes: [] })
    const { wrapper, router } = await mountList({ productId: 7, ownerLabel: 'PR-7' }, NewChecklistButton)

    await wrapper.get('[data-testid="cl-new"]').trigger('click')
    const dialog = wrapper.getComponent(ChecklistOwnerDialog)
    expect(dialog.props('initialOwner')).toEqual({ kind: 'product', id: 7, label: 'PR-7' })
    // The machinery types belong to a product only, so the kind of owner is not offered.
    expect(dialog.find('[data-testid="cl-owner-kind"]').exists()).toBe(false)
    dialog.vm.$emit('save', 'pneumatics', { kind: 'product', id: 7, label: 'PR-7' })
    await flushPromises()

    const body = createChecklist.mock.calls[0]?.[0]
    expect(body).toMatchObject({
      type: 'pneumatics',
      title: 'Pneumatics checklist, PR-7, Press 12',
      project_id: null,
      product_id: 7,
      answers: {},
      definition_version: 1,
    })
    expect(body?.header).toMatchObject({
      ownerNumber: 'PR-7',
      ownerCustomer: 'ACME',
      designation: 'Press 12',
      legalBasis: 'regulation',
    })
    expect(router.currentRoute.value.fullPath).toBe('/checklists/42')
  })
})
