import { computed, ref, watch } from 'vue'
import type { Ref } from 'vue'

import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import type { AppLocale } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { toDayKey } from '@/core/utils/dates'
import { createReportContext } from '@/shared/reports'
import { getMeetingNotesMailTemplate, getMeetingRecipientSuggestions } from '../api/meetingsApi'
import type { BuildMeetingNotes, BuiltMeetingNotes } from './useMeetingNotesPdf'
import type {
  MeetingIssueResponse,
  MeetingRecipientSuggestionResponse,
  MeetingResponse,
} from '../types/meetingResponse'
import { fillMeetingNotesTemplate, fitAttachments, hasAddress, removeAddress, addAddress } from '../utils/meetingNotesMail'
import type { AttachmentCandidate } from '../utils/meetingNotesMail'
import { DEFAULT_MEETING_NOTES_OPTIONS, includedCards, sendIssuedOn } from '../utils/meetingNotesReport'

export interface MeetingSendInputs {
  visible: Ref<boolean>
  meeting: () => MeetingResponse
  issue: () => MeetingIssueResponse | null
  build: () => BuildMeetingNotes
  /** Puts the filled template's HTML into the editable body. */
  setBody: (html: string) => void
}

/**
 * The state of the send dialog: the recipients with the suggestions, the
 * subject and text from the default template in the chosen language, the
 * options of the PDF and the PDF itself, built again whenever the language,
 * an option or the notes change, so its size is known for the documents
 * that still fit next to it under the attachment limit.
 */
export function useMeetingSend(inputs: MeetingSendInputs) {
  const hostStore = useHostStore()
  const currentUserStore = useCurrentUserStore()

  const to = ref<string[]>([])
  const cc = ref<string[]>([])
  const suggestions = ref<MeetingRecipientSuggestionResponse[]>([])
  const suggestionsLoading = ref(false)
  const locale = ref<AppLocale>('enGB')
  const subject = ref('')
  const body = ref('')
  const bodyEdited = ref(false)
  const includeTodos = ref(DEFAULT_MEETING_NOTES_OPTIONS.include_todos)
  const includeInternal = ref(DEFAULT_MEETING_NOTES_OPTIONS.include_internal)
  const attachDocuments = ref(false)

  const pdf = ref<BuiltMeetingNotes | null>(null)
  const pdfError = ref(false)
  let pending: Promise<BuiltMeetingNotes | null> | null = null
  let buildEpoch = 0

  const internalCount = computed(() => inputs.meeting().cards.filter((card) => card.internal).length)
  const documents = computed<(AttachmentCandidate & { fileId: number })[]>(() =>
    inputs.meeting().files.map((file) => ({ id: file.id, fileId: file.id, name: file.file_name, size: file.size_bytes })),
  )
  const limitMb = computed(() => hostStore.mailAttachmentLimitMb)
  const fit = computed(() => fitAttachments(pdf.value?.pdf.size ?? 0, documents.value, limitMb.value))
  const pdfTooLarge = computed(() => !!pdf.value && pdf.value.pdf.size > limitMb.value * 1024 * 1024)
  const attachedIds = computed(() => (attachDocuments.value ? fit.value.attached.map((file) => file.id) : []))

  function nameOf(address: string): string | null {
    return suggestions.value.find((entry) => entry.email.toLowerCase() === address.toLowerCase())?.name ?? null
  }

  function isSuggestionOn(entry: MeetingRecipientSuggestionResponse): boolean {
    return hasAddress(to.value, entry.email)
  }

  function toggleSuggestion(entry: MeetingRecipientSuggestionResponse, on: boolean): void {
    to.value = on ? addAddress(to.value, entry.email) : removeAddress(to.value, entry.email)
  }

  function templateVars(): Record<string, string> {
    const meeting = inputs.meeting()
    const user = currentUserStore.user
    const issue = inputs.issue()
    return {
      meeting_name: meeting.name,
      meeting_number: meeting.meeting_number,
      meeting_date: createReportContext(locale.value).date(toDayKey(meeting.starts_at)),
      owner_number: meeting.owner.number,
      issue: issue ? String(issue.send.issue_number) : '',
      user_full_name: user?.full_name ?? '',
      user_email: user?.email ?? '',
    }
  }

  async function loadTemplate(): Promise<void> {
    const meeting = inputs.meeting()
    const requested = locale.value
    try {
      const template = await getMeetingNotesMailTemplate(requested)
      if (locale.value !== requested || !inputs.visible.value) return
      const vars = templateVars()
      subject.value = template.configured
        ? fillMeetingNotesTemplate(template.subject, vars, false)
        : `${meeting.meeting_number} ${meeting.name}`
      body.value = template.configured ? fillMeetingNotesTemplate(template.body, vars, true) : ''
    } catch {
      subject.value = `${meeting.meeting_number} ${meeting.name}`
      body.value = ''
    }
    bodyEdited.value = false
    inputs.setBody(body.value)
  }

  async function loadSuggestions(): Promise<void> {
    suggestionsLoading.value = true
    try {
      suggestions.value = await getMeetingRecipientSuggestions(inputs.meeting().id)
      for (const entry of suggestions.value) if (entry.preselected) to.value = addAddress(to.value, entry.email)
    } catch {
      suggestions.value = []
    } finally {
      suggestionsLoading.value = false
    }
  }

  /** Builds the PDF for the options as they are now; an older build still running is dropped. */
  function rebuild(): Promise<BuiltMeetingNotes | null> {
    const issue = inputs.issue()
    const epoch = ++buildEpoch
    pdf.value = null
    pdfError.value = false
    if (!issue) {
      pending = Promise.resolve(null)
      return pending
    }
    const run = inputs
      .build()({
        locale: locale.value,
        options: {
          include_todos: includeTodos.value,
          include_internal: includeInternal.value,
          list_documents: DEFAULT_MEETING_NOTES_OPTIONS.list_documents,
        },
        label: issue.send,
        issuedOn: sendIssuedOn(),
      })
      .then((built) => {
        if (epoch === buildEpoch) pdf.value = built
        return built
      })
      .catch(() => {
        if (epoch === buildEpoch) pdfError.value = true
        return null
      })
    pending = run
    return run
  }

  /** The PDF for the options as they are now, waiting for a build still running. */
  async function currentPdf(): Promise<BuiltMeetingNotes | null> {
    const built = pdf.value ?? (await (pending ?? rebuild()))
    return built ?? (await rebuild())
  }

  function reset(): void {
    locale.value = i18n.global.locale.value as AppLocale
    to.value = []
    const own = currentUserStore.user?.email
    cc.value = own ? [own] : []
    includeTodos.value = DEFAULT_MEETING_NOTES_OPTIONS.include_todos
    includeInternal.value = DEFAULT_MEETING_NOTES_OPTIONS.include_internal
    attachDocuments.value = false
    subject.value = ''
    body.value = ''
    bodyEdited.value = false
    suggestions.value = []
  }

  watch(
    inputs.visible,
    (open) => {
      if (!open) return
      reset()
      void loadSuggestions()
      void loadTemplate()
      void rebuild()
    },
    { immediate: true },
  )

  // A text the user changed stays when the language changes; only the
  // template's own text follows it.
  watch(locale, () => {
    if (!inputs.visible.value) return
    if (!bodyEdited.value) void loadTemplate()
    void rebuild()
  })

  watch([includeTodos, includeInternal], () => {
    if (inputs.visible.value) void rebuild()
  })

  // The notes changed under the dialog, such as after a send that found
  // them outdated: the PDF is built from them again.
  const versions = computed(() => {
    const meeting = inputs.meeting()
    const cards = includedCards(meeting, { include_internal: true })
    const issue = inputs.issue()
    return `${meeting.edit_version}|${cards.map((card) => `${card.id}:${card.edit_version}`).join(',')}|${issue?.send.issue_number ?? ''}`
  })
  watch(versions, () => {
    if (inputs.visible.value) void rebuild()
  })

  function onBodyInput(html: string): void {
    body.value = html
    bodyEdited.value = true
  }

  return {
    to,
    cc,
    suggestions,
    suggestionsLoading,
    locale,
    subject,
    body,
    includeTodos,
    includeInternal,
    attachDocuments,
    pdf,
    pdfError,
    internalCount,
    documents,
    limitMb,
    fit,
    pdfTooLarge,
    attachedIds,
    nameOf,
    isSuggestionOn,
    toggleSuggestion,
    currentPdf,
    onBodyInput,
  }
}
