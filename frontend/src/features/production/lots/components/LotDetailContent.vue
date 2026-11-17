<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { todayKey } from '@/core/utils/dates'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useUsersStore } from '@/core/stores/usersStore'
import { MadeItemDetailDialog } from '@/features/made-items'
import { BoughtItemDetailDialog } from '@/features/bought-items'
import { SourceItemDetailDialog } from '@/features/source-items'
import SourceItemDemandDetailDialog from '../../source-item-demands/components/SourceItemDemandDetailDialog.vue'
import LotMaterialSourceDialog from './LotMaterialSourceDialog.vue'
import LotRejectSourceDialog from './LotRejectSourceDialog.vue'
import ScrapPiecesDialog from '../../components/ScrapPiecesDialog.vue'
import { hasAction } from '@/core/utils/lifecycleActions'
import { hasInternalPosition } from '../utils/lotScrapEligibility'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { useLotStructureDraft } from '../composables/useLotStructureDraft'
import { useLotDetailDialogs } from '../composables/useLotDetailDialogs'
import { useMaterialSourceChange } from '../composables/useMaterialSourceChange'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { LiveResource } from '@/core/realtime/resources'
import { useLotRecordData } from '../composables/useLotRecordData'
import { useLotPrinting } from './lots-table/useLotPrinting'
import LotDetailHeader from './lot-detail/LotDetailHeader.vue'
import LotDetailRecordGrid from './lot-detail/LotDetailRecordGrid.vue'
import LotManagePositionsDock from './lot-detail/LotManagePositionsDock.vue'
import LotStepList from './LotStepList.vue'
import LotPositionGrouping from './LotPositionGrouping.vue'
import LotForceStatusConfirmDialog from './LotForceStatusConfirmDialog.vue'
import SourceItemDemandCreateDialog from './SourceItemDemandCreateDialog.vue'
import { buildLotStateSummary } from '../utils/lotStateSummary'
import { canDemandSourceItem } from '../utils/lotSourceEligibility'

import type { LotPrintClassifier } from './lots-table/useLotPrinting'
import { HelpButton } from '@/shared/help'
import { ReportExportDialog, useReportExport } from '@/shared/reports'
import { inspectionReportSpec } from '../utils/inspectionReport'

const props = withDefaults(
  defineProps<{
    lotId: number
    /** 'page' hides the header row; the standalone page renders those tags/actions in its own bars. */
    variant?: 'dialog' | 'page'
  }>(),
  { variant: 'dialog' },
)

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { withErrorToast } = useErrorToast()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const usersStore = useUsersStore()
const detailStore = useProductionLotDetailStore()

const canWrite = computed(() => hasPermission(Permission.WRITE_LOTS))
const canWriteOrders = computed(() => hasPermission(Permission.WRITE_ORDERS))
const canManage = computed(() => hasPermission(Permission.MANAGE_LOTS))
const canApprove = computed(() => hasPermission(Permission.MANAGE_LOTS))
// Scrapping is a production-order action, so it needs write:production_orders
// rather than a lot permission.
const canScrap = computed(() => hasPermission(Permission.WRITE_PRODUCTION_ORDERS))
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))

// Guards against a stale lot from a previous open, since the store is shared.
const lot = computed(() => (detailStore.lot?.id === props.lotId ? detailStore.lot : null))
// The structure is read-only once the lot no longer offers structure edits,
// as for a completed, canceled or scrapped lot.
const readonly = computed(() => !!lot.value && !hasAction(lot.value, 'edit_structure'))
const canScrapPosition = computed(() => !!lot.value && hasInternalPosition(lot.value))

// The step table and grouping chain edit a draft that Save writes in one
// request.
const structureDraft = useLotStructureDraft(lot)

async function saveStructureDraft(): Promise<void> {
  await withErrorToast(() => structureDraft.save(props.lotId), {
    summary: t('production.lots.editSteps.saveError'),
  })
}

const manageMode = ref(false)

function toggleManage(): void {
  manageMode.value = !manageMode.value
}

// Manage mode replaces the record, since the record cards would squeeze the
// editable surface out of the dialog's fixed height.
const showManage = computed(() => manageMode.value && canWrite.value)

// Manage mode re-hosts the Source card's actions, so these conditions must
// mirror LotRecordSource.vue and LotRecordSourceDemand.vue.
const { sourceChangeBlocked } = useMaterialSourceChange(lot, canWrite)
const showCreateDemand = computed(
  () => !!lot.value && !lot.value.input_demand_id && !lot.value.is_alteration,
)
const createDemandAllowed = computed(() => !!lot.value && canDemandSourceItem(lot.value))
const approveSourceOffered = computed(() => hasAction(lot.value, 'approve_source'))
const rejectSourceOffered = computed(() => hasAction(lot.value, 'reject_source'))
const sourceDecisionBlocked = computed(() => (canApprove.value ? '' : missing(Permission.MANAGE_LOTS)))

const recordData = useLotRecordData()

const lotIdRef = computed(() => props.lotId)

const {
  sourceItemDemand,
  showDemandSourceItem,
  showDemandDetail,
  showMaterialSource,
  currentMaterialSource,
  onMaterialSourceUpdated,
  loadSourceItemDemand,
  openDemandDetail,
  sourceItemDemandSummary,
  sourceItemDemandArrived,
  demandAllocations,
  onSourceItemDemandCreated,
  onSourceItemDemandUpdated,
  showRejectSource,
  rejectingSource,
  approvingSource,
  approveSource,
  openRejectSource,
  confirmRejectSource,
  eventsLoading,
  lotChangelog,
  loadEvents,
  madeItemDetail,
  sourceMadeItemDetail,
  sourceBoughtItemDetail,
  sourceItem,
  showSourceItem,
  openMadeItemDetail,
  openSourceItemDetail,
  showForceStatus,
  forceStatusAction,
  forceStatusSubmitting,
  openForceStatus,
  confirmForceStatus,
  showHold,
  holdReason,
  holding,
  openHold,
  submitHold,
  resumeLotAction,
} = useLotDetailDialogs(lotIdRef, lot)

// LotPositionResponse lacks an external position's delivery instant, so it
// is read off the order item.
const externalDeliveryDates = computed<Record<number, string | null>>(() => {
  if (!lot.value) return {}
  const dates: Record<number, string | null> = {}
  for (const position of lot.value.positions ?? []) {
    if (position.kind !== 'external' && position.kind !== 'mixed') continue
    dates[position.id] = recordData.orderItemForPosition(position)?.delivery_date ?? null
  }
  return dates
})

// Falls back to the lot_completed event for lots completed before the column
// existed. The verdict needs it when no order date exists, e.g. a
// force-completed lot without assignments.
const lotCompletedAt = computed(
  () =>
    lot.value?.completed_at ??
    detailStore.events.find((e) => e.event_type === 'lot_completed')?.occurred_at ??
    null,
)

// today is computed per render so a dialog left open past midnight stays
// correct.
const stateSignals = computed(() =>
  lot.value
    ? buildLotStateSummary({
        lot: lot.value,
        productionOrders: recordData.productionOrders.value,
        sourceItemDemand: sourceItemDemand.value,
        sourceItemDemandArrived: sourceItemDemandArrived.value,
        externalDeliveryDates: externalDeliveryDates.value,
        completedAt: lotCompletedAt.value,
        today: todayKey(),
      })
    : [],
)

async function load(): Promise<void> {
  await detailStore.fetch(props.lotId)
  // Loaded once for all cards that resolve user names.
  void usersStore.ensureLoaded()
  await Promise.all([
    loadSourceItemDemand(),
    loadEvents(),
    detailStore.lot ? recordData.load(detailStore.lot) : Promise.resolve(),
  ])
}

watch(() => props.lotId, load, { immediate: true })

// No per-lot filtering needed, refetch() reloads the lot the shared store
// holds, which is the one on screen.
useLiveRefresh([LiveResource.PRODUCTION_LOTS, LiveResource.SOURCE_ITEM_DEMANDS], async () => {
  await detailStore.refetch()
  void loadSourceItemDemand()
  void loadEvents()
  if (detailStore.lot) void recordData.load(detailStore.lot)
})

const scrapDialogRef = ref<InstanceType<typeof ScrapPiecesDialog> | null>(null)

function openScrap(): void {
  if (!lot.value) return
  void scrapDialogRef.value?.open({ kind: 'lot', lotId: lot.value.id })
}

// The scrap endpoint returns only a summary, so every card is reloaded.
function onPiecesScrapped(): void {
  void load()
}

const { isPrintingLot, onPrintLot } = useLotPrinting()

function isPrinting(classifier: LotPrintClassifier): boolean {
  return !!lot.value && isPrintingLot(lot.value, classifier)
}

async function printLot(classifier: LotPrintClassifier): Promise<void> {
  if (!lot.value) return
  await onPrintLot(lot.value, classifier)
}

// The page variant renders these in its own bars instead of the header row.
const { visible: reportVisible, report, open: openReport } = useReportExport()

/** Opens the export dialog of the lot's inspection report. */
function openInspectionReport(): void {
  const current = lot.value
  if (!current) return
  openReport(inspectionReportSpec(current, t('production.lots.report.title', { lot: current.lot_number })))
}

defineExpose({
  openInspectionReport,
  lot,
  loading: computed(() => detailStore.loading),
  stateSignals,
  canWrite,
  canManage,
  canScrap,
  canScrapPosition,
  canPrint,
  manageMode,
  toggleManage,
  isPrinting,
  printLot,
  openHold,
  resumeLot: resumeLotAction,
  openForceStatus,
  openScrap,
  reload: load,
})
</script>

<template>
  <div class="lot-detail">
    <!-- Gated on !lot too, so a live-refresh refetch does not blank an open
         lot back to the skeleton. -->
    <template v-if="!lot && detailStore.loading">
      <template v-if="variant === 'dialog'">
        <div class="lot-header">
          <div class="lot-header-info">
            <div class="lot-header-state">
              <Skeleton width="7rem" height="1.5rem" border-radius="1rem" />
              <Skeleton width="5.5rem" height="1.5rem" border-radius="1rem" />
            </div>
          </div>
          <div class="lot-header-actions">
            <Skeleton width="2.5rem" height="2.5rem" />
            <Skeleton width="6.5rem" height="2.5rem" />
          </div>
        </div>

        <Divider />
      </template>

      <div class="lot-body">
        <div class="record-grid record-grid--skeleton">
          <div class="record-column">
            <Skeleton border-radius="var(--p-content-border-radius)" height="100%" />
            <Skeleton border-radius="var(--p-content-border-radius)" height="100%" />
          </div>
          <Skeleton border-radius="var(--p-content-border-radius)" height="100%" />
        </div>
      </div>
    </template>

    <template v-else-if="lot">
      <template v-if="variant === 'dialog'">
        <LotDetailHeader
          :status="lot.status"
          :actions="lot.actions"
          :blocked-actions="lot.blocked_actions"
          :state-signals="stateSignals"
          :can-write="canWrite"
          :can-manage="canManage"
          :manage-mode="manageMode"
          :can-scrap-position="canScrapPosition"
          :can-scrap="canScrap"
          :can-print="canPrint"
          :has-scrap="(lot.quantity_scrapped ?? 0) > 0"
          :is-printing="isPrinting"
          @print="printLot"
          @report="openInspectionReport"
          @toggle-manage="toggleManage"
          @open-hold="openHold"
          @resume="resumeLotAction"
          @open-force-status="openForceStatus"
          @open-scrap="openScrap"
        />

        <Divider />
      </template>

      <div class="lot-body">
        <LotDetailRecordGrid
          v-if="!showManage"
          :lot="lot"
          :variant="variant"
          :changelog="lotChangelog"
          :record-data="recordData"
          :events="detailStore.events"
          :events-loading="eventsLoading"
          :source-item-demand="sourceItemDemand"
          :source-item-demand-arrived="sourceItemDemandArrived"
          :source-item-demand-summary="sourceItemDemandSummary"
          :demand-allocations="demandAllocations"
          :manage-mode="manageMode"
          :can-write="canWrite"
          :can-approve="canApprove"
          :approving="approvingSource"
          @view-item="openMadeItemDetail"
          @view-source-item="openSourceItemDetail"
          @change-source="showMaterialSource = true"
          @view-demand="openDemandDetail"
          @create-demand="showDemandSourceItem = true"
          @approve-source="approveSource"
          @reject-source="openRejectSource"
        />

        <template v-if="showManage">
          <div class="manage-section">

            <div class="material-source-section">
              <span class="material-source-title">{{
                t('production.lots.detail.materialSource.sectionTitle')
              }}</span>
              <div class="material-source-actions compact-buttons">
                <span v-tooltip.top="sourceChangeBlocked || undefined">
                  <Button
                    icon="mdi mdi-swap-horizontal"
                    size="small"
                    severity="secondary"
                    outlined
                    :label="t('production.lots.detail.materialSource.change')"
                    :disabled="sourceChangeBlocked !== ''"
                    @click="showMaterialSource = true"
                  />
                </span>
                <Button
                  v-if="showCreateDemand"
                  :label="t('production.lots.detail.rawMaterial.createDemand')"
                  icon="mdi mdi-plus"
                  size="small"
                  severity="secondary"
                  outlined
                  :disabled="!createDemandAllowed"
                  v-tooltip.top="
                    !createDemandAllowed
                      ? t('production.lots.detail.rawMaterial.noMaterialSource')
                      : undefined
                  "
                  @click="showDemandSourceItem = true"
                />
                <span v-if="approveSourceOffered" v-tooltip.top="sourceDecisionBlocked || undefined">
                  <Button
                    :label="t('production.lots.detail.record.sourceApproval.approve')"
                    icon="mdi mdi-check"
                    size="small"
                    severity="success"
                    :disabled="!canApprove"
                    :loading="approvingSource"
                    @click="approveSource"
                  />
                </span>
                <span v-if="rejectSourceOffered" v-tooltip.top="sourceDecisionBlocked || undefined">
                  <Button
                    :label="t('production.lots.detail.record.sourceApproval.reject')"
                    icon="mdi mdi-close"
                    size="small"
                    severity="danger"
                    outlined
                    :disabled="!canApprove"
                    @click="openRejectSource"
                  />
                </span>
              </div>
            </div>


            <div v-if="structureDraft.isDirty.value" class="structure-draft-bar">
              <Message class="draft-message" severity="warn" size="small" :closable="false">
                {{ t('production.lots.editSteps.unsaved') }}
              </Message>
              <Button
                :label="t('common.cancel')"
                size="small"
                severity="secondary"
                outlined
                :disabled="structureDraft.saving.value"
                @click="structureDraft.reset"
              />
              <Button
                :label="t('common.save')"
                size="small"
                :loading="structureDraft.saving.value"
                @click="saveStructureDraft"
              />
            </div>

            <LotStepList
              :lot-id="lotId"
              :steps="structureDraft.draftSteps.value"
              :positions="structureDraft.draftPositions.value"
              :made-item-id="lot.made_item_id"
              :made-item-part-number="lot.made_item_part_number"
              :made-item-revision="lot.made_item_revision"
              :made-item-article-name="lot.made_item_article_name"
              :readonly="readonly || !canWrite"
              :pending-assignments="structureDraft.pendingAssignments.value"
              :pending-reassignments="structureDraft.pendingReassignments.value"
              staged
              @edit-step="structureDraft.editStep"
              @remove-step="structureDraft.removeStep"
              @append-step="structureDraft.appendStep"
              @reorder-positions="structureDraft.reorderPositions"
              @assign-position="structureDraft.assignPosition"
              @clear-assignment="structureDraft.clearAssignment"
              @reassign-order="structureDraft.reassignOrder"
              @clear-reassignment="structureDraft.clearReassignment"
            />

            <LotPositionGrouping
              :lot-id="lotId"
              :steps="structureDraft.draftSteps.value"
              :positions="structureDraft.draftPositions.value"
              :readonly="readonly || !canWrite"
              staged
              @regroup="structureDraft.regroup"
            />

            <LotManagePositionsDock :lot-id="lotId" :lot="lot" :can-write-orders="canWriteOrders" />
          </div>
        </template>
      </div>
    </template>

    <div v-else class="lot-detail-notfound">
      {{ t('production.lots.detail.notFound') }}
    </div>

    <Dialog
      v-model:visible="showHold"
      modal
      :header="t('production.lots.detail.hold')"
      :style="{ width: 'var(--dialog-width-sm)' }"
    >
      <div class="field">
        <label :for="`${uid}-hold-reason`">{{ t('production.lots.detail.holdReason') }} *</label>
        <Textarea v-model="holdReason" :id="`${uid}-hold-reason`" rows="3" auto-resize fluid />
      </div>
      <template #footer>
        <Button
          :label="t('common.cancel')"
          severity="secondary"
          outlined
          :disabled="holding"
          @click="showHold = false"
        />
        <Button
          :label="t('common.save')"
          :loading="holding"
          :disabled="!holdReason.trim()"
          @click="submitHold"
        />
      </template>
    </Dialog>

    <LotForceStatusConfirmDialog
      v-model:visible="showForceStatus"
      :lot-id="lotId"
      :action="forceStatusAction"
      :lot="lot"
      :submitting="forceStatusSubmitting"
      @confirm="confirmForceStatus"
    />

    <SourceItemDemandCreateDialog
      v-model:visible="showDemandSourceItem"
      :lot-id="lot?.id ?? null"
      :lot-quantity="lot?.quantity ?? 0"
      @created="onSourceItemDemandCreated"
    />

    <SourceItemDemandDetailDialog
      v-model:visible="showDemandDetail"
      :demand="sourceItemDemand"
      @updated="onSourceItemDemandUpdated"
    />

    <LotMaterialSourceDialog
      v-model:visible="showMaterialSource"
      :lot-id="lot?.id ?? null"
      :made-item-id="lot?.made_item_id ?? null"
      :current-source="currentMaterialSource"
      :current-demand-status="lot?.demand_status ?? null"
      :input-demand-id="lot?.input_demand_id ?? null"
      :edit-version="lot?.edit_version ?? null"
      @updated="onMaterialSourceUpdated"
      @conflict="onMaterialSourceUpdated"
    />

    <LotRejectSourceDialog
      v-model:visible="showRejectSource"
      :lot-number="lot?.lot_number ?? ''"
      :loading="rejectingSource"
      @confirm="confirmRejectSource"
    />

    <ScrapPiecesDialog ref="scrapDialogRef" @scrapped="onPiecesScrapped" />

    <MadeItemDetailDialog
      v-model:visible="madeItemDetail.showDetail.value"
      :item="madeItemDetail.detailItem.value"
    />
    <MadeItemDetailDialog
      v-model:visible="sourceMadeItemDetail.showDetail.value"
      :item="sourceMadeItemDetail.detailItem.value"
    />
    <BoughtItemDetailDialog
      v-model:visible="sourceBoughtItemDetail.showDetail.value"
      :item="sourceBoughtItemDetail.detailItem.value"
    />
    <SourceItemDetailDialog v-model:visible="showSourceItem" :item="sourceItem" />
    <ReportExportDialog v-model:visible="reportVisible" :report="report">
      <template #handbook>
        <HelpButton slug="production/inspection-report" icon="mdi mdi-help" rounded />
      </template>
    </ReportExportDialog>
  </div>
</template>

<style scoped lang="scss">
// Fills the dialog's flex column (see LotDetailDialog.vue's contentStyle).
.lot-detail {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-2);
}

.lot-detail-notfound {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  color: var(--p-text-muted-color);
}

.lot-header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
}

.lot-header-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  flex: 1;
}

.lot-header-state {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.lot-header-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.lot-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

// Manage mode is alone in the body, so it takes the leftover height and
// scrolls itself.
.manage-section {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.material-source-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.material-source-title {
  font-size: var(--font-size-xs);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-text-muted-color);
}

.material-source-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.structure-draft-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
}

.draft-message {
  flex: 1;
  margin: 0;
}

// Mirrors LotDetailRecordGrid's layout.
.record-grid--skeleton {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  gap: var(--space-4);

  .record-column {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
}
</style>
