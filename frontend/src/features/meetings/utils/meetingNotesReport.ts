import { toDayKey } from '@/core/utils/dates'
import {
  CONTENT_WIDTH,
  REPORT_EMPTY,
  cell,
  dataTable,
  group,
  keyValueGrid,
  list,
  notice,
  noteCell,
  orDash,
  paragraph,
  picture,
  section,
  span,
  subheading,
} from '@/shared/reports'
import type {
  Content,
  Inline,
  KeyValue,
  ListBlock,
  ReportContext,
  ReportOption,
  ReportSpec,
  ReportTranslate,
} from '@/shared/reports'
import type {
  MeetingAttendanceStatus,
  MeetingCardResponse,
  MeetingIssueLabelResponse,
  MeetingResponse,
  MeetingTodoOwnerResponse,
} from '../types/meetingResponse'
import { parseCardMarkdown } from './cardMarkdown'
import type { CardBlock, CardInline, CardList } from './cardMarkdown'

/**
 * The PDF of the meeting notes, the minutes that go to the customer: the
 * meeting's facts and attendees, every card with its scope, its text, its
 * decisions and who wrote it, a summary of the decisions, the todos, the
 * documents and the next meeting. Internal cards are left out unless the
 * options include them, and the todos and the documents can be left out
 * too. The header carries the issue the PDF goes out as ("Issue 2 · 6 Nov
 * 2026", "Draft after issue 2" or "Draft"), and the QR code opens the
 * meeting.
 *
 * Printing and downloading go through the meeting's own routes, which check
 * the cards the PDF was built from, so the spec names no print target.
 */

const M = 'meetings'

export const MEETING_NOTES_OPTION_KEYS = ['include_todos', 'include_internal', 'list_documents'] as const

export type MeetingNotesOptionKey = (typeof MEETING_NOTES_OPTION_KEYS)[number]

export type MeetingNotesOptions = Record<MeetingNotesOptionKey, boolean>

/** The options of the notes as the server defaults them: todos and documents in, internal cards out. */
export const DEFAULT_MEETING_NOTES_OPTIONS: Readonly<MeetingNotesOptions> = {
  include_todos: true,
  include_internal: false,
  list_documents: true,
}

export const MEETING_NOTES_OPTIONS: readonly ReportOption[] = [
  { key: 'include_todos', labelKey: `${M}.report.options.includeTodos` },
  { key: 'include_internal', labelKey: `${M}.report.options.includeInternal` },
  { key: 'list_documents', labelKey: `${M}.report.options.listDocuments` },
]

/** The pixels a card image is scaled to at most, wide or tall, before it goes into the PDF. */
export const CARD_IMAGE_MAX_PIXELS = 1600

/** The box a card image is fitted into on the page, in points. */
const IMAGE_BOX: [number, number] = [CONTENT_WIDTH, 320]

export interface MeetingNotesReportInput {
  meeting: MeetingResponse
  /** The issue the PDF carries. */
  label: Pick<MeetingIssueLabelResponse, 'issue_number' | 'draft'>
  /** The day that issue went out, as "2026-11-06": today for a send, the last send for a print of it. */
  issuedOn: string | null
  /** The current name of a user, for mentions, authors and owners. */
  userName: (userId: number) => string | undefined
  /** A card image as a data URL scaled for the PDF, or null when it cannot be loaded. */
  loadImage: (fileId: number) => Promise<string | null>
}

/** The option values of one build, every option the notes offer with its default where none was chosen. */
export function meetingNotesOptions(values: Readonly<Record<string, boolean>> = {}): MeetingNotesOptions {
  return {
    include_todos: values.include_todos ?? DEFAULT_MEETING_NOTES_OPTIONS.include_todos,
    include_internal: values.include_internal ?? DEFAULT_MEETING_NOTES_OPTIONS.include_internal,
    list_documents: values.list_documents ?? DEFAULT_MEETING_NOTES_OPTIONS.list_documents,
  }
}

/** The cards a PDF with these options contains, in their order, as the server counts them. */
export function includedCards(meeting: MeetingResponse, options: Readonly<Record<string, boolean>>): MeetingCardResponse[] {
  const withInternal = meetingNotesOptions(options).include_internal
  return [...meeting.cards]
    .sort((a, b) => a.position - b.position || a.id - b.id)
    .filter((card) => withInternal || !card.internal)
}

/** The issue as the PDF and the dialogs name it: "Issue 2 · 6 Nov 2026", "Draft after issue 2" or "Draft". */
export function issueLabelText(
  label: Pick<MeetingIssueLabelResponse, 'issue_number' | 'draft'>,
  issuedOn: string | null,
  t: ReportTranslate,
  date: (value: string) => string,
): string {
  if (label.draft) {
    return label.issue_number > 0 ? t(`${M}.issue.draftAfter`, { issue: label.issue_number }) : t(`${M}.issue.draft`)
  }
  return issuedOn
    ? t(`${M}.issue.issuedOn`, { issue: label.issue_number, date: date(issuedOn) })
    : t(`${M}.issue.issue`, { issue: label.issue_number })
}

/** The day the issue a print or download carries went out, or null while it is a draft. */
export function printIssuedOn(issue: { print: { draft: boolean }; last_sent_at: string | null }): string | null {
  return !issue.print.draft && issue.last_sent_at ? toDayKey(issue.last_sent_at) : null
}

/** The day a send goes out, which its issue carries. */
export function sendIssuedOn(now: Date = new Date()): string {
  return toDayKey(now.toISOString())
}

// ── Card text ─────────────────────────────────────────────────────────

interface Rendering {
  t: ReportTranslate
  userName: (userId: number) => string | undefined
  images: ReadonlyMap<number, string | null>
}

function linkLabel(url: string): string {
  return url.replace(/^mailto:/i, '')
}

function plainText(nodes: CardInline[]): string {
  return nodes
    .map((node) => {
      switch (node.kind) {
        case 'text':
          return node.text
        case 'code':
          return node.code
        case 'mention':
          return node.name
        case 'image':
          return node.alt
        case 'break':
          return ' '
        default:
          return plainText(node.children)
      }
    })
    .join('')
}

function runs(nodes: CardInline[], r: Rendering): Inline[] {
  return nodes.flatMap((node): Inline[] => {
    switch (node.kind) {
      case 'text':
        return [node.text]
      case 'break':
        return ['\n']
      case 'code':
        return [span(node.code, 'muted')]
      case 'mention':
        return [span(r.userName(node.userId) ?? node.name, 'emphasis')]
      case 'image':
        return [span(node.alt || r.t(`${M}.report.image`), 'muted')]
      case 'strong':
        return [span(runs(node.children, r), 'emphasis')]
      case 'em':
        return [span(runs(node.children, r), 'italic')]
      case 'link': {
        // Paper cannot follow a link, so its address is printed after its text.
        const label = linkLabel(node.url)
        const text = runs(node.children, r)
        return plainText(node.children).trim() === label ? text : [...text, span(` (${label})`, 'muted')]
      }
    }
  })
}

/** A paragraph's text with its images taken out as pictures of their own. */
function paragraphBlocks(inline: CardInline[], r: Rendering): Content[] {
  const blocks: Content[] = []
  let pending: CardInline[] = []
  const flush = (): void => {
    if (pending.some((node) => node.kind !== 'break')) blocks.push(paragraph(runs(pending, r), undefined, 'tight'))
    pending = []
  }
  for (const node of inline) {
    if (node.kind !== 'image') {
      pending.push(node)
      continue
    }
    flush()
    const image = r.images.get(node.fileId)
    blocks.push(
      image
        ? group([picture(image, IMAGE_BOX)], 'tight')
        : paragraph(span(node.alt || r.t(`${M}.report.image`), 'muted'), undefined, 'tight'),
    )
  }
  flush()
  return blocks
}

function listBlock(cardList: CardList, r: Rendering): ListBlock {
  return {
    ordered: cardList.ordered,
    start: cardList.items[0]?.number,
    entries: cardList.items.map((item) => ({
      text: runs(item.inline, r),
      sublists: item.children.map((child) => listBlock(child, r)),
    })),
  }
}

function bodyBlocks(blocks: CardBlock[], r: Rendering): Content[] {
  return blocks.flatMap((block): Content[] => {
    if (block.kind === 'heading') return [paragraph(runs(block.inline, r), 'emphasis', 'before')]
    if (block.kind === 'paragraph') return paragraphBlocks(block.inline, r)
    return [list(listBlock(block, r))]
  })
}

function imageIds(blocks: CardBlock[]): number[] {
  const ids: number[] = []
  const walk = (nodes: CardInline[]): void => {
    for (const node of nodes) {
      if (node.kind === 'image') ids.push(node.fileId)
      else if (node.kind === 'link' || node.kind === 'strong' || node.kind === 'em') walk(node.children)
    }
  }
  const walkList = (cardList: CardList): void => {
    for (const item of cardList.items) {
      walk(item.inline)
      item.children.forEach(walkList)
    }
  }
  for (const block of blocks) {
    if (block.kind === 'list') walkList(block)
    else walk(block.inline)
  }
  return ids
}

// ── Sections ──────────────────────────────────────────────────────────

function scopeOf(card: MeetingCardResponse, t: ReportTranslate): string {
  return card.scope || t(`${M}.card.noScope`)
}

function personName(user: { id: number; full_name: string } | null, r: Rendering): string {
  return user ? (r.userName(user.id) ?? user.full_name) : r.t(`${M}.unknownUser`)
}

function ownerNames(owners: MeetingTodoOwnerResponse[], r: Rendering): string {
  if (!owners.length) return REPORT_EMPTY
  return owners.map((owner) => (owner.user ? (r.userName(owner.user.id) ?? owner.name) : owner.name)).join(', ')
}

function meetingWhen(meeting: MeetingResponse, context: ReportContext): string {
  const end = context.sameDay(meeting.starts_at, meeting.ends_at)
    ? context.time(meeting.ends_at)
    : context.dateTime(meeting.ends_at)
  return `${context.dateTime(meeting.starts_at)} – ${end}`
}

const ATTENDANCE: readonly MeetingAttendanceStatus[] = ['present', 'excused', 'distribution_only']

function attendeesSection(meeting: MeetingResponse, r: Rendering): Content {
  const rows: KeyValue[] = ATTENDANCE.flatMap((status) => {
    const names = [...meeting.attendees]
      .sort((a, b) => a.position - b.position)
      .filter((attendee) => attendee.status === status)
      .map((attendee) => {
        if (attendee.anonymised) return r.t(`${M}.attendees.anonymised`)
        return attendee.user ? (r.userName(attendee.user.id) ?? attendee.name) : attendee.name
      })
    return names.length ? [{ label: r.t(`${M}.attendees.status.${status}`), value: names.join(', ') }] : []
  })
  return section(
    r.t(`${M}.info.attendees`),
    rows.length ? keyValueGrid(rows, 1) : paragraph(r.t(`${M}.attendees.none`), 'muted'),
  )
}

function cardBlock(
  card: MeetingCardResponse,
  index: number,
  context: ReportContext,
  r: Rendering,
  parsed: CardBlock[],
): Content {
  const { t, dateTime } = context
  const heading: Inline[] = [`${index + 1}. ${scopeOf(card, t)}`]
  if (card.scope_icon) heading.push(span(` · ${t(`${M}.scopeIcons.${card.scope_icon}`)}`, 'muted'))
  if (card.internal) heading.push(span(` · ${t(`${M}.card.internal`)}`, 'alert'))

  const body = bodyBlocks(parsed, r)
  const decisions = [...card.decisions].sort((a, b) => a.position - b.position || a.id - b.id)
  const author = [t(`${M}.report.writtenBy`, { name: personName(card.creator, r), at: dateTime(card.created) })]
  if (card.changed) {
    author.push(t(`${M}.report.changedBy`, { name: personName(card.changed_by, r), at: dateTime(card.changed) }))
  }
  return group(
    [
      subheading(heading),
      ...(body.length ? body : [paragraph(t(`${M}.card.empty`), 'muted')]),
      ...(decisions.length
        ? [
            notice(
              list({ ordered: false, entries: decisions.map((decision) => ({ text: decision.text })) }),
              'info',
              t(`${M}.decisions.heading`),
            ),
          ]
        : []),
      paragraph(author.join(' · '), 'note', 'tight'),
    ],
    'after',
  )
}

function decisionsSection(cards: MeetingCardResponse[], { t }: ReportContext): Content | null {
  const rows = cards.flatMap((card) =>
    [...card.decisions]
      .sort((a, b) => a.position - b.position || a.id - b.id)
      .map((decision) => ({ decision, card })),
  )
  if (!rows.length) return null
  return section(
    t(`${M}.report.decisionsSummary`),
    dataTable(
      [
        { header: '#', align: 'right' },
        { header: t(`${M}.decisions.text`), width: '*' },
        { header: t(`${M}.report.scope`), width: 120 },
      ],
      rows.map(({ decision, card }, index) => [
        cell(String(index + 1), { noWrap: true }),
        decision.text,
        scopeOf(card, t),
      ]),
    ),
  )
}

function todosSection(cards: MeetingCardResponse[], context: ReportContext, r: Rendering): Content {
  const { t, date, dateTime } = context
  const rows = cards.flatMap((card) =>
    [...card.todos].sort((a, b) => a.position - b.position || a.id - b.id).map((todo) => ({ todo, card })),
  )
  if (!rows.length) return section(t(`${M}.todos.heading`), paragraph(t(`${M}.todos.none`), 'muted'))
  return section(
    t(`${M}.todos.heading`),
    dataTable(
      [
        { header: '#', align: 'right' },
        { header: t(`${M}.todos.title`), width: '*' },
        { header: t(`${M}.report.scope`), width: 90 },
        { header: t(`${M}.todos.owners`), width: 100 },
        { header: t(`${M}.todos.due`) },
        { header: t(`${M}.report.status`) },
      ],
      rows.map(({ todo, card }, index) => [
        cell(String(index + 1), { noWrap: true }),
        noteCell(todo.title, todo.note ? [todo.note] : []),
        scopeOf(card, t),
        ownerNames(todo.owners, r),
        cell(todo.due_date ? date(todo.due_date) : REPORT_EMPTY, { noWrap: true }),
        todo.done
          ? cell(todo.done_at ? t(`${M}.report.doneOn`, { at: dateTime(todo.done_at) }) : t(`${M}.report.done`), {
              style: 'muted',
            })
          : cell(t(`${M}.report.open`), { style: 'emphasis', noWrap: true }),
      ]),
    ),
  )
}

function documentsSection(meeting: MeetingResponse, { t }: ReportContext): Content | null {
  if (!meeting.files.length) return null
  return section(
    t(`${M}.documents.title`),
    list({ ordered: false, entries: meeting.files.map((file) => ({ text: file.file_name })) }),
  )
}

function nextMeetingSection(meeting: MeetingResponse, { t, date }: ReportContext): Content | null {
  if (!meeting.next_meeting_date) return null
  const rows: KeyValue[] = [{ label: t(`${M}.report.date`), value: date(meeting.next_meeting_date) }]
  if (meeting.next_meeting_time) rows.push({ label: t(`${M}.report.time`), value: meeting.next_meeting_time.slice(0, 5) })
  if (meeting.next_meeting_location) rows.push({ label: t(`${M}.info.location`), value: meeting.next_meeting_location })
  return section(t(`${M}.info.nextMeeting`), keyValueGrid(rows, 1))
}

// ── The spec ──────────────────────────────────────────────────────────

/** The report of the meeting notes as they are now, carrying the given issue. */
export function meetingNotesReportSpec(input: MeetingNotesReportInput): ReportSpec {
  const { meeting, label } = input
  return {
    title: `${meeting.meeting_number} ${meeting.name}`,
    options: MEETING_NOTES_OPTIONS,
    printTarget: null,
    build: async (context) => {
      const { t } = context
      const options = meetingNotesOptions(context.options)
      const cards = includedCards(meeting, options)
      const parsed = new Map(cards.map((card) => [card.id, parseCardMarkdown(card.body)]))
      const ids = [...new Set([...parsed.values()].flatMap(imageIds))]
      const loaded = await Promise.all(ids.map(async (id) => [id, await input.loadImage(id)] as const))
      const r: Rendering = { t, userName: input.userName, images: new Map(loaded) }
      const issue = issueLabelText(label, input.issuedOn, t, context.date)

      const body: Content[] = [attendeesSection(meeting, r)]
      body.push(
        section(
          t(`${M}.notes.title`),
          ...(cards.length
            ? cards.map((card, index) => cardBlock(card, index, context, r, parsed.get(card.id) ?? []))
            : [paragraph(t(`${M}.report.noCards`), 'muted')]),
        ),
      )
      const decisions = decisionsSection(cards, context)
      if (decisions) body.push(decisions)
      if (options.include_todos) body.push(todosSection(cards, context, r))
      const documents = options.list_documents ? documentsSection(meeting, context) : null
      if (documents) body.push(documents)
      const next = nextMeetingSection(meeting, context)
      if (next) body.push(next)

      return {
        kind: t(`${M}.report.kind`),
        title: meeting.name,
        subtitle: issue,
        details: [
          { label: t(`${M}.report.number`), value: meeting.meeting_number },
          { label: t(`${M}.report.owner.${meeting.owner.kind}`), value: meeting.owner.number },
          { label: t(`${M}.report.when`), value: meetingWhen(meeting, context) },
          { label: t(`${M}.info.location`), value: orDash(meeting.location) },
          { label: t(`${M}.report.issue`), value: issue },
        ],
        notice: label.draft ? { text: t(`${M}.report.draftNotice`), tone: 'warn' } : null,
        identity: { publicId: meeting.public_id, reference: `${meeting.meeting_number} · ${issue}` },
        body,
      }
    },
  }
}
