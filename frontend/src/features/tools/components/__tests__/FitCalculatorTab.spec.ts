import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import FitCalculatorTab from '../FitCalculatorTab.vue'
import { toolTestHost } from '../../composables/useToolState'

// Starts the tool as the tools view does: on a saved calculation's inputs,
// or on its defaults when there are none.
async function mountAt(inputs: Record<string, string> | null = null) {
  const host = toolTestHost(inputs)
  const wrapper = mountWithApp(FitCalculatorTab, { global: { provide: host.provide } })
  await flushPromises()
  return { state: host.state, wrapper }
}

function text(wrapper: Awaited<ReturnType<typeof mountAt>>['wrapper'], testid: string): string {
  return wrapper.get(`[data-testid="${testid}"]`).text()
}

describe('FitCalculatorTab', () => {
  it('starts with 25 H7/g6 and publishes it as its inputs', async () => {
    const { state, wrapper } = await mountAt()

    expect(text(wrapper, 'fit-code')).toContain('H7/g6')
    expect(text(wrapper, 'fit-hole-upper')).toBe('+0.021 mm')
    expect(text(wrapper, 'fit-shaft-lower')).toBe('-0.020 mm')
    expect(text(wrapper, 'fit-type')).toBe('Clearance fit')
    expect(text(wrapper, 'fit-maxClearance')).toBe('0.041 mm')
    expect(text(wrapper, 'fit-minClearance')).toBe('0.007 mm')
    expect(state.value?.inputs).toEqual({ d: '25', hole: 'H7', shaft: 'g6' })

    wrapper.unmount()
  })

  it('opens saved inputs with its size and fit', async () => {
    const { wrapper } = await mountAt({ d: '30', hole: 'H8', shaft: 'f7' })

    expect(text(wrapper, 'fit-maxClearance')).toBe('0.074 mm')
    expect(text(wrapper, 'fit-minClearance')).toBe('0.020 mm')
    expect(wrapper.find('[data-testid="fit-recommended"]').text()).toContain('series 1')
    expect(text(wrapper, 'fit-explain-maxClearance')).toBe('= 30.033 mm − 29.959 mm = 0.074 mm')
    expect(text(wrapper, 'fit-explain-shaft-max')).toBe('= 30 mm − 0.020 mm = 29.980 mm')
    expect(text(wrapper, 'fit-explain-type-clearance')).toContain('Current fit')
    expect(text(wrapper, 'fit-explain-type-transition')).not.toContain('Current fit')

    wrapper.unmount()
  })

  it('falls back to the default for an invalid part of saved inputs', async () => {
    const { state, wrapper } = await mountAt({ d: '40', hole: 'Q7', shaft: 'k6' })

    expect(text(wrapper, 'fit-code')).toContain('H7/k6')
    expect(text(wrapper, 'fit-type')).toBe('Transition fit')
    expect(state.value?.inputs).toEqual({ d: '40', hole: 'H7', shaft: 'k6' })

    wrapper.unmount()
  })

  it('applies a recommendation on click', async () => {
    const { state, wrapper } = await mountAt()

    await wrapper.get('[data-testid="fit-rec-H7-r6"]').trigger('click')
    await flushPromises()

    expect(text(wrapper, 'fit-code')).toContain('H7/r6')
    expect(text(wrapper, 'fit-type')).toBe('Interference fit')
    expect(text(wrapper, 'fit-maxInterference')).toBe('0.041 mm')
    expect(text(wrapper, 'fit-minInterference')).toBe('0.007 mm')
    expect(state.value?.inputs.shaft).toBe('r6')

    wrapper.unmount()
  })

  it('explains a combination without standard values instead of showing numbers', async () => {
    const { wrapper } = await mountAt({ d: '600', hole: 'H7', shaft: 'g6' })

    expect(text(wrapper, 'fit-hole-upper')).toBe('+0.070 mm')
    expect(text(wrapper, 'fit-shaft-card')).toContain('no standard values for g6')
    expect(wrapper.find('[data-testid="fit-type"]').exists()).toBe(false)

    wrapper.unmount()
  })
})
