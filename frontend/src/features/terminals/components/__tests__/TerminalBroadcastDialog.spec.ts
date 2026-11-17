import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makeBroadcast, makeScreen, makeTerminal } from './terminalFixtures'

import type {
  TerminalBroadcastAudienceRequest,
  TerminalBroadcastCreateRequest,
  TerminalBroadcastResponse,
} from '../../types/terminalResponse'

const sendMock = vi.fn<(body: TerminalBroadcastCreateRequest) => Promise<TerminalBroadcastResponse>>()
const endMock = vi.fn<(id: number) => Promise<TerminalBroadcastResponse>>()
const reachMock = vi.fn<(body: TerminalBroadcastAudienceRequest) => Promise<number>>()

vi.mock('../../api/terminalBroadcastsApi', () => ({
  sendTerminalBroadcast: (body: TerminalBroadcastCreateRequest) => sendMock(body),
  endTerminalBroadcast: (id: number) => endMock(id),
  countTerminalBroadcastReach: (body: TerminalBroadcastAudienceRequest) => reachMock(body),
}))

import TerminalBroadcastDialog from '../TerminalBroadcastDialog.vue'

const MISSING = 'This needs the permission Manage Terminals.'

let wrapper: VueWrapper | null = null

async function openDialog(
  broadcasts: TerminalBroadcastResponse[] = [],
  canManage = true,
) {
  wrapper = mountWithApp(TerminalBroadcastDialog, {
    attachTo: document.body,
    props: {
      visible: false,
      broadcasts,
      terminals: [makeTerminal({ id: 1, name: 'Hall 1' }), makeTerminal({ id: 5, name: 'Office' })],
      screens: [makeScreen({ id: 3, name: 'Hall board' })],
      canManage,
      missingHint: canManage ? '' : MISSING,
    },
  })
  await wrapper.setProps({ visible: true })
  await settle()
  return wrapper
}

// The reach count waits for the audience to settle before asking the server.
async function settle(): Promise<void> {
  await vi.advanceTimersByTimeAsync(400)
  await flushPromises()
}

function byTestId<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.body.querySelector<T>(`[data-testid="${id}"]`)
}

async function type(id: string, value: string): Promise<void> {
  const input = byTestId<HTMLTextAreaElement>(id)!
  input.value = value
  input.dispatchEvent(new Event('input'))
  await flushPromises()
}

function select(name: string, testId: string) {
  return wrapper!
    .findAllComponents({ name })
    .find((c) => c.attributes('data-testid') === testId)!
}

describe('TerminalBroadcastDialog', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    sendMock.mockReset()
    endMock.mockReset()
    reachMock.mockReset()
    reachMock.mockResolvedValue(4)
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
    vi.useRealTimers()
  })

  it('sends a message to all terminals, shown for an hour by default', async () => {
    const sent = makeBroadcast()
    sendMock.mockResolvedValue(sent)
    const w = await openDialog()

    expect(reachMock).toHaveBeenLastCalledWith({ all_terminals: true })
    expect(byTestId('terminal-broadcast-reach')!.textContent).toContain(
      i18n.global.t('terminals.broadcast.reachNow', { count: 4 }, 4),
    )
    await type('terminal-broadcast-text', '  Fire drill at **10:00** ')
    byTestId('terminal-broadcast-send')!.click()
    await flushPromises()

    const body = sendMock.mock.calls[0]![0]
    expect(body).toMatchObject({
      text: 'Fire drill at **10:00**',
      severity: 'info',
      style: 'banner',
      all_terminals: true,
    })
    const minutes = (Date.parse(body.show_until) - Date.now()) / 60_000
    expect(minutes).toBeGreaterThan(58)
    expect(minutes).toBeLessThanOrEqual(60)
    expect(w.emitted('sent')).toEqual([[sent]])
  })

  it('counts the reach of a pick of terminals and infoscreens', async () => {
    await openDialog()

    await select('SelectButton', 'terminal-broadcast-audience').vm.$emit('update:modelValue', 'both')
    await settle()
    await select('MultiSelect', 'terminal-broadcast-terminals').vm.$emit('update:modelValue', [5])
    await select('MultiSelect', 'terminal-broadcast-screens').vm.$emit('update:modelValue', [3])
    await settle()

    expect(reachMock).toHaveBeenLastCalledWith({
      all_terminals: false,
      terminal_ids: [5],
      infoscreen_ids: [3],
    })
  })

  it('asks for a text and a pick before sending', async () => {
    await openDialog()
    await select('SelectButton', 'terminal-broadcast-audience').vm.$emit('update:modelValue', 'terminals')
    await settle()

    byTestId('terminal-broadcast-send')!.click()
    await flushPromises()

    expect(sendMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(i18n.global.t('terminals.broadcast.errors.textRequired'))
    expect(document.body.textContent).toContain(i18n.global.t('terminals.broadcast.errors.audienceEmpty'))
  })

  it('sets the end from a quick pick', async () => {
    sendMock.mockResolvedValue(makeBroadcast())
    await openDialog()
    await type('terminal-broadcast-text', 'Lunch is ready')

    byTestId('terminal-broadcast-pick-quarterHour')!.click()
    await flushPromises()
    byTestId('terminal-broadcast-send')!.click()
    await flushPromises()

    const minutes = (Date.parse(sendMock.mock.calls[0]![0].show_until) - Date.now()) / 60_000
    expect(minutes).toBeGreaterThan(13)
    expect(minutes).toBeLessThanOrEqual(15)
  })

  it('lists the active messages with their audience, and ends one now', async () => {
    const broadcast = makeBroadcast({ all_terminals: false, terminal_ids: [1], infoscreen_ids: [3] })
    const ended = { ...broadcast, ended_at: new Date().toISOString() }
    endMock.mockResolvedValue(ended)
    const w = await openDialog([broadcast])

    const item = byTestId('terminal-broadcast')!
    expect(item.textContent).toContain('Fire drill at **10:00**')
    expect(item.textContent).toContain(i18n.global.t('terminals.broadcast.terminalCount', { count: 1 }, 1))
    expect(item.textContent).toContain(i18n.global.t('terminals.broadcast.screenCount', { count: 1 }, 1))
    byTestId('terminal-broadcast-end')!.click()
    await flushPromises()

    expect(endMock).toHaveBeenCalledWith(11)
    expect(w.emitted('ended')).toEqual([[ended]])
  })

  it('shows the active messages but disables sending and ending without manage:terminals', async () => {
    await openDialog([makeBroadcast()], false)

    expect(byTestId<HTMLButtonElement>('terminal-broadcast-send')!.disabled).toBe(true)
    expect(byTestId<HTMLButtonElement>('terminal-broadcast-end')!.disabled).toBe(true)
  })
})
