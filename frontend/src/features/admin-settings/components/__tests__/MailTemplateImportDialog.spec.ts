import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { planMailTemplateImport } from '../../utils/mailTemplateFile'

const updateMock = vi.fn<(kind: string, cmd: unknown) => Promise<unknown>>()
const getMock = vi.fn<() => Promise<unknown>>()

vi.mock('../../api/updateMailTemplates', () => ({
  updateMailTemplates: (kind: string, cmd: unknown) => updateMock(kind, cmd),
}))
vi.mock('../../api/getMailTemplates', () => ({ getMailTemplates: () => getMock() }))

import MailTemplateImportDialog from '../MailTemplateImportDialog.vue'

// The Dialog teleports its content to document.body, so the DOM is read
// from there, see MailTemplateEditorDialog.spec.ts.

function rows() {
  return planMailTemplateImport(
    [
      { name: 'welcome.enGB.html', text: '<title>Hi</title>\n<p>en</p>' },
      { name: 'welcome.deAT.html', text: '<title>Hallo</title>\n<p>de</p>' },
      { name: 'test_mail.enGB.html', text: '<title>Test</title>\n<p>t</p>' },
      { name: 'readme.html', text: '' },
    ],
    ['welcome', 'test_mail'],
    ['enGB', 'deAT'],
    () => false,
  )
}

async function mountDialog() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(['write:settings'])
  const wrapper = mountWithApp(MailTemplateImportDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: true, rows: rows() },
  })
  await flushPromises()
  return wrapper
}

function confirmButton(): HTMLButtonElement {
  return document.body.querySelector('[data-testid="mail-import-confirm"]') as HTMLButtonElement
}

describe('MailTemplateImportDialog', () => {
  beforeEach(() => {
    updateMock.mockReset()
    getMock.mockReset()
    getMock.mockResolvedValue([])
    document.body.innerHTML = ''
  })

  it('lists every picked file and counts the importable ones', async () => {
    const wrapper = await mountDialog()

    expect(document.body.querySelectorAll('[data-testid="mail-import-rows"] tbody tr')).toHaveLength(4)
    expect(confirmButton().textContent).toContain('3')

    wrapper.unmount()
  })

  it('saves once per kind with the files of that kind, then fetches every template again', async () => {
    updateMock.mockImplementation(async (kind) => ({ kind, entries: [] }))
    const wrapper = await mountDialog()

    confirmButton().click()
    await flushPromises()

    expect(updateMock).toHaveBeenCalledTimes(2)
    expect(updateMock).toHaveBeenCalledWith('welcome', {
      entries: [
        { language: 'enGB', subject: 'Hi', body: '<p>en</p>' },
        { language: 'deAT', subject: 'Hallo', body: '<p>de</p>' },
      ],
    })
    expect(updateMock).toHaveBeenCalledWith('test_mail', {
      entries: [{ language: 'enGB', subject: 'Test', body: '<p>t</p>' }],
    })
    expect(getMock).toHaveBeenCalled()
    expect(wrapper.emitted('update:visible')?.at(-1)).toEqual([false])

    wrapper.unmount()
  })

  it('stops at a failed save and stays open', async () => {
    updateMock.mockRejectedValue(new Error('boom'))
    const wrapper = await mountDialog()

    confirmButton().click()
    await flushPromises()

    expect(updateMock).toHaveBeenCalledTimes(1)
    expect(getMock).toHaveBeenCalled()
    expect(wrapper.emitted('update:visible')).toBeUndefined()

    wrapper.unmount()
  })
})
