import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { computed, defineComponent, h, ref } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { SequenceDocument } from '../../composables/useSequenceDocument'
import { useSequenceTiming } from '../../composables/useSequenceTiming'
import type { SequenceStep } from '../../types/sequence'
import { normalizeSteps } from '../../utils/steps'

vi.mock('@/features/product-devices/api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: () => Promise.resolve([]),
  getProductDeviceKinds: () => Promise.resolve([]),
}))

import SequenceDisplacementDiagram from '../SequenceDisplacementDiagram.vue'

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
        '11': {
          label: { enGB: 'Extended' },
          device_label: 'Robot pickup',
          unit: null,
          takes_value: false,
          travel_time_ms: 1500,
        },
      },
    },
  },
  variants: {},
}

function released(steps: SequenceStep[]): SequenceDocument {
  return {
    sequence: ref({ frozen: FROZEN }),
    devices: ref([]),
    variants: ref([]),
    steps: ref(steps),
    editable: computed(() => false),
  } as unknown as SequenceDocument
}

describe('SequenceDisplacementDiagram', () => {
  it('draws a row per moved device with the names frozen at the release', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const steps = normalizeSteps([
      {
        key: 's1',
        actions: [{ key: 'a1', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 11 }],
        transitions: [{ key: 't1', target: 'end' }],
      },
    ])
    const wrapper = mountWithApp(SequenceDisplacementDiagram, { pinia, props: { doc: released(steps) } })
    await flushPromises()
    const svg = wrapper.find('[data-testid="sequence-displacement-diagram"]')
    expect(svg.exists()).toBe(true)
    expect(svg.text()).toContain('B01 Lift P1')
    expect(svg.text()).toContain('Robot pickup')
    expect(svg.text()).toContain('End')
    expect(wrapper.findAll('polyline.move')).toHaveLength(1)
  })

  it('says so when no step moves a device', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const wrapper = mountWithApp(SequenceDisplacementDiagram, { pinia, props: { doc: released([]) } })
    await flushPromises()
    expect(wrapper.text()).toContain('No step moves a device yet.')
  })

  it('sizes the columns by the estimated step durations on the time axis', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const steps = normalizeSteps([
      {
        key: 's1',
        actions: [{ key: 'a1', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 11 }],
        transitions: [{ key: 't1', target: 'next' }],
      },
      {
        key: 's2',
        actions: [{ key: 'a2', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 10 }],
        transitions: [{ key: 't2', target: 'end' }],
      },
    ])
    // The page shares one timing between its controls bar and the diagram.
    const Page = defineComponent({
      setup() {
        const doc = released(steps)
        const timing = useSequenceTiming(doc)
        timing.toggleTimeAxis()
        return () => h(SequenceDisplacementDiagram, { doc, timing })
      },
    })
    const wrapper = mountWithApp(Page, { pinia })
    await flushPromises()
    const durations = wrapper.findAll('[data-testid="sequence-diagram-duration"]').map((d) => d.text())
    // Step 2 has no travel time, so it has no estimate.
    expect(durations).toEqual(['1.5 s', '?'])
  })
})
