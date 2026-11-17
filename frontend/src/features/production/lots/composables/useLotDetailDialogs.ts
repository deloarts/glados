import { computed, ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { getSourceItemDemand, sourceItemsApi } from '@/features/source-items'
import { useSourceItemsAllocationsStore } from '../../source-item-demands/stores/sourceItemsAllocationsStore'
import { useMadeItemDetail } from '@/features/made-items'
import { useBoughtItemDetail } from '@/features/bought-items'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { getLotChangelog } from '../api/getLotChangelog'
import { approveLotSource } from '../api/approveLotSource'
import { rejectLotSource } from '../api/rejectLotSource'
import { parseChangelogEntry } from '../types/lotChangelogResponse'
import { refreshOnConflict } from '../utils/refreshOnConflict'

import type { LotChangelogEntry } from '../types/lotChangelogResponse'
import type { LotResponse } from '../../types/productionLotsResponse'
import type { MaterialSource } from '@/features/made-items'
import type { SourceItemDemandResponse, SourceItemResponse } from '@/features/source-items'

/**
 * The non-structural dialogs of the lot detail: audit trail, hold, force
 * complete or cancel, raw-material demand, material source, source approval
 * and item detail popups, each with its handler and the refetch that
 * follows a mutation.
 */
export function useLotDetailDialogs(lotId: Ref<number>, lot: Ref<LotResponse | null>) {
  const { t } = useI18n()
  const toast = useAppToast()
  const { withErrorToast, toastOnError } = useErrorToast()
  const detailStore = useProductionLotDetailStore()
  const sourceItemAllocationsStore = useSourceItemsAllocationsStore()

  // ── Raw material demand + material source change ─────────────────────

  const sourceItemDemand = ref<SourceItemDemandResponse | null>(null)
  const showDemandSourceItem = ref(false)
  const showDemandDetail = ref(false)
  const showMaterialSource = ref(false)

  const currentMaterialSource = computed<MaterialSource>(() => ({
    bought_item_id: lot.value?.source_bought_item_id ?? null,
    source_item_id: lot.value?.source_item_id ?? null,
    made_item_id: lot.value?.source_made_item_id ?? null,
  }))

  async function onMaterialSourceUpdated(): Promise<void> {
    await detailStore.refetch()
  }

  async function loadSourceItemDemand(): Promise<void> {
    const demandId = lot.value?.input_demand_id
    if (!demandId) {
      sourceItemDemand.value = null
      return
    }
    const succeeded = await withErrorToast(
      async () => {
        sourceItemDemand.value = await getSourceItemDemand(demandId)
        await Promise.all([
          sourceItemAllocationsStore.fetchSummaries([demandId]),
          sourceItemAllocationsStore.fetchAllocations(demandId),
        ])
        return true
      },
      { summary: t('production.lots.detail.rawMaterial.createError') },
    )
    if (!succeeded) sourceItemDemand.value = null
  }

  function openDemandDetail(): void {
    showDemandDetail.value = true
  }

  // "Arrived" counts delivered plus fulfilled-from-stock, like the
  // raw-material gate, since a pooled demand can span several order items.
  const sourceItemDemandSummary = computed(
    () =>
      (sourceItemDemand.value
        ? sourceItemAllocationsStore.getSummary(sourceItemDemand.value.id)
        : null) ?? null,
  )

  const sourceItemDemandArrived = computed(() => {
    const summary = sourceItemDemandSummary.value
    return summary ? summary.delivered + summary.fulfilled_from_stock : 0
  })

  const demandAllocations = computed(() =>
    sourceItemDemand.value
      ? (sourceItemAllocationsStore.allocations[sourceItemDemand.value.id] ?? [])
      : [],
  )

  async function onSourceItemDemandCreated(): Promise<void> {
    await detailStore.refetch()
    await loadSourceItemDemand()
  }

  async function onSourceItemDemandUpdated(): Promise<void> {
    await loadSourceItemDemand()
  }

  // ── Source approval (Approve/Reject) ─────────────────────────────────

  const showRejectSource = ref(false)
  const rejectingSource = ref(false)
  const approvingSource = ref(false)

  // A refused decision means the tab holds an older lot, so it reloads the
  // lot and its raw material demand.
  async function refetchAfterConflict(): Promise<void> {
    await detailStore.refetch()
    await loadSourceItemDemand()
  }

  // A second click while the approval is on its way is ignored, so a double
  // click cannot send it twice.
  async function approveSource(): Promise<void> {
    if (!lot.value || approvingSource.value) return
    const lotNumber = lot.value.lot_number
    const editVersion = lot.value.edit_version
    approvingSource.value = true
    const succeeded = await withErrorToast(
      async () => {
        await refreshOnConflict(
          () => approveLotSource(lotId.value, editVersion),
          refetchAfterConflict,
        )
        await detailStore.refetch()
        await loadSourceItemDemand()
        return true
      },
      { summary: t('production.lots.detail.record.sourceApproval.title') },
    ).finally(() => {
      approvingSource.value = false
    })
    if (succeeded) {
      toast.success(lotNumber, t('production.lots.detail.record.sourceApproval.approveSuccess'))
    }
  }

  function openRejectSource(): void {
    showRejectSource.value = true
  }

  async function confirmRejectSource(reason: string): Promise<void> {
    if (!lot.value) return
    const lotNumber = lot.value.lot_number
    const editVersion = lot.value.edit_version
    rejectingSource.value = true
    const succeeded = await withErrorToast(
      async () => {
        await refreshOnConflict(
          () => rejectLotSource(lotId.value, { reason, expected_edit_version: editVersion }),
          refetchAfterConflict,
        )
        await detailStore.refetch()
        await loadSourceItemDemand()
        return true
      },
      { summary: t('production.lots.detail.record.sourceApproval.title') },
    )
    if (succeeded) {
      showRejectSource.value = false
      toast.success(lotNumber, t('production.lots.detail.record.sourceApproval.rejectSuccess'))
    }
    rejectingSource.value = false
  }

  // ── Audit trail (ISO 9001 event log) ──────────────────────────────────

  const eventsLoading = ref(false)
  const lotChangelog = ref<LotChangelogEntry[]>([])

  // The event trail and the changes column load and fail together, so no tab
  // stays silently empty.
  async function loadEvents(): Promise<void> {
    eventsLoading.value = true
    await withErrorToast(
      async () => {
        const [, changelog] = await Promise.all([
          detailStore.fetchEvents(lotId.value),
          getLotChangelog(lotId.value),
        ])
        lotChangelog.value = changelog.map(parseChangelogEntry)
      },
      { summary: t('production.lots.detail.audit.loadError') },
    )
    eventsLoading.value = false
  }

  // ── Made item / source item detail (full inline records, not #id refs) ─

  const madeItemDetail = useMadeItemDetail()
  const sourceMadeItemDetail = useMadeItemDetail()
  const sourceBoughtItemDetail = useBoughtItemDetail()
  const sourceItem = ref<SourceItemResponse | null>(null)
  const showSourceItem = ref(false)

  function openMadeItemDetail(): void {
    if (lot.value) madeItemDetail.openDetailById(lot.value.made_item_id).catch(toastOnError())
  }

  async function openSourceItemDetail(): Promise<void> {
    if (!lot.value) return
    if (lot.value.source_bought_item_id !== null) {
      await sourceBoughtItemDetail.openDetailById(lot.value.source_bought_item_id)
    } else if (lot.value.source_made_item_id !== null) {
      await sourceMadeItemDetail.openDetailById(lot.value.source_made_item_id)
    } else if (lot.value.source_item_id !== null) {
      sourceItem.value = null
      showSourceItem.value = true
      const page = await sourceItemsApi.list({ id: lot.value.source_item_id, limit: 1 })
      sourceItem.value = page.items[0] ?? null
    }
  }

  // ── Force status (complete/cancel) ────────────────────────────────────

  const showForceStatus = ref(false)
  const forceStatusAction = ref<'complete' | 'cancel'>('cancel')
  const forceStatusSubmitting = ref(false)

  function openForceStatus(action: 'complete' | 'cancel'): void {
    forceStatusAction.value = action
    showForceStatus.value = true
  }

  async function confirmForceStatus(reason: string | null): Promise<void> {
    const shown = lot.value
    if (!shown) return
    forceStatusSubmitting.value = true
    const succeeded = await withErrorToast(
      async () => {
        if (forceStatusAction.value === 'complete') {
          await detailStore.complete(lotId.value, shown.edit_version, reason)
        } else {
          await detailStore.cancel(lotId.value, shown.edit_version, reason)
        }
        return true
      },
      {
        summary:
          forceStatusAction.value === 'complete'
            ? t('production.lots.detail.completeError')
            : t('production.lots.detail.cancelError'),
      },
    )
    if (succeeded) showForceStatus.value = false
    forceStatusSubmitting.value = false
  }

  // ── Hold / resume ──────────────────────────────────────────────────────

  const showHold = ref(false)
  const holdReason = ref('')
  const holding = ref(false)

  function openHold(): void {
    holdReason.value = ''
    showHold.value = true
  }

  async function submitHold(): Promise<void> {
    if (!holdReason.value.trim()) return
    holding.value = true
    const succeeded = await withErrorToast(
      async () => {
        await detailStore.hold(lotId.value, holdReason.value.trim())
        return true
      },
      { summary: t('production.lots.detail.holdError') },
    )
    if (succeeded) showHold.value = false
    holding.value = false
  }

  async function resumeLotAction(): Promise<void> {
    await withErrorToast(() => detailStore.resume(lotId.value), {
      summary: t('production.lots.detail.resumeError'),
    })
  }

  return {
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
  }
}
