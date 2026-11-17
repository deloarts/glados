import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'


const getMock = vi.fn<(url: string) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import LotPositionAssignInternalDialog from '../LotPositionAssignInternalDialog.vue'
import type {
  FabricationLotStep,
  LotPositionResponse,
  LotStepResponse,
} from '../../../types/productionLotsResponse'
import type { ProductionMachineResponse } from '@/features/production-machines'
import { mountWithApp } from '@/test-utils/mountWithApp'

function makeStep(overrides: Partial<FabricationLotStep> = {}): LotStepResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-07-01',
    note: null,
    estimated_setup_minutes: 5,
    estimated_minutes_per_piece: 2,
    time_budget_per_piece: null,
    sequence: 1,
    creator_id: 1,
    fabrication_method_id: 1,
    role: 'fabrication',
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
    ...overrides,
  }
}

function makePosition(steps: LotStepResponse[]): LotPositionResponse {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    sequence: 1,
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

function makeMachine(
  overrides: Partial<ProductionMachineResponse> = {},
): ProductionMachineResponse {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    archived: false,
    created: '2026-07-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    internal_name: 'CNC1',
    vendor: 'Contoso',
    model: 'VF-2',
    fabrication_method_ids: [1],
    fabrication_methods: [],
    max_part_dimension: null,
    is_qa_machine: false,
    note: null,
    creator_id: 1,
    creator_full_name: 'Glados System',
    changes: [],
    active_orders: [],
    live_order_count: 0,
    open_downtime: null,
    status: 'down',
    ...overrides,
  }
}

// The dialog only fetches machines on a visible false -> true *transition*
// (its `watch(visible, ...)` has no `immediate: true`, matching how the real
// caller opens it), so tests mount closed and flip it open, exactly like
// LotDetailContent.vue setting showAssignInternal.value = true.
async function mountDialog(position: LotPositionResponse) {
  const wrapper = mountWithApp(LotPositionAssignInternalDialog, {
    attachTo: document.body,
    props: { visible: false, lotId: 1, position },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  await flushPromises()
  return wrapper
}

describe('LotPositionAssignInternalDialog', () => {
  it('lists a machine covering only the machine-requiring step, ignoring a mixed-in manual step', async () => {
    getMock.mockResolvedValue({
      data: {
        items: [makeMachine({ fabrication_method_ids: [1] })],
        total: 1,
        limit: 200,
        skip: 0,
      },
    })
    const position = makePosition([
      makeStep({ id: 1, fabrication_method_id: 1, fabrication_method_requires_machine: true }),
      makeStep({ id: 2, fabrication_method_id: 2, fabrication_method_requires_machine: false }),
    ])

    const wrapper = await mountDialog(position)

    expect(document.body.textContent).not.toContain('No machine covers')
    expect(document.body.textContent).not.toContain('manual, no machine is needed')

    wrapper.unmount()
  })

  it('shows an info message instead of a warning when every step is manual', async () => {
    getMock.mockResolvedValue({
      data: {
        items: [makeMachine({ fabrication_method_ids: [99] })],
        total: 1,
        limit: 200,
        skip: 0,
      },
    })
    const position = makePosition([
      makeStep({ id: 1, fabrication_method_id: 2, fabrication_method_requires_machine: false }),
    ])

    const wrapper = await mountDialog(position)

    expect(document.body.textContent).toContain('manual, no machine is needed')
    expect(document.body.textContent).not.toContain('No machine covers')

    // Manual positions are still savable with no machine selected.
    const saveButton = Array.from(document.body.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Save',
    )
    expect(saveButton?.disabled).toBe(false)

    wrapper.unmount()
  })

  it('warns with an actionable hint when no machine covers the required method', async () => {
    getMock.mockResolvedValue({
      data: {
        items: [makeMachine({ fabrication_method_ids: [99] })],
        total: 1,
        limit: 200,
        skip: 0,
      },
    })
    const position = makePosition([
      makeStep({ id: 1, fabrication_method_id: 1, fabrication_method_requires_machine: true }),
    ])

    const wrapper = await mountDialog(position)

    expect(document.body.textContent).toContain('No machine covers')
    expect(document.body.textContent).toContain('Resources')

    wrapper.unmount()
  })

  it('warns but stays assignable when a step is typically outsourced', async () => {
    getMock.mockResolvedValue({
      data: {
        items: [makeMachine({ fabrication_method_ids: [1] })],
        total: 1,
        limit: 200,
        skip: 0,
      },
    })
    const position = makePosition([
      makeStep({
        id: 1,
        fabrication_method_id: 1,
        fabrication_method_requires_machine: true,
        fabrication_method_required_external: true,
        fabrication_method_name: { enGB: 'Anodizing' },
      }),
    ])

    const wrapper = await mountDialog(position)

    expect(document.body.textContent).toContain('typically outsourced')
    expect(document.body.textContent).toContain('Anodizing')

    wrapper.unmount()
  })

  it('does not warn about outsourcing when no step is flagged required_external', async () => {
    getMock.mockResolvedValue({
      data: {
        items: [makeMachine({ fabrication_method_ids: [1] })],
        total: 1,
        limit: 200,
        skip: 0,
      },
    })
    const position = makePosition([
      makeStep({ id: 1, fabrication_method_id: 1, fabrication_method_requires_machine: true }),
    ])

    const wrapper = await mountDialog(position)

    expect(document.body.textContent).not.toContain('typically outsourced')

    wrapper.unmount()
  })

  it('removing a middle row keeps the remaining rows their own entered quantities', async () => {
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 200, skip: 0 } })
    const position = makePosition([makeStep()])

    const wrapper = await mountDialog(position)

    const addButton = Array.from(document.body.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Add Machine',
    )
    expect(addButton).toBeTruthy()
    addButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()
    addButton!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()

    const quantityInputs = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(quantityInputs).toHaveLength(3)
    quantityInputs[0]!.vm.$emit('update:modelValue', 10)
    quantityInputs[1]!.vm.$emit('update:modelValue', 5)
    quantityInputs[2]!.vm.$emit('update:modelValue', 15)
    await flushPromises()

    const removeButtons = Array.from(document.body.querySelectorAll('button')).filter(
      (b) => b.getAttribute('aria-label') === 'Remove Machine',
    )
    expect(removeButtons).toHaveLength(3)
    // Remove the middle row (originally holding quantity 5).
    removeButtons[1]!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()

    const remainingInputs = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(remainingInputs).toHaveLength(2)
    expect(remainingInputs[0]!.props('modelValue')).toBe(10)
    expect(remainingInputs[1]!.props('modelValue')).toBe(15)

    wrapper.unmount()
  })

  it('pre-fills the rest a line closed short left and caps the assignment at it', async () => {
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 200, skip: 0 } })
    const position = {
      ...makePosition([makeStep()]),
      kind: 'external' as const,
      quantity_remaining: 2,
      order_item_status: 'delivered' as const,
      order_item_closed_short: true,
    }

    const wrapper = await mountDialog(position)

    const [quantityInput] = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(quantityInput!.props('modelValue')).toBe(2)
    expect(document.body.textContent).toContain('Assigned: 2 / 2')
    const submit = () =>
      Array.from(document.body.querySelectorAll('button')).find(
        (b) => b.textContent?.trim() === 'Save',
      )

    quantityInput!.vm.$emit('update:modelValue', 5)
    await flushPromises()
    expect(submit()?.disabled).toBe(true)

    wrapper.unmount()
  })

  it('renders without console errors when opened', async () => {
    getMock.mockResolvedValue({ data: { items: [], total: 0, limit: 200, skip: 0 } })
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = await mountDialog(makePosition([makeStep()]))

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })
})
