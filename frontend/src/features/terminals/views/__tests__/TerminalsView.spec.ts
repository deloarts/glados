import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter, userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { i18n } from '@/core/i18n'
import type { PageResponse } from '@/core/api/types'
import type { TokenFilterParams, TokenSummary } from '@/shared/types/tokenTypes'
import {
  makeBroadcast,
  makePendingTerminal,
  makeScreen,
  makeTerminal,
} from '../../components/__tests__/terminalFixtures'

import type {
  TerminalBroadcastResponse,
  TerminalResponse,
  TerminalScreenOption,
} from '../../types/terminalResponse'
import type { TerminalBulkAction } from '../../api/terminalsApi'

const getTerminalsMock = vi.fn<() => Promise<TerminalResponse[]>>()
const getScreensMock = vi.fn<() => Promise<TerminalScreenOption[]>>()
const listKeysMock = vi.fn<(params?: TokenFilterParams) => Promise<PageResponse<TokenSummary>>>()
const getBroadcastsMock = vi.fn<() => Promise<TerminalBroadcastResponse[]>>()
const bulkMock = vi.fn<(action: TerminalBulkAction) => Promise<number>>()

vi.mock('../../api/terminalsApi', () => ({
  getTerminals: () => getTerminalsMock(),
  getScreenOptions: () => getScreensMock(),
  approveTerminal: vi.fn<() => Promise<unknown>>(),
  updateTerminal: vi.fn<() => Promise<unknown>>(),
  revokeTerminal: vi.fn<() => Promise<unknown>>(),
  reloadTerminal: vi.fn<() => Promise<unknown>>(),
  identifyTerminal: vi.fn<() => Promise<unknown>>(),
  deleteTerminal: vi.fn<() => Promise<unknown>>(),
  setDisplayOverride: vi.fn<() => Promise<unknown>>(),
  clearDisplayOverride: vi.fn<() => Promise<unknown>>(),
  runBulkTerminalAction: (action: TerminalBulkAction) => bulkMock(action),
}))

vi.mock('../../api/terminalBroadcastsApi', () => ({
  getActiveTerminalBroadcasts: () => getBroadcastsMock(),
  sendTerminalBroadcast: vi.fn<() => Promise<unknown>>(),
  endTerminalBroadcast: vi.fn<() => Promise<unknown>>(),
  countTerminalBroadcastReach: async () => 0,
}))

vi.mock('@/shared/api/createTokenApi', () => ({
  createTokenApi: () => ({ list: (params?: TokenFilterParams) => listKeysMock(params) }),
}))

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import TerminalsView from '../TerminalsView.vue'

function byTestId<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.body.querySelector<T>(`[data-testid="${id}"]`)
}

function menuItem(label: string): HTMLElement {
  const items = [...document.body.querySelectorAll<HTMLElement>('[role="menuitem"]')]
  const item = items.find((element) => element.textContent?.includes(label))
  if (!item) throw new Error(`No menu item ${label}`)
  return item.querySelector<HTMLElement>('a, div') ?? item
}

function keyPage(items: Partial<TokenSummary>[]): PageResponse<TokenSummary> {
  return { items: items as TokenSummary[], total: items.length, limit: 100, skip: 0 }
}

let wrapper: VueWrapper | null = null

async function mountView(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const router = makeTestRouter()
  wrapper = mountWithApp(TerminalsView, {
    attachTo: document.body,
    pinia,
    global: { plugins: [ConfirmationService, router] },
  })
  await flushPromises()
  return wrapper
}

describe('TerminalsView', () => {
  beforeEach(() => {
    getTerminalsMock.mockResolvedValue([makePendingTerminal(), makeTerminal()])
    getScreensMock.mockResolvedValue([makeScreen()])
    listKeysMock.mockResolvedValue(keyPage([]))
    getBroadcastsMock.mockResolvedValue([])
    bulkMock.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('keeps waiting terminals out of the table and counts them on the waiting button', async () => {
    const w = await mountView(['manage:terminals'])

    expect(w.get('[data-testid="enrolled-terminals"]').text()).toContain('Hall 1')
    expect(w.get('[data-testid="enrolled-terminals"]').text()).not.toContain('K7M2QX')
    expect(w.find('[data-testid="pending-terminals"]').exists()).toBe(false)
    expect(w.get('[data-testid="terminals-waiting"]').text()).toContain('1')
  })

  it('opens the waiting terminals in a dialog', async () => {
    const w = await mountView(['manage:terminals'])

    await w.get('[data-testid="terminals-waiting"]').trigger('click')
    await flushPromises()

    expect(byTestId('pending-terminals')!.textContent).toContain('K7M2QX')
  })

  it('shows no count on the waiting button while nothing waits, and an empty dialog', async () => {
    getTerminalsMock.mockResolvedValue([makeTerminal()])
    const w = await mountView(['manage:terminals'])

    const button = w.get('[data-testid="terminals-waiting"]')
    expect(button.text()).toBe(i18n.global.t('terminals.controls.waiting'))
    await button.trigger('click')
    await flushPromises()

    expect(byTestId('pending-terminals')!.textContent).toContain(
      i18n.global.t('terminals.pending.empty'),
    )
  })

  it('follows a search over the name and the location', async () => {
    getTerminalsMock.mockResolvedValue([
      makeTerminal({ id: 1, name: 'Hall 1', location: 'North wall' }),
      makeTerminal({ id: 3, name: 'Office', location: 'Reception' }),
    ])
    const w = await mountView(['manage:terminals'])

    expect(w.get('[data-testid="enrolled-terminals"]').text()).toContain('Office')
    const input = w
      .findAll('input')
      .find((i) => i.attributes('placeholder') === i18n.global.t('terminals.controls.search'))!
    await input.setValue('north')
    await flushPromises()

    const table = w.get('[data-testid="enrolled-terminals"]').text()
    expect(table).toContain('Hall 1')
    expect(table).not.toContain('Office')
  })

  it('reloads all approved terminals after a confirm that names the count', async () => {
    getTerminalsMock.mockResolvedValue([
      makePendingTerminal(),
      makeTerminal({ id: 1 }),
      makeTerminal({ id: 3, name: 'Office' }),
    ])
    bulkMock.mockResolvedValue(2)
    const w = await mountView(['manage:terminals'])

    await w.get('[data-testid="terminals-all"]').trigger('click')
    await flushPromises()
    menuItem(i18n.global.t('terminals.bulk.reload.item', { count: 2 })).click()
    await flushPromises()

    expect(byTestId('terminals-bulk-message')!.textContent).toContain(
      i18n.global.t('terminals.bulk.reload.message', { count: 2 }, 2),
    )
    expect(byTestId('terminals-bulk-typed')).toBeNull()
    byTestId('terminals-bulk-confirm')!.click()
    await flushPromises()

    expect(bulkMock).toHaveBeenCalledWith('reload')
  })

  it('deletes all terminals only after the count is typed', async () => {
    getTerminalsMock.mockResolvedValue([makePendingTerminal(), makeTerminal()])
    bulkMock.mockResolvedValue(2)
    const w = await mountView(['manage:terminals'])

    await w.get('[data-testid="terminals-all"]').trigger('click')
    await flushPromises()
    menuItem(i18n.global.t('terminals.bulk.delete.item', { count: 2 })).click()
    await flushPromises()

    const confirmButton = byTestId<HTMLButtonElement>('terminals-bulk-confirm')!
    expect(confirmButton.disabled).toBe(true)
    const typed = byTestId<HTMLInputElement>('terminals-bulk-typed')!
    typed.value = '3'
    typed.dispatchEvent(new Event('input'))
    await flushPromises()
    expect(confirmButton.disabled).toBe(true)
    typed.value = '2'
    typed.dispatchEvent(new Event('input'))
    await flushPromises()
    expect(confirmButton.disabled).toBe(false)

    confirmButton.click()
    await flushPromises()
    expect(bulkMock).toHaveBeenCalledWith('delete')
  })

  it('counts the active messages on the message button', async () => {
    getBroadcastsMock.mockResolvedValue([
      makeBroadcast(),
      makeBroadcast({ id: 12, show_until: '2020-01-01T00:00:00Z' }),
    ])
    const w = await mountView(['manage:terminals'])

    expect(w.get('[data-testid="terminals-message"]').text()).toContain('1')
  })

  it('asks the server for one usable terminal key only', async () => {
    await mountView(['manage:terminals', 'manage:api_keys'])

    expect(listKeysMock).toHaveBeenCalledExactlyOnceWith({
      kind: 'terminal',
      expiry: 'unexpired',
      limit: 1,
    })
  })

  it('points to the API keys tab when no usable terminal key exists', async () => {
    listKeysMock.mockResolvedValue(keyPage([]))
    const w = await mountView(['manage:terminals', 'manage:api_keys'])

    expect(w.get('[data-testid="terminals-key-hint"]').text()).toContain(
      i18n.global.t('terminals.keyHint.message'),
    )
  })

  it('shows no hint once a terminal key exists', async () => {
    listKeysMock.mockResolvedValue(
      keyPage([{ id: 2, kind: 'terminal', revoked_at: null, is_expired: false }]),
    )
    const w = await mountView(['manage:terminals', 'manage:api_keys'])

    expect(w.find('[data-testid="terminals-key-hint"]').exists()).toBe(false)
  })

  it('does not guess without manage:api_keys and has no key button', async () => {
    const w = await mountView(['manage:terminals'])

    expect(listKeysMock).not.toHaveBeenCalled()
    expect(w.find('[data-testid="terminals-key-hint"]').exists()).toBe(false)
    expect(w.find('[data-testid="terminals-api-keys"]').exists()).toBe(false)
  })

  it('shows the actions column only after Show Actions is switched on', async () => {
    const w = await mountView(['manage:terminals'])

    expect(w.find('[data-testid="terminal-reload"]').exists()).toBe(false)

    w.findComponent(ViewsBar).vm.$emit('toggle-show-actions')
    await flushPromises()
    expect(w.findComponent(ViewsBar).props('showActions')).toBe(true)
    expect(w.find('[data-testid="terminal-reload"]').exists()).toBe(true)
  })

  it('disables approving, the all terminals menu and messages without manage:terminals', async () => {
    const w = await mountView([])
    w.findComponent(ViewsBar).vm.$emit('toggle-show-actions')
    await flushPromises()

    expect(w.get('[data-testid="terminal-reload"]').attributes('disabled')).toBeDefined()
    expect(w.get('[data-testid="terminals-all"]').attributes('disabled')).toBeDefined()
    expect(w.get('[data-testid="terminals-message"]').attributes('disabled')).toBeDefined()
    expect(w.get('[data-testid="terminals-waiting"]').attributes('disabled')).toBeUndefined()

    await w.get('[data-testid="terminals-waiting"]').trigger('click')
    await flushPromises()
    expect(byTestId<HTMLButtonElement>('terminal-approve')!.disabled).toBe(true)
  })
})
