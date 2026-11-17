import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeScreen, makeTerminal } from './terminalFixtures'

import type { TerminalResponse, TerminalUpdateRequest } from '../../types/terminalResponse'

const updateMock = vi.fn<(id: number, body: TerminalUpdateRequest) => Promise<TerminalResponse>>()

vi.mock('../../api/terminalsApi', () => ({
  updateTerminal: (id: number, body: TerminalUpdateRequest) => updateMock(id, body),
}))

import TerminalEditDialog from '../TerminalEditDialog.vue'

let wrapper: VueWrapper | null = null

async function openDialog(terminal: TerminalResponse, field: 'name' | 'screen') {
  wrapper = mountWithApp(TerminalEditDialog, {
    attachTo: document.body,
    props: { visible: false, terminal, field, screens: [makeScreen()] },
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

async function save(): Promise<void> {
  byTestId('terminal-edit-save')!.click()
  await flushPromises()
}

describe('TerminalEditDialog', () => {
  beforeEach(() => {
    updateMock.mockReset()
    updateMock.mockResolvedValue(makeTerminal())
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    document.body.innerHTML = ''
  })

  it('edits the name and the location together', async () => {
    await openDialog(makeTerminal({ location: 'North wall' }), 'name')

    expect(byTestId<HTMLInputElement>('terminal-edit-location')!.value).toBe('North wall')
    await type('terminal-edit-location', ' Hall 2, gate 3 ')
    await save()

    expect(updateMock).toHaveBeenCalledWith(1, { name: 'Hall 1', location: 'Hall 2, gate 3' })
  })

  it('clears the location when the field is emptied', async () => {
    await openDialog(makeTerminal({ location: 'North wall' }), 'name')

    await type('terminal-edit-location', '  ')
    await save()

    expect(updateMock).toHaveBeenCalledWith(1, { name: 'Hall 1', location: null })
  })

  it('changes only the screen from the screen action', async () => {
    await openDialog(makeTerminal(), 'screen')

    expect(byTestId('terminal-edit-location')).toBeNull()
    await save()

    expect(updateMock).toHaveBeenCalledWith(1, { infoscreen_id: 3 })
  })
})
