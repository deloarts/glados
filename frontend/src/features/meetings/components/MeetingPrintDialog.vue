<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { i18n } from '@/core/i18n'
import type { AppLocale } from '@/core/i18n'
import { LOCALE_MESSAGES, localeEndonym } from '@/core/i18n/localeMessages'
import { formatISODate } from '@/core/utils/dates'
import { apiErrorStatus, extractApiError } from '@/core/utils/errors'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { HelpDrawer } from '@/shared/help'
import { downloadPdf, getDocumentPrinters } from '@/shared/reports'
import type { DocumentPrinter } from '@/shared/reports'
import { downloadMeetingNotes, printMeetingNotes } from '../api/meetingsApi'
import type { BuildMeetingNotes, BuiltMeetingNotes } from '../composables/useMeetingNotesPdf'
import type { MeetingIssueResponse, MeetingResponse } from '../types/meetingResponse'
import {
  DEFAULT_MEETING_NOTES_OPTIONS,
  MEETING_NOTES_OPTIONS,
  issueLabelText,
  printIssuedOn,
} from '../utils/meetingNotesReport'

/**
 * Prints or downloads the meeting notes as a PDF in a chosen language,
 * with or without the todos, the internal cards and the list of documents.
 * The PDF carries the issue a print carries now: the last issue while the
 * notes are unchanged since it was sent, otherwise a draft. The server
 * checks the cards the PDF was built from and journals it with a snapshot;
 * when a card changed meanwhile it names the card, the page reads the notes
 * again and the next press builds the PDF from them. Printing needs the
 * print permission.
 */
const props = defineProps<{
  meeting: MeetingResponse
  issue: MeetingIssueResponse | null
  build: BuildMeetingNotes
}>()

const emit = defineEmits<{
  /** A print or download was journaled. */
  done: []
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

const MAX_COPIES = 10

const locale = ref<AppLocale>('enGB')
const options = ref<Record<string, boolean>>({ ...DEFAULT_MEETING_NOTES_OPTIONS })
const printers = ref<DocumentPrinter[]>([])
const printersLoading = ref(false)
const printerId = ref<number | null>(null)
const copies = ref(1)
const twoSided = ref(false)
const busy = ref<'download' | 'print' | null>(null)
const errorMessage = ref('')

const languageOptions = (Object.keys(LOCALE_MESSAGES) as AppLocale[]).map((value) => ({
  value,
  label: localeEndonym(value),
}))

const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))
const printBlocked = computed(() => missing(Permission.PRINT_DOCUMENTS))
const printer = computed(() => printers.value.find((entry) => entry.id === printerId.value) ?? null)
// A raw connection sends the bytes and nothing else, so it cannot ask for two sides.
const twoSidedAvailable = computed(() => printer.value?.transport === 'ipp')
const printerOptions = computed(() =>
  printers.value.map((entry) => ({
    value: entry.id,
    label: entry.location ? `${entry.name} (${entry.location})` : entry.name,
  })),
)

const internalCount = computed(() => props.meeting.cards.filter((card) => card.internal).length)
const issueText = computed(() => {
  const issue = props.issue
  if (!issue) return ''
  return issueLabelText(issue.print, printIssuedOn(issue), t, formatISODate)
})

async function loadPrinters(): Promise<void> {
  printersLoading.value = true
  try {
    printers.value = await getDocumentPrinters()
  } catch {
    printers.value = []
  } finally {
    printersLoading.value = false
  }
  printerId.value = printers.value[0]?.id ?? null
}

watch(
  visible,
  (open) => {
    if (!open) return
    locale.value = i18n.global.locale.value as AppLocale
    options.value = { ...DEFAULT_MEETING_NOTES_OPTIONS }
    copies.value = 1
    twoSided.value = false
    errorMessage.value = ''
    if (canPrint.value) void loadPrinters()
  },
  { immediate: true },
)

async function buildPdf(): Promise<BuiltMeetingNotes | null> {
  const issue = props.issue
  if (!issue) return null
  return props.build({
    locale: locale.value,
    options: options.value,
    label: issue.print,
    issuedOn: printIssuedOn(issue),
  })
}

function buildParams(built: BuiltMeetingNotes) {
  return {
    pdf: built.pdf,
    fileName: built.fileName,
    language: built.locale,
    reportVersion: __APP_VERSION__,
    options: built.options,
    cards: built.cards,
    issueNumber: built.label.issue_number,
  }
}

function fail(err: unknown): void {
  const message = extractApiError(err) ?? t('meetings.errors.unknown')
  if (apiErrorStatus(err) === 409) {
    errorMessage.value = t('meetings.printDialog.outdated', { reason: message })
    emit('outdated')
  } else {
    errorMessage.value = message
  }
}

async function download(): Promise<void> {
  if (busy.value) return
  busy.value = 'download'
  errorMessage.value = ''
  try {
    const built = await buildPdf()
    if (!built) return
    // The server journals the download first, so a PDF of outdated notes is never saved.
    await downloadMeetingNotes(props.meeting.id, buildParams(built), built.label.draft)
    downloadPdf(built.pdf, built.fileName)
    toast.success(props.meeting.meeting_number, t('meetings.printDialog.downloaded'))
    visible.value = false
    emit('done')
  } catch (err) {
    fail(err)
  } finally {
    busy.value = null
  }
}

async function print(): Promise<void> {
  const chosen = printer.value
  if (busy.value || !chosen) return
  busy.value = 'print'
  errorMessage.value = ''
  try {
    const built = await buildPdf()
    if (!built) return
    const job = await printMeetingNotes(props.meeting.id, buildParams(built), built.label.draft, {
      printerId: chosen.id,
      copies: copies.value,
      twoSided: twoSided.value && twoSidedAvailable.value,
    })
    if (job.status !== 'sent') {
      errorMessage.value = job.error_message ?? t('reports.export.printFailed')
      return
    }
    toast.success(props.meeting.meeting_number, t('reports.export.printSent', { printer: chosen.name }))
    visible.value = false
    emit('done')
  } catch (err) {
    fail(err)
  } finally {
    busy.value = null
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-sm)' }"
    data-testid="meeting-print-dialog"
  >
    <template #header>
      <div class="print-header">
        <span class="p-dialog-title">{{ t('meetings.printDialog.title') }}</span>
        <Button
          type="button"
          class="print-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('meetings.printDialog.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('meetings.printDialog.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div class="print-form">
      <p class="print-subject">{{ meeting.meeting_number }} · {{ meeting.name }}</p>
      <div v-if="issueText" class="print-issue" data-testid="meeting-print-issue">
        <span class="issue-caption">{{ t('meetings.report.issue') }}</span>
        <span>{{ issueText }}</span>
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
          data-testid="meeting-print-language"
        />
      </div>

      <div v-for="option in MEETING_NOTES_OPTIONS" :key="option.key" class="checkbox-field">
        <Checkbox
          v-model="options[option.key]"
          :input-id="`${uid}-${option.key}`"
          binary
          :data-testid="`meeting-print-${option.key}`"
        />
        <label :for="`${uid}-${option.key}`">
          {{ t(option.labelKey) }}
          <span v-if="option.key === 'include_internal' && internalCount" class="text-muted">
            {{ t('meetings.report.options.internalCount', { count: internalCount }, internalCount) }}
          </span>
        </label>
      </div>
      <small class="hint">{{ t('meetings.printDialog.hint') }}</small>

      <section v-if="canPrint" class="print-section">
        <h3 class="print-heading">{{ t('reports.export.printHeading') }}</h3>
        <Message v-if="!printersLoading && printers.length === 0" severity="info" :closable="false">
          {{ t('reports.export.noPrinters') }}
        </Message>
        <template v-else>
          <div class="field">
            <label :id="`${uid}-printer-label`" :for="`${uid}-printer`">{{ t('reports.export.printer') }}</label>
            <Select
              v-model="printerId"
              :input-id="`${uid}-printer`"
              :aria-labelledby="`${uid}-printer-label`"
              :options="printerOptions"
              option-label="label"
              option-value="value"
              :loading="printersLoading"
              fluid
              data-testid="meeting-print-printer"
            />
          </div>
          <div class="print-options">
            <div class="field">
              <label :for="`${uid}-copies`">{{ t('reports.export.copies') }}</label>
              <InputNumber
                v-model="copies"
                :input-id="`${uid}-copies`"
                :min="1"
                :max="MAX_COPIES"
                show-buttons
                :allow-empty="false"
                :input-style="{ width: '4rem' }"
              />
            </div>
            <div class="checkbox-field">
              <Checkbox v-model="twoSided" :input-id="`${uid}-two-sided`" binary :disabled="!twoSidedAvailable" />
              <label :for="`${uid}-two-sided`">{{ t('reports.export.twoSided') }}</label>
            </div>
          </div>
          <small v-if="printer && !twoSidedAvailable" class="hint">{{ t('reports.export.twoSidedRaw') }}</small>
        </template>
      </section>
    </div>

    <template #footer>
      <Message
        v-if="errorMessage"
        severity="error"
        size="small"
        class="footer-error"
        data-testid="meeting-print-error"
      >
        {{ errorMessage }}
      </Message>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="t('reports.export.download')"
        icon="mdi mdi-download"
        severity="secondary"
        :loading="busy === 'download'"
        :disabled="!issue || busy !== null"
        data-testid="meeting-print-download"
        @click="download"
      />
      <span v-tooltip.top="printBlocked || undefined">
        <Button
          :label="t('reports.export.print')"
          icon="mdi mdi-printer-outline"
          :loading="busy === 'print'"
          :disabled="!canPrint || !issue || !printer || busy !== null"
          data-testid="meeting-print-submit"
          @click="print"
        />
      </span>
    </template>
  </Dialog>
  <HelpDrawer v-model:visible="explainVisible" slug="workspace/meeting-distribution" />
</template>

<style scoped lang="scss">
.print-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.print-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.print-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.print-subject {
  margin: 0;
  font-weight: 600;
}

.print-issue {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.issue-caption {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.print-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.print-heading {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.print-options {
  display: flex;
  align-items: flex-end;
  gap: var(--space-5);
}

.checkbox-field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
