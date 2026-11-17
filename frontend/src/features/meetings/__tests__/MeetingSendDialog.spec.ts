import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeUserResponse } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import type { BuildMeetingNotes, BuiltMeetingNotes } from '../composables/useMeetingNotesPdf'
import type { MeetingFileResponse, MeetingRecipientSuggestionResponse, MeetingResponse } from '../types/meetingResponse'
import { makeCard, makeIssue, makeMeeting } from './meetingFixtures'

vi.mock('../api/meetingsApi', async (importOriginal) => {
  const actual = await importOriginal<Record<string, unknown>>()
  return Object.fromEntries(Object.keys(actual).map((name) => [name, vi.fn<(...args: unknown[]) => unknown>()]))
})

let granted = new Set<string>()
vi.mock('@/core/composables/usePermissions', () => ({
  usePermissions: () => ({ hasPermission: (permission: string) => granted.has(permission) }),
}))

import * as api from '../api/meetingsApi'
import MeetingSendDialog from '../components/MeetingSendDialog.vue'

const MB = 1024 * 1024
let wrapper: VueWrapper | null = null

function find(testId: string): HTMLElement | null {
  return document.body.querySelector<HTMLElement>(`[data-testid="${testId}"]`)
}

function file(id: number, name: string, size: number): MeetingFileResponse {
  return {
    id,
    public_id: `00000000-0000-0000-0000-0000000000${id}`,
    meeting_id: 21,
    card_id: null,
    category: 'pdf',
    file_name: name,
    mime_type: 'application/pdf',
    size_bytes: size,
    sha256: 'a',
    storage_path: `meetings/${id}`,
    stored_name: `${id}.pdf`,
    uploaded_by_user_id: 2,
    created: '2026-11-06T09:15:00Z',
    url: null,
  }
}

function suggestion(email: string, name: string | null, preselected: boolean, kind: string): MeetingRecipientSuggestionResponse {
  return {
    email,
    name,
    preselected,
    sources: [
      {
        kind: kind as MeetingRecipientSuggestionResponse['sources'][number]['kind'],
        attendee_id: kind === 'attendee' ? 7 : null,
        attendee_status: kind === 'attendee' ? 'distribution_only' : null,
        contact_id: kind === 'customer' ? null : 9,
        customer_id: kind === 'customer' ? 3 : null,
      },
    ],
  }
}

function apiError(status: number, detail: string): Error {
  return Object.assign(new Error(`HTTP ${status}`), { isAxiosError: true, response: { status, data: { detail } } })
}

let build: ReturnType<typeof vi.fn<BuildMeetingNotes>>

async function mountDialog(meeting: MeetingResponse = makeMeeting(), pdfBytes = MB / 2) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = makeUserResponse({ id: 1, full_name: 'Jonas Example', email: 'jonas@glados.example' })
  useHostStore().mailAttachmentLimitMb = 1
  build = vi.fn<BuildMeetingNotes>(async (request) => {
    const built: BuiltMeetingNotes = {
      pdf: new Blob([new Uint8Array(pdfBytes)], { type: 'application/pdf' }),
      fileName: 'MTG-26-0021-Design-Review-Gripper_2026-11-10.pdf',
      locale: request.locale,
      options: {
        include_todos: request.options.include_todos ?? true,
        include_internal: request.options.include_internal ?? false,
        list_documents: true,
      },
      label: request.label,
      cards: [{ id: 1, edit_version: 3 }],
    }
    return built
  })
  wrapper = mountWithApp(MeetingSendDialog, {
    pinia,
    attachTo: document.body,
    props: { visible: true, meeting, issue: makeIssue({ issue_number: 1, send: { issue_number: 2, draft: false, revision: '2' } }), build },
  })
  await flushPromises()
  return wrapper
}

function chips(field: 'to' | 'cc'): string[] {
  return [...(find(`meeting-send-${field}`)?.querySelectorAll<HTMLElement>('[data-testid^="recipient-chip-"]') ?? [])].map(
    (chip) => chip.dataset.testid?.replace('recipient-chip-', '') ?? '',
  )
}

beforeEach(() => {
  granted = new Set(['write:meetings', 'send:mail'])
  vi.mocked(api.getMeetingRecipientSuggestions).mockResolvedValue([
    suggestion('thomas@muster.example', 'Thomas Muster', true, 'project_contact'),
    suggestion('office@inspect.example', 'Inspector Office', true, 'attendee'),
    suggestion('office@muster.example', null, false, 'customer'),
  ])
  vi.mocked(api.getMeetingNotesMailTemplate).mockResolvedValue({
    kind: 'meeting_notes',
    language: 'enGB',
    configured: true,
    subject: 'Minutes {{ meeting_number }}: {{ meeting_name }}',
    body: '<p>Notes of {{ meeting_name }}, issue {{ issue }}, by {{ user_full_name }}. {{ not_a_variable }}</p>',
  })
  vi.mocked(api.sendMeetingNotes).mockResolvedValue({} as Awaited<ReturnType<typeof api.sendMeetingNotes>>)
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
})

describe('MeetingSendDialog', () => {
  it('puts the pre-selected suggestions in To and the sender in CC', async () => {
    await mountDialog()

    expect(chips('to')).toEqual(['thomas@muster.example', 'office@inspect.example'])
    expect(chips('cc')).toEqual(['jonas@glados.example'])
    const suggestions = find('meeting-send-suggestions')?.textContent ?? ''
    expect(suggestions).toContain('Thomas Muster')
    expect(suggestions).toContain('Project contact')
    expect(suggestions).toContain('Attendee, Distribution')
    expect(suggestions).toContain('Customer e-mail')
  })

  it('adds and removes a suggestion with its checkbox', async () => {
    await mountDialog()

    const box = find('meeting-send-suggestion-office@muster.example')?.querySelector('input')
    box?.click()
    await flushPromises()
    expect(chips('to')).toContain('office@muster.example')

    find('meeting-send-suggestion-thomas@muster.example')?.querySelector('input')?.click()
    await flushPromises()
    expect(chips('to')).not.toContain('thomas@muster.example')
  })

  it('fills the template, escaping the values in the text but not in the subject', async () => {
    await mountDialog(makeMeeting({ name: 'Gripper & <Cups>' }))

    expect((find('meeting-send-subject') as HTMLInputElement).value).toBe('Minutes MTG-26-0021: Gripper & <Cups>')
    const body = find('meeting-send-body')?.innerHTML ?? ''
    expect(body).toContain('Notes of Gripper &amp; &lt;Cups&gt;, issue 2, by Jonas Example.')
    expect(body).not.toContain('<Cups>')
    // A placeholder without a value stays, so the user sees it.
    expect(body).toContain('{{ not_a_variable }}')
  })

  it('builds the PDF with the next issue and sends it with the recipients', async () => {
    await mountDialog()

    expect(build).toHaveBeenCalledWith(expect.objectContaining({ label: { issue_number: 2, draft: false, revision: '2' } }))
    find('meeting-send-submit')?.click()
    await flushPromises()

    expect(api.sendMeetingNotes).toHaveBeenCalledWith(
      21,
      expect.objectContaining({ issueNumber: 2, cards: [{ id: 1, edit_version: 3 }], language: 'enGB' }),
      expect.objectContaining({
        to: ['thomas@muster.example', 'office@inspect.example'],
        cc: ['jonas@glados.example'],
        subject: 'Minutes MTG-26-0021: Design Review Gripper',
        attachFileIds: [],
      }),
    )
    expect(wrapper?.emitted('sent')).toHaveLength(1)
  })

  it('builds the PDF again with the internal cards when they are included', async () => {
    await mountDialog(makeMeeting({ cards: [makeCard(), makeCard({ id: 2, internal: true })] }))

    expect(find('meeting-send-dialog')?.textContent).toContain('(1 left out)')
    find('meeting-send-include_internal')?.querySelector('input')?.click()
    await flushPromises()

    expect(build).toHaveBeenLastCalledWith(expect.objectContaining({ options: expect.objectContaining({ include_internal: true }) }))
  })

  it('attaches the documents that fit under the limit and names the ones left out', async () => {
    const meeting = makeMeeting({
      files: [file(41, 'layout.pdf', 0.3 * MB), file(42, 'drawing.pdf', 0.4 * MB), file(43, 'photo.pdf', 0.1 * MB)],
    })
    await mountDialog(meeting, MB / 2)

    find('meeting-send-documents')?.querySelector('input')?.click()
    await flushPromises()

    expect(find('meeting-send-attached')?.textContent).toContain('layout.pdf')
    expect(find('meeting-send-attached')?.textContent).toContain('photo.pdf')
    expect(find('meeting-send-left-out')?.textContent).toContain('drawing.pdf (0.4 MB)')
    find('meeting-send-submit')?.click()
    await flushPromises()
    expect(api.sendMeetingNotes).toHaveBeenCalledWith(21, expect.anything(), expect.objectContaining({ attachFileIds: [41, 43] }))
  })

  it.each([
    [413, 'The attachments come to 12.0 MB, more than the 10 MB a mail may carry. These do not fit: drawing.pdf (4.0 MB).'],
    [502, 'The mail server refused the mail: 550 mailbox unavailable.'],
  ])('shows the %s error of the server in the footer and stays open', async (status, detail) => {
    vi.mocked(api.sendMeetingNotes).mockRejectedValue(apiError(status, detail))
    await mountDialog()

    find('meeting-send-submit')?.click()
    await flushPromises()

    expect(find('meeting-send-error')?.textContent).toContain(detail)
    expect(wrapper?.emitted('sent')).toBeUndefined()
    expect(find('meeting-send-dialog')).not.toBeNull()
  })

  it('names the changed card on a 409 and has the page read the notes again', async () => {
    vi.mocked(api.sendMeetingNotes).mockRejectedValue(
      apiError(409, "Card 'Vacuum gripper' (#1) was changed since the notes were built; build them again."),
    )
    await mountDialog()

    find('meeting-send-submit')?.click()
    await flushPromises()

    expect(find('meeting-send-error')?.textContent).toContain("Card 'Vacuum gripper' (#1) was changed")
    expect(wrapper?.emitted('outdated')).toHaveLength(1)
  })

  it('asks for a recipient before it sends', async () => {
    vi.mocked(api.getMeetingRecipientSuggestions).mockResolvedValue([])
    await mountDialog()

    find('meeting-send-submit')?.click()
    await flushPromises()

    expect(find('meeting-send-error')?.textContent).toContain('Add at least one recipient.')
    expect(api.sendMeetingNotes).not.toHaveBeenCalled()
  })

  it('keeps Send visible but disabled without send:mail', async () => {
    granted = new Set(['write:meetings'])
    await mountDialog()

    expect(find('meeting-send-submit')?.hasAttribute('disabled')).toBe(true)
  })
})
