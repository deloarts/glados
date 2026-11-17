import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import GeneralTolerancesTab from '../GeneralTolerancesTab.vue'
import { toolTestHost } from '../../composables/useToolState'

// Starts the tool as the tools view does: on a saved calculation's inputs,
// or on its defaults when there are none.
async function mountAt(inputs: Record<string, string> | null = null) {
  const host = toolTestHost(inputs)
  const wrapper = mountWithApp(GeneralTolerancesTab, { global: { provide: host.provide } })
  await flushPromises()
  return { state: host.state, wrapper }
}

function text(wrapper: Awaited<ReturnType<typeof mountAt>>['wrapper'], testid: string): string {
  return wrapper.get(`[data-testid="${testid}"]`).text()
}

describe('GeneralTolerancesTab', () => {
  it('starts with ISO 2768-mK at 25 mm and publishes it as its inputs', async () => {
    const { state, wrapper } = await mountAt()

    expect(text(wrapper, 'gt-designation')).toBe('ISO 2768-mK')
    expect(text(wrapper, 'gt-linear')).toBe('±0.2 mm')
    expect(text(wrapper, 'gt-maxSize')).toBe('25.2 mm')
    expect(text(wrapper, 'gt-minSize')).toBe('24.8 mm')
    expect(text(wrapper, 'gt-brokenEdge')).toBe('±1 mm')
    expect(text(wrapper, 'gt-angular')).toBe('±0° 30′')
    expect(text(wrapper, 'gt-straightnessFlatness')).toBe('0.1 mm')
    expect(text(wrapper, 'gt-perpendicularity')).toBe('0.4 mm')
    expect(text(wrapper, 'gt-symmetry')).toBe('0.6 mm')
    expect(text(wrapper, 'gt-circularRunOut')).toBe('0.2 mm')
    expect(state.value?.inputs).toEqual({ d: '25', linear: 'm', geometric: 'K' })

    wrapper.unmount()
  })

  it('highlights the matching cell of every table', async () => {
    const { wrapper } = await mountAt({ d: '150', linear: 'c', geometric: 'L' })

    expect(text(wrapper, 'ref-hit-linear')).toBe('±1.2')
    expect(text(wrapper, 'ref-hit-angular')).toBe('±0° 15′')
    expect(text(wrapper, 'ref-hit-straightnessFlatness')).toBe('0.8')
    expect(text(wrapper, 'ref-hit-circularRunOut')).toBe('0.5')

    wrapper.unmount()
  })

  it('explains sizes and classes the standard leaves open', async () => {
    const { wrapper } = await mountAt({ d: '2', linear: 'v', geometric: 'none' })

    expect(text(wrapper, 'gt-designation')).toBe('ISO 2768-v')
    expect(text(wrapper, 'gt-linear')).toContain('Not defined for class v')
    expect(text(wrapper, 'gt-card-geometric')).toContain('No general tolerance class')
    expect(wrapper.find('[data-testid="ref-hit-straightnessFlatness"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('falls back to the defaults for invalid parts of saved inputs', async () => {
    const { state, wrapper } = await mountAt({ d: 'abc', linear: 'x', geometric: 'H' })

    expect(text(wrapper, 'gt-designation')).toBe('ISO 2768-mH')
    expect(state.value?.inputs).toEqual({ d: '25', linear: 'm', geometric: 'H' })

    wrapper.unmount()
  })
})
