import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import ProductionWipTable from '../ProductionWipTable.vue'
import type { WipLotResponse } from '../../types/productionWipResponse'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { mountWithApp } from '@/test-utils/mountWithApp'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/', component: { template: '<div />' } }],
})

const lot: WipLotResponse = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  lot_number: 'LOT-0001',
  quantity: 10,
  status: 'in_progress',
  priority: 'high',
  made_item_id: 1,
  made_item_part_number: 'PN-001',
  made_item_revision: 'A',
  made_item_article_name: 'Widget',
  raw_count: 3,
  finished_count: 4,
  stages: [
    {
      position_id: 1,
      sequence: 1,
      kind: 'internal',
      status: 'in_progress',
      quantity: 10,
      quantity_completed: 4,
      machine_names: ['CNC-1'],
      supplier_name: '',
    },
    {
      position_id: 2,
      sequence: 2,
      kind: 'external',
      status: 'ordered_or_queued',
      quantity: 10,
      quantity_completed: 0,
      machine_names: [],
      supplier_name: 'Acme Supplier',
    },
  ],
}

describe('ProductionWipTable', () => {
  it('renders without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(ProductionWipTable, {
      attachTo: document.body,
      props: { lots: [lot], loading: false },
      global: {
        plugins: [router],
      },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(wrapper.text()).toContain('LOT-0001')
    expect(wrapper.text()).toContain('PN-001')
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  // selectionMode="single" makes the row keyboard-reachable
  // and gives Enter the same effect as a click, via the shared
  // useRowOpenGuard recipe proven on OrdersTable/ArticleGroupManagementTable.
  it('makes the first row keyboard-focusable and opens the lot detail on @row-select like @row-click', async () => {
    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(ProductionWipTable, {
      attachTo: document.body,
      props: { lots: [lot], loading: false },
      global: {
        plugins: [router],
      },
    })
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.exists()).toBe(true)
    expect(row.attributes('tabindex')).toBe('0')

    const { lotId, visible } = useLotDetail()
    expect(visible.value).toBe(false)

    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('row-select', { data: lot, index: 0, originalEvent: new Event('keydown') })
    await flushPromises()

    expect(visible.value).toBe(true)
    expect(lotId.value).toBe(lot.id)

    wrapper.unmount()
  })

  // OpenVue's own `rowTabindex` (BodyRow.vue) only roves tabindex to a row
  // while `selection` stays null. Once any row is ever selected it returns -1
  // for every row, permanently. Binding `v-model:selection` would make the
  // very first row-open leave the whole table keyboard-unreachable, so the
  // table does not bind `selection` at all and it never leaves the null
  // state OpenVue's own logic depends on.
  it('keeps the first row keyboard-reachable after a row is opened via click', async () => {
    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(ProductionWipTable, {
      attachTo: document.body,
      props: { lots: [lot], loading: false },
      global: {
        plugins: [router],
      },
    })
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.attributes('tabindex')).toBe('0')

    await row.trigger('click')
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('tr[data-p-selectable-row="true"]').attributes('tabindex')).toBe('0')

    wrapper.unmount()
  })

  it('keeps the first row keyboard-reachable after a row is opened via Enter', async () => {
    await router.push('/')
    await router.isReady()

    const wrapper = mountWithApp(ProductionWipTable, {
      attachTo: document.body,
      props: { lots: [lot], loading: false },
      global: {
        plugins: [router],
      },
    })
    await flushPromises()
    await flushPromises()

    const row = wrapper.find('tr[data-p-selectable-row="true"]')
    expect(row.attributes('tabindex')).toBe('0')

    await row.trigger('keydown', { code: 'Enter' })
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('tr[data-p-selectable-row="true"]').attributes('tabindex')).toBe('0')

    wrapper.unmount()
  })
})

describe('ProductionWipTable row filters', () => {
  const lots: WipLotResponse[] = [
    { ...lot, id: 1, lot_number: 'LOT-0001', status: 'in_progress', priority: 'high', raw_count: 3, finished_count: 4 },
    {
      ...lot,
      id: 2,
      lot_number: 'LOT-0002',
      made_item_article_name: 'Bracket',
      made_item_part_number: 'PN-777',
      status: 'planned',
      priority: 'normal',
      raw_count: 10,
      finished_count: 0,
      stages: [],
    },
    {
      ...lot,
      id: 3,
      lot_number: 'LOT-0103',
      made_item_article_name: 'Housing',
      made_item_part_number: 'PN-900',
      status: 'on_hold',
      priority: 'low',
      raw_count: 0,
      finished_count: 9,
      stages: [],
    },
  ]

  type FilterVm = {
    filters: Record<string, { value: unknown; matchMode: string }>
    clearFilters(): void
    hasActiveFilters: boolean
  }

  async function mountWithLots() {
    await router.push('/')
    await router.isReady()
    const wrapper = mountWithApp(ProductionWipTable, {
      attachTo: document.body,
      props: { lots },
      global: {
        plugins: [router],
      },
    })
    await flushPromises()
    return wrapper
  }

  function lotNumbers(wrapper: Awaited<ReturnType<typeof mountWithLots>>): string[] {
    return wrapper
      .findAll('tr[data-p-selectable-row="true"]')
      .map((row) => row.findAll('td')[1]?.text() ?? '')
  }

  async function setFilter(
    wrapper: Awaited<ReturnType<typeof mountWithLots>>,
    field: string,
    value: unknown,
  ): Promise<void> {
    const vm = wrapper.vm as unknown as FilterVm
    vm.filters = { ...vm.filters, [field]: { ...vm.filters[field]!, value } }
    await flushPromises()
  }

  it('narrows rows by lot number typed into the filter row', async () => {
    const wrapper = await mountWithLots()
    expect(lotNumbers(wrapper)).toEqual(['LOT-0001', 'LOT-0002', 'LOT-0103'])

    const input = wrapper.find(`input[aria-label="Filter by Lot Number"]`)
    await input.setValue('0103')
    await flushPromises()

    expect(lotNumbers(wrapper)).toEqual(['LOT-0103'])
    expect((wrapper.vm as unknown as FilterVm).hasActiveFilters).toBe(true)
    wrapper.unmount()
  })

  it('narrows rows by article name or part number in the item filter', async () => {
    const wrapper = await mountWithLots()
    await setFilter(wrapper, '_itemText', 'bracket')
    expect(lotNumbers(wrapper)).toEqual(['LOT-0002'])
    await setFilter(wrapper, '_itemText', 'PN-900')
    expect(lotNumbers(wrapper)).toEqual(['LOT-0103'])
    wrapper.unmount()
  })

  it('narrows rows by status and priority', async () => {
    const wrapper = await mountWithLots()
    await setFilter(wrapper, 'status', ['planned', 'on_hold'])
    expect(lotNumbers(wrapper)).toEqual(['LOT-0002', 'LOT-0103'])
    await setFilter(wrapper, 'priority', ['low'])
    expect(lotNumbers(wrapper)).toEqual(['LOT-0103'])
    wrapper.unmount()
  })

  it('narrows rows by raw and finished count ranges', async () => {
    const wrapper = await mountWithLots()
    await setFilter(wrapper, 'raw_count', [3, null])
    expect(lotNumbers(wrapper)).toEqual(['LOT-0001', 'LOT-0002'])
    await setFilter(wrapper, 'finished_count', [null, 2])
    expect(lotNumbers(wrapper)).toEqual(['LOT-0002'])
    wrapper.unmount()
  })

  it('shows every row again after clearFilters', async () => {
    const wrapper = await mountWithLots()
    await setFilter(wrapper, 'lot_number', '0002')
    expect(lotNumbers(wrapper)).toEqual(['LOT-0002'])

    const vm = wrapper.vm as unknown as FilterVm
    vm.clearFilters()
    await flushPromises()

    expect(lotNumbers(wrapper)).toEqual(['LOT-0001', 'LOT-0002', 'LOT-0103'])
    expect(vm.hasActiveFilters).toBe(false)
    wrapper.unmount()
  })
})
