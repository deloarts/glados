import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { computed, ref } from 'vue'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { SequenceDocument } from '../../composables/useSequenceDocument'
import type { SequenceStep } from '../../types/sequence'
import { normalizeSteps } from '../../utils/steps'

vi.mock('@/features/product-devices/api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: () => Promise.resolve([]),
  getProductDeviceKinds: () => Promise.resolve([]),
}))

import SequenceEditor from '../SequenceEditor.vue'

/** The parts of the document the editor reads. */
function fakeDoc(editable: boolean): SequenceDocument {
  return {
    sequence: ref(null),
    devices: ref([]),
    variants: ref([]),
    editable: computed(() => editable),
  } as unknown as SequenceDocument
}

async function mountEditor(initial: SequenceStep[], editable = true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const steps = ref<SequenceStep[]>(normalizeSteps(initial))
  const wrapper = mountWithApp(SequenceEditor, {
    pinia,
    props: {
      doc: fakeDoc(editable),
      name: 'Automatic',
      steps: steps.value,
      'onUpdate:steps': (next: SequenceStep[]) => {
        steps.value = next
        void wrapper.setProps({ steps: next })
      },
    },
  })
  await flushPromises()
  return { wrapper, steps }
}

describe('SequenceEditor', () => {
  it('adds steps that go on to each other and end the sequence at the last one', async () => {
    const { wrapper, steps } = await mountEditor([])
    await wrapper.find('[data-testid="sequence-add-step"]').trigger('click')
    await wrapper.find('[data-testid="sequence-add-step"]').trigger('click')
    await flushPromises()
    expect(steps.value).toHaveLength(2)
    expect(steps.value[0]!.transitions![0]!.target).toBe('next')
    expect(steps.value[1]!.transitions![0]!.target).toBe('end')
    expect(wrapper.findAll('[data-testid^="sequence-step-"]').length).toBeGreaterThanOrEqual(2)
  })

  it('drops the references to a removed step', async () => {
    const { wrapper, steps } = await mountEditor([
      {
        key: 's1',
        transitions: [{ key: 't1', target: 'next', condition: [{ kind: 'step_complete', step_key: 's2' }] }],
      },
      { key: 's2', transitions: [{ key: 't2', target: 's1' }] },
      { key: 's3', transitions: [{ key: 't3', target: 's2' }] },
    ])
    const removes = wrapper.findAll('[data-testid="sequence-remove-step"]')
    await removes[1]!.trigger('click')
    await flushPromises()
    expect(steps.value.map((s) => s.key)).toEqual(['s1', 's3'])
    expect(steps.value[0]!.transitions![0]!.condition![0]!.step_key).toBeNull()
    // The step that led to the removed one goes on to the next step instead,
    // which as the last step ends the sequence.
    expect(steps.value[1]!.transitions![0]!.target).toBe('end')
  })

  it('shows the problems of a step while editing', async () => {
    const { wrapper } = await mountEditor([
      { key: 's1', actions: [{ key: 'a1', kind: 'text', qualifier: 'stored' }], transitions: [{ key: 't1', target: 'end' }] },
    ])
    expect(wrapper.text()).toContain('An action needs a device and a position, or a text.')
  })

  it('offers no editing buttons when read-only', async () => {
    const { wrapper } = await mountEditor([{ key: 's1', transitions: [{ key: 't1', target: 'end' }] }], false)
    expect(wrapper.find('[data-testid="sequence-add-step"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sequence-remove-step"]').exists()).toBe(false)
  })

  it('reads as text without inputs when read-only', async () => {
    const { wrapper } = await mountEditor(
      [
        {
          key: 's1',
          description: 'Clamp the part',
          timeout_ms: 5000,
          actions: [{ key: 'a1', kind: 'text', text: 'Close the guard', qualifier: 'pulse', description: 'By hand' }],
          transitions: [{ key: 't1', target: 'end', condition: [{ kind: 'external', text: 'Robot ready' }] }],
        },
      ],
      false,
    )
    expect(wrapper.find('input').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sequence-name-text"]').text()).toBe('Automatic')
    expect(wrapper.find('[data-testid="sequence-step-description"]').text()).toBe('Clamp the part')
    expect(wrapper.find('[data-testid="sequence-action-text"]').text()).toBe('Close the guard')
    expect(wrapper.find('[data-testid="sequence-action-qualifier"]').text()).toBe('P')
    expect(wrapper.find('[data-testid="sequence-transition-target"]').text()).toBe('End of sequence')
    expect(wrapper.text()).toContain('5000 ms')
    expect(wrapper.text()).toContain('By hand')
    expect(wrapper.text()).toContain('Robot ready')
  })

  it('shows each step\'s estimated duration and lets a step expect one', async () => {
    const { wrapper, steps } = await mountEditor([{ key: 's1', transitions: [{ key: 't1', target: 'end' }] }])
    expect(wrapper.find('[data-testid="sequence-step-duration"]').text()).toBe('0 ms')
    steps.value = [{ ...steps.value[0]!, expected_duration_ms: { common: 2500, per_variant: {} } }]
    await wrapper.setProps({ steps: steps.value })
    expect(wrapper.find('[data-testid="sequence-step-duration"]').text()).toBe('2.5 s')
  })

  it('inserts a step between two steps that the step before goes on to', async () => {
    const { wrapper, steps } = await mountEditor([
      { key: 's1', transitions: [{ key: 't1', target: 'next' }] },
      { key: 's2', transitions: [{ key: 't2', target: 's1' }] },
    ])
    const inserts = wrapper.findAll('[data-testid="sequence-insert-step"]')
    expect(inserts).toHaveLength(1)
    await inserts[0]!.trigger('click')
    await flushPromises()
    expect(steps.value).toHaveLength(3)
    expect(steps.value[0]!.key).toBe('s1')
    expect(steps.value[2]!.key).toBe('s2')
    expect(steps.value[0]!.transitions![0]!.target).toBe('next')
    expect(steps.value[1]!.transitions![0]!.target).toBe('next')
    expect(steps.value[2]!.transitions![0]!.target).toBe('s1')
  })

  it("offers a transition the positions its step moves to and adds one on click", async () => {
    const { wrapper, steps } = await mountEditor([
      {
        key: 's1',
        actions: [{ key: 'a1', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 11 }],
        transitions: [{ key: 't1', target: 'end' }],
      },
    ])
    const suggestions = wrapper.findAll('[data-testid="sequence-suggestion"]')
    expect(suggestions).toHaveLength(1)
    await suggestions[0]!.trigger('click')
    await flushPromises()
    expect(steps.value[0]!.transitions![0]!.condition).toEqual([
      expect.objectContaining({ kind: 'device_position', device_id: 5, position_id: 11 }),
    ])
    expect(wrapper.find('[data-testid="sequence-suggestion"]').exists()).toBe(false)
  })

  it('offers no step insertion or suggestions when read-only', async () => {
    const { wrapper } = await mountEditor(
      [
        {
          key: 's1',
          actions: [{ key: 'a1', kind: 'device', qualifier: 'stored', device_id: 5, position_id: 11 }],
          transitions: [{ key: 't1', target: 'next' }],
        },
        { key: 's2', transitions: [{ key: 't2', target: 'end' }] },
      ],
      false,
    )
    expect(wrapper.find('[data-testid="sequence-insert-step"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sequence-suggestion"]').exists()).toBe(false)
  })
})
