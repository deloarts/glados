import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { ProductDeviceKind } from '../../types/productDevice'
import { newComponentForm, newSignal } from '../../utils/deviceForm'
import type { ProductDeviceComponentForm } from '../../utils/deviceForm'

vi.mock('../../api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: () => Promise.resolve([]),
  getProductDeviceKinds: () => Promise.resolve([]),
}))
vi.mock('@/features/bought-items/api/getBoughtItems', () => ({
  getBoughtItems: async () => ({ items: [], total: 0, skip: 0, limit: 50 }),
}))

import ProductDeviceComponentsEditor from '../ProductDeviceComponentsEditor.vue'

const KIND: ProductDeviceKind = {
  id: 1,
  public_id: 'k',
  created: '2026-10-22T00:00:00Z',
  changed: '2026-10-22T00:00:00Z',
  changed_by: null,
  changed_by_id: null,
  label: { enGB: 'Servo axis' },
  sort_order: 0,
  archived: false,
  creator_id: 1,
  creator: null,
  without_driving_medium: false,
  positions: [
    {
      id: 10,
      public_id: 'p',
      label: { enGB: 'Home' },
      takes_value: false,
      unit: null,
      sort_order: 0,
      archived: false,
      plc_state_name: null,
      plc_command_name: null,
    },
  ],
  parameters: [],
  signals: [
    { id: 30, public_id: 's', label: { enGB: 'Enable' }, signal_type: 'do', plc_name: 'Freigabe', sort_order: 0, archived: false },
  ],
}

function mountEditor() {
  setActivePinia(createPinia())
  const component = newComponentForm()
  component.signals.push(newSignal(false))
  const rows: ProductDeviceComponentForm[] = [component]
  const wrapper = mountWithApp(ProductDeviceComponentsEditor, {
    props: { modelValue: rows, kind: KIND },
  })
  return { wrapper, signal: component.signals[0]! }
}

describe('ProductDeviceComponentsEditor', () => {
  it("offers the kind's positions and signals in one picker, and a kind signal brings its type", async () => {
    const { wrapper, signal } = mountEditor()
    await flushPromises()
    const picker = wrapper.findAllComponents({ name: 'Select' }).find((s) => s.attributes('data-testid') === 'signal-position')!
    const groups = picker.props('options') as Array<{ items: Array<{ value: string }> }>
    expect(groups.map((g) => g.items.map((i) => i.value))).toEqual([['position:10'], ['signal:30']])

    picker.vm.$emit('update:modelValue', 'signal:30')
    await flushPromises()
    expect(signal.kind_signal_id).toBe(30)
    expect(signal.position_id).toBeNull()
    expect(signal.signal_type).toBe('do')

    picker.vm.$emit('update:modelValue', 'position:10')
    await flushPromises()
    expect(signal.kind_signal_id).toBeNull()
    expect(signal.position_id).toBe(10)
  })
})
