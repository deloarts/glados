<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { i18n } from '@/core/i18n'
import type { AppLocale } from '@/core/i18n'
import { LOCALE_MESSAGES, localeEndonym } from '@/core/i18n/localeMessages'
import { extractApiError } from '@/core/utils/errors'
import { safeStorage } from '@/core/utils/safeStorage'
import { getDocumentPrinters, printReport, recordReportDownload } from '../api'
import type { DocumentPrinter, ReportExportFacts } from '../api'
import type { ReportBranding, ReportOptionValues, ReportSpec } from '../types'
import { composeReport } from '../utils/composeReport'
import { downloadPdf, renderPdf } from '../utils/renderPdf'
import { reportFileName } from '../utils/reportLocale'

/**
 * Exports a report as a PDF in a chosen language, with the options the
 * report offers: downloaded, or sent to a document printer. Printing needs
 * the print permission and a saved record, since the print job is logged
 * against it. Every download and print of a saved record is written to its
 * export journal with the file's SHA-256. The last printer, the two-sided
 * choice and the options are
 * remembered in this browser. The `#handbook` slot puts the page's handbook
 * button in the header, since shared code cannot import the handbook
 * feature itself.
 */

const props = defineProps<{ report: ReportSpec | null }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const toast = useAppToast()
const { hasPermission } = usePermissions()
const brandingStore = usePublicBrandingStore()
const currentUserStore = useCurrentUserStore()

const STORAGE_KEY = 'glados.reportExport'
const MAX_COPIES = 10

interface Remembered {
  printerId: number | null
  twoSided: boolean
  options: Record<string, boolean>
}

function readRemembered(): Remembered {
  try {
    const raw = JSON.parse(safeStorage.get(STORAGE_KEY) ?? '{}') as Partial<Remembered>
    const options: Record<string, boolean> = {}
    if (raw.options && typeof raw.options === 'object') {
      for (const [key, value] of Object.entries(raw.options)) options[key] = value === true
    }
    return {
      printerId: typeof raw.printerId === 'number' ? raw.printerId : null,
      twoSided: raw.twoSided === true,
      options,
    }
  } catch {
    return { printerId: null, twoSided: false, options: {} }
  }
}

// Best effort only; a private window or blocked site data loses the choice.
function remember(change: Partial<Remembered>): void {
  const current = readRemembered()
  safeStorage.set(
    STORAGE_KEY,
    JSON.stringify({ ...current, ...change, options: { ...current.options, ...change.options } }),
  )
}

const locale = ref<AppLocale>(i18n.global.locale.value as AppLocale)
const printers = ref<DocumentPrinter[]>([])
const printersLoading = ref(false)
const printerId = ref<number | null>(null)
const copies = ref(1)
const twoSided = ref(false)
const optionValues = ref<Record<string, boolean>>({})
const busy = ref<'download' | 'print' | null>(null)

const languageOptions = (Object.keys(LOCALE_MESSAGES) as AppLocale[]).map((value) => ({
  value,
  label: localeEndonym(value),
}))

const reportOptions = computed(() => props.report?.options ?? [])
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))
// Without print:documents the printer section stays away, since the
// printers are not loaded, but Print stays visible, disabled, naming it.
const { missing } = useMissingPermission()
const printBlocked = computed(() => missing(Permission.PRINT_DOCUMENTS))
const printTarget = computed(() => props.report?.printTarget ?? null)
const printer = computed(() => printers.value.find((p) => p.id === printerId.value) ?? null)
// A raw connection sends the bytes and nothing else, so it cannot ask for two sides.
const twoSidedAvailable = computed(() => printer.value?.transport === 'ipp')

const printerOptions = computed(() =>
  printers.value.map((p) => ({
    value: p.id,
    label: p.location ? `${p.name} (${p.location})` : p.name,
  })),
)

async function loadPrinters(): Promise<void> {
  printersLoading.value = true
  try {
    printers.value = await getDocumentPrinters()
  } catch {
    printers.value = []
  } finally {
    printersLoading.value = false
  }
  const remembered = readRemembered()
  const known = printers.value.some((p) => p.id === remembered.printerId)
  printerId.value = known ? remembered.printerId : (printers.value[0]?.id ?? null)
  twoSided.value = remembered.twoSided
}

watch(visible, (open) => {
  if (!open) return
  locale.value = i18n.global.locale.value as AppLocale
  copies.value = 1
  const remembered = readRemembered().options
  optionValues.value = Object.fromEntries(reportOptions.value.map((o) => [o.key, remembered[o.key] ?? false]))
  if (canPrint.value && printTarget.value) void loadPrinters()
})

// Read when exporting, so a renamed company or a new logo shows at once.
function branding(): ReportBranding {
  return {
    appName: brandingStore.appName,
    companyName: brandingStore.companyName,
    companyLogoUrl: brandingStore.companyLogoUrl,
    domain: brandingStore.domain,
    exportedBy: currentUserStore.user?.full_name ?? '',
  }
}

function facts(): ReportExportFacts {
  return {
    language: locale.value,
    options: { ...optionValues.value },
    reportVersion: __APP_VERSION__,
    engineVersion: props.report?.engineVersion ?? null,
  }
}

async function render(): Promise<Blob | null> {
  const report = props.report
  if (!report) return null
  const options: ReportOptionValues = { ...optionValues.value }
  remember({ options })
  return renderPdf(await composeReport(report, branding(), locale.value, options))
}

async function download(): Promise<void> {
  const report = props.report
  if (!report || busy.value) return
  busy.value = 'download'
  try {
    const blob = await render()
    if (blob) downloadPdf(blob, reportFileName(report.title, new Date()))
    visible.value = false
    const target = printTarget.value
    if (blob && target) {
      recordReportDownload(target, facts(), blob).catch(() =>
        toast.warn(report.title, t('reports.export.journalFailed')),
      )
    }
  } catch (e) {
    toast.error(report.title, extractApiError(e) ?? t('reports.export.renderFailed'))
  } finally {
    busy.value = null
  }
}

async function print(): Promise<void> {
  const report = props.report
  const target = printTarget.value
  const chosen = printer.value
  if (!report || !target || !chosen || busy.value) return
  busy.value = 'print'
  const sides = twoSided.value && twoSidedAvailable.value
  remember({ printerId: chosen.id, twoSided: twoSided.value })
  try {
    const blob = await render()
    if (!blob) return
    const job = await printReport(target, blob, { printerId: chosen.id, copies: copies.value, twoSided: sides }, facts())
    if (job.status !== 'sent') {
      toast.error(report.title, job.error_message ?? t('reports.export.printFailed'))
      return
    }
    if (job.attributes_substituted) {
      toast.warn(report.title, t('reports.export.printSubstituted', { printer: chosen.name }))
    } else {
      toast.success(report.title, t('reports.export.printSent', { printer: chosen.name }))
    }
    visible.value = false
  } catch (e) {
    toast.error(report.title, extractApiError(e) ?? t('reports.export.printFailed'))
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
    :breakpoints="{ '640px': '95vw' }"
    :pt="{ header: { 'data-testid': 'report-export-header' } }"
  >
    <!-- Own header row so the handbook button sits right of the title and
         left of the Dialog's own close icon. -->
    <template #header>
      <div class="export-header">
        <span class="p-dialog-title">{{ t('reports.export.title') }}</span>
        <span v-if="$slots.handbook" class="export-help" data-testid="report-export-help">
          <slot name="handbook" />
        </span>
      </div>
    </template>

    <div class="export-form" data-testid="report-export">
      <p class="export-subject">{{ report?.title }}</p>

      <div class="field">
        <span id="report-language-label">{{ t('reports.export.language') }}</span>
        <SelectButton
          v-model="locale"
          :options="languageOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="report-language-label"
          data-testid="report-language"
        />
      </div>

      <div v-for="option in reportOptions" :key="option.key" class="checkbox-field checkbox-field--option">
        <Checkbox
          v-model="optionValues[option.key]"
          :input-id="`report-option-${option.key}`"
          binary
          :data-testid="`report-option-${option.key}`"
        />
        <label :for="`report-option-${option.key}`">{{ t(option.labelKey) }}</label>
      </div>

      <section v-if="canPrint" class="export-print" data-testid="report-print-section">
        <h3 class="export-heading">{{ t('reports.export.printHeading') }}</h3>
        <Message v-if="!printTarget" severity="info" :closable="false" data-testid="report-print-unsaved">
          {{ t('reports.export.unsaved') }}
        </Message>
        <Message
          v-else-if="!printersLoading && printers.length === 0"
          severity="info"
          :closable="false"
          data-testid="report-no-printers"
        >
          {{ t('reports.export.noPrinters') }}
        </Message>
        <template v-else>
          <div class="field">
            <label id="report-printer-label" for="report-printer">{{ t('reports.export.printer') }}</label>
            <Select
              v-model="printerId"
              input-id="report-printer"
              aria-labelledby="report-printer-label"
              :options="printerOptions"
              option-label="label"
              option-value="value"
              :loading="printersLoading"
              fluid
              data-testid="report-printer"
            />
          </div>
          <div class="print-options">
            <div class="field">
              <label for="report-copies">{{ t('reports.export.copies') }}</label>
              <InputNumber
                v-model="copies"
                input-id="report-copies"
                :min="1"
                :max="MAX_COPIES"
                show-buttons
                :allow-empty="false"
                :input-style="{ width: '4rem' }"
                data-testid="report-copies"
              />
            </div>
            <div class="checkbox-field">
              <Checkbox
                v-model="twoSided"
                input-id="report-two-sided"
                binary
                :disabled="!twoSidedAvailable"
                data-testid="report-two-sided"
              />
              <label for="report-two-sided">{{ t('reports.export.twoSided') }}</label>
            </div>
          </div>
          <small v-if="printer && !twoSidedAvailable" class="hint">{{ t('reports.export.twoSidedRaw') }}</small>
        </template>
      </section>
    </div>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="t('reports.export.download')"
        icon="mdi mdi-download"
        severity="secondary"
        :loading="busy === 'download'"
        :disabled="!report || busy !== null"
        data-testid="report-download"
        @click="download"
      />
      <span v-tooltip.top="printBlocked || undefined">
        <Button
          :label="t('reports.export.print')"
          icon="mdi mdi-printer-outline"
          :loading="busy === 'print'"
          :disabled="!canPrint || !printTarget || !printer || busy !== null"
          data-testid="report-print"
          @click="print"
        />
      </span>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
// Fills the header row so the handbook button lands right before the
// Dialog's own close icon.
.export-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

// Matches the close button's 14px icon instead of the icon font's default.
.export-help :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.export-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.export-subject {
  margin: 0;
  font-weight: 600;
}

.export-print {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.export-heading {
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
  padding-bottom: var(--space-2);

  &--option {
    padding-bottom: 0;
  }
}
</style>
