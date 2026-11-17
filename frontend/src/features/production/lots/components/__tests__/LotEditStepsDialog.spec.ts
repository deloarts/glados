import { beforeEach, describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { Permission } from '@/core/auth/permissions'

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>(() =>
  Promise.resolve({ data: [] }),
)
const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>(() =>
  Promise.resolve({ data: {} }),
)
const deleteMock = vi.fn<(url: string) => Promise<unknown>>(() => Promise.resolve({ data: {} }))

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => {
      if (url === '/inspection-methods/') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 5,
                public_id: '55555555-5555-5555-5555-555555555555',
                created: '2026-01-01',
                changed: null,
                deleted: false,
                name: 'Visual Inspection',
                description: '',
                label_color: '#999999',
                label_font_color: '#000000',
                requires_evidence: false,
                archived: false,
                creator_id: 1,
                creator: null,
              },
            ],
            total: 1,
            limit: 1000,
            skip: 0,
          },
        })
      }
      if (url === '/fabrication-methods/') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 1,
                public_id: '11111111-1111-1111-1111-111111111111',
                created: '2026-01-01',
                changed: null,
                deleted: false,
                name: 'Milling',
                description: '',
                label_color: '#999999',
                label_font_color: '#000000',
                requires_machine: true,
                required_external: false,
                default_supplier_id: null,
                archived: false,
                creator_id: 1,
                creator: null,
              },
            ],
            total: 1,
            limit: 1000,
            skip: 0,
          },
        })
      }
      // The Machine/Order column's assign Select needs a capable machine to
      // offer for the staged-assignment test below. Method id 1 is what
      // every fixture step here already uses.
      if (url === '/production-machines/') {
        return Promise.resolve({
          data: {
            items: [
              {
                id: 1,
                public_id: '66666666-6666-6666-6666-666666666666',
                deleted: false,
                created: '2026-07-01',
                changed: null,
                internal_name: 'Machine 1',
                vendor: 'Acme',
                model: 'M100',
                fabrication_method_ids: [1],
                fabrication_methods: [],
                max_part_dimension: null,
                is_qa_machine: false,
                note: null,
                creator_id: 1,
                creator_full_name: 'Alice',
                changes: [],
              },
            ],
            total: 1,
            limit: 200,
            skip: 0,
          },
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 1000, skip: 0 } })
    },
    put: (url: string, payload: unknown) => putMock(url, payload),
    post: (url: string, payload: unknown) => postMock(url, payload),
    delete: (url: string) => deleteMock(url),
  },
}))

import LotEditStepsDialog from '../LotEditStepsDialog.vue'
import { useProductionLotDetailStore } from '../../stores/productionLotDetailStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import type { LotPositionResponse, LotStepResponse } from '../../../types/productionLotsResponse'

function makeStep(id: number, positionId: number, sequence: number): LotStepResponse {
  return {
    id,
    public_id: `0000000${id}-0000-0000-0000-000000000000`,
    created: '2026-08-01T09:00:00',
    note: null,
    estimated_setup_minutes: 10,
    estimated_minutes_per_piece: 2,
    time_budget_per_piece: null,
    sequence,
    creator_id: 1,
    fabrication_method_id: 1,
    fabrication_method_name: { enGB: 'Milling' },
    fabrication_method_requires_machine: true,
    fabrication_method_required_external: false,
    fabrication_method_default_supplier_id: null,
    lot_id: 1,
    position_id: positionId,
    source_process_id: null,
    role: 'fabrication',
    inspection_method_id: null,
    inspection_method_name: null,
    inspection_method_requires_evidence: null,
  }
}

function makePosition(id: number, sequence: number, steps: LotStepResponse[]): LotPositionResponse {
  return {
    id,
    public_id: `22222222-2222-2222-2222-${String(id).padStart(12, '0')}`,
    created: '2026-08-01T09:00:00',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    sequence,
    kind: 'unassigned',
    status: 'pending',
    quantity: 5,
    quantity_completed: 0,
    quantity_remaining: 5,
    note: null,
    creator_id: 1,
    lot_id: 1,
    steps,
    order_item_id: null,
    order_id: null,
    order_number: '',
    supplier_name: '',
    order_item_status: '',
    order_item_closed_short: false,
    earlier_order_lines: [],
    expected_delivery_date: null,
    production_orders: [],
    actions: [],
    planned_delivery_date: null,
    planned_pickup_date: null,
  }
}

function mountDialog(permissions?: string[], lotOverrides: Record<string, unknown> = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  if (permissions) useCurrentUserStore().user = userWithPermissions(permissions)
  const detailStore = useProductionLotDetailStore()
  const steps = [makeStep(1, 10, 1), makeStep(2, 11, 2)]
  detailStore.lot = {
    id: 1,
    lot_number: 'LN-26-00030',
    status: 'draft',
    // A draft lot offers structure edits.
    actions: ['cancel', 'scrap', 'edit_structure', 'reorder_positions', 'edit_quantity'],
    quantity: 5,
    project_id: 7,
    made_item_id: 1,
    made_item_part_number: 'PN-1',
    made_item_article_name: 'Bracket',
    steps,
    positions: [makePosition(10, 1, [steps[0]!]), makePosition(11, 2, [steps[1]!])],
    ...lotOverrides,
  } as unknown as typeof detailStore.lot
  detailStore.fetch = vi.fn<(lotId: number) => Promise<void>>(() => Promise.resolve())

  const wrapper = mountWithApp(LotEditStepsDialog, {
    pinia,
    attachTo: document.body,
    props: { lotId: 1, canWrite: true, visible: true },
  })
  return { wrapper, detailStore }
}

function findButton(wrapper: ReturnType<typeof mountDialog>['wrapper'], label: string) {
  return wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)
}

describe('LotEditStepsDialog', () => {
  beforeEach(() => {
    putMock.mockClear()
    postMock.mockClear()
    deleteMock.mockClear()
  })

  it('stages a deletion instead of writing it, then saves the whole structure at once', async () => {
    const { wrapper } = mountDialog()
    await flushPromises()
    await flushPromises()

    // Delete the second step from the table.
    const deleteButtons = wrapper
      .findAllComponents({ name: 'Button' })
      .filter((b) => b.props('icon') === 'mdi mdi-delete-outline')
    expect(deleteButtons.length).toBe(2)
    await deleteButtons[1]!.trigger('click')
    await flushPromises()

    // Nothing has been written: not the delete, not anything else.
    expect(deleteMock).not.toHaveBeenCalled()
    expect(putMock).not.toHaveBeenCalled()
    expect(postMock).not.toHaveBeenCalled()

    await findButton(wrapper, 'Save')!.trigger('click')
    await flushPromises()

    // One transactional request carrying the surviving structure.
    expect(putMock).toHaveBeenCalledTimes(1)
    expect(putMock).toHaveBeenCalledWith('/production-lots/1/structure', {
      positions: [{ steps: [expect.objectContaining({ id: 1 })] }],
    })

    wrapper.unmount()
  })

  it('keeps a scrapped lot read-only, as it offers no structure edit', async () => {
    const { wrapper } = mountDialog(undefined, { status: 'scrapped', actions: [] })
    await flushPromises()
    await flushPromises()

    const editableDeletes = wrapper
      .findAllComponents({ name: 'Button' })
      .filter((b) => b.props('icon') === 'mdi mdi-delete-outline' && !b.props('disabled'))
    expect(editableDeletes).toHaveLength(0)

    wrapper.unmount()
  })

  it('sends a staged new step with a null id so the backend creates it', async () => {
    const { wrapper } = mountDialog()
    await flushPromises()
    await flushPromises()

    await findButton(wrapper, 'Add Step')!.trigger('click')
    await flushPromises()
    expect(postMock).not.toHaveBeenCalled()

    await findButton(wrapper, 'Save')!.trigger('click')
    await flushPromises()

    const payload = putMock.mock.calls[0]![1] as {
      positions: { steps: { id: number | null }[] }[]
    }
    expect(payload.positions).toHaveLength(3)
    expect(payload.positions[2]!.steps[0]!.id).toBeNull()

    wrapper.unmount()
  })

  it('discards the draft on cancel', async () => {
    const { wrapper } = mountDialog()
    await flushPromises()
    await flushPromises()

    const deleteButtons = wrapper
      .findAllComponents({ name: 'Button' })
      .filter((b) => b.props('icon') === 'mdi mdi-delete-outline')
    await deleteButtons[0]!.trigger('click')
    await flushPromises()

    await findButton(wrapper, 'Cancel')!.trigger('click')
    await flushPromises()

    expect(putMock).not.toHaveBeenCalled()
    expect(deleteMock).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])

    wrapper.unmount()
  })

  it('stays open when save cannot apply a staged assignment, closes once it can (Revision 2)', async () => {
    // Both fixture positions are unassigned and machine-requiring (method
    // id 1), the same shape a real draft lot with unassigned positions
    // has. The /production-machines branch in this file's own get mock,
    // above, offers a capable machine for that method.
    const { wrapper } = mountDialog([Permission.WRITE_PRODUCTION_ORDERS])
    await flushPromises()
    await flushPromises()

    const stepList = wrapper.findComponent({ name: 'LotStepList' })
    const assignSelect = stepList.get('.machine-cell--assign').findComponent({ name: 'Select' })
    await assignSelect.vm.$emit('update:modelValue', 'machine:1')
    await flushPromises()

    // Staged: picking never writes on its own.
    expect(postMock).not.toHaveBeenCalled()

    // Save applies the staged pick; the assign call itself fails, so
    // save() resolves false and the dialog stays open with the pick still
    // pending (structure was clean, so no structure PUT happens either).
    postMock.mockRejectedValueOnce(new Error('boom'))
    await findButton(wrapper, 'Save')!.trigger('click')
    await flushPromises()
    await flushPromises()

    expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/10/assign-internal', {
      orders: [{ machine_id: 1, quantity: 5 }],
    })
    expect(putMock).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:visible')).toBeUndefined()

    // Save again. The same pick is still staged, and this time the assign
    // call succeeds, so save() resolves true and the dialog closes.
    await findButton(wrapper, 'Save')!.trigger('click')
    await flushPromises()
    await flushPromises()

    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])

    wrapper.unmount()
  })
})
