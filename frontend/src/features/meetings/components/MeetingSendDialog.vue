<script setup lang="ts">
import { computed, nextTick, ref, useId, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import type { AppLocale } from '@/core/i18n'
import { LOCALE_MESSAGES, localeEndonym } from '@/core/i18n/localeMessages'
import { formatISODate, formatISODateTime } from '@/core/utils/dates'
import { apiErrorStatus, extractApiError } from '@/core/utils/errors'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { HelpDrawer } from '@/shared/help'
import { sanitizeMailHtml } from '@/shared/utils/sanitizeMailHtml'
import { sendMeetingNotes } from '../api/meetingsApi'
import type { BuildMeetingNotes } from '../composables/useMeetingNotesPdf'
import { useMeetingSend } from '../composables/useMeetingSend'
import type {
  MeetingIssueResponse,
  MeetingRecipientSourceResponse,
  MeetingRecipientSuggestionResponse,
  MeetingResponse,
} from '../types/meetingResponse'
import { formatMegabytes } from '../utils/meetingNotesMail'
import { issueLabelText, sendIssuedOn } from '../utils/meetingNotesReport'
import MeetingRecipientField from './MeetingRecipientField.vue'

/**
 * Sends the meeting notes as a PDF to the customer: To and CC as chips with
 * the suggested addresses (the attendees and the contacts that receive
 * meeting notes ticked), the subject and text from the admin's meeting
 * notes template in the chosen language, and the PDF with or without the
 * todos and the internal cards. The meeting's documents go along only while
 * they fit next to the PDF under the attachment limit, and the dialog names
 * the ones left out. The PDF carries the next issue. A refusal of the
 * server, such as notes changed meanwhile, attachments over the limit or a
 * mail server that refused the mail, shows in the footer and nothing is
 * recorded. Sending needs write:meetings and send:mail.
 */
const props = defineProps<{
  meeting: MeetingResponse
  issue: MeetingIssueResponse | null
  build: BuildMeetingNotes
}>()

const emit = defineEmits<{
  sent: []
  /** The notes changed since the PDF was built, so the page reads them again. */
  outdated: []
}>()

const visible = defineModel<boolean>('visible', { default: false })
const explainVisible = ref(false)

const { t } = useI18n()
const uid = useId()
const toast = useAppToast()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const bodyRef = useTemplateRef<HTMLDivElement>('bodyRef')
const toField = useTemplateRef<{ commit: () => void }>('toField')
const ccField = useTemplateRef<{ commit: () => void }>('ccField')

async function setBody(html: string): Promise<void> {
  await nextTick()
  if (bodyRef.value) bodyRef.value.innerHTML = sanitizeMailHtml(html)
}

const send = useMeetingSend({
  visible,
  meeting: () => props.meeting,
  issue: () => props.issue,
  build: () => props.build,
  setBody: (html) => void setBody(html),
})
const { to, cc, suggestions, locale, subject, includeTodos, includeInternal, attachDocuments, pdf, fit } = send

// The body element mounts with the dialog's content, after the template may have arrived.
watch(bodyRef, (element) => {
  if (element) element.innerHTML = sanitizeMailHtml(send.body.value)
})

const sending = ref(false)
const errorMessage = ref('')
watch(visible, (open) => {
  if (open) errorMessage.value = ''
})

const canSend = computed(() => hasPermission(Permission.WRITE_MEETINGS) && hasPermission(Permission.SEND_MAIL))
const sendBlocked = computed(() => missing(Permission.WRITE_MEETINGS, Permission.SEND_MAIL))

const languageOptions = (Object.keys(LOCALE_MESSAGES) as AppLocale[]).map((value) => ({
  value,
  label: localeEndonym(value),
}))

const issueText = computed(() =>
  props.issue ? issueLabelText(props.issue.send, sendIssuedOn(), t, formatISODate) : '',
)

const changesSinceSend = computed(() => {
  const issue = props.issue
  if (!issue?.last_sent_at) return 0
  return issue.changed_card_ids.length + issue.added_card_ids.length + issue.removed_card_ids.length
})

function sourceLabel(source: MeetingRecipientSourceResponse): string {
  if (source.kind === 'attendee' && source.attendee_status) {
    return t('meetings.sendDialog.sources.attendeeWithStatus', {
      status: t(`meetings.attendees.status.${source.attendee_status}`),
    })
  }
  return t(`meetings.sendDialog.sources.${source.kind}`)
}

function sourcesOf(entry: MeetingRecipientSuggestionResponse): string {
  return [...new Set(entry.sources.map(sourceLabel))].join(', ')
}

const pdfLabel = computed(() => {
  if (send.pdfError.value) return t('meetings.sendDialog.pdfFailed')
  if (!pdf.value) return t('meetings.sendDialog.pdfBuilding')
  return formatMegabytes(pdf.value.pdf.size)
})

const leftOutText = computed(() =>
  fit.value.leftOut.map((file) => `${file.name} (${formatMegabytes(file.size)})`).join(', '),
)

function onBodyInput(event: Event): void {
  send.onBodyInput((event.target as HTMLDivElement).innerHTML)
}

async function onSend(): Promise<void> {
  if (sending.value) return
  toField.value?.commit()
  ccField.value?.commit()
  errorMessage.value = ''
  if (!to.value.length) {
    errorMessage.value = t('meetings.sendDialog.noRecipients')
    return
  }
  sending.value = true
  try {
    const built = await send.currentPdf()
    if (!built) {
      errorMessage.value = t('meetings.sendDialog.pdfFailed')
      return
    }
    await sendMeetingNotes(
      props.meeting.id,
      {
        pdf: built.pdf,
        fileName: built.fileName,
        language: built.locale,
        reportVersion: __APP_VERSION__,
        options: built.options,
        cards: built.cards,
        issueNumber: built.label.issue_number,
      },
      {
        to: to.value,
        cc: cc.value,
        subject: subject.value.trim(),
        // Sanitized again, since a paste can bring anything into the editable body.
        htmlBody: sanitizeMailHtml(send.body.value),
        attachFileIds: send.attachedIds.value,
      },
    )
    const count = to.value.length + cc.value.length
    toast.success(props.meeting.meeting_number, t('meetings.sendDialog.sent', { count }, count))
    visible.value = false
    emit('sent')
  } catch (err) {
    const message = extractApiError(err) ?? t('meetings.errors.unknown')
    if (apiErrorStatus(err) === 409) {
      errorMessage.value = t('meetings.printDialog.outdated', { reason: message })
      emit('outdated')
    } else {
      errorMessage.value = message
    }
  } finally {
    sending.value = false
  }
}

const lastSentAt = computed(() => (props.issue?.last_sent_at ? formatISODateTime(props.issue.last_sent_at) : ''))
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-lg)' }"
    data-testid="meeting-send-dialog"
  >
    <template #header>
      <div class="send-header">
        <span class="p-dialog-title">{{ t('meetings.sendDialog.title') }}</span>
        <Button
          type="button"
          class="send-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('meetings.sendDialog.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('meetings.sendDialog.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div class="send-form">
      <Message v-if="changesSinceSend" severity="warn" size="small" data-testid="meeting-send-changes">
        {{ t('meetings.sendDialog.changedSince', { count: changesSinceSend, at: lastSentAt }, changesSinceSend) }}
      </Message>

      <fieldset class="dialog-section">
        <legend>{{ t('meetings.sendDialog.recipients') }}</legend>
        <div class="field">
          <label :id="`${uid}-to-label`" :for="`${uid}-to`">{{ t('mail.compose.to') }}</label>
          <MeetingRecipientField
            ref="toField"
            v-model="to"
            :input-id="`${uid}-to`"
            :label-id="`${uid}-to-label`"
            :name-of="send.nameOf"
            :placeholder="t('meetings.sendDialog.addAddress')"
            data-testid="meeting-send-to"
          />
        </div>
        <div v-if="suggestions.length" class="field">
          <span class="suggestions-caption">{{ t('meetings.sendDialog.suggested') }}</span>
          <div class="suggestions" data-testid="meeting-send-suggestions">
            <div v-for="entry in suggestions" :key="entry.email" class="checkbox-field">
              <Checkbox
                :model-value="send.isSuggestionOn(entry)"
                :input-id="`${uid}-suggestion-${entry.email}`"
                binary
                :data-testid="`meeting-send-suggestion-${entry.email}`"
                @update:model-value="(on: boolean) => send.toggleSuggestion(entry, on)"
              />
              <label :for="`${uid}-suggestion-${entry.email}`">
                {{ entry.name || entry.email }}
                <span class="text-muted">
                  <template v-if="entry.name">{{ entry.email }} · </template>{{ sourcesOf(entry) }}
                </span>
              </label>
            </div>
          </div>
          <small class="hint">{{ t('meetings.sendDialog.suggestedHint') }}</small>
        </div>
        <div class="form-grid">
          <div class="field">
            <label :id="`${uid}-cc-label`" :for="`${uid}-cc`">{{ t('mail.compose.cc') }}</label>
            <MeetingRecipientField
              ref="ccField"
              v-model="cc"
              :input-id="`${uid}-cc`"
              :label-id="`${uid}-cc-label`"
              :name-of="send.nameOf"
              :placeholder="t('meetings.sendDialog.addAddress')"
              data-testid="meeting-send-cc"
            />
          </div>
          <div class="field">
            <span :id="`${uid}-language`">{{ t('reports.export.language') }}</span>
            <SelectButton
              v-model="locale"
              :options="languageOptions"
              option-label="label"
              option-value="value"
              :allow-empty="false"
              :aria-labelledby="`${uid}-language`"
              data-testid="meeting-send-language"
            />
          </div>
        </div>
      </fieldset>

      <fieldset class="dialog-section">
        <legend>{{ t('meetings.sendDialog.message') }}</legend>
        <div class="field">
          <label :for="`${uid}-subject`">{{ t('mail.compose.subject') }}</label>
          <InputText
            :id="`${uid}-subject`"
            v-model="subject"
            maxlength="500"
            autocomplete="off"
            fluid
            data-testid="meeting-send-subject"
          />
        </div>
        <div class="field">
          <span :id="`${uid}-body`">{{ t('meetings.sendDialog.text') }}</span>
          <div
            ref="bodyRef"
            class="send-body"
            contenteditable="true"
            role="textbox"
            aria-multiline="true"
            :aria-labelledby="`${uid}-body`"
            data-testid="meeting-send-body"
            @input="onBodyInput"
          />
          <small class="hint">{{ t('meetings.sendDialog.textHint') }}</small>
        </div>
      </fieldset>

      <fieldset class="dialog-section">
        <legend>{{ t('meetings.sendDialog.attachment') }}</legend>
        <div class="attachment" data-testid="meeting-send-pdf">
          <i class="mdi mdi-file-pdf-box" aria-hidden="true" />
          <span class="attachment-name">{{ pdf?.fileName ?? `${meeting.meeting_number}.pdf` }}</span>
          <span class="text-muted">{{ issueText }} · {{ pdfLabel }}</span>
        </div>
        <Message v-if="send.pdfTooLarge.value" severity="warn" size="small" data-testid="meeting-send-pdf-too-large">
          {{ t('meetings.sendDialog.pdfTooLarge', { limit: send.limitMb.value }) }}
        </Message>
        <div class="checkbox-field">
          <Checkbox v-model="includeTodos" :input-id="`${uid}-todos`" binary data-testid="meeting-send-include_todos" />
          <label :for="`${uid}-todos`">{{ t('meetings.report.options.includeTodos') }}</label>
        </div>
        <div class="checkbox-field">
          <Checkbox
            v-model="includeInternal"
            :input-id="`${uid}-internal`"
            binary
            data-testid="meeting-send-include_internal"
          />
          <label :for="`${uid}-internal`">
            {{ t('meetings.report.options.includeInternal') }}
            <span v-if="send.internalCount.value && !includeInternal" class="text-muted">
              {{ t('meetings.sendDialog.internalLeftOut', { count: send.internalCount.value }, send.internalCount.value) }}
            </span>
          </label>
        </div>
        <div class="checkbox-field">
          <Checkbox
            v-model="attachDocuments"
            :input-id="`${uid}-documents`"
            binary
            :disabled="!send.documents.value.length"
            data-testid="meeting-send-documents"
          />
          <label :for="`${uid}-documents`">
            {{ t('meetings.sendDialog.attachDocuments') }}
            <span class="text-muted">({{ send.documents.value.length }})</span>
          </label>
        </div>
        <template v-if="attachDocuments">
          <ul v-if="fit.attached.length" class="attached" data-testid="meeting-send-attached">
            <li v-for="file in fit.attached" :key="file.id">{{ file.name }} · {{ formatMegabytes(file.size) }}</li>
          </ul>
          <Message v-if="fit.leftOut.length" severity="warn" size="small" data-testid="meeting-send-left-out">
            {{ t('meetings.sendDialog.leftOut', { limit: send.limitMb.value, files: leftOutText }) }}
          </Message>
        </template>
      </fieldset>
    </div>

    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error" data-testid="meeting-send-error">
        {{ errorMessage }}
      </Message>
      <span v-else class="footer-hint hint">{{ t('meetings.sendDialog.footerHint') }}</span>
      <Button :label="t('common.cancel')" severity="secondary" text :disabled="sending" @click="visible = false" />
      <span v-tooltip.top="sendBlocked || undefined">
        <Button
          :label="t('meetings.sendDialog.submit')"
          icon="mdi mdi-send"
          :loading="sending"
          :disabled="!canSend || !issue || sending"
          data-testid="meeting-send-submit"
          @click="onSend"
        />
      </span>
    </template>
  </Dialog>
  <HelpDrawer v-model:visible="explainVisible" slug="workspace/meeting-distribution" />
</template>

<style scoped lang="scss">
.send-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.send-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.send-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.suggestions-caption {
  font-size: var(--font-size-sm);
}

.suggestions {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.checkbox-field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.send-body {
  min-height: 12rem;
  max-height: 40vh;
  overflow-y: auto;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
  background: var(--p-content-background);
  line-height: 1.5;
  outline: none;

  &:focus {
    border-color: var(--p-primary-color);
  }

  :deep(p) {
    margin: 0 0 0.5em;
  }
}

.attachment {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;

  .mdi {
    font-size: var(--font-size-lg);
    color: var(--p-red-500);
  }
}

.attachment-name {
  font-weight: 600;
}

.attached {
  margin: 0;
  padding-left: var(--space-5);
}

.footer-error,
.footer-hint {
  flex: 1 1 auto;
  align-self: center;
  margin-right: auto;
}
</style>
