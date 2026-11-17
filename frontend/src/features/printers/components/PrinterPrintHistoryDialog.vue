<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { getPrintJobs } from '../api/getPrintJobs'
import { formatDateOrDash, formatDateTimeOrEmpty } from '@/core/utils/dates'
import { HelpButton } from '@/shared/help'

import type { PrinterResponse } from '../types/printerResponse'
import type { PrintJobResponse } from '../types/printJobResponse'

const props = defineProps<{
  printer: PrinterResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

/** The dialog has no paginator and shows at most this many print jobs. */
const PRINT_HISTORY_LIMIT = 200

const { t, te } = useI18n()

const loading = ref(false)
const jobs = ref<PrintJobResponse[]>([])

function classifierLabel(classifier: string): string {
  const labelKey = `printLabels.classifiers.${classifier}`
  if (te(labelKey)) return t(labelKey)
  const docketKey = `printDockets.classifiers.${classifier}`
  if (te(docketKey)) return t(docketKey)
  const reportKey = `reports.classifiers.${classifier}`
  if (te(reportKey)) return t(reportKey)
  return classifier
}

/** An auto-print shows as printing from its claim until the printer answered. */
function statusSeverity(status: PrintJobResponse['status']): 'success' | 'info' | 'danger' {
  if (status === 'sent') return 'success'
  if (status === 'printing') return 'info'
  return 'danger'
}

watch(visible, async (open) => {
  if (!open || !props.printer) return
  loading.value = true
  try {
    const result = await getPrintJobs({ printer_id: props.printer.id, limit: PRINT_HISTORY_LIMIT })
    jobs.value = result.items
  } finally {
    loading.value = false
  }
})

watch(
  () => props.printer,
  () => {
    jobs.value = []
  },
)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-full)' }"
    :draggable="false"
  >
    <template #header>
      <div class="history-header">
        <span class="p-dialog-title">{{
          printer ? `${t('printers.history.title')}, ${printer.name}` : t('printers.history.title')
        }}</span>
        <span class="history-help">
          <HelpButton slug="resources/printers" anchor="history" icon="mdi mdi-help" rounded />
        </span>
      </div>
    </template>
    <div v-if="loading" class="loading-state">
      <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
    </div>
    <div v-else-if="jobs.length === 0" class="empty-note">
      {{ t('printers.history.empty') }}
    </div>
    <table v-else class="history-table">
      <thead>
        <tr>
          <th>{{ t('printers.history.columns.classifier') }}</th>
          <th>{{ t('printers.history.columns.root') }}</th>
          <th>{{ t('printers.history.columns.status') }}</th>
          <th>{{ t('printers.history.columns.copies') }}</th>
          <th>{{ t('printers.history.columns.trigger') }}</th>
          <th>{{ t('printers.history.columns.actor') }}</th>
          <th>{{ t('printers.history.columns.created') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="job in jobs"
          :key="job.id"
          :class="{ 'row-sent': job.status === 'sent' }"
        >
          <td>
            <strong>{{ classifierLabel(job.classifier) }}</strong>
          </td>
          <td>{{ job.root_type }} #{{ job.root_id }}</td>
          <td>
            <Tag
              :value="t(`printers.history.statuses.${job.status}`)"
              :severity="statusSeverity(job.status)"
              v-tooltip.top="job.status === 'failed' ? (job.error_message ?? undefined) : undefined"
            />
          </td>
          <td class="num-cell">{{ job.copies }}</td>
          <td>
            <Tag
              :value="t(`printers.history.triggers.${job.trigger}`)"
              :severity="job.trigger === 'auto' ? 'info' : 'secondary'"
            />
          </td>
          <td>{{ job.actor_full_name }}</td>
          <td :title="formatDateTimeOrEmpty(job.created)">
            {{ formatDateOrDash(job.created) }}
          </td>
        </tr>
      </tbody>
    </table>
  </Dialog>
</template>

<style scoped lang="scss">
.history-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.history-help :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  font-size: var(--font-size-2xl);
  color: var(--p-text-muted-color);
}

.empty-note {
  padding: var(--space-5) 0;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);

  th {
    text-align: left;
    padding: var(--space-1) var(--space-3);
    color: var(--p-text-muted-color);
    font-weight: 600;
    font-size: var(--font-size-xs);
    white-space: nowrap;
    border-bottom: 1px solid var(--p-content-border-color);
  }

  td {
    padding: var(--space-2) var(--space-3);
    vertical-align: middle;
    white-space: nowrap;
    border-bottom: 1px solid var(--p-content-border-color);
  }

  .p-dark & td {
    border-bottom-color: var(--p-surface-800);
  }
}

.row-sent td {
  opacity: 0.6;
}

.num-cell {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
