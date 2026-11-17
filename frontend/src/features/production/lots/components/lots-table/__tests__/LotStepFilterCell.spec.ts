import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Select from 'openvue/select'
import Tooltip from 'openvue/tooltip'


// Both method stores load through the shared axios wrapper; dispatching on
// the URL keeps one mock for the two catalogues.
const getMock = vi.fn<(url: string) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
  },
}))

import LotStepFilterCell from '../LotStepFilterCell.vue'
import LotDateRangeFilter from '../LotDateRangeFilter.vue'
import LotFilterSelect from '../LotFilterSelect.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'
import NumberRangeFilter from '@/shared/components/table-filters/NumberRangeFilter.vue'
import { useProductionLotsFiltersStore } from '../../../stores/productionLotsFiltersStore'

import type { StepCellKind } from '../../../utils/lotStepColumns'

function page(items: unknown[]) {
  return { data: { items, total: items.length, limit: 1000, skip: 0 } }
}

function method(id: number, name: string, archived = false) {
  return { id, name, archived }
}

function mountCell(kind: StepCellKind) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const filtersStore = useProductionLotsFiltersStore()
  const wrapper = mountWithApp(LotStepFilterCell, {
    pinia,
    props: { kind },
    global: {
      directives: { tooltip: Tooltip },
    },
  })
  return { wrapper, filtersStore }
}

describe('LotStepFilterCell', () => {
  beforeEach(() => {
    getMock.mockReset()
    getMock.mockImplementation(async (url: string) => {
      if (url === '/fabrication-methods/') {
        return page([method(1, 'Milling'), method(2, 'Turning'), method(3, 'Old', true)])
      }
      if (url === '/inspection-methods/') return page([method(7, 'CMM')])
      return page([])
    })
  })

  describe('method', () => {
    it('loads both catalogues on first open and offers the live methods grouped, values encoded', async () => {
      const { wrapper } = mountCell('method')
      await flushPromises()
      expect(getMock).not.toHaveBeenCalled()

      const select = wrapper.findComponent(Select)
      select.vm.$emit('before-show')
      await flushPromises()

      expect(getMock).toHaveBeenCalledWith('/fabrication-methods/')
      expect(getMock).toHaveBeenCalledWith('/inspection-methods/')
      expect(getMock).toHaveBeenCalledTimes(2)

      // Reopening does not refetch, the stores keep the lists.
      select.vm.$emit('before-show')
      await flushPromises()
      expect(getMock).toHaveBeenCalledTimes(2)

      const groups = select.props('options') as { label: string; items: { value: string }[] }[]
      expect(groups.map((g) => g.label)).toEqual(['Fabrication Methods', 'Inspection Methods'])
      expect(groups[0]!.items.map((i) => i.value)).toEqual(['fabrication:1', 'fabrication:2'])
      expect(groups[1]!.items.map((i) => i.value)).toEqual(['inspection:7'])
    })

    it('writes the encoded selection to the store and clears it back to null', async () => {
      const { wrapper, filtersStore } = mountCell('method')
      await flushPromises()

      const select = wrapper.findComponent(Select)
      select.vm.$emit('update:modelValue', 'inspection:7')
      expect(filtersStore.stepMethod).toBe('inspection:7')

      select.vm.$emit('update:modelValue', null)
      expect(filtersStore.stepMethod).toBeNull()
    })

    it('does not fetch the catalogues for any other kind', async () => {
      mountCell('status')
      mountCell('note')
      await flushPromises()

      expect(getMock).not.toHaveBeenCalled()
    })
  })

  it('status: offers every display key with its label and writes the pick to the store', () => {
    const { wrapper, filtersStore } = mountCell('status')

    const select = wrapper.findComponent(LotFilterSelect)
    const options = select.props('options') as { label: string; value: string }[]
    expect(options.map((o) => o.value)).toEqual([
      'pending',
      'allocated',
      'ordered',
      'queued',
      'ordered_or_queued',
      'in_progress',
      'partially_completed',
      'completed',
      'canceled',
    ])
    expect(options.find((o) => o.value === 'ordered_or_queued')!.label).toBe('Ordered / Queued')

    select.vm.$emit('update:modelValue', 'queued')
    expect(filtersStore.stepStatus).toBe('queued')
  })

  it('setup: binds an integer min/max range to the setup fields', () => {
    const { wrapper, filtersStore } = mountCell('setup')

    const range = wrapper.findComponent(NumberRangeFilter)
    expect(range.props('fractionDigits')).toBe(0)
    expect(range.props('unit')).toBe('min')

    range.vm.$emit('update:modelValue', [5, 20])
    expect(filtersStore.stepSetupMin).toBe(5)
    expect(filtersStore.stepSetupMax).toBe(20)

    range.vm.$emit('update:modelValue', null)
    expect(filtersStore.stepSetupMin).toBeNull()
    expect(filtersStore.stepSetupMax).toBeNull()
  })

  it('perPiece: binds a fractional min/max range to the per-piece fields', () => {
    const { wrapper, filtersStore } = mountCell('perPiece')

    const range = wrapper.findComponent(NumberRangeFilter)
    expect(range.props('fractionDigits')).toBe(2)

    range.vm.$emit('update:modelValue', [0.5, null])
    expect(filtersStore.stepPerPieceMin).toBe(0.5)
    expect(filtersStore.stepSetupMin).toBeNull()
  })

  it.each([
    ['plannedStart', 'stepPlannedStartFrom', 'stepPlannedStartTo'],
    ['plannedDate', 'stepPlannedEndFrom', 'stepPlannedEndTo'],
    ['deliveryDate', 'stepDeliveryFrom', 'stepDeliveryTo'],
  ] as const)('%s: writes the picked range into %s / %s and clears both', (kind, fromKey, toKey) => {
    const { wrapper, filtersStore } = mountCell(kind)
    const from = new Date(2026, 2, 1)
    const to = new Date(2026, 2, 9)

    const picker = wrapper.findComponent(LotDateRangeFilter)
    picker.vm.$emit('update:modelValue', [from, to])
    expect(filtersStore[fromKey]).toBe(from)
    expect(filtersStore[toKey]).toBe(to)

    picker.vm.$emit('update:modelValue', null)
    expect(filtersStore[fromKey]).toBeNull()
    expect(filtersStore[toKey]).toBeNull()
  })

  it('note: a text input bound to stepNote', async () => {
    const { wrapper, filtersStore } = mountCell('note')

    await wrapper.find('input').setValue('deburr')
    expect(filtersStore.stepNote).toBe('deburr')
  })
})
