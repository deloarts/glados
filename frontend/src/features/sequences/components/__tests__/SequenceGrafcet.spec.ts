import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { computed, ref } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { SequenceDocument } from '../../composables/useSequenceDocument'
import { normalizeSteps } from '../../utils/steps'

vi.mock('@/features/product-devices/api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: () => Promise.resolve([]),
  getProductDeviceKinds: () => Promise.resolve([]),
}))

import SequenceGrafcet from '../SequenceGrafcet.vue'

const FROZEN = {
  product_number: 'M26001',
  devices: {
    '5': {
      name: 'B01 Lift P1',
      name_ascii: 'B01_Lift_P1',
      kind: { enGB: 'Linear drive' },
      initial_position_id: 10,
      initial_position_value: null,
      positions: {
        '10': { label: { enGB: 'Retracted' }, device_label: null, unit: null, takes_value: false },
        '12': { label: { enGB: 'Stroke' }, device_label: null, unit: 'mm', takes_value: true },
      },
    },
  },
  variants: { '1': 'Clamp 60', '2': 'Clamp 80' },
}

describe('SequenceGrafcet', () => {
  it('writes actions, conditions in GRAFCET notation and the values of the picked variant', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const steps = normalizeSteps([
      {
        key: 's1',
        actions: [
          {
            key: 'a1',
            kind: 'device',
            qualifier: 'stored',
            device_id: 5,
            position_id: 12,
            value: { common: null, per_variant: { '1': 60, '2': 80 } },
          },
        ],
        transitions: [
          {
            key: 't1',
            target: 'next',
            condition: [
              { kind: 'device_position', device_id: 5, position_id: 12 },
              { kind: 'time', duration_ms: { common: 500 } },
            ],
          },
        ],
      },
      { key: 's2', transitions: [{ key: 't2', target: 's1', condition: [{ kind: 'step_complete', step_key: 's1' }] }] },
    ])
    const doc = {
      sequence: ref({ frozen: FROZEN }),
      devices: ref([]),
      variants: ref([]),
      steps: ref(steps),
      editable: computed(() => false),
    } as unknown as SequenceDocument
    const wrapper = mountWithApp(SequenceGrafcet, { pinia, props: { doc } })
    await flushPromises()

    const svg = wrapper.find('[data-testid="sequence-grafcet"]')
    expect(svg.text()).toContain('B01 Lift P1')
    expect(wrapper.find('[data-testid="grafcet-action-command"]').text()).toBe('Stroke Per variant')
    expect(svg.text()).toContain('B01 Lift P1: Stroke · 500 ms/X1')
    expect(svg.text()).toContain('X1')

    await wrapper.findAll('[data-testid="sequence-grafcet-variant"] button').at(-1)!.trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="grafcet-action-command"]').text()).toBe('Stroke 80 mm')
  })
})
