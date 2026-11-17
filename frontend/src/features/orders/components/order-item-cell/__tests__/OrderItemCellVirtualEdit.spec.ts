import { describe, it, expect, vi } from 'vitest'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
  },
}))

import OrderItemCellVirtualEdit from '../OrderItemCellVirtualEdit.vue'
import type { BoughtItemResponse } from '@/features/bought-items'
import { mountWithApp } from '@/test-utils/mountWithApp'

function mountCell(
  props: { originalItemId: number | null },
  modelValue: {
    virtualName?: string
    selectedItem?: BoughtItemResponse | null
    substituteReason?: string
  } = {},
) {
  return mountWithApp(OrderItemCellVirtualEdit, {
    props: {
      ...props,
      virtualName: modelValue.virtualName ?? '',
      'onUpdate:virtualName': () => {},
      selectedItem: modelValue.selectedItem ?? null,
      'onUpdate:selectedItem': () => {},
      substituteReason: modelValue.substituteReason ?? '',
      'onUpdate:substituteReason': () => {},
    },
  })
}

describe('OrderItemCellVirtualEdit', () => {
  it('shows the free-text name input when no catalogue item is selected', () => {
    const wrapper = mountCell({ originalItemId: null })
    expect(wrapper.find('input').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'BoughtItemSelect' }).exists()).toBe(true)
  })

  it('hides the free-text name input once a catalogue item is selected', () => {
    const selectedItem = { id: 7, article_name: 'Widget' } as BoughtItemResponse
    const wrapper = mountCell({ originalItemId: null }, { selectedItem })
    const inputs = wrapper.findAllComponents({ name: 'InputText' })
    // Only the substitute-reason InputText should render, not the name one.
    expect(inputs).toHaveLength(1)
  })

  it('shows the substitute-reason input only when the selection differs from the original item', () => {
    const selectedItem = { id: 7, article_name: 'Widget' } as BoughtItemResponse

    const same = mountCell({ originalItemId: 7 }, { selectedItem })
    expect(same.findAllComponents({ name: 'InputText' })).toHaveLength(0)

    const different = mountCell({ originalItemId: 3 }, { selectedItem })
    expect(different.findAllComponents({ name: 'InputText' })).toHaveLength(1)
  })
})
