import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { i18n } from '@/core/i18n'
import { setDisplayTimezone } from '@/core/utils/dates'
import { composeReport, createReportContext } from '@/shared/reports'
import type { ReportBranding, ReportContent } from '@/shared/reports'
import { reportTexts } from '@/test-utils/reportTexts'
import { isPdfA2b, renderPdfForTest } from '@/test-utils/renderPdfForTest'
import type { MeetingResponse } from '../types/meetingResponse'
import {
  MEETING_NOTES_OPTIONS,
  includedCards,
  issueLabelText,
  meetingNotesReportSpec,
} from '../utils/meetingNotesReport'
import type { MeetingNotesReportInput } from '../utils/meetingNotesReport'
import { ANNA, makeCard, makeMeeting, makeTodo } from './meetingFixtures'

const PIXEL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='

const BRANDING: ReportBranding = {
  appName: 'Glados',
  companyName: 'Example Ltd',
  companyLogoUrl: null,
  domain: 'https://glados.example',
  exportedBy: 'Jonas Example',
}

function meeting(): MeetingResponse {
  return makeMeeting({
    next_meeting_date: '2026-11-20',
    next_meeting_time: '09:30:00',
    next_meeting_location: 'Site, line 2',
    attendees: [
      ...makeMeeting().attendees,
      {
        id: 6,
        public_id: '00000000-0000-0000-0000-000000000006',
        kind: 'contact',
        status: 'excused',
        position: 1,
        user: null,
        contact_id: 9,
        name: 'Thomas Muster',
        email: 'thomas@muster.example',
        anonymised: false,
      },
      {
        id: 7,
        public_id: '00000000-0000-0000-0000-000000000007',
        kind: 'guest',
        status: 'distribution_only',
        position: 2,
        user: null,
        contact_id: null,
        name: 'Inspector Office',
        email: 'office@inspect.example',
        anonymised: false,
      },
    ],
    cards: [
      makeCard({
        id: 2,
        position: 1,
        scope: 'Schedule',
        scope_icon: 'schedule',
        body: 'Ask [the portal](https://portal.example) and [mail@x.example](mailto:mail@x.example).',
        decisions: [],
        todos: [],
      }),
      makeCard({
        id: 1,
        position: 0,
        body: [
          'The cups show wear after **40,000 cycles**, says @[Anna](user:2).',
          '',
          '- Replace the cups',
          '  - Order spares',
          '',
          '![Worn cup](file:41)',
          '',
          '![Missing photo](file:42)',
        ].join('\n'),
        changed: '2026-11-06T09:20:00Z',
        changed_by: ANNA,
        decisions: [
          {
            id: 51,
            public_id: '00000000-0000-0000-0000-000000000051',
            meeting_id: 21,
            card_id: 1,
            position: 0,
            text: 'Switch to silicone cups',
            created: '2026-11-06T09:12:00Z',
            creator: ANNA,
          },
        ],
        todos: [
          makeTodo({ id: 11, note: 'Rev. D with the new cups' }),
          makeTodo({ id: 12, title: 'Confirm the colour', due_date: null, done: true, done_at: '2026-11-07T10:00:00Z', owners: [{ user: null, contact_id: 9, name: 'Thomas Muster' }] }),
        ],
      }),
      makeCard({ id: 3, position: 2, scope: 'Pricing', scope_icon: 'commercial', internal: true, body: 'Margin stays at 18 %.' }),
    ],
    files: [
      {
        id: 41,
        public_id: '00000000-0000-0000-0000-000000000041',
        meeting_id: 21,
        card_id: 1,
        category: 'image',
        file_name: 'worn-cup.jpg',
        mime_type: 'image/jpeg',
        size_bytes: 120_000,
        sha256: 'a',
        storage_path: 'meetings/41',
        stored_name: '41.jpg',
        uploaded_by_user_id: 2,
        created: '2026-11-06T09:15:00Z',
        url: null,
      },
    ],
  })
}

function input(overrides: Partial<MeetingNotesReportInput> = {}): MeetingNotesReportInput {
  return {
    meeting: meeting(),
    label: { issue_number: 2, draft: false },
    issuedOn: '2026-11-06',
    // The user is called by their current name, not the one in the text.
    userName: (id) => (id === ANNA.id ? 'Anna Generic-Hypothetical' : undefined),
    loadImage: async (fileId) => (fileId === 41 ? PIXEL : null),
    ...overrides,
  }
}

async function build(
  overrides: Partial<MeetingNotesReportInput> = {},
  options: Record<string, boolean> = {},
  locale: 'enGB' | 'deAT' = 'enGB',
): Promise<ReportContent> {
  return meetingNotesReportSpec(input(overrides)).build(createReportContext(locale, options))
}

describe('issueLabelText', () => {
  const t = (key: string, params?: Record<string, unknown>) => i18n.global.t(key, params ?? {}, { locale: 'enGB' })
  const date = createReportContext('enGB').date

  it('names an issue with the day it went out, a draft after it, and a draft before the first send', () => {
    expect(issueLabelText({ issue_number: 2, draft: false }, '2026-11-06', t, date)).toBe('Issue 2 · 6 Nov 2026')
    expect(issueLabelText({ issue_number: 2, draft: false }, null, t, date)).toBe('Issue 2')
    expect(issueLabelText({ issue_number: 2, draft: true }, null, t, date)).toBe('Draft after issue 2')
    expect(issueLabelText({ issue_number: 0, draft: true }, null, t, date)).toBe('Draft')
  })
})

describe('meetingNotesReportSpec', () => {
  // The report prints times in the tenant's timezone, which falls back to
  // the machine's own, so the expected times hold on a runner in UTC too.
  beforeEach(() => setDisplayTimezone('Europe/Vienna'))
  afterEach(() => setDisplayTimezone(null))

  it('offers the todos, the internal cards and the documents as options and prints through the meeting', () => {
    const spec = meetingNotesReportSpec(input())

    expect(spec.title).toBe('MTG-26-0021 Design Review Gripper')
    expect(spec.printTarget).toBeNull()
    expect(spec.options).toBe(MEETING_NOTES_OPTIONS)
    expect(MEETING_NOTES_OPTIONS.map((option) => option.key)).toEqual(['include_todos', 'include_internal', 'list_documents'])
  })

  it('carries the issue in the header, the details and next to the QR code', async () => {
    const report = await build()

    expect(report.kind).toBe('Meeting Notes')
    expect(report.title).toBe('Design Review Gripper')
    expect(report.subtitle).toBe('Issue 2 · 6 Nov 2026')
    expect(reportTexts(report.details.map((detail) => [detail.label, detail.value]))).toEqual(
      expect.arrayContaining([
        'Number',
        'MTG-26-0021',
        'Project',
        '26-0142',
        '6 Nov 2026, 09:00 – 10:30',
        'Room Danube',
        'Issue',
        'Issue 2 · 6 Nov 2026',
      ]),
    )
    expect(report.identity).toEqual({
      publicId: '00000000-0000-0000-0000-000000000021',
      reference: 'MTG-26-0021 · Issue 2 · 6 Nov 2026',
    })
    expect(report.notice).toBeNull()
  })

  it('marks a draft after an issue and a plain draft as such', async () => {
    const after = await build({ label: { issue_number: 2, draft: true }, issuedOn: null })
    const first = await build({ label: { issue_number: 0, draft: true }, issuedOn: null })

    expect(after.subtitle).toBe('Draft after issue 2')
    expect(after.notice?.tone).toBe('warn')
    expect(first.subtitle).toBe('Draft')
    expect(first.identity?.reference).toBe('MTG-26-0021 · Draft')
  })

  it('lists the attendees as present, excused and distribution', async () => {
    const body = reportTexts((await build()).body)

    expect(body).toEqual(
      expect.arrayContaining(['Present', 'Anna Generic-Hypothetical', 'Excused', 'Thomas Muster', 'Distribution', 'Inspector Office']),
    )
  })

  it('prints each card with its scope, its rendered text, its decisions and who wrote it', async () => {
    const report = await build()
    const body = reportTexts(report.body)

    expect(body).toEqual(
      expect.arrayContaining([
        '1. Vacuum gripper',
        ' · Mechanics',
        '40,000 cycles',
        'Anna Generic-Hypothetical',
        'Replace the cups',
        'Order spares',
        'Decisions',
        'Switch to silicone cups',
        '2. Schedule',
        'the portal',
        ' (https://portal.example)',
        'mail@x.example',
        'Missing photo',
      ]),
    )
    // The mention shows the user's current name, not the one in the text.
    expect(body).not.toContain('Anna')
    // A link whose text is its address is not printed twice.
    expect(body).not.toContain(' (mail@x.example)')
    expect(body.some((text) => text.startsWith('Written by Anna Generic-Hypothetical') && text.includes('changed by'))).toBe(
      true,
    )
    // The image that loaded is embedded; the one that did not leaves its alt text.
    expect(JSON.stringify(report.body)).toContain(PIXEL)
  })

  it('loads the images of the included cards only', async () => {
    const loadImage = vi.fn<(fileId: number) => Promise<string | null>>(async () => null)

    await build({ loadImage })

    expect(loadImage.mock.calls.map(([fileId]) => fileId).sort()).toEqual([41, 42])
  })

  it('repeats the decisions in a summary and lists the todos with owners, due date and status', async () => {
    const body = reportTexts((await build()).body)

    expect(body).toEqual(
      expect.arrayContaining([
        'Decisions Summary',
        'Todos',
        'Send layout drawing rev. D',
        'Rev. D with the new cups',
        'Anna Generic-Hypothetical',
        '13 Nov 2026',
        'Open',
        'Confirm the colour',
        'Thomas Muster',
        'Documents',
        'worn-cup.jpg',
        'Next Meeting',
        '20 Nov 2026',
        '09:30',
        'Site, line 2',
      ]),
    )
    expect(body.some((text) => text.startsWith('Done '))).toBe(true)
  })

  it('leaves the internal cards out unless they are included', async () => {
    const without = reportTexts((await build()).body)
    const withInternal = reportTexts((await build({}, { include_internal: true })).body)

    expect(without.some((text) => text.includes('Pricing'))).toBe(false)
    expect(withInternal).toEqual(expect.arrayContaining(['3. Pricing', ' · Internal', 'Margin stays at 18 %.']))
    expect(includedCards(meeting(), {}).map((card) => card.id)).toEqual([1, 2])
    expect(includedCards(meeting(), { include_internal: true }).map((card) => card.id)).toEqual([1, 2, 3])
  })

  it('leaves the todos and the documents out when asked', async () => {
    const body = reportTexts((await build({}, { include_todos: false, list_documents: false })).body)

    expect(body).not.toContain('Todos')
    expect(body).not.toContain('Send layout drawing rev. D')
    expect(body).not.toContain('worn-cup.jpg')
    // The decisions stay, since they belong to the cards.
    expect(body).toContain('Decisions Summary')
  })

  it('writes the notes in the chosen language', async () => {
    const report = await build({}, {}, 'deAT')
    const body = reportTexts(report.body)

    expect(report.kind).toBe('Besprechungsprotokoll')
    expect(report.subtitle).toBe('Ausgabe 2 · 06.11.2026')
    expect(body).toEqual(expect.arrayContaining(['Anwesend', 'Entschuldigt', 'Beschlüsse im Überblick', 'Offen']))
  })

  it('renders as an archival PDF', async () => {
    const spec = meetingNotesReportSpec(input())

    const pdf = await renderPdfForTest(await composeReport(spec, BRANDING, 'enGB', { include_internal: true }))

    expect(isPdfA2b(pdf)).toBe(true)
  })
})
