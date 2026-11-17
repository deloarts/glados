<script setup lang="ts">
/**
 * The controls bar of a single QA task: navigation, the task's lifecycle
 * (start and record) and its documents (photo upload and the report). The
 * parent owns the completion dialog and refetches the order on `started`.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePermissions } from '@/core/composables/usePermissions'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { Permission } from '@/core/auth/permissions'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { ProductionOrderStartDialog } from '@/features/production'
import { useProductionOrderFilesStore } from '@/features/production'
import { useProductionQueueStore } from '@/features/production'
import { inspectionReportSpec } from '@/features/production'
import { ReportExportDialog, useReportExport } from '@/shared/reports'
import { HelpButton } from '@/shared/help'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import { EVIDENCE_ACCEPT } from '../utils/evidenceFiles'

import type { LotResponse, LotStepResponse, ProductionOrderResponse } from '@/features/production'

const props = defineProps<{
  order: ProductionOrderResponse | null
  steps: LotStepResponse[]
  /** The lot of the order, whose inspection report the page offers. */
  lot: Pick<LotResponse, 'id' | 'public_id' | 'lot_number'> | null
}>()

const emit = defineEmits<{
  back: []
  record: []
  started: []
}>()

const { t } = useI18n()
const { hasPermission } = usePermissions()
const { withErrorToast } = useErrorToast()
const hostStore = useHostStore()
const currentUserStore = useCurrentUserStore()
const evidenceStore = useProductionOrderFilesStore()
const queueStore = useProductionQueueStore()

const isInspectionTask = computed(() => props.steps.some((s) => s.role === 'inspection'))
const isTerminal = computed(
  () => props.order?.status === 'completed' || props.order?.status === 'canceled',
)

const canRecord = computed(() => hasPermission(Permission.WRITE_INSPECTIONS))
// A result is recorded only while the order runs, as the backend offers it;
// a queued task is started first.
const recordOffered = computed(() => hasAction(props.order, 'record_completion'))
// Starting an inspection order needs both, as the backend enforces.
const canStartPermission = computed(
  () => canRecord.value && hasPermission(Permission.WRITE_PRODUCTION_ORDERS),
)

// ── Starting ──────────────────────────────────────────────────────────

const isStartable = computed(
  () => props.order?.status === 'queued' || props.order?.status === 'paused',
)

// A pure-manual position never gets a machine, so only a machine position
// with neither a machine nor a pool blocks the start.
const needsMachineOrPool = computed(() => {
  if (!props.order) return false
  const isManual =
    props.steps.length > 0 && props.steps.every((s) => !s.fabrication_method_requires_machine)
  return !isManual && props.order.machine_id === null && props.order.machine_pool_id == null
})

const startBlocked = computed(
  () =>
    !isInspectionTask.value ||
    !canStartPermission.value ||
    props.order?.can_start !== true ||
    needsMachineOrPool.value,
)

// Most actionable message first.
const startBlockedTooltip = computed<string | undefined>(() => {
  if (!canStartPermission.value) return t('productionQa.detail.startPermissionTooltip')
  if (needsMachineOrPool.value) return t('productionQueue.card.noMachineTooltip')
  if (props.order?.can_start !== true) return t('productionQa.detail.notStartable')
  return undefined
})

const showStart = ref(false)
const starting = ref(false)

// The dialog is only needed when there is something to ask: an operator on
// a shared account, or a machine for an order assigned to a pool.
async function onStart(): Promise<void> {
  if (!props.order) return
  const needsMachineSelection =
    props.order.machine_pool_id != null && props.order.machine_id === null
  if (currentUserStore.isSharedAccount || needsMachineSelection) {
    showStart.value = true
    return
  }
  const id = props.order.id
  starting.value = true
  try {
    await withErrorToast(() => queueStore.start(id), {
      summary: t('productionQueue.card.startError'),
    })
    emit('started')
  } finally {
    starting.value = false
  }
}

// ── Documents ─────────────────────────────────────────────────────────

const documentInput = ref<HTMLInputElement | null>(null)
const uploadingDocuments = ref(false)
const canAddDocument = computed(
  () => canRecord.value && isInspectionTask.value && !isTerminal.value,
)
// The tooltips of the disabled Record Result and Add Document buttons when a
// permission is what blocks them.
const recordPermissionBlocked = computed(() =>
  canRecord.value ? '' : t('productionQa.detail.recordPermissionTooltip'),
)

// Photos and reports land in the evidence category the evidence card lists.
async function onDocumentsPicked(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement
  const picked = Array.from(input.files ?? [])
  // Cleared so picking the same file again still fires a change.
  input.value = ''
  if (!props.order || picked.length === 0) return
  const id = props.order.id
  uploadingDocuments.value = true
  try {
    for (const file of picked) {
      await withErrorToast(() => evidenceStore.upload(id, file, 'measurement_report'), {
        summary: t('productionQa.detail.addDocumentError', { name: file.name }),
      })
    }
  } finally {
    uploadingDocuments.value = false
  }
}

// ── Report ────────────────────────────────────────────────────────────

const { visible: reportVisible, report, open: openReport } = useReportExport()

function openInspectionReport(): void {
  const lot = props.lot
  if (lot) openReport(inspectionReportSpec(lot, t('production.lots.report.title', { lot: lot.lot_number })))
}
</script>

<template>
  <ControlsBar>
    <template #start>
      <Button
        icon="mdi mdi-arrow-left"
        :label="t('productionQa.detail.back')"
        severity="contrast"
        text
        @click="emit('back')"
      />

      <template v-if="order && !isTerminal">
        <Divider layout="vertical" />

        <!-- Each span carries the tooltip, since a disabled button shows
             none of its own. -->
        <span v-if="isStartable" v-tooltip.bottom="startBlockedTooltip">
          <Button
            :label="
              order.status === 'paused' ? t('productionQa.detail.resume') : t('productionQa.detail.start')
            "
            icon="mdi mdi-play-circle-outline"
            severity="contrast"
            text
            :loading="starting"
            :disabled="startBlocked"
            data-testid="qa-start"
            @click="onStart"
          />
        </span>
        <span v-if="recordOffered" v-tooltip.bottom="recordPermissionBlocked || undefined">
          <Button
            :label="t('productionQa.detail.record')"
            icon="mdi mdi-clipboard-check-outline"
            severity="contrast"
            text
            :disabled="!canRecord || !isInspectionTask"
            data-testid="qa-record"
            @click="emit('record')"
          />
        </span>
      </template>

      <template v-if="order">
        <Divider layout="vertical" />

        <span
          v-if="hostStore.storageEnabled && !isTerminal"
          v-tooltip.bottom="recordPermissionBlocked || undefined"
        >
          <Button
            :label="t('productionQa.detail.addDocument')"
            icon="mdi mdi-camera-plus-outline"
            severity="contrast"
            text
            :loading="uploadingDocuments"
            :disabled="!canAddDocument"
            data-testid="qa-add-document"
            @click="documentInput?.click()"
          />
        </span>
        <Button
          :label="t('production.lots.report.print')"
          icon="mdi mdi-file-certificate-outline"
          severity="contrast"
          text
          :disabled="!lot"
          data-testid="qa-inspection-report"
          @click="openInspectionReport"
        />
      </template>
    </template>
    <template #handbook>
      <HelpButton rounded />
    </template>
  </ControlsBar>

  <input
    ref="documentInput"
    type="file"
    aria-hidden="true"
    tabindex="-1"
    class="hidden-input"
    :accept="EVIDENCE_ACCEPT"
    multiple
    data-testid="qa-document-input"
    @change="onDocumentsPicked"
  />

  <ProductionOrderStartDialog v-model:visible="showStart" :order="order" @started="emit('started')" />

  <ReportExportDialog v-model:visible="reportVisible" :report="report">
    <template #handbook>
      <HelpButton slug="production/inspection-report" icon="mdi mdi-help" rounded />
    </template>
  </ReportExportDialog>
</template>

<style scoped lang="scss">
.hidden-input {
  display: none;
}
</style>
