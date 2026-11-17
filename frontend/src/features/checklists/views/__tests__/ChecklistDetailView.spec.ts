import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { RouterView, createMemoryHistory, createRouter } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { ChecklistResponse, ChecklistSummaryResponse, ChecklistUpdateRequest } from '../../types/checklist'
import { CHECKLISTS } from '../../utils/definitions'

const checklists = new Map<number, ChecklistResponse>()
let revisions: ChecklistSummaryResponse[] = []

const getChecklist = vi.fn<(id: number) => Promise<ChecklistResponse>>()
const updateChecklist = vi.fn<(id: number, body: ChecklistUpdateRequest) => Promise<ChecklistResponse>>()
const reviseChecklist = vi.fn<(id: number, reason: string) => Promise<ChecklistResponse>>()
const lockChecklist = vi.fn<(id: number, takeOver: boolean) => Promise<ChecklistResponse>>()

vi.mock('../../api/getChecklist', () => ({ getChecklist: (id: number) => getChecklist(id) }))
vi.mock('../../api/getChecklistRevisions', () => ({
  getChecklistRevisions: async () => revisions,
}))
vi.mock('../../api/updateChecklist', () => ({
  updateChecklist: (id: number, body: ChecklistUpdateRequest) => updateChecklist(id, body),
}))
vi.mock('../../api/lockChecklist', () => ({
  lockChecklist: (id: number, takeOver: boolean) => lockChecklist(id, takeOver),
  unlockChecklist: async (id: number) => checklists.get(id),
}))
vi.mock('../../api/reviseChecklist', () => ({
  reviseChecklist: (id: number, reason: string) => reviseChecklist(id, reason),
}))
vi.mock('@/features/projects', () => ({
  getProjects: vi.fn<() => Promise<unknown>>(async () => ({
    items: [
      {
        id: 3,
        project_number: 'P-1001',
        customer: { name: 'ACME Ltd' },
        product: { id: 7, product_number: 'PR-7' },
        designated_user_id: null,
      },
    ],
    total: 1,
  })),
}))
vi.mock('@/features/products', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/products')>()),
  getProducts: vi.fn<() => Promise<unknown>>(async () => ({
    items: [{ id: 7, product_number: 'PR-7', designation: 'Press 12', legal_basis: 'directive' }],
    total: 1,
  })),
  useProductsStore: () => ({ items: [], loading: false, refresh: vi.fn<() => Promise<void>>() }),
}))

import ChecklistDetailView from '../ChecklistDetailView.vue'
import ReviseChecklistDialog from '../../components/ReviseChecklistDialog.vue'
import { controlledDocumentFields } from '@/test-utils/controlledDocument'
import { readLocalDraft, writeLocalDraft } from '@/shared/documents/utils/localDraft'
import { LOCAL_DRAFT_WRITE_MS } from '@/shared/documents'

const hydraulics = CHECKLISTS.hydraulics
const [first, second] = hydraulics.items
if (!first || !second) throw new Error('too few items')

function checklist(overrides: Partial<ChecklistResponse> = {}): ChecklistResponse {
  return {
    designation: null,
    ...controlledDocumentFields(),
    id: 2,
    public_id: '11111111-1111-1111-1111-111111111112',
    created: '2026-10-09T10:00:00Z',
    changed: '2026-10-09T10:00:00Z',
    type: 'hydraulics',
    title: 'Hydraulics checklist, P-1001',
    definition_version: 1,
    item_count: hydraulics.items.length,
    answered_count: 1,
    finding_count: 0,
    verdict: 'open',
    project_id: 3,
    project_number: 'P-1001',
    product_id: null,
    product_number: null,
    lineage: '22222222-2222-2222-2222-222222222222',
    document_number: 'CHK-26-0002',
    revision: 'B',
    revision_reason: 'Pump replaced',
    is_latest: true,
    superseded_at: null,
    release_required: true,
    read_only: false,
    finished: false,
    creator_id: 1,
    creator_full_name: 'Author',
    released_at: null,
    released_by_id: null,
    released_by_full_name: null,
    header: { legalBasis: 'directive', ownerNumber: 'P-1001', designation: 'Press 12' },
    answers: { [first!.id]: 'yes' },
    remarks: {},
    changes: [],
    ...overrides,
  }
}

function summaryOf(c: ChecklistResponse): ChecklistSummaryResponse {
  const { header: _h, answers: _a, remarks: _r, changes: _c, ...rest } = c
  return rest
}

async function mountView(
  userId = 1,
  permissions: string[] = ['write:checklists', 'release:checklists'],
  path = '/checklists/2',
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { id: userId, permissions, is_systemuser: false } as never
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/checklists/:id(\\d+)', name: 'ChecklistDetail', component: ChecklistDetailView },
      { path: '/checklists/:id(\\d+)/compare', name: 'ChecklistCompare', component: { template: '<div />' } },
      { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
    ],
  })
  await router.push(path)
  const Host = defineComponent({ render: () => h(RouterView) })
  const wrapper = mountWithApp(Host, {
    pinia,
    global: { plugins: [router, ConfirmationService], directives: { tooltip: Tooltip } },
  })
  await flushPromises()
  return { wrapper, router }
}

/**
 * The tooltip of a button, which sits on the span around it so it shows
 * while the button is disabled. OpenVue's Tooltip directive keeps its text
 * on that element.
 */
function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)?.$_ptooltipValue
}

describe('ChecklistDetailView', () => {
  beforeEach(() => {
    localStorage.clear()
    checklists.clear()
    const previous = checklist({
      id: 1,
      revision: 'A',
      revision_reason: null,
      is_latest: false,
      read_only: true,
      released_at: '2026-10-08T10:00:00Z',
      released_by_full_name: 'Reviewer',
      answers: { [first!.id]: 'no', [second!.id]: 'yes' },
      remarks: { [first!.id]: 'Leaks' },
    })
    checklists.set(1, previous)
    checklists.set(2, checklist())
    revisions = [summaryOf(checklists.get(2)!), summaryOf(previous)]
    getChecklist.mockReset()
    getChecklist.mockImplementation(async (id) => {
      const found = checklists.get(id)
      if (!found) throw new Error('not found')
      return found
    })
    lockChecklist.mockReset()
    lockChecklist.mockImplementation(async (id) => {
      const locked = { ...checklists.get(id)!, locked_by_id: 1, locked_by_full_name: 'Author', locked_at: '2026-10-09T11:00:00Z' }
      checklists.set(id, locked)
      return locked
    })
    updateChecklist.mockReset()
    updateChecklist.mockImplementation(async (id, body) => ({
      ...checklist({ id }),
      title: body.title,
      header: body.header ?? {},
      answers: body.answers ?? {},
      remarks: body.remarks ?? {},
    }))
    reviseChecklist.mockReset()
  })

  it('shows the revision and marks what changed since the one before', async () => {
    const { wrapper } = await mountView()

    expect(wrapper.get('[data-testid="cl-info-number"]').text()).toBe('CHK-26-0002')
    expect(wrapper.get('[data-testid="cl-info-revision"]').text()).toBe('Rev. B')
    expect(wrapper.get('[data-testid="cl-info-title"]').text()).toBe('Hydraulics Checklist')
    expect(wrapper.get('[data-testid="cl-info-owner"]').text()).toBe('P-1001')
    expect(wrapper.get('[data-testid="cl-changes-since"]').text()).toContain('revision A: 2')
    expect(wrapper.get('[data-testid="cl-header-owner-customer"]').text()).toBe('ACME Ltd')
    expect(wrapper.find('[data-testid="cl-compare"]').exists()).toBe(true)
  })

  it('saves edited answers with a fresh owner snapshot and title', async () => {
    const { wrapper } = await mountView()
    // A draft is read only until Edit takes its lock.
    expect(wrapper.find('[data-testid="cl-save"]').exists()).toBe(false)
    await wrapper.get('[data-testid="cl-edit"]').trigger('click')
    await flushPromises()
    expect(lockChecklist).toHaveBeenCalledWith(2, false)
    const save = () => wrapper.get('[data-testid="cl-save"]')
    expect(save().attributes('disabled')).toBeDefined()

    await wrapper.get('[data-testid="cl-section-toggle-assessment"]').trigger('click')
    await wrapper.get(`[data-testid="cl-answer-${second!.id}-defect"]`).trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="cl-info-unsaved"]').exists()).toBe(true)

    await save().trigger('click')
    await flushPromises()

    const [id, body] = updateChecklist.mock.calls[0] ?? []
    expect(id).toBe(2)
    expect(body).toMatchObject({
      title: 'Hydraulics checklist, P-1001, Press 12',
      project_id: 3,
      product_id: null,
      item_count: hydraulics.items.length,
      answers: { [first!.id]: 'yes', [second!.id]: 'defect' },
    })
    expect(body?.header).toMatchObject({ ownerCustomer: 'ACME Ltd', ownerProduct: 'PR-7', designation: 'Press 12' })
    expect(wrapper.find('[data-testid="cl-info-unsaved"]').exists()).toBe(false)
  })

  it('offers Release while editing and reads Done until an answer changes', async () => {
    const { wrapper } = await mountView()
    await wrapper.get('[data-testid="cl-edit"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="cl-finish"]').text()).toBe('Done')
    // The creator of the revision may not release it, and the button says why.
    const release = wrapper.get('[data-testid="cl-release"]')
    expect(release.attributes('disabled')).toBeDefined()
    expect(tooltipOf(release)).toContain('Someone other than the creator of this revision has to release it.')

    await wrapper.get('[data-testid="cl-section-toggle-assessment"]').trigger('click')
    await wrapper.get(`[data-testid="cl-answer-${second!.id}-defect"]`).trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="cl-finish"]').text()).toBe('Discard')
    expect(tooltipOf(wrapper.get('[data-testid="cl-release"]'))).not.toContain('Save your changes first.')
  })

  it('shows a draft another user edits read only, with take over disabled without manage and enabled for a manager', async () => {
    checklists.set(2, checklist({ locked_by_id: 9, locked_by_full_name: 'Jane Doe', locked_at: '2026-10-09T11:00:00Z' }))
    const writer = await mountView()
    expect(writer.wrapper.get('[data-testid="document-locked"]').text()).toContain('Jane Doe')
    expect(writer.wrapper.find('[data-testid="cl-edit"]').exists()).toBe(false)
    const blocked = writer.wrapper.get('[data-testid="document-take-over"]')
    expect(blocked.attributes('disabled')).toBeDefined()
    expect(tooltipOf(blocked)).toBe('This needs the permission Manage Checklists.')
    writer.wrapper.unmount()

    const manager = await mountView(1, ['write:checklists', 'manage:checklists'])
    expect(manager.wrapper.get('[data-testid="document-take-over"]').attributes('disabled')).toBeUndefined()
  })

  it('shows the reason of a revision marked invalid', async () => {
    checklists.set(
      2,
      checklist({
        released_at: '2026-10-09T12:00:00Z',
        read_only: true,
        invalid_at: '2026-10-10T08:00:00Z',
        invalid_by_full_name: 'Jane Doe',
        invalid_reason: 'Wrong pump checked',
      }),
    )
    const { wrapper } = await mountView()
    expect(wrapper.get('[data-testid="document-invalid"]').text()).toContain('Wrong pump checked')
    expect(wrapper.find('[data-testid="cl-mark-invalid"]').exists()).toBe(false)
  })

  it('keeps release disabled for the creator of the revision and for an incomplete list', async () => {
    const own = await mountView(1)
    expect(own.wrapper.get('[data-testid="cl-release"]').attributes('disabled')).toBeDefined()
    own.wrapper.unmount()

    const other = await mountView(5, ['release:checklists'])
    expect(other.wrapper.get('[data-testid="cl-release"]').attributes('disabled')).toBeDefined()
    expect(other.wrapper.find('[data-testid="cl-save"]').exists()).toBe(false)
    other.wrapper.unmount()

    const complete = Object.fromEntries(hydraulics.items.map((item) => [item.id, 'yes']))
    checklists.set(2, checklist({ answers: complete, answered_count: hydraulics.items.length, verdict: 'passed' }))
    const ready = await mountView(5, ['release:checklists'])
    expect(ready.wrapper.get('[data-testid="cl-release"]').attributes('disabled')).toBeUndefined()
  })

  it('shows the actions without the rights for them disabled, naming the missing permission', async () => {
    const reader = await mountView(5, [])
    const edit = reader.wrapper.get('[data-testid="cl-edit"]')
    expect(edit.attributes('disabled')).toBeDefined()
    expect(tooltipOf(edit)).toBe('This needs the permission Write Checklists.')
    const remove = reader.wrapper.get('[data-testid="cl-delete"]')
    expect(remove.attributes('disabled')).toBeDefined()
    expect(tooltipOf(remove)).toBe('This needs the permission Write Checklists.')
    const release = reader.wrapper.get('[data-testid="cl-release"]')
    expect(release.attributes('disabled')).toBeDefined()
    expect(tooltipOf(release)).toContain('This needs the permission Release Checklists.')
    reader.wrapper.unmount()

    const writer = await mountView(5, ['write:checklists'])
    const otherEdit = writer.wrapper.get('[data-testid="cl-edit"]')
    expect(otherEdit.attributes('disabled')).toBeDefined()
    expect(tooltipOf(otherEdit)).toBe('This needs the permission Manage Checklists.')
    writer.wrapper.unmount()
  })

  it('starts a new revision of a released checklist and opens it', async () => {
    checklists.set(
      2,
      checklist({ read_only: true, finished: true, released_at: '2026-10-09T12:00:00Z', released_by_full_name: 'Reviewer' }),
    )
    reviseChecklist.mockResolvedValue(checklist({ id: 3, revision: 'C' }))
    checklists.set(3, checklist({ id: 3, revision: 'C' }))
    const { wrapper, router } = await mountView()

    expect(wrapper.find('[data-testid="cl-save"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="cl-header-checked-by"]').text()).toContain('Reviewer')
    await wrapper.get('[data-testid="cl-revise"]').trigger('click')
    wrapper.getComponent(ReviseChecklistDialog).vm.$emit('revise', 'Valve block replaced')
    await flushPromises()

    expect(reviseChecklist).toHaveBeenCalledWith(2, 'Valve block replaced')
    expect(router.currentRoute.value.fullPath).toBe('/checklists/3')
  })

  it('keeps unsaved answers on this device and asks before leaving them', async () => {
    const { wrapper, router } = await mountView()
    await wrapper.get('[data-testid="cl-edit"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="cl-section-toggle-assessment"]').trigger('click')
    vi.useFakeTimers()
    await wrapper.get(`[data-testid="cl-answer-${second!.id}-defect"]`).trigger('click')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(LOCAL_DRAFT_WRITE_MS)
    vi.useRealTimers()

    expect(readLocalDraft(1, 'checklist.2')).toMatchObject({
      base: '2026-10-09T10:00:00Z',
      value: { answers: { [first!.id]: 'yes', [second!.id]: 'defect' } },
    })

    void router.push('/elsewhere')
    await flushPromises()
    expect(document.body.textContent).toContain('Your changes are not saved.')
    expect(router.currentRoute.value.path).toBe('/checklists/2')
    wrapper.unmount()
  })

  it('offers the answers kept on this device and restores them under its own lock', async () => {
    writeLocalDraft(
      1,
      'checklist.2',
      { header: { legalBasis: 'directive', designation: 'Press 12' }, answers: { [first!.id]: 'yes', [second!.id]: 'defect' }, remarks: {} },
      '2026-10-09T10:00:00Z',
    )
    const { wrapper } = await mountView()

    const restore = document.querySelector<HTMLButtonElement>('[data-testid="document-draft-restore"]')
    expect(restore).not.toBeNull()
    expect(document.querySelector('[data-testid="document-draft-stale"]')).toBeNull()
    restore!.click()
    await flushPromises()

    expect(lockChecklist).toHaveBeenCalledWith(2, false)
    expect(wrapper.find('[data-testid="cl-info-unsaved"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="cl-save"]').attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })


  it('starts editing when the row menu of a list opened it for that', async () => {
    const { router } = await mountView(1, ['write:checklists', 'release:checklists'], '/checklists/2?action=edit')
    await flushPromises()

    expect(lockChecklist).toHaveBeenCalledWith(2, false)
    expect(router.currentRoute.value.fullPath).toBe('/checklists/2')
  })

})
