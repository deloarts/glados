import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makeTerminal } from './terminalFixtures'

import type {
  TerminalDisplayOverrideRequest,
  TerminalResponse,
} from '../../types/terminalResponse'

const setMock = vi.fn<(id: number, body: TerminalDisplayOverrideRequest) => Promise<TerminalResponse>>()
const clearMock = vi.fn<(id: number) => Promise<TerminalResponse>>()

vi.mock('../../api/terminalsApi', () => ({
  setDisplayOverride: (id: number, body: TerminalDisplayOverrideRequest) => setMock(id, body),
  clearDisplayOverride: (id: number) => clearMock(id),
}))

import TerminalDisplayOverrideDialog from '../TerminalDisplayOverrideDialog.vue'

const NOW = Date.now()
const IN_TWO_HOURS = new Date(NOW + 2 * 60 * 60_000).toISOString()

let wrapper: VueWrapper | null = null

async function openDialog(terminal: TerminalResponse) {
  wrapper = mountWithApp(TerminalDisplayOverrideDialog, {
    attachTo: document.body,
    props: { visible: false, terminal, now: NOW },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function byTestId<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.body.querySelector<T>(`[data-testid="${id}"]`)
}

describe('TerminalDisplayOverrideDialog', () => {
  beforeEach(() => {
    setMock.mockReset()
    clearMock.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('switches a display that is on off until the next schedule change by default', async () => {
    const saved = makeTerminal({ display_power: 'off' })
    setMock.mockResolvedValue(saved)
    const w = await openDialog(
      makeTerminal({ display_power: 'on', display_power_changes_at: IN_TWO_HOURS }),
    )

    expect(byTestId('terminal-override-submit')!.textContent).toContain(
      i18n.global.t('terminals.override.switchOff'),
    )
    byTestId('terminal-override-submit')!.click()
    await flushPromises()

    expect(setMock).toHaveBeenCalledWith(1, { power: 'off', until: null })
    expect(w.emitted('saved')).toEqual([[saved, false]])
  })

  it('needs an end when the schedule changes nothing ahead', async () => {
    await openDialog(makeTerminal({ display_power: 'on', display_power_changes_at: null }))

    expect(byTestId<HTMLInputElement>('terminal-override-next')!.querySelector('input')!.disabled).toBe(
      true,
    )
    byTestId('terminal-override-submit')!.click()
    await flushPromises()

    expect(setMock).not.toHaveBeenCalled()
    expect(byTestId('terminal-override-until-error')!.textContent).toContain(
      i18n.global.t('terminals.override.errors.untilRequired'),
    )
  })

  it('hands a display switched by hand back to its schedule', async () => {
    const cleared = makeTerminal()
    clearMock.mockResolvedValue(cleared)
    const w = await openDialog(
      makeTerminal({
        display_power: 'off',
        display_override: 'off',
        display_override_until: IN_TWO_HOURS,
        display_power_changes_at: IN_TWO_HOURS,
      }),
    )

    expect(byTestId('terminal-override-submit')!.textContent).toContain(
      i18n.global.t('terminals.override.switchOn'),
    )
    byTestId('terminal-override-clear')!.click()
    await flushPromises()

    expect(clearMock).toHaveBeenCalledWith(1)
    expect(w.emitted('saved')).toEqual([[cleared, true]])
  })

  it('offers no clear without an override', async () => {
    await openDialog(makeTerminal())

    expect(byTestId('terminal-override-clear')).toBeNull()
  })
})
