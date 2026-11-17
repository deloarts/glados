import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { toolTestHost } from '../../composables/useToolState'
import { encodeDriveSizingInputs } from '../../utils/driveSizing/inputs'
import { emptyDriveSizingInput } from '../../utils/driveSizing/model'
import { sampleDriveSizingInput } from '@/features/tools/__tests__/fixtures'
import DriveSizingTab from '../DriveSizingTab.vue'

const { warn } = vi.hoisted(() => ({ warn: vi.fn<(summary: string, detail?: string) => void>() }))

vi.mock('@/core/composables/useAppToast', () => ({
  useAppToast: () => ({
    warn,
    success: vi.fn<(summary: string, detail?: string) => void>(),
    info: vi.fn<(summary: string, detail?: string) => void>(),
    error: vi.fn<(summary: string, detail?: string) => void>(),
  }),
}))

const SAMPLE_INPUTS = encodeDriveSizingInputs(sampleDriveSizingInput())
const EMPTY_INPUTS = encodeDriveSizingInputs(emptyDriveSizingInput())

// Starts the tool as the tools view does: on a saved calculation's inputs,
// or without them on a cleared form, and captures what it publishes.
async function mountWith(inputs: Record<string, string> | null) {
  const host = toolTestHost(inputs)
  const wrapper = mountWithApp(DriveSizingTab, { global: { provide: host.provide } })
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

async function setField(wrapper: Wrapper, testid: string, value: number | null) {
  const input = wrapper
    .findAllComponents({ name: 'InputNumber' })
    .find((c) => c.attributes('data-testid') === testid)
  if (!input) throw new Error(`No input ${testid}`)
  input.vm.$emit('update:modelValue', value)
  await flushPromises()
}

describe('DriveSizingTab', () => {
  beforeEach(() => warn.mockClear())

  it('opens the sample vertical axis and publishes its inputs and results', async () => {
    const { wrapper, published } = await mountWith(SAMPLE_INPUTS)

    expect(published().description).toBe('Vertical axis, 140 kg, i = 12')
    expect(text(wrapper, 'ds-verdict')).toBe('All checks passed.')
    expect(text(wrapper, 'ds-figure-cycleTime')).toBe('18.47 s')
    expect(text(wrapper, 'ds-check-peakTorque-value')).toBe('6.47 Nm')
    expect(text(wrapper, 'ds-check-peakTorque-utilisation')).toBe('36%')
    expect(text(wrapper, 'ds-check-rmsTorque-value')).toBe('4.91 Nm')
    expect(text(wrapper, 'ds-check-brakeHolding-status')).toBe('OK')
    expect(text(wrapper, 'ds-result-0-phase')).toBe('up, accelerating')
    expect(text(wrapper, 'ds-result-3-phase')).toBe('standstill, brake holds')
    expect(text(wrapper, 'ds-brake-stop')).toContain('stopping distance 13.9 mm')
    expect(published()).toMatchObject({
      inputs: SAMPLE_INPUTS,
      title: 'Vertical axis, 140 kg, i = 12',
      results: { ok: true, peakTorqueNm: 6.47, failedChecks: 0 },
    })
    expect(warn).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('shows one settings group at a time and switches between them', async () => {
    const { wrapper } = await mountWith(SAMPLE_INPUTS)
    const hidden = (group: string) =>
      wrapper.get(`[data-testid="ds-group-${group}"]`).classes().includes('ds-group--hidden')

    expect(hidden('axis')).toBe(false)
    expect(hidden('motor')).toBe(true)

    wrapper.findComponent({ name: 'SelectButton' }).vm.$emit('update:modelValue', 'motor')
    await flushPromises()
    expect(hidden('axis')).toBe(true)
    expect(hidden('motor')).toBe(false)

    wrapper.unmount()
  })

  it('recalculates when an input changes', async () => {
    const { wrapper, published } = await mountWith(SAMPLE_INPUTS)

    // 400 kg payload: up with payload F = 500 kg * (9.81 + 0.45) = 5130 N,
    // M = 5130 * 0.045835 / 12 / 0.855 + 0.053 = 22.97 Nm, above M_max = 18 Nm.
    await setField(wrapper, 'ds-field-payloadMassKg', 400)

    expect(published().description).toBe('Vertical axis, 500 kg, i = 12')
    expect(text(wrapper, 'ds-check-peakTorque-value')).toBe('22.97 Nm')
    expect(text(wrapper, 'ds-check-peakTorque-status')).toBe('Exceeded')
    expect(text(wrapper, 'ds-verdict')).not.toBe('All checks passed.')
    expect(published().inputs.mp).toBe('400')
    expect(published().title).toBe('Vertical axis, 500 kg, i = 12')

    wrapper.unmount()
  })

  it('lists what is missing instead of results', async () => {
    const { wrapper } = await mountWith(SAMPLE_INPUTS)

    await setField(wrapper, 'ds-field-ratio', null)

    expect(text(wrapper, 'ds-errors')).toContain('Ratio (Gearbox) is missing.')
    // The checks card stays, holding the missing list instead of a verdict.
    expect(wrapper.find('[data-testid="ds-checks"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ds-verdict"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('edits the profile and publishes the new segments', async () => {
    const { wrapper, published } = await mountWith(SAMPLE_INPUTS)

    await wrapper.get('[data-testid="ds-add-pause"]').trigger('click')
    await flushPromises()
    expect(published().inputs.seg).toMatch(/\|w:3:0:0\|w:1:0:0$/)

    await wrapper.get('[data-testid="ds-segment-16-remove"]').trigger('click')
    await flushPromises()
    expect(published().inputs.seg).toBe(SAMPLE_INPUTS.seg)

    wrapper.unmount()
  })

  it('opens saved inputs with their settings', async () => {
    const { wrapper, published } = await mountWith({
      ...SAMPLE_INPUTS,
      o: 'h',
      tr: 'b',
      st: '2000',
      d: '60',
      i: '5',
      mu: '0.05',
      seg: 'm:500:0:1:0|m:500:1:0:0|w:1:0:0|m:-1000:0:0.5:0',
    })

    expect(published().description).toBe('Horizontal axis, 140 kg, i = 5')
    expect(text(wrapper, 'ds-result-3-phase')).toBe('backward, accelerating')
    expect(wrapper.find('[data-testid="ds-check-brakeHolding"]').exists()).toBe(false)
    expect(warn).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('starts on a cleared form without saved inputs and lists what is missing', async () => {
    const { wrapper, published } = await mountWith(null)

    const missing = text(wrapper, 'ds-errors')
    expect(missing).toContain('Stroke (Axis) is missing.')
    expect(missing).toContain('Carriage mass (Load) is missing.')
    expect(missing).toContain('The motion profile needs at least one move.')
    expect(missing).not.toContain('NaN')
    expect(text(wrapper, 'ds-profile')).toContain('No segments yet.')
    expect(wrapper.find('[data-testid="ds-add-move"]').exists()).toBe(true)
    // The checks card stays, holding the missing list instead of a verdict.
    expect(wrapper.find('[data-testid="ds-checks"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ds-verdict"]').exists()).toBe(false)
    expect(published()).toMatchObject({
      inputs: EMPTY_INPUTS,
      title: 'New drive sizing',
      description: 'New drive sizing',
      results: { ok: false },
    })
    expect(warn).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('reopens a saved cleared form without a warning', async () => {
    const { wrapper, published } = await mountWith(EMPTY_INPUTS)

    expect(published().inputs).toEqual(EMPTY_INPUTS)
    expect(text(wrapper, 'ds-errors')).toContain('The motion profile needs at least one move.')
    expect(warn).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('resets invalid saved inputs and says so', async () => {
    const { wrapper, published } = await mountWith({ o: 'diagonal', st: '-5', seg: 'garbage' })

    expect(warn).toHaveBeenCalledExactlyOnceWith(
      '',
      'Some saved values are no longer valid for this tool and were reset. Check the inputs and save again.',
    )
    expect(published().inputs).toEqual(EMPTY_INPUTS)

    wrapper.unmount()
  })
})
