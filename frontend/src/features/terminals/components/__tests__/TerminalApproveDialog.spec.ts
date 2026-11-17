import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { AxiosError, AxiosHeaders } from 'axios'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { makePendingTerminal, makeScreen, makeTerminal } from './terminalFixtures'

import type { TerminalApproveRequest, TerminalResponse } from '../../types/terminalResponse'

const approveMock = vi.fn<(id: number, body: TerminalApproveRequest) => Promise<TerminalResponse>>()

vi.mock('../../api/terminalsApi', () => ({
  approveTerminal: (id: number, body: TerminalApproveRequest) => approveMock(id, body),
}))

import TerminalApproveDialog from '../TerminalApproveDialog.vue'

let wrapper: VueWrapper | null = null

// The dialog teleports to document.body, so inputs are reached through it.
async function openDialog() {
  wrapper = mountWithApp(TerminalApproveDialog, {
    attachTo: document.body,
    props: { visible: false, terminal: makePendingTerminal(), screens: [makeScreen()] },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function byTestId<T extends HTMLElement = HTMLElement>(id: string): T | null {
  return document.body.querySelector<T>(`[data-testid="${id}"]`)
}

async function type(id: string, value: string): Promise<void> {
  const input = byTestId<HTMLInputElement>(id)!
  input.value = value
  input.dispatchEvent(new Event('input'))
  await flushPromises()
}

async function submit(): Promise<void> {
  byTestId('terminal-approve-submit')!.click()
  await flushPromises()
}

function serverError(status: number, detail: string): AxiosError {
  const headers = new AxiosHeaders()
  return new AxiosError('failed', String(status), { headers }, null, {
    status,
    statusText: '',
    headers,
    config: { headers },
    data: { detail },
  })
}

describe('TerminalApproveDialog', () => {
  beforeEach(() => {
    approveMock.mockReset()
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('asks for the code and a name before calling the server', async () => {
    await openDialog()

    await submit()

    expect(approveMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain(i18n.global.t('terminals.approve.errors.codeRequired'))
    expect(document.body.textContent).toContain(i18n.global.t('terminals.approve.errors.nameRequired'))
  })

  it.each(['K7M2Q', 'K7M2QXA', 'K7M2Q0', 'K7M2QO', 'K7M2Q1', 'K7M2QI', 'K7M2QL'])(
    'refuses %s as a pairing code',
    async (code) => {
      await openDialog()
      await type('terminal-approve-code', code)
      await type('terminal-approve-name', 'Hall 1')

      await submit()

      expect(approveMock).not.toHaveBeenCalled()
      expect(byTestId('terminal-approve-code-error')!.textContent).toContain(
        i18n.global.t('terminals.approve.errors.codeFormat'),
      )
    },
  )

  it('sends the typed code in upper case without spaces or dashes', async () => {
    const approved = makeTerminal({ id: 2 })
    approveMock.mockResolvedValue(approved)
    const w = await openDialog()

    await type('terminal-approve-code', 'k7m-2qx')
    await type('terminal-approve-name', '  Hall 1 ')
    await submit()

    expect(approveMock).toHaveBeenCalledWith(2, {
      pairing_code: 'K7M2QX',
      name: 'Hall 1',
      mode: 'infoscreen',
      infoscreen_id: null,
    })
    expect(w.emitted('approved')).toEqual([[approved]])
    expect(w.emitted('update:visible')).toContainEqual([false])
  })

  it('sends the location trimmed when one is typed', async () => {
    approveMock.mockResolvedValue(makeTerminal({ id: 2 }))
    await openDialog()

    await type('terminal-approve-code', 'K7M2QX')
    await type('terminal-approve-name', 'Hall 1')
    await type('terminal-approve-location', '  Hall 2, north wall above gate 3 ')
    await submit()

    expect(approveMock).toHaveBeenCalledWith(2, {
      pairing_code: 'K7M2QX',
      name: 'Hall 1',
      mode: 'infoscreen',
      infoscreen_id: null,
      location: 'Hall 2, north wall above gate 3',
    })
  })

  it('stays open and shows the server message when the code does not match', async () => {
    approveMock.mockRejectedValue(serverError(422, 'The pairing code does not match.'))
    const w = await openDialog()

    await type('terminal-approve-code', 'K7M2QX')
    await type('terminal-approve-name', 'Hall 1')
    await submit()

    expect(document.body.textContent).toContain('The pairing code does not match.')
    expect(w.emitted('approved')).toBeUndefined()
  })

  it('offers the kiosk mode only as a disabled entry', async () => {
    const w = await openDialog()

    const select = w
      .findAllComponents({ name: 'Select' })
      .find((c) => c.attributes('data-testid') === 'terminal-approve-mode')!
    const options = select.props('options') as { value: string; disabled: boolean }[]

    expect(options).toEqual([
      expect.objectContaining({ value: 'infoscreen', disabled: false }),
      expect.objectContaining({ value: 'kiosk', disabled: true }),
    ])
  })
})
