import { postFile } from '@/core/api/postFile'
import { webApi } from '@/core/api/webRequest'

import type {
  MeetingCardCreateRequest,
  MeetingCardUpdateRequest,
  MeetingCreateRequest,
  MeetingDecisionRequest,
  MeetingListParams,
  MeetingScopeParams,
  MeetingScopeRenameRequest,
  MeetingTagParams,
  MeetingTodoRequest,
  MeetingUpdateRequest,
} from '../types/meetingRequest'
import type {
  MeetingCardResponse,
  MeetingCardRevisionResponse,
  MeetingDecisionResponse,
  MeetingDefaultMailTemplateResponse,
  MeetingDistributionEntryResponse,
  MeetingEventResponse,
  MeetingFileResponse,
  MeetingIssueResponse,
  MeetingListRowResponse,
  MeetingOpenPointResponse,
  MeetingPrintResponse,
  MeetingRecipientSuggestionResponse,
  MeetingResponse,
  MeetingScopeRenameResponse,
  MeetingScopeSuggestionsResponse,
  MeetingSnapshotResponse,
  MeetingTagSuggestionsResponse,
  MeetingTodoResponse,
} from '../types/meetingResponse'
import type { AppLocale } from '@/core/i18n'

// ── Meetings ──────────────────────────────────────────────────────────

/** The meetings of one project or one product, latest start first. */
export async function getMeetings(params: MeetingListParams): Promise<MeetingListRowResponse[]> {
  return webApi.get('/meetings/', { query: params })
}

export async function getMeeting(meetingId: number): Promise<MeetingResponse> {
  return webApi.get('/meetings/{meeting_id}', { path: { meeting_id: meetingId } })
}

export async function createMeeting(body: MeetingCreateRequest): Promise<MeetingResponse> {
  return webApi.post('/meetings/', { body })
}

export async function updateMeeting(meetingId: number, body: MeetingUpdateRequest): Promise<MeetingResponse> {
  return webApi.put('/meetings/{meeting_id}', { path: { meeting_id: meetingId }, body })
}

export async function deleteMeeting(meetingId: number, expectedEditVersion: number): Promise<void> {
  await webApi.delete('/meetings/{meeting_id}', {
    path: { meeting_id: meetingId },
    query: { expected_edit_version: expectedEditVersion },
  })
}

export async function invalidateMeeting(meetingId: number, reason: string): Promise<MeetingResponse> {
  return webApi.post('/meetings/{meeting_id}/invalidate', { path: { meeting_id: meetingId }, body: { reason } })
}

export async function restoreMeeting(meetingId: number, note: string | null): Promise<MeetingResponse> {
  return webApi.post('/meetings/{meeting_id}/restore', { path: { meeting_id: meetingId }, body: { note } })
}

export async function createFollowUpMeeting(meetingId: number): Promise<MeetingResponse> {
  return webApi.post('/meetings/{meeting_id}/follow-up', { path: { meeting_id: meetingId } })
}

/** The open todos of the meeting this one follows and of its predecessors. */
export async function getMeetingOpenPoints(meetingId: number): Promise<MeetingOpenPointResponse[]> {
  return webApi.get('/meetings/{meeting_id}/open-points', { path: { meeting_id: meetingId } })
}

export async function getMeetingHistory(meetingId: number): Promise<MeetingEventResponse[]> {
  return webApi.get('/meetings/{meeting_id}/history', { path: { meeting_id: meetingId } })
}

/** Blanks a guest's name and e-mail address on the meeting. */
export async function anonymiseMeetingAttendee(meetingId: number, attendeeId: number): Promise<MeetingResponse> {
  return webApi.post('/meetings/{meeting_id}/attendees/{attendee_id}/anonymise', {
    path: { meeting_id: meetingId, attendee_id: attendeeId },
  })
}

// ── Cards ─────────────────────────────────────────────────────────────

export async function createMeetingCard(
  meetingId: number,
  body: MeetingCardCreateRequest,
): Promise<MeetingCardResponse> {
  return webApi.post('/meetings/{meeting_id}/cards', { path: { meeting_id: meetingId }, body })
}

export async function getMeetingCard(meetingId: number, cardId: number): Promise<MeetingCardResponse> {
  return webApi.get('/meetings/{meeting_id}/cards/{card_id}', { path: { meeting_id: meetingId, card_id: cardId } })
}

/** Saves the card; a card that moved since `expected_edit_version` answers 409. */
export async function updateMeetingCard(
  meetingId: number,
  cardId: number,
  body: MeetingCardUpdateRequest,
): Promise<MeetingCardResponse> {
  return webApi.put('/meetings/{meeting_id}/cards/{card_id}', {
    path: { meeting_id: meetingId, card_id: cardId },
    body,
  })
}

export async function deleteMeetingCard(meetingId: number, cardId: number, expectedEditVersion: number): Promise<void> {
  await webApi.delete('/meetings/{meeting_id}/cards/{card_id}', {
    path: { meeting_id: meetingId, card_id: cardId },
    query: { expected_edit_version: expectedEditVersion },
  })
}

/** The card's revisions, newest first. */
export async function getMeetingCardRevisions(
  meetingId: number,
  cardId: number,
): Promise<MeetingCardRevisionResponse[]> {
  return webApi.get('/meetings/{meeting_id}/cards/{card_id}/revisions', {
    path: { meeting_id: meetingId, card_id: cardId },
  })
}

export async function restoreMeetingCardRevision(
  meetingId: number,
  cardId: number,
  revisionId: number,
  expectedEditVersion: number,
): Promise<MeetingCardResponse> {
  return webApi.post('/meetings/{meeting_id}/cards/{card_id}/revisions/{revision_id}/restore', {
    path: { meeting_id: meetingId, card_id: cardId, revision_id: revisionId },
    body: { expected_edit_version: expectedEditVersion },
  })
}

/** The editor's heartbeat, or with `editing` false the end of editing. */
export async function announceMeetingCardPresence(meetingId: number, cardId: number, editing: boolean): Promise<void> {
  await webApi.post('/meetings/{meeting_id}/cards/{card_id}/presence', {
    path: { meeting_id: meetingId, card_id: cardId },
    body: { editing },
  })
}

// ── Decisions ─────────────────────────────────────────────────────────

export async function createMeetingDecision(
  meetingId: number,
  cardId: number,
  body: MeetingDecisionRequest,
): Promise<MeetingDecisionResponse> {
  return webApi.post('/meetings/{meeting_id}/cards/{card_id}/decisions', {
    path: { meeting_id: meetingId, card_id: cardId },
    body,
  })
}

export async function updateMeetingDecision(
  meetingId: number,
  decisionId: number,
  body: MeetingDecisionRequest,
): Promise<MeetingDecisionResponse> {
  return webApi.put('/meetings/{meeting_id}/decisions/{decision_id}', {
    path: { meeting_id: meetingId, decision_id: decisionId },
    body,
  })
}

export async function deleteMeetingDecision(meetingId: number, decisionId: number): Promise<void> {
  await webApi.delete('/meetings/{meeting_id}/decisions/{decision_id}', {
    path: { meeting_id: meetingId, decision_id: decisionId },
  })
}

// ── Todos ─────────────────────────────────────────────────────────────

export async function createMeetingTodo(
  meetingId: number,
  cardId: number,
  body: MeetingTodoRequest,
): Promise<MeetingTodoResponse> {
  return webApi.post('/meetings/{meeting_id}/cards/{card_id}/todos', {
    path: { meeting_id: meetingId, card_id: cardId },
    body,
  })
}

export async function updateMeetingTodo(
  meetingId: number,
  todoId: number,
  body: MeetingTodoRequest,
): Promise<MeetingTodoResponse> {
  return webApi.put('/meetings/{meeting_id}/todos/{todo_id}', { path: { meeting_id: meetingId, todo_id: todoId }, body })
}

export async function deleteMeetingTodo(meetingId: number, todoId: number): Promise<void> {
  await webApi.delete('/meetings/{meeting_id}/todos/{todo_id}', { path: { meeting_id: meetingId, todo_id: todoId } })
}

/** Ticks the todo off for everyone, or opens it again. */
export async function setMeetingTodoDone(meetingId: number, todoId: number, done: boolean): Promise<MeetingTodoResponse> {
  const path = { meeting_id: meetingId, todo_id: todoId }
  return done
    ? webApi.post('/meetings/{meeting_id}/todos/{todo_id}/done', { path })
    : webApi.post('/meetings/{meeting_id}/todos/{todo_id}/reopen', { path })
}

// ── Files ─────────────────────────────────────────────────────────────

/** Uploads an image or a PDF; an image pasted into a card names the card. */
export async function uploadMeetingFile(
  meetingId: number,
  file: File,
  cardId: number | null = null,
): Promise<MeetingFileResponse> {
  const category = file.type.startsWith('image/') ? 'image' : 'pdf'
  return postFile('/meetings/{meeting_id}/files', file, {
    path: { meeting_id: meetingId },
    fields: cardId === null ? { category } : { category, card_id: String(cardId) },
  })
}

export async function fetchMeetingFileBlob(meetingId: number, fileId: number): Promise<Blob> {
  return (await webApi.get('/meetings/{meeting_id}/files/{file_id}', {
    path: { meeting_id: meetingId, file_id: fileId },
    query: { disposition: 'inline' },
    config: { responseType: 'blob' },
  })) as Blob
}

/** Renames a file of the meeting; the stored file stays as it is. */
export async function renameMeetingFile(meetingId: number, fileId: number, fileName: string): Promise<MeetingFileResponse> {
  return webApi.patch('/meetings/{meeting_id}/files/{file_id}', {
    path: { meeting_id: meetingId, file_id: fileId },
    body: { file_name: fileName },
  })
}

export async function deleteMeetingFile(meetingId: number, fileId: number): Promise<void> {
  await webApi.delete('/meetings/{meeting_id}/files/{file_id}', { path: { meeting_id: meetingId, file_id: fileId } })
}

// ── Scopes ────────────────────────────────────────────────────────────

/** The owner's scopes, most used first, and the one `q` nearly repeats. */
export async function getMeetingScopeSuggestions(params: MeetingScopeParams): Promise<MeetingScopeSuggestionsResponse> {
  return webApi.get('/meeting-scopes/', { query: params })
}

/** Renames a scope on every card of the owner's valid meetings. */
export async function renameMeetingScope(body: MeetingScopeRenameRequest): Promise<MeetingScopeRenameResponse> {
  return webApi.post('/meeting-scopes/rename', { body })
}

// ── Tags ──────────────────────────────────────────────────────────────

/** The tags the meetings carry that contain `q`, most used first. */
export async function getMeetingTagSuggestions(params: MeetingTagParams = {}): Promise<MeetingTagSuggestionsResponse> {
  return webApi.get('/meeting-tags/', { query: params })
}

// ── Distribution ──────────────────────────────────────────────────────

/** Every print, download and send of the notes. */
export async function getMeetingDistribution(meetingId: number): Promise<MeetingDistributionEntryResponse[]> {
  return webApi.get('/meetings/{meeting_id}/distribution', { path: { meeting_id: meetingId } })
}

/** The issue a send carries, the one a print carries now, and the cards changed since the last send. */
export async function getMeetingIssue(meetingId: number): Promise<MeetingIssueResponse> {
  return webApi.get('/meetings/{meeting_id}/issue', { path: { meeting_id: meetingId } })
}

/** What one print, download or send contained. */
export async function getMeetingSnapshot(meetingId: number, snapshotId: number): Promise<MeetingSnapshotResponse> {
  return webApi.get('/meetings/{meeting_id}/distribution/snapshots/{snapshot_id}', {
    path: { meeting_id: meetingId, snapshot_id: snapshotId },
  })
}

/** The addresses the send dialog offers, the pre-selected first. */
export async function getMeetingRecipientSuggestions(meetingId: number): Promise<MeetingRecipientSuggestionResponse[]> {
  return webApi.get('/meetings/{meeting_id}/recipient-suggestions', { path: { meeting_id: meetingId } })
}

/** The default text of the meeting notes mail in a language, with its `{{ var }}` placeholders. */
export async function getMeetingNotesMailTemplate(language: AppLocale): Promise<MeetingDefaultMailTemplateResponse> {
  return webApi.get('/mail/templates/default', { query: { kind: 'meeting_notes', language } })
}

/** How the browser built a PDF of the notes, which the server checks against the notes as they are. */
export interface MeetingNotesBuildParams {
  pdf: Blob
  fileName: string
  language: AppLocale
  reportVersion: string
  options: Readonly<Record<string, boolean>>
  cards: ReadonlyArray<{ id: number; edit_version: number }>
  issueNumber: number
}

function buildForm(build: MeetingNotesBuildParams): FormData {
  const form = new FormData()
  form.append('file', build.pdf, build.fileName)
  form.append('language', build.language)
  form.append('report_version', build.reportVersion)
  form.append('options', JSON.stringify(build.options))
  form.append('cards', JSON.stringify(build.cards.map((card) => ({ id: card.id, edit_version: card.edit_version }))))
  form.append('issue_number', String(build.issueNumber))
  return form
}

const MULTIPART = { headers: { 'Content-Type': 'multipart/form-data' } }

/** Journals a download before the browser saves the file; 409 when the notes changed since they were built. */
export async function downloadMeetingNotes(
  meetingId: number,
  build: MeetingNotesBuildParams,
  draft: boolean,
): Promise<MeetingDistributionEntryResponse> {
  const form = buildForm(build)
  form.append('draft', String(draft))
  return webApi.post('/meetings/{meeting_id}/distribution/download', {
    path: { meeting_id: meetingId },
    body: form,
    config: MULTIPART,
  })
}

export interface MeetingPrintParams {
  printerId: number
  copies: number
  twoSided: boolean
}

/** Sends the PDF to a printer; a print that reached it comes back with its distribution entry. */
export async function printMeetingNotes(
  meetingId: number,
  build: MeetingNotesBuildParams,
  draft: boolean,
  printer: MeetingPrintParams,
): Promise<MeetingPrintResponse> {
  const form = buildForm(build)
  form.append('draft', String(draft))
  form.append('printer_id', String(printer.printerId))
  form.append('copies', String(printer.copies))
  form.append('two_sided', String(printer.twoSided))
  return webApi.post('/meetings/{meeting_id}/distribution/print', {
    path: { meeting_id: meetingId },
    body: form,
    config: MULTIPART,
  })
}

export interface MeetingMailParams {
  to: readonly string[]
  cc: readonly string[]
  subject: string
  htmlBody: string
  attachFileIds: readonly number[]
}

/**
 * Mails the PDF and the documents asked for. Answers 409 when the notes
 * changed since they were built, 413 when the attachments are over the
 * limit and the mail server's error when it refuses the mail.
 */
export async function sendMeetingNotes(
  meetingId: number,
  build: MeetingNotesBuildParams,
  mail: MeetingMailParams,
): Promise<MeetingDistributionEntryResponse> {
  const form = buildForm(build)
  form.append('to', mail.to.join(', '))
  if (mail.cc.length) form.append('cc', mail.cc.join(', '))
  form.append('subject', mail.subject)
  form.append('html_body', mail.htmlBody)
  for (const fileId of mail.attachFileIds) form.append('attach_file_ids', String(fileId))
  return webApi.post('/meetings/{meeting_id}/distribution/send', {
    path: { meeting_id: meetingId },
    body: form,
    config: MULTIPART,
  })
}
