import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import type { OrderItemResponse, OrderResponse } from '@/features/orders'

function makeOrderItem(overrides: Partial<OrderItemResponse> = {}): OrderItemResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    status: 'pending',
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    position: 1,
    quantity: 10,
    quantity_delivered: 0,
    unit: 'PCS',
    items_per_unit: 1,
    price: null,
    note: null,
    ordered_date: null,
    expected_delivery_date: null,
    delivery_date: null,
    storage_place: null,
    expected_pickup_date: null,
    ready_for_pickup_date: null,
    creator_id: 1,
    creator: null,
    orderer_id: null,
    orderer: null,
    receiver_id: null,
    receiver: null,
    bought_item_id: null,
    source_item_id: 1,
    virtual_name: null,
    quote_request_line_id: null,
    quote_request_id: null,
    quote_request_number: '',
    item_order_code_1: '',
    item_order_code_2: null,
    item_specification: '',
    item_article_name: 'D10',
    item_part_number: null,
    item_material: null,
    item_dimension: null,
    item_type_name: null,
    item_revision: null,
    item_base_size: null,
    item_mass: null,
    item_manufacturer: null,
    made_item_id: null,
    order_id: 10,
    supplier_id: 1,
    supplier_name: 'Acme',
    project_id: 1,
    project_number: 'P-1',
    project_customer: 'Acme',
    project_description: '',
    project_status: 'active',
    demand_substitutions: [],
    delivery_records: [],
    line_type: 'SOURCE',
    lot_position_id: null,
    lot_id: null,
    lot_number: '',
    fabrication_method: '',
    actions: [],
    blocked_actions: {},
    canceled_at: null,
    requested_at: null,
    closed_short_at: null,
    closed_short_from: null,
    ...overrides,
  }
}

// The matching SOURCE line, a different SOURCE line (substitution
// candidate), and a BOUGHT line that must never show up as an option
// regardless of which demand kind is being allocated.
const matchingSourceItem = makeOrderItem({ id: 1, source_item_id: 1, item_article_name: 'D10' })
const otherSourceItem = makeOrderItem({ id: 2, source_item_id: 2, item_article_name: 'D12' })
const boughtItem = makeOrderItem({
  id: 3,
  source_item_id: null,
  bought_item_id: 3,
  item_article_name: 'Bolt M6',
})

const draftOrder: OrderResponse = {
  edit_version: 0,
  id: 10,
  public_id: 'dddddddd-0000-0000-0000-000000000010',
  order_number: 'ORD-10',
  status: 'draft',
  created: '2026-01-01T00:00:00Z',
  changed: null,
  changed_by: null,
  changed_by_id: null,
  supplier_archived: false,
  extra_costs: [],
  quote_requests: [],
  lines_total: null,
  extra_costs_total: 0,
  net_total: null,
  note: null,
  ordered_date: null,
  expected_delivery_date: null,
  delivery_date: null,
  storage_place: null,
  creator_id: 1,
  creator: null,
  supplier_id: 5,
  supplier_name: 'Acme Supplies',
  supplier_vat_id: '',
  items: [matchingSourceItem, otherSourceItem, boughtItem],
  actions: [],
  blocked_actions: {},
  canceled_at: null,
  requested_at: null,
}

const postMock = vi.fn<(url: string, body?: unknown) => Promise<unknown>>()
const getMock = vi.fn<(url: string) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    post: (url: string, body?: unknown) => postMock(url, body),
  },
}))

import SourceItemManageAllocationsDialog from '../SourceItemManageAllocationsDialog.vue'

function mountDialog(props: Partial<InstanceType<typeof SourceItemManageAllocationsDialog>['$props']>) {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mountWithApp(SourceItemManageAllocationsDialog, {
    pinia,
    attachTo: document.body,
    props: {
      visible: false,
      demandId: null,
      demandUnit: 'PCS',
      boughtItemId: null,
      sourceItemId: null,
      projectId: 1,
      itemArticleName: 'D10',
      itemOrderCode: 'RB-10',
      ...props,
    },
  })
}

async function openDialog(
  wrapper: ReturnType<typeof mountDialog>,
  props: Record<string, unknown>,
): Promise<void> {
  await wrapper.setProps({ visible: true, ...props })
  await flushPromises()
}

async function selectOrder(wrapper: ReturnType<typeof mountDialog>): Promise<void> {
  const orderSelect = wrapper.findAllComponents({ name: 'Select' })[0]!
  orderSelect.vm.$emit('update:modelValue', draftOrder)
  await flushPromises()
}

function orderItemSelect(wrapper: ReturnType<typeof mountDialog>) {
  return wrapper.findAllComponents({ name: 'Select' })[1]!
}

// The Dialog teleports its content to document.body, outside the wrapper's
// own root DOM node, so plain CSS `wrapper.find(...)` queries come back
// empty (see OrderCreateForm.spec.ts for the same caveat); component
// queries (findComponent/findAllComponents) still work since they walk the
// VNode tree rather than the DOM. With no existing allocations and a
// matching order item, InputNumber[0] is the order-allocation quantity
// field (InputNumber[1] is the stock-allocation one).
async function addOrderAllocation(
  wrapper: ReturnType<typeof mountDialog>,
  quantity: number,
): Promise<void> {
  wrapper.findAllComponents({ name: 'InputNumber' })[0]!.vm.$emit('update:modelValue', quantity)
  await flushPromises()
  // The Dialog's own header close icon is also a named "Button" component
  // (label null), preceding both "Add" buttons ("Link Order Item" and "Add
  // Stock Allocation" share the same label), so filter by label and take
  // the first to land on the order-allocation one specifically.
  const addButton = wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === i18n.global.t('sourceItems.demands.allocationsDialog.add'))
  await addButton!.trigger('click')
  await flushPromises()
}

describe('SourceItemManageAllocationsDialog', () => {
  beforeEach(() => {
    postMock.mockReset()
    getMock.mockReset()
    getMock.mockImplementation((url: string) => {
      if (url === '/orders/') {
        return Promise.resolve({ data: { items: [draftOrder], total: 1, limit: 200, skip: 0 } })
      }
      if (url.startsWith('/source-item-allocations/demand/')) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 0, skip: 0 } })
    })
    postMock.mockImplementation((url: string, body?: unknown) => {
      if (url === '/source-item-allocations/demands/summary-batch') {
        return Promise.resolve({ data: {} })
      }
      if (url === '/source-item-allocations/') {
        return Promise.resolve({ data: { ...(body as object), source: 'order' } })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('for a source-sourced demand, lists non-matching SOURCE lines but excludes the BOUGHT line', async () => {
    const wrapper = mountDialog({ sourceItemId: 1, boughtItemId: null })
    await openDialog(wrapper, { demandId: 1, sourceItemId: 1 })
    await selectOrder(wrapper)

    const options = orderItemSelect(wrapper).props('options') as OrderItemResponse[]
    expect(options.map((o) => o.id).sort()).toEqual([1, 2])

    wrapper.unmount()
  })

  it('for a bought-sourced demand, keeps the exact bought_item_id match only', async () => {
    const wrapper = mountDialog({ sourceItemId: null, boughtItemId: 3 })
    await openDialog(wrapper, { demandId: 1, boughtItemId: 3, sourceItemId: null })
    await selectOrder(wrapper)

    const options = orderItemSelect(wrapper).props('options') as OrderItemResponse[]
    expect(options.map((o) => o.id)).toEqual([3])

    wrapper.unmount()
  })

  it('warns on an allocation whose order line is in another unit', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/orders/') {
        return Promise.resolve({ data: { items: [draftOrder], total: 1, limit: 200, skip: 0 } })
      }
      if (url.startsWith('/source-item-allocations/demand/')) {
        return Promise.resolve({
          data: [
            {
              demand_item_id: 1,
              order_item_id: 1,
              quantity: 2,
              source: 'order',
              order_item_unit: 'M',
              demand_unit: 'PCS',
              unit_mismatch: true,
            },
          ],
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 0, skip: 0 } })
    })
    const wrapper = mountDialog({ sourceItemId: 1 })
    await openDialog(wrapper, { demandId: 1, sourceItemId: 1 })

    const warning = wrapper.findComponent({ name: 'UnitMismatchWarning' })
    expect(warning.exists()).toBe(true)
    expect(warning.props()).toEqual({ demandUnit: 'PCS', lineUnit: 'M' })

    wrapper.unmount()
  })

  it('leaves out the lines the demand is already allocated to', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/orders/') {
        return Promise.resolve({ data: { items: [draftOrder], total: 1, limit: 200, skip: 0 } })
      }
      if (url.startsWith('/source-item-allocations/demand/')) {
        return Promise.resolve({
          data: [{ demand_item_id: 1, order_item_id: 1, quantity: 2, source: 'order' }],
        })
      }
      return Promise.resolve({ data: { items: [], total: 0, limit: 0, skip: 0 } })
    })
    const wrapper = mountDialog({ sourceItemId: 1, boughtItemId: null })
    await openDialog(wrapper, { demandId: 1, sourceItemId: 1 })
    await selectOrder(wrapper)

    const options = orderItemSelect(wrapper).props('options') as OrderItemResponse[]
    expect(options.map((o) => o.id)).toEqual([2])

    wrapper.unmount()
  })

  it('shows no substitution warning when the selected line matches the demand material', async () => {
    const wrapper = mountDialog({ sourceItemId: 1, boughtItemId: null })
    await openDialog(wrapper, { demandId: 1, sourceItemId: 1 })
    await selectOrder(wrapper)

    orderItemSelect(wrapper).vm.$emit('update:modelValue', matchingSourceItem)
    await flushPromises()

    expect(document.body.querySelector('.alloc-substitute-row')).toBeNull()

    wrapper.unmount()
  })

  it('shows the substitution warning + reason input when the selected line differs, and sends substitute fields', async () => {
    const wrapper = mountDialog({ sourceItemId: 1, boughtItemId: null })
    await openDialog(wrapper, { demandId: 1, sourceItemId: 1 })
    await selectOrder(wrapper)

    orderItemSelect(wrapper).vm.$emit('update:modelValue', otherSourceItem)
    await flushPromises()

    expect(document.body.querySelector('.alloc-substitute-row')).not.toBeNull()

    // Two of OpenVue's own Selects render an internal filter InputText
    // (modelValue undefined, driven by their own internal state); the
    // substitute-reason field is the only one actually bound to a `''`
    // string via v-model, so filter on that to find it reliably.
    const reasonInput = wrapper
      .findAllComponents({ name: 'InputText' })
      .find((c) => c.props('modelValue') === '')!
    reasonInput.vm.$emit('update:modelValue', '  Preferred size  ')
    await addOrderAllocation(wrapper, 4)

    const allocCall = postMock.mock.calls.find(([url]) => url === '/source-item-allocations/')
    expect(allocCall).toBeDefined()
    const body = allocCall![1] as Record<string, unknown>
    expect(body.substitute_source_item_id).toBe(2)
    expect(body.substitute_reason).toBe('Preferred size')

    wrapper.unmount()
  })

  it('sends a null substitute when the selected line matches the demand material', async () => {
    const wrapper = mountDialog({ sourceItemId: 1, boughtItemId: null })
    await openDialog(wrapper, { demandId: 1, sourceItemId: 1 })
    await selectOrder(wrapper)

    orderItemSelect(wrapper).vm.$emit('update:modelValue', matchingSourceItem)
    await flushPromises()

    await addOrderAllocation(wrapper, 4)

    const allocCall = postMock.mock.calls.find(([url]) => url === '/source-item-allocations/')
    expect(allocCall).toBeDefined()
    const body = allocCall![1] as Record<string, unknown>
    expect(body.substitute_source_item_id).toBeNull()
    expect(body.substitute_reason).toBeNull()

    wrapper.unmount()
  })
})
