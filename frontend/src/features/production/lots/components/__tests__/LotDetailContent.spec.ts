import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { Permission } from '@/core/auth/permissions'

import type { LotPositionResponse, LotResponse } from '../../../types/productionLotsResponse'

const { lotFixture } = vi.hoisted(() => {
  const lotFixture: LotResponse = {
    edit_version: 0,
    id: 1,
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    public_id: '00000000-0000-0000-0000-000000000001',
    lot_number: 'LOT-0001',
    quantity: 10,
    quantity_completed: 4,
    status: 'in_progress',
    // What the backend offers a manager of lots on this running lot.
    actions: ['hold', 'cancel', 'force_complete', 'scrap', 'edit_structure', 'reorder_positions'],
    blocked_actions: {},
    priority: 'normal',
    note: null,
    required_delivery_date: null,
    creator_id: 1,
    creator: null,
    made_item_id: 1,
    made_item_part_number: 'PN-1',
    made_item_article_name: 'Bracket',
    made_item_revision: 'A',
    made_item_material: '1.0037',
    source_bought_item_id: null,
    source_item_id: null,
    source_made_item_id: null,
    source_label: '',
    source_sublabel: '',
    demand_status: '',
    is_alteration: false,
    project_id: 42,
    project_number: 'P-001',
    project_customer: 'Acme',
    input_demand_id: null,
    source_approval_status: 'not_required',
    positions: [
      {
        id: 1,
        public_id: '22222222-2222-2222-2222-222222222222',
        created: '2026-07-01',
        changed: null,
        changed_by: null,
        changed_by_id: null,
        sequence: 1,
        kind: 'internal',
        status: 'in_progress',
        quantity: 10,
        quantity_completed: 4,
        quantity_remaining: 6,
        note: null,
        creator_id: 1,
        lot_id: 1,
        steps: [
          {
            id: 1,
            public_id: '11111111-1111-1111-1111-111111111111',
            created: '2026-07-01',
            note: null,
            estimated_setup_minutes: 10,
            estimated_minutes_per_piece: 2,
            time_budget_per_piece: null,
            sequence: 1,
            creator_id: 1,
            fabrication_method_id: 1,
            role: 'fabrication' as const,
            inspection_method_id: null,
            inspection_method_name: null,
            inspection_method_requires_evidence: null,
            fabrication_method_name: { enGB: 'Milling' },
            fabrication_method_requires_machine: true,
            fabrication_method_required_external: false,
            fabrication_method_default_supplier_id: null,
            lot_id: 1,
            position_id: 1,
            source_process_id: null,
          },
        ],
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
      },
    ],
    steps: [
      {
        id: 1,
        public_id: '11111111-1111-1111-1111-111111111111',
        created: '2026-07-01',
        note: null,
        estimated_setup_minutes: 10,
        estimated_minutes_per_piece: 2,
        time_budget_per_piece: null,
        sequence: 1,
        creator_id: 1,
        fabrication_method_id: 1,
        role: 'fabrication' as const,
        inspection_method_id: null,
        inspection_method_name: null,
        inspection_method_requires_evidence: null,
        fabrication_method_name: { enGB: 'Milling' },
        fabrication_method_requires_machine: true,
        fabrication_method_required_external: false,
        fabrication_method_default_supplier_id: null,
        lot_id: 1,
        position_id: 1,
        source_process_id: null,
      },
    ],
    canceled_at: null,
    completed_at: null,
    follow_up_lots: [],
    force_completed_at: null,
    held_at: null,
    origin_disposition: null,
    origin_lot_id: null,
    origin_lot_number: null,
    source_approved_by_id: null,
    source_approved_date: null,
    source_delivery_date: null,
    source_expected_delivery_date: null,
    source_order_id: null,
    source_order_number: null,
    source_rejected_by_id: null,
    source_rejected_date: null,
    source_rejection_reason: null,
  }
  return { lotFixture }
})

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>(() =>
  Promise.resolve({ data: [] }),
)
const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>(() =>
  Promise.resolve({ data: {} }),
)
const deleteMock = vi.fn<(url: string) => Promise<unknown>>(() => Promise.resolve({ data: {} }))

// Offered by the staged-assign test below (Revision 2): a capable machine
// for method id 1, which the fixture's own step already uses.
const MACHINE_FIXTURE = {
  id: 5,
  public_id: '66666666-6666-6666-6666-666666666666',
  deleted: false,
  created: '2026-07-01',
  changed: null,
  internal_name: 'Machine 5',
  vendor: 'Acme',
  model: 'M5',
  fabrication_method_ids: [1],
  fabrication_methods: [],
  max_part_dimension: null,
  is_qa_machine: false,
  note: null,
  creator_id: 1,
  creator_full_name: 'Alice',
  changes: [],
}

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<unknown>>(async (url: string) => {
      if (/^\/production-lots\/\d+$/.test(url)) return { data: lotFixture }
      if (/^\/production-lots\/\d+\/events$/.test(url)) return { data: [] }
      if (/^\/production-lots\/\d+\/demands$/.test(url)) return { data: [] }
      if (url === '/production-machines/') {
        return { data: { items: [MACHINE_FIXTURE], total: 1, limit: 200, skip: 0 } }
      }
      return { data: { items: [], total: 0, limit: 1000, skip: 0 } }
    }),
    post: (url: string, payload: unknown) => postMock(url, payload),
    put: (url: string, payload: unknown) => putMock(url, payload),
    delete: (url: string) => deleteMock(url),
  },
}))

import LotDetailContent from '../LotDetailContent.vue'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'

function mountDialog(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  const wrapper = mountWithApp(LotDetailContent, {
    pinia,
    attachTo: document.body,
    props: { lotId: 1 },
    global: {
      plugins: [ConfirmationService],
      stubs: { RouterLink: true },
    },
  })
  return wrapper
}

describe('LotDetailContent', () => {
  it('is read-only by default: no editable step controls, but the lifecycle actions are present', async () => {
    const wrapper = mountDialog([Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    await flushPromises()
    await flushPromises()

    // The editable step table never mounts outside manage mode.
    expect(wrapper.findComponent({ name: 'LotStepList' }).exists()).toBe(false)

    // The lot number itself lives in the dialog header (LotDetailDialog.vue),
    // not in this component. The header here instead shows quantity.
    expect(wrapper.text()).toContain('4 / 10')
    expect(wrapper.findComponent({ name: 'LotForceStatusConfirmDialog' }).exists()).toBe(true)
    const buttonLabels = wrapper.findAll('button').map((b) => b.text())
    expect(buttonLabels.some((t) => /hold/i.test(t))).toBe(true)
    expect(buttonLabels.some((t) => /complete/i.test(t))).toBe(true)
    expect(buttonLabels.some((t) => /cancel/i.test(t))).toBe(true)

    wrapper.unmount()
  })

  it('swaps the record cards for the editable step list once Manage is toggled on', async () => {
    const wrapper = mountDialog([Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    await flushPromises()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'LotStepList' }).exists()).toBe(false)
    expect(wrapper.find('.record-grid').exists()).toBe(true)

    const manageButton = wrapper.findAll('button').find((b) => /manage/i.test(b.text()))
    expect(manageButton).toBeTruthy()
    await manageButton!.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'LotStepList' }).exists()).toBe(true)
    // Manage mode replaces the read-only record rather than stacking under
    // it. Both together overflowed the dialog with nothing to scroll.
    expect(wrapper.find('.record-grid').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'LotRecordExecution' }).exists()).toBe(false)

    // The Source card's manage-only material actions have to survive the
    // card being unmounted, so manage mode re-hosts them in its header.
    const labels = wrapper.findAll('button').map((b) => b.text())
    expect(labels.some((l) => /source/i.test(l))).toBe(true)

    wrapper.unmount()
  })

  it('opens on the Execution tab and mounts the other record cards only when their tab is picked', async () => {
    const wrapper = mountDialog([Permission.WRITE_LOTS])
    await flushPromises()
    await flushPromises()

    expect(wrapper.findComponent({ name: 'LotRecordLot' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'LotRecordItem' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'LotRecordExecution' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'LotRecordAudit' }).exists()).toBe(false)

    const auditTab = wrapper
      .findAll('[role="tab"]')
      .find((el) => el.text().includes(i18n.global.t('production.lots.detail.audit.title')))
    expect(auditTab).toBeTruthy()
    await auditTab!.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent({ name: 'LotRecordAudit' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'LotRecordExecution' }).exists()).toBe(false)

    wrapper.unmount()
  })

  it('gives every scrolling record card a .card-scroll-body to scroll', async () => {
    // .record-card--scroll takes .p-panel-content out of flow at
    // overflow: hidden and moves the scrolling onto .card-scroll-body, so a
    // card that carries the modifier without the hook silently clips its
    // content instead of scrolling. Both the Audit and Demands cards
    // shipped that way; assert the contract for all of them at once rather
    // than per card, since the next card added is the one at risk.
    const wrapper = mountDialog([Permission.WRITE_LOTS])
    await flushPromises()
    await flushPromises()

    const scrollCards = wrapper.findAll('.record-card--scroll')
    expect(scrollCards.length).toBeGreaterThan(0)

    const missing = scrollCards
      .filter((card) => !card.find('.card-scroll-body').exists())
      .map((card) => card.find('[data-testid="record-card-header"]').text())
    expect(missing).toEqual([])

    wrapper.unmount()
  })

  it('shows the Manage toggle disabled for a user without write access', async () => {
    const wrapper = mountDialog([])
    await flushPromises()
    await flushPromises()

    const manageButton = wrapper.findAll('button').find((b) => /manage/i.test(b.text()))
    expect(manageButton?.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('stages step edits here too - nothing is written until its own Save', async () => {
    putMock.mockClear()
    deleteMock.mockClear()

    const wrapper = mountDialog([Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    await flushPromises()
    await flushPromises()

    await wrapper
      .findAll('button')
      .find((b) => /manage/i.test(b.text()))!
      .trigger('click')
    await flushPromises()

    // No draft bar until something is actually edited.
    expect(wrapper.find('.structure-draft-bar').exists()).toBe(false)

    // The fixture's position is already assigned, so its note is the edit
    // that stays available there (methods and deletes are locked).
    const noteInput = wrapper
      .findComponent({ name: 'LotStepList' })
      .findAllComponents({ name: 'InputText' })
      .at(-1)
    expect(noteInput).toBeDefined()
    await noteInput!.setValue('staged note')
    await flushPromises()

    expect(deleteMock).not.toHaveBeenCalled()
    expect(putMock).not.toHaveBeenCalled()
    expect(wrapper.find('.structure-draft-bar').exists()).toBe(true)

    const saveButton = wrapper
      .findAllComponents({ name: 'Button' })
      .find(
        (b) =>
          b.props('label') === 'Save' && b.element.closest('.structure-draft-bar') !== null,
      )
    expect(saveButton).toBeDefined()
    await saveButton!.trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledTimes(1)
    expect(putMock.mock.calls[0]![0]).toBe('/production-lots/1/structure')

    wrapper.unmount()
  })

  it('stages an assign pick behind Save: no write until Save applies it (Revision 2)', async () => {
    // Unassigned-position fixture variant: the base fixture's only
    // position is already `internal`, which never renders the assign
    // Select. This one is `unassigned` and needs method 1, same as
    // MACHINE_FIXTURE above.
    const unassignedPosition: LotPositionResponse = {
      id: 2,
      public_id: '22222222-2222-2222-2222-222222222223',
      created: '2026-07-01',
      changed: null,
      changed_by: null,
      changed_by_id: null,
      sequence: 2,
      kind: 'unassigned',
      status: 'pending',
      quantity: 5,
      quantity_completed: 0,
      quantity_remaining: 5,
      note: null,
      creator_id: 1,
      lot_id: 1,
      steps: [
        {
          id: 2,
          public_id: '11111111-1111-1111-1111-111111111112',
          created: '2026-07-01',
          note: null,
          estimated_setup_minutes: null,
          estimated_minutes_per_piece: null,
          time_budget_per_piece: null,
          sequence: 1,
          creator_id: 1,
          fabrication_method_id: 1,
          role: 'fabrication' as const,
          inspection_method_id: null,
          inspection_method_name: null,
          inspection_method_requires_evidence: null,
          fabrication_method_name: { enGB: 'Milling' },
          fabrication_method_requires_machine: true,
          fabrication_method_required_external: false,
          fabrication_method_default_supplier_id: null,
          lot_id: 1,
          position_id: 2,
          source_process_id: null,
        },
      ],
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
    lotFixture.positions!.push(unassignedPosition)

    try {
      postMock.mockClear()
      putMock.mockClear()

      const wrapper = mountDialog([
        Permission.WRITE_LOTS,
        Permission.MANAGE_LOTS,
        Permission.WRITE_PRODUCTION_ORDERS,
      ])
      await flushPromises()
      await flushPromises()

      await wrapper
        .findAll('button')
        .find((b) => /manage/i.test(b.text()))!
        .trigger('click')
      await flushPromises()

      const stepList = wrapper.findComponent({ name: 'LotStepList' })

      const assignSelect = stepList.get('.machine-cell--assign').findComponent({ name: 'Select' })
      await assignSelect.vm.$emit('update:modelValue', 'machine:5')
      await flushPromises()

      // Staged: picking never writes on its own, but it dirties the draft.
      expect(postMock).not.toHaveBeenCalled()
      expect(wrapper.find('.structure-draft-bar').exists()).toBe(true)

      const saveButton = wrapper
        .findAllComponents({ name: 'Button' })
        .find(
          (b) => b.props('label') === 'Save' && b.element.closest('.structure-draft-bar') !== null,
        )
      expect(saveButton).toBeDefined()
      await saveButton!.trigger('click')
      await flushPromises()
      await flushPromises()

      // The structure itself never changed, only a PENDING assignment was
      // added, so Save applies the pick directly, no structure PUT first.
      expect(putMock).not.toHaveBeenCalled()
      expect(postMock).toHaveBeenCalledWith('/production-lots/1/positions/2/assign-internal', {
        orders: [{ machine_id: 5, quantity: 5 }],
      })
      expect(wrapper.find('.structure-draft-bar').exists()).toBe(false)

      wrapper.unmount()
    } finally {
      // Restore the shared fixture so later tests see the original,
      // single-position lot.
      lotFixture.positions = lotFixture.positions!.filter((p) => p.id !== 2)
    }
  })

  it('falls back to the pool name when a production order is pool-assigned but unresolved to a machine', async () => {
    // machine_id null + machine_pool_id set = "assigned to a pool, not yet
    // resolved". Showing only machine_internal_name (as before) would
    // render blank here.
    lotFixture.positions![0]!.production_orders = [
      {
        id: 30,
        production_order_number: 'PO-30',
        edit_version: 0,
        status: 'queued',
        priority: 'normal',
        quantity: 6,
        quantity_completed: 0,
        machine_id: null,
        machine_internal_name: '',
        machine_pool_id: 9,
        machine_pool_name: 'Mill Pool',
        conflicts: [],
      },
    ]

    try {
      const wrapper = mountDialog([Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
      await flushPromises()
      await flushPromises()

      await wrapper
        .findAll('button')
        .find((b) => /manage/i.test(b.text()))!
        .trigger('click')
      await flushPromises()

      const machineOrder = wrapper.get('.machine-order')
      expect(machineOrder.text()).toContain('Mill Pool')
      expect(machineOrder.find('.machine-pool-label').exists()).toBe(true)

      wrapper.unmount()
    } finally {
      // Restore the shared fixture so later test runs (or a different
      // ordering) still see the original empty production_orders.
      lotFixture.positions![0]!.production_orders = []
    }
  })
})
