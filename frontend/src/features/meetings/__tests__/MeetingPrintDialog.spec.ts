import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { BuildMeetingNotes } from '../composables/useMeetingNotesPdf'
import { makeIssue, makeMeeting } from './meetingFixtures'

vi.mock('../api/meetingsApi', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return Object.fromEntries(Object.keys(actual).map((name) => [name, vi.fn<(...args: unknown[]) => unknown>()]))
})

const downloadPdf = vi.fn<(blob: Blob, name: string) => void>()
vi.mock('@/shared/reports', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  downloadPdf: (blob: Blob, name: string) => downloadPdf(blob, name),
  getDocumentPrinters: async () => [],
}))

let granted = new Set<string>()
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => granted.has(permission) }),
}))

import * as api from '../api/meetingsApi'
import MeetingPrintDialog from '../components/MeetingPrintDialog.vue'

let wrapper: VueWrapper | null = null

function find(testId: string): HTMLElement | null {
  return document.body.querySelector<HTMLElement>(`[data-testid="${testId}"]`)
}

const build = vi.fn<BuildMeetingNotes>(async (request) => ({
  pdf: new Blob(['%PDF-1.7'], { type: 'application/pdf' }),
  fileName: 'MTG-26-0021.pdf',
  locale: request.locale,
  options: { include_todos: true, include_internal: false, list_documents: true },
  label: request.label,
  cards: [{ id: 1, edit_version: 3 }],
}))

async function mountDialog() {
  wrapper = mountWithApp(MeetingPrintDialog, {
    attachTo: document.body,
    props: {
      visible: true,
      meeting: makeMeeting(),
      issue: makeIssue({
        issue_number: 2,
        last_sent_at: '2026-11-06T10:00:00Z',
        print: { issue_number: 2, draft: true, revision: '2-draft' },
        send: { issue_number: 3, draft: false, revision: '3' },
      }),
      build,
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  granted = new Set()
  build.mockClear()
  downloadPdf.mockReset()
  vi.mocked(api.downloadMeetingNotes).mockReset()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
})

describe('MeetingPrintDialog', () => {
  it('names the issue a print carries now', async () => {
    await mountDialog()

    expect(find('meeting-print-issue')?.textContent).toContain('Draft after issue 2')
    // Printing needs print:documents; downloading does not.
    expect(find('meeting-print-submit')?.hasAttribute('disabled')).toBe(true)
  })

  it('journals the download with the issue it carries before it saves the PDF', async () => {
    vi.mocked(api.downloadMeetingNotes).mockResolvedValue({} as Awaited<ReturnType<typeof api.downloadMeetingNotes>>)
    const view = await mountDialog()

    find('meeting-print-download')?.click()
    await flushPromises()

    expect(build).toHaveBeenCalledWith(
      expect.objectContaining({ label: { issue_number: 2, draft: true, revision: '2-draft' }, issuedOn: null }),
    )
    expect(api.downloadMeetingNotes).toHaveBeenCalledWith(
      21,
      expect.objectContaining({ issueNumber: 2, cards: [{ id: 1, edit_version: 3 }] }),
      true,
    )
    expect(downloadPdf).toHaveBeenCalledWith(expect.any(Blob), 'MTG-26-0021.pdf')
    expect(view.emitted('done')).toHaveLength(1)
  })

  it('names the changed card, has the page read the notes again and saves nothing', async () => {
    vi.mocked(api.downloadMeetingNotes).mockRejectedValue(
      Object.assign(new Error('HTTP 409'), {
        isAxiosError: true,
        response: { status: 409, data: { detail: "Card 'Vacuum gripper' (#1) was changed since the notes were built; build them again." } },
      }),
    )
    const view = await mountDialog()

    find('meeting-print-download')?.click()
    await flushPromises()

    expect(find('meeting-print-error')?.textContent).toContain("Card 'Vacuum gripper' (#1) was changed")
    expect(view.emitted('outdated')).toHaveLength(1)
    expect(downloadPdf).not.toHaveBeenCalled()
  })
})
