import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import { dateToParam, setDisplayTimezone } from '@/core/utils/dates'
import type { CreatedToken } from '@/shared/types/tokenTypes'
import type { TerminalKeyCreateRequest } from '../../types/terminalKeyTypes'

const createTerminalKeyMock = vi.fn<(cmd: TerminalKeyCreateRequest) => Promise<CreatedToken>>()

vi.mock('../../api/apiKeysApi', () => ({
  createTerminalKey: (cmd: TerminalKeyCreateRequest) => createTerminalKeyMock(cmd),
}))

import TerminalKeyDialog from '../TerminalKeyDialog.vue'

function createdKey(): CreatedToken {
  return {
    id: 7,
    public_id: '22222222-2222-2222-2222-222222222222',
    name: 'Hall displays',
    token_prefix: 'gk_abcd',
    permissions: ['connect:terminals'],
    created: '2026-10-30T08:00:00Z',
    expires_at: null,
    is_expired: false,
    revoked_at: null,
    created_by_id: 1,
    kind: 'terminal',
    secret: 'gk_abcd_secret',
  } as CreatedToken
}

let wrapper: VueWrapper | null = null

// The dialog teleports to document.body, so the specs read the body and
// reach inputs through it rather than through the wrapper's own subtree.
async function openDialog(tokenMaxLifetimeDays = 365) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useHostStore().tokenMaxLifetimeDays = tokenMaxLifetimeDays
  wrapper = mountWithApp(TerminalKeyDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: false },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function byTestId<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.body.querySelector<T>(`[data-testid="${id}"]`)
}

async function typeName(value: string): Promise<void> {
  const input = byTestId<HTMLInputElement>('terminal-key-name')!
  input.value = value
  input.dispatchEvent(new Event('input'))
  await flushPromises()
}

async function clickSave(): Promise<void> {
  byTestId('terminal-key-save')!.click()
  await flushPromises()
}

describe('TerminalKeyDialog', () => {
  beforeEach(() => {
    createTerminalKeyMock.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  describe('in the tenant timezone', () => {
    beforeEach(() => {
      // 23:30 UTC on 6 August is already 08:30 on the 7th in Tokyo.
      vi.useFakeTimers({ toFake: ['Date'] })
      vi.setSystemTime(new Date('2026-08-06T23:30:00Z'))
      setDisplayTimezone('Asia/Tokyo')
    })

    afterEach(() => {
      vi.useRealTimers()
      setDisplayTimezone(null)
    })

    it('offers the days from tomorrow to the last one inside the lifetime cap', async () => {
      const w = await openDialog()
      const picker = w.findComponent({ name: 'DatePicker' })

      expect(dateToParam(picker.props('minDate') as Date)).toBe('2026-08-08')
      // 365 days on is 7 August 2027 in Tokyo; a key ending that day would
      // live the full cap, which the backend refuses.
      expect(dateToParam(picker.props('maxDate') as Date)).toBe('2027-08-06')
    })

    it('lets the key run until midnight of the picked day in the tenant timezone', async () => {
      createTerminalKeyMock.mockResolvedValue(createdKey())
      const w = await openDialog()

      await typeName('Hall displays')
      await w.findComponent({ name: 'DatePicker' }).vm.$emit('update:modelValue', new Date(2026, 8, 1))
      await clickSave()

      expect(createTerminalKeyMock).toHaveBeenCalledWith({
        name: 'Hall displays',
        expires_at: '2026-09-01T14:59:59.999Z',
      })
    })
  })

  it('offers no permission picker, only a name and an expiry', async () => {
    await openDialog()

    expect(byTestId('terminal-key-name')).not.toBeNull()
    expect(document.body.querySelectorAll('input[type="checkbox"]')).toHaveLength(0)
  })

  it('asks for a name before it calls the server', async () => {
    await openDialog()

    await clickSave()

    expect(createTerminalKeyMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(
      i18n.global.t('settings.apiKeys.terminalKey.nameRequired'),
    )
  })

  it('asks for an expiry before it calls the server while a cap is set', async () => {
    await openDialog()

    await typeName('Hall displays')
    await clickSave()

    expect(createTerminalKeyMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(
      i18n.global.t('settings.apiKeys.terminalKey.expiryRequired'),
    )
  })

  it('offers no last day when the cap is lifted', async () => {
    const w = await openDialog(0)

    expect(w.findComponent({ name: 'DatePicker' }).props('maxDate')).toBeUndefined()
  })

  it('creates the key without an expiry and shows it once as an env line', async () => {
    createTerminalKeyMock.mockResolvedValue(createdKey())
    const w = await openDialog(0)

    await typeName('  Hall displays ')
    await clickSave()

    expect(createTerminalKeyMock).toHaveBeenCalledWith({ name: 'Hall displays', expires_at: null })
    expect(byTestId<HTMLInputElement>('terminal-key-env-line')!.value).toBe(
      'IDENTITY__API_KEY=gk_abcd_secret',
    )
    expect(document.body.textContent).toContain(
      i18n.global.t('settings.apiKeys.terminalKey.secretWhere'),
    )
    expect(w.emitted('created')).toHaveLength(1)
  })

  it('forgets the key when it is opened again', async () => {
    createTerminalKeyMock.mockResolvedValue(createdKey())
    const w = await openDialog(0)
    await typeName('Hall displays')
    await clickSave()

    await w.setProps({ visible: false })
    await w.setProps({ visible: true })
    await flushPromises()

    expect(byTestId('terminal-key-env-line')).toBeNull()
    expect(byTestId('terminal-key-name')).not.toBeNull()
  })

  it('keeps the form open and shows the server message on an error', async () => {
    createTerminalKeyMock.mockRejectedValue(new Error('boom'))
    await openDialog(0)

    await typeName('Hall displays')
    await clickSave()

    expect(byTestId('terminal-key-env-line')).toBeNull()
    expect(document.body.textContent).toContain(
      i18n.global.t('settings.apiKeys.terminalKey.saveFailed'),
    )
  })
})
