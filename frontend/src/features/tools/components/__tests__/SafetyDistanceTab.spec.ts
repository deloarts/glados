import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { i18n } from '@/core/i18n'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { toolTestHost } from '../../composables/useToolState'
import { emptySafetyDistanceInputs } from '../../utils/safetyDistance/inputs'
import { encodeSafetyDistanceInputs } from '../../utils/safetyDistance/inputRecord'
import { sampleSafetyDistanceInputs } from '@/features/tools/__tests__/fixtures'
import type { SafetyDistanceMode } from '../../utils/safetyDistance/types'
import SafetyDistanceTab from '../SafetyDistanceTab.vue'

const { warn } = vi.hoisted(() => ({ warn: vi.fn<(summary: string, detail?: string) => void>() }))

vi.mock('@/core/composables/useAppToast', () => ({
  useAppToast: () => ({
    warn,
    success: vi.fn<(summary: string, detail?: string) => void>(),
    info: vi.fn<(summary: string, detail?: string) => void>(),
    error: vi.fn<(summary: string, detail?: string) => void>(),
  }),
}))

const SAMPLE_INPUTS = encodeSafetyDistanceInputs(sampleSafetyDistanceInputs())

/** The saved record of the sample in one mode, since a record keeps only the keys of its mode. */
function sampleRecord(mode: SafetyDistanceMode): Record<string, string> {
  return encodeSafetyDistanceInputs({ ...sampleSafetyDistanceInputs(), mode })
}

// The test host stands in for the tools view: it hands the tab its start
// inputs and keeps what the tab publishes.
async function mountWith(inputs: Record<string, string> | null) {
  const host = toolTestHost(inputs)
  const wrapper = mountWithApp(SafetyDistanceTab, { global: { provide: host.provide } })
  await flushPromises()
  const published = () => {
    if (!host.state.value) throw new Error('The tab published no state')
    return host.state.value
  }
  return { wrapper, published }
}

type Wrapper = Awaited<ReturnType<typeof mountWith>>['wrapper']

function text(wrapper: Wrapper, testid: string): string {
  return wrapper.get(`[data-testid="${testid}"]`).text()
}

async function chooseOption(wrapper: Wrapper, group: string, label: string) {
  const button = wrapper
    .get(`[data-testid="${group}"]`)
    .findAll('button')
    .find((b) => b.text() === label)
  if (!button) throw new Error(`No option labelled ${label} in ${group}`)
  await button.trigger('click')
  await flushPromises()
}

async function setField(wrapper: Wrapper, testid: string, value: number | null) {
  const input = wrapper
    .findAllComponents({ name: 'InputNumber' })
    .find((c) => c.attributes('data-testid') === testid)
  if (!input) throw new Error(`No input ${testid}`)
  input.vm.$emit('update:modelValue', value)
  await flushPromises()
}

describe('SafetyDistanceTab', () => {
  beforeEach(() => warn.mockClear())

  it('starts with a finger protecting light curtain and its side view', async () => {
    const { wrapper } = await mountWith(SAMPLE_INPUTS)

    expect(warn).not.toHaveBeenCalled()
    expect(text(wrapper, 'sd-s')).toBe('S = 200 mm')
    expect(text(wrapper, 'sd-k')).toBe('2000 mm/s')
    expect(text(wrapper, 'sd-formula')).toBe('S = K · T + DDS + Z')
    expect(text(wrapper, 'sd-step-reachThrough')).toContain('= 0 mm')
    expect(text(wrapper, 'sd-path-under')).toContain('160 mm')
    expect(text(wrapper, 'ref-hit-reachOver')).toBe('0')
    expect(text(wrapper, 'sd-sketch-s')).toBe('S = 200 mm')
    expect(wrapper.find('[data-testid="sd-sketch-path-through"]').attributes('data-governs')).toBe('true')
    expect(wrapper.find('[data-testid="tool-share-button"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('marks the path that sets the result in the side view', async () => {
    const { wrapper } = await mountWith({ ...SAMPLE_INPUTS, de: '30', hdb: '200', hh: '500' })

    expect(text(wrapper, 'sd-s')).toBe('S = 960 mm')
    const under = wrapper.get('[data-testid="sd-sketch-path-under"]')
    expect(under.attributes('data-governs')).toBe('true')
    expect(under.text()).toContain('800 mm')
    expect(wrapper.get('[data-testid="sd-sketch-path-through"]').attributes('data-governs')).toBe('false')
    expect(text(wrapper, 'sd-sketch-seg-reach')).toContain('800 mm')

    wrapper.unmount()
  })

  it('switches the mode and publishes only the keys the new mode uses', async () => {
    const { wrapper, published } = await mountWith(SAMPLE_INPUTS)

    expect(published().inputs).toMatchObject({ mode: 'espe', dev: 'curtain', de: '14', t: '0.1' })
    expect(published().title).toBe('Light curtain d = 14 mm, S = 200 mm')

    await chooseOption(wrapper, 'sd-mode', 'Two-hand control')

    // The response time is shared between the modes; the two-hand fields start empty.
    expect(published().inputs).toEqual({ mode: 'twoHand', tmode: 'direct', t: '0.1', prevent: '0', type: '', gap: '' })
    expect(text(wrapper, 'sd-s')).toBe('S = 710 mm')
    wrapper.unmount()
  })

  it('gives the safety distance of a two-hand control', async () => {
    const { wrapper, published } = await mountWith(sampleRecord('twoHand'))

    expect(published().inputs).toEqual({ mode: 'twoHand', tmode: 'direct', t: '0.1', prevent: '0', type: 'IIIC', gap: '550' })
    expect(published().results).toMatchObject({ mode: 'twoHand', s: 710, k: 1600 })

    expect(text(wrapper, 'sd-s')).toBe('S = 710 mm')
    expect(text(wrapper, 'sd-formula')).toBe('S = 1600 · T + 550')
    expect(wrapper.find('[data-testid="sd-paths"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sd-sketch-espe"]').exists()).toBe(false)
    expect(text(wrapper, 'sd-sketch-seg-reach')).toContain('550 mm')

    wrapper.unmount()
  })

  it('redraws the control sketch when the actuation changes', async () => {
    const { wrapper } = await mountWith({ mode: 'holdToRun', tmode: 'direct', t: '0.1', act: 'hand' })

    expect(wrapper.find('[data-testid="sd-sketch-reach-hand"]').exists()).toBe(true)
    expect(text(wrapper, 'sd-sketch-seg-reach')).toContain('2200 mm')

    await chooseOption(wrapper, 'sd-actuation', 'Foot')

    expect(wrapper.find('[data-testid="sd-sketch-reach-foot"]').exists()).toBe(true)
    expect(text(wrapper, 'sd-sketch-seg-reach')).toContain('2500 mm')
    expect(text(wrapper, 'sd-sketch-s')).toBe('S = 2660 mm')

    wrapper.unmount()
  })

  it('draws the entered beam heights and the matching row of Annex C', async () => {
    const { wrapper } = await mountWith({ mode: 'espe', dev: 'multiBeam', beams: '200,500,800,1100', t: '0.1' })

    expect(wrapper.findAll('[data-testid="sd-sketch-beam"]')).toHaveLength(4)
    expect(text(wrapper, 'sd-sketch-match')).toBe('Table C.1, 4 beams')
    expect(wrapper.find('[data-testid="sd-sketch-limit-top"]').exists()).toBe(true)

    await wrapper.get('[data-testid="sd-beams"]').setValue('300 700 1100')
    await flushPromises()

    expect(wrapper.findAll('[data-testid="sd-sketch-beam"]')).toHaveLength(3)
    expect(text(wrapper, 'sd-sketch-match')).toBe('Table C.2, 3 beams')

    wrapper.unmount()
  })

  it('shows the parallel zone with its depth and S', async () => {
    const { wrapper } = await mountWith({ mode: 'parallel', t: '0.5', de: '50', hd: '150', fd: '', gd: '' })

    expect(text(wrapper, 'sd-sketch-depth')).toBe('FD ≥ 1200 mm')
    expect(text(wrapper, 'sd-sketch-s')).toBe('S = 2000 mm')

    wrapper.unmount()
  })

  it('draws a hinged guard in plan view and the reach through its opening', async () => {
    const { wrapper } = await mountWith({
      mode: 'guard',
      tmode: 'direct',
      t: '0.5',
      lock: '1',
      tdy: '0.3',
      dgt: '850',
      em: 'hinged',
      gw: '1000',
      w: '5',
      gt: '20',
    })

    expect(text(wrapper, 'sd-s')).toBe('S = 1170 mm')
    expect(text(wrapper, 'sd-step-opening')).toContain('67.2 mm')
    expect(text(wrapper, 'ref-row-hingeGap')).toContain('87.2')
    expect(text(wrapper, 'sd-sketch-hinge-b')).toBe('b = 87.2 mm')
    expect(text(wrapper, 'sd-sketch-hinge-e')).toBe('e = 67.2 mm')
    expect(text(wrapper, 'sd-sketch-seg-reach')).toContain('850 mm')
    expect(text(wrapper, 'sd-sketch-seg-time')).toContain('320 mm')

    wrapper.unmount()
  })

  it('evaluates measurements per condition', async () => {
    const { wrapper } = await mountWith({
      mode: 'twoHand',
      tmode: 'measured',
      cold: '0.561,0.553,0.612,0.544,0.553,0.571,0.567,0.583,0.656,0.554',
      warm: '0.663,0.654,0.655,0.651,0.727,0.656,0.678,0.665,0.683,0.714',
    })

    expect(text(wrapper, 'sd-rt-cold')).toBe('0.6785 s')
    expect(text(wrapper, 'sd-rt-warm')).toBe('0.7541 s')
    expect(text(wrapper, 'sd-t-used')).toBe('0.7541 s')

    wrapper.unmount()
  })

  it('draws the components of T as a timeline', async () => {
    const { wrapper } = await mountWith({ mode: 'twoHand', tmode: 'components', ti: '0.02', tl: '0.01', tm: '0.17' })

    expect(text(wrapper, 'sd-sketch-time-total')).toBe('T = 0.2 s')
    expect(wrapper.find('[data-testid="sd-sketch-time-tI"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="sd-sketch-time-tO"]').exists()).toBe(false)

    await setField(wrapper, 'sd-tO', 0.1)

    expect(text(wrapper, 'sd-sketch-time-total')).toBe('T = 0.3 s')
    expect(wrapper.find('[data-testid="sd-sketch-time-tO"]').exists()).toBe(true)

    wrapper.unmount()
  })

  it('reports a configuration the standard does not permit', async () => {
    const { wrapper } = await mountWith({ ...SAMPLE_INPUTS, hdb: '350' })

    expect(text(wrapper, 'sd-s')).toBe('Not permitted or not covered')
    expect(text(wrapper, 'sd-message-bottomEdgeTooHigh')).toContain('300 mm')
    expect(text(wrapper, 'sd-sketch-path-under')).toContain('not covered')

    wrapper.unmount()
  })

  it('starts cleared for a new calculation, without numbers and asking for the fields', async () => {
    const { wrapper, published } = await mountWith(null)

    expect(text(wrapper, 'sd-s')).toBe('No result yet')
    expect(text(wrapper, 'sd-message-missingInputs')).toBe('Fill in the fields above to get a result.')
    expect(wrapper.find('[data-testid="sd-message-missingResponseTime"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="sd-k"]').exists()).toBe(false)
    expect(text(wrapper, 'sd-sketch-s')).toBe('S')
    expect(wrapper.find('[data-testid="sd-sketch-espe"]').text()).not.toMatch(/\d/)
    expect(wrapper.html()).not.toContain('NaN')
    expect(published().inputs).toEqual({
      mode: 'espe',
      tmode: 'direct',
      t: '',
      z: '',
      dev: 'curtain',
      de: '',
      hdt: '',
      hdb: '',
      hh: '',
      ind: '1',
      rs: '0',
      above: '0',
      below: '0',
    })
    expect(published().title).toBe('New safety distance')
    expect(warn).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('renders every mode cleanly while it is empty', async () => {
    const { wrapper } = await mountWith(null)

    for (const mode of ['Parallel approach', 'Two-hand control', 'Hold-to-run control', 'Interlocking guard']) {
      await chooseOption(wrapper, 'sd-mode', mode)
      expect(text(wrapper, 'sd-s')).toBe('No result yet')
      expect(text(wrapper, 'sd-sketch-s')).toBe('S')
      expect(wrapper.html()).not.toContain('NaN')
    }

    wrapper.unmount()
  })

  it('switches to the reach distances of ISO 13857 and back to the mode last used', async () => {
    const { wrapper, published } = await mountWith(sampleRecord('structure'))

    expect(wrapper.find('[data-testid="sd-response-time"]').exists()).toBe(false)
    expect(text(wrapper, 'sd-s')).toBe('sh = 800 mm')
    expect(text(wrapper, 'sd-ref')).toBe('ISO 13857:2019, 4.2.2, Table 2')
    expect(text(wrapper, 'ref-hit-structure')).toBe('800')
    expect(text(wrapper, 'sd-sketch-sh')).toBe('sh = 800 mm')
    expect(published().inputs).toEqual({ mode: 'structure', hh: '1400', hps: '1800', sh: '', low: '0' })
    expect(published().title).toBe('Protective structure 1800 mm, hazard at 1400 mm, safety distance 800 mm')

    await chooseOption(wrapper, 'sd-group', 'Protective device · ISO 13855')
    await chooseOption(wrapper, 'sd-mode', 'Interlocking guard')
    await chooseOption(wrapper, 'sd-group', 'Reach distance · ISO 13857')
    expect(published().inputs).toMatchObject({ mode: 'structure', hh: '1400', hps: '1800' })

    await chooseOption(wrapper, 'sd-group', 'Protective device · ISO 13855')
    expect(published().inputs).toMatchObject({ mode: 'guard' })

    wrapper.unmount()
  })

  it('gives the reach distance through an opening', async () => {
    const { wrapper } = await mountWith(sampleRecord('opening'))

    expect(text(wrapper, 'sd-s')).toBe('sr = 200 mm')
    expect(text(wrapper, 'sd-sketch-part')).toBe('Arm up to the shoulder')
    expect(text(wrapper, 'ref-hit-openings')).toBe('≥ 200')

    wrapper.unmount()
  })

  it('checks a structure as built and names the structure that would be enough', async () => {
    const { wrapper } = await mountWith({ mode: 'structure', hh: '1400', hps: '1600', sh: '600', low: '0' })

    expect(text(wrapper, 'sd-s')).toBe('sh = 900 mm')
    expect(text(wrapper, 'sd-message-structureTooClose')).toContain('900 mm')
    expect(text(wrapper, 'sd-message-structureHeightForDistance')).toContain('2000 mm')
    expect(text(wrapper, 'sd-sketch-built')).toBe('as built 600 mm')

    wrapper.unmount()
  })

  it('gives the minimum gap of a crushing point and the table row it comes from', async () => {
    const { wrapper, published } = await mountWith({ mode: 'crushing', part: 'arm', a: '100' })

    expect(text(wrapper, 'sd-s')).toBe('a = 120 mm')
    expect(text(wrapper, 'sd-message-gapTooSmall')).toContain('120 mm')
    expect(text(wrapper, 'ref-hit-crushing')).toBe('120')
    expect(text(wrapper, 'sd-ref')).toBe('ISO 13854:2017, 4.2, Table 1')
    expect(published().title).toBe('Crushing point, Arm, minimum gap 120 mm')

    wrapper.unmount()
  })

  it('renders the new modes cleanly while they are empty', async () => {
    const { wrapper } = await mountWith(null)

    await chooseOption(wrapper, 'sd-group', 'Reach distance · ISO 13857')
    for (const mode of ['Over a protective structure', 'Through an opening']) {
      await chooseOption(wrapper, 'sd-mode', mode)
      expect(text(wrapper, 'sd-s')).toBe('No result yet')
      expect(wrapper.html()).not.toContain('NaN')
    }
    await chooseOption(wrapper, 'sd-group', 'Crushing point · ISO 13854')
    expect(text(wrapper, 'sd-s')).toBe('No result yet')
    expect(text(wrapper, 'sd-sketch-a')).toBe('a')
    expect(wrapper.html()).not.toContain('NaN')

    wrapper.unmount()
  })

  it('reopens an empty saved calculation without calling it invalid', async () => {
    const { wrapper, published } = await mountWith(encodeSafetyDistanceInputs(emptySafetyDistanceInputs()))

    expect(warn).not.toHaveBeenCalled()
    expect(text(wrapper, 'sd-s')).toBe('No result yet')
    expect(published().inputs).toEqual(encodeSafetyDistanceInputs(emptySafetyDistanceInputs()))

    wrapper.unmount()
  })

  it('resets invalid saved inputs and says so', async () => {
    const { wrapper, published } = await mountWith({ mode: 'laser', t: 'abc', de: '500' })

    expect(text(wrapper, 'sd-s')).toBe('No result yet')
    expect(published().inputs).toMatchObject({ mode: 'espe', t: '', de: '' })
    expect(warn).toHaveBeenCalledWith('', i18n.global.t('tools.calculations.errors.invalidInputs'))

    wrapper.unmount()
  })
})
