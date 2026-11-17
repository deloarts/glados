import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import ThreadsTab from '../ThreadsTab.vue'
import { toolTestHost } from '../../composables/useToolState'

// Starts the tool as the tools view does: on a saved calculation's inputs,
// or on its defaults when there are none.
async function mountAt(inputs: Record<string, string> | null = null) {
  const host = toolTestHost(inputs)
  const wrapper = mountWithApp(ThreadsTab, { global: { provide: host.provide } })
  await flushPromises()
  return { state: host.state, wrapper }
}

type Wrapper = Awaited<ReturnType<typeof mountAt>>['wrapper']

function text(wrapper: Wrapper, testid: string): string {
  return wrapper.get(`[data-testid="${testid}"]`).text()
}

async function showSection(wrapper: Wrapper, label: string) {
  const button = wrapper
    .get('[data-testid="th-section"]')
    .findAll('button')
    .find((b) => b.text() === label)
  if (!button) throw new Error(`No section button "${label}"`)
  await button.trigger('click')
  await flushPromises()
}

async function selectThread(wrapper: Wrapper, code: string) {
  const select = wrapper.findAllComponents({ name: 'Select' }).find((c) => c.attributes('data-testid') === 'th-thread')
  if (!select) throw new Error('No thread select')
  select.vm.$emit('update:modelValue', code)
  await flushPromises()
}

async function selectClass(wrapper: Wrapper, cls: string) {
  const button = wrapper
    .get('[data-testid="th-class"]')
    .findAll('button')
    .find((b) => b.text() === cls)
  if (!button) throw new Error(`No class button "${cls}"`)
  await button.trigger('click')
  await flushPromises()
}

// The label of the row a reference table highlights, or null when it
// highlights none.
function highlightedRow(wrapper: Wrapper, table: string): string | null {
  const row = wrapper.find(`[data-testid="ref-row-${table}"]`)
  if (!row.exists()) return null
  expect(row.attributes('aria-current')).toBe('true')
  return row.get('th').text()
}

const HOLE_TABLES = ['clearance', 'capScrew', 'hex', 'countersinkSlotted', 'countersinkSocket']

describe('ThreadsTab', () => {
  it('starts with M8 in class 8.8 and publishes it as its inputs', async () => {
    const { state, wrapper } = await mountAt()

    expect(text(wrapper, 'th-designation')).toBe('M8')
    expect(text(wrapper, 'th-pitch')).toBe('1.25 mm')
    expect(text(wrapper, 'th-pitchDiameter')).toBe('7.188 mm')
    expect(text(wrapper, 'th-tapDrill')).toBe('Ø 6.8 mm')
    expect(text(wrapper, 'th-widthAcrossFlats')).toBe('13 mm')
    expect(text(wrapper, 'th-clearanceMedium')).toBe('Ø 9 mm')
    expect(text(wrapper, 'th-counterboreCapScrew')).toBe('Ø 15 × 8.6 mm')
    expect(text(wrapper, 'th-counterboreHex')).toBe('Ø 24 × 6.1 mm')
    expect(text(wrapper, 'th-countersinkSocket')).toBe('Ø 18.3 mm, 90°')
    expect(text(wrapper, 'th-countersinkSlotted')).toBe('Ø 17.3 … 17.6 mm, 90°')
    expect(text(wrapper, 'th-torque')).toBe('27.3 Nm')
    expect(text(wrapper, 'th-preload')).toBe('18.1 kN')
    expect(state.value?.inputs).toEqual({ thread: 'M8', class: '8.8' })

    wrapper.unmount()
  })

  it('takes the torque of the chosen property class and highlights it in the table', async () => {
    const { wrapper } = await mountAt({ thread: 'M16', class: '12.9' })

    expect(text(wrapper, 'th-torque')).toBe('395 Nm')
    expect(text(wrapper, 'ref-row-coarse')).toContain('M16')
    expect(wrapper.find('[data-testid="ref-table-torque"]').exists()).toBe(false)

    await showSection(wrapper, 'Tightening')

    expect(text(wrapper, 'ref-hit-torque')).toBe('395')
    expect(wrapper.find('[data-testid="ref-table-coarse"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('highlights the selected thread in every table and follows a new selection', async () => {
    const { wrapper } = await mountAt({ thread: 'M10' })

    expect(highlightedRow(wrapper, 'coarse')).toBe('M10')
    expect(highlightedRow(wrapper, 'fine')).toBeNull()
    expect(highlightedRow(wrapper, 'limits')).toBe('M10')
    expect(wrapper.get('[data-testid="th-details"]').findAll('tr[aria-current="true"]')).toHaveLength(2)

    await selectThread(wrapper, 'M10x1')

    expect(highlightedRow(wrapper, 'coarse')).toBeNull()
    expect(highlightedRow(wrapper, 'fine')).toBe('M10 × 1')
    expect(highlightedRow(wrapper, 'limits')).toBe('M10 × 1')

    await showSection(wrapper, 'Holes and counterbores')

    for (const table of HOLE_TABLES) expect(highlightedRow(wrapper, table)).toBe('M10')

    await selectThread(wrapper, 'M12')

    expect(highlightedRow(wrapper, 'clearance')).toBe('M12')
    expect(highlightedRow(wrapper, 'hex')).toBe('M12')

    wrapper.unmount()
  })

  it('highlights the thread row and the property class column of the tightening tables', async () => {
    const { wrapper } = await mountAt({ thread: 'M12', class: '8.8' })
    await showSection(wrapper, 'Tightening')

    expect(highlightedRow(wrapper, 'torque')).toBe('M12')
    expect(highlightedRow(wrapper, 'preload')).toBe('M12')
    expect(text(wrapper, 'ref-hit-torque')).toBe('93')

    await selectClass(wrapper, '10.9')

    expect(text(wrapper, 'ref-hit-torque')).toBe('137')
    expect(text(wrapper, 'ref-hit-preload')).toBe('61.5')

    // The tightening values hold for coarse threads only, so a fine thread
    // of the same size marks no row.
    await selectThread(wrapper, 'M12x1.5')

    expect(highlightedRow(wrapper, 'torque')).toBeNull()

    wrapper.unmount()
  })

  it('shows a fine thread with its tap drill and no tightening values', async () => {
    const { wrapper } = await mountAt({ thread: 'M12x1.5', class: '10.9' })

    expect(text(wrapper, 'th-designation')).toBe('M12 × 1.5')
    expect(text(wrapper, 'th-tapDrill')).toBe('Ø 10.5 mm')
    expect(text(wrapper, 'th-card-tightening')).toContain('only available for coarse threads')
    expect(text(wrapper, 'ref-row-limits')).toContain('11.026')

    wrapper.unmount()
  })

  it('says when a size has no counterbore', async () => {
    const { wrapper } = await mountAt({ thread: 'M1' })

    expect(text(wrapper, 'th-counterboreCapScrew')).toBe('Not listed for this size')
    expect(text(wrapper, 'th-clearanceMedium')).toBe('Ø 1.2 mm')

    await showSection(wrapper, 'Holes and counterbores')

    expect(text(wrapper, 'ref-row-clearance')).toContain('1.2')
    expect(wrapper.find('[data-testid="ref-row-capScrew"]').exists()).toBe(false)

    wrapper.unmount()
  })

  it('falls back to the defaults for invalid parts of saved inputs', async () => {
    const { state, wrapper } = await mountAt({ thread: 'M9', class: '9.9' })

    expect(text(wrapper, 'th-designation')).toBe('M8')
    expect(state.value?.inputs).toEqual({ thread: 'M8', class: '8.8' })

    wrapper.unmount()
  })
})
