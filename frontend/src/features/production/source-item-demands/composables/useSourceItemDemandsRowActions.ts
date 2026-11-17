import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { useClipboard } from '@/core/composables/useClipboard'
import { usePermissions } from '@/core/composables/usePermissions'
import { extractApiError } from '@/core/utils/errors'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useBucketsStore } from '@/features/buckets'
import { demandBucketMenuItems } from '@/shared/components/demands/demandBucketMenu'
import { demandContextMenu } from '@/shared/components/demands/demandContextMenu'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import {
  bulkStatusFailureToast,
  useDemandRowActions,
} from '@/shared/composables/useDemandRowActions'
import { useSourceItemDemandsStore } from '@/features/source-items'
import { useSourceItemDemandsFiltersStore } from '../stores/sourceItemDemandsFiltersStore'
import { useSourceItemDemandsSelectionStore } from '../stores/sourceItemDemandsSelectionStore'
import { useSourceItemsAllocationsStore } from '../stores/sourceItemsAllocationsStore'
import { cancelBlockedReason, type CancelBlockedReason } from '../utils/sourceItemDemandCancel'

import type { MenuItem } from 'openvue/menuitem'
import type { SourceItemDemandResponse, SourceItemDemandStatus } from '@/features/source-items'

/** What the table hands in: its dialogs, its row-open guard and its refetch. */
export interface SourceItemDemandsRowActionsDeps {
  openDetail: (demand: SourceItemDemandResponse) => void
  openManageAllocations: (demand: SourceItemDemandResponse) => void
  openFulfillFromStock: (demand: SourceItemDemandResponse) => void
  guardRowOpen: (id: number, open: () => void) => void
  fetchItems: () => void
}

/**
 * The row interactions of the source item demands table: row clicks and
 * selection, the context menu with its status, bucket, allocation, panel and
 * cancel entries, the fulfil confirmation, the cancel prompt that asks what
 * becomes of the lot, and adding a demand to one of the Manage panels.
 */
export function useSourceItemDemandsRowActions(deps: SourceItemDemandsRowActionsDeps) {
  const { t } = useI18n()
  const { copyToClipboard } = useClipboard()
  const toast = useAppToast()
  const { hasPermission } = usePermissions()
  const { missing } = useMissingPermission()

  const demandsStore = useSourceItemDemandsStore()
  const selectionStore = useSourceItemDemandsSelectionStore()
  const filtersStore = useSourceItemDemandsFiltersStore()
  const allocationsStore = useSourceItemsAllocationsStore()
  const bucketsStore = useBucketsStore()

  const canWrite = computed(() => hasPermission(Permission.WRITE_LOTS))
  const canWriteAllocations = computed(() => hasPermission(Permission.WRITE_ALLOCATIONS))
  const canWriteOrders = computed(() => hasPermission(Permission.WRITE_ORDERS))
  // Buckets need write:demand_items rather than write:lots.
  const canWriteBuckets = computed(() => hasPermission(Permission.WRITE_DEMAND_ITEMS))
  // The status submenus offer only fulfilled and canceled, which are
  // irreversible, so the backend's demand status rule reserves them for
  // holders of both write:demand_items and manage:demand_items.
  const canSetStatus = computed(
    () =>
      hasPermission(Permission.WRITE_DEMAND_ITEMS) &&
      hasPermission(Permission.MANAGE_DEMAND_ITEMS),
  )

  // Row actions shared with the bought and made item demand tables.
  const rowActions = useDemandRowActions<SourceItemDemandStatus, SourceItemDemandResponse>({
    getSelection: () => selectionStore.selectedDemands,
    setSelection: (demands) => {
      selectionStore.selectedDemands = demands
    },
    hasPanelOpen: () =>
      filtersStore.showManageOrderPanel ||
      filtersStore.showManageStockPanel ||
      filtersStore.showManageQuotePanel,
    openDetail: deps.openDetail,
    guardRowOpen: deps.guardRowOpen,
    fetchItems: deps.fetchItems,
    updateStatus: (id, status) => demandsStore.updateStatus(id, status),
    setBucket: (id, bucketId) => demandsStore.setBucket(id, bucketId),
    canceledStatus: 'canceled',
  })

  const reportBulkStatusFailures = bulkStatusFailureToast(toast, t, 'sourceItems.demands')

  function addToPanel(demand: SourceItemDemandResponse, panel: 'orders' | 'stock' | 'quotes'): void {
    if (!selectionStore.selectedDemands.some((d) => d.id === demand.id)) {
      selectionStore.selectedDemands = [...selectionStore.selectedDemands, demand]
    }
    filtersStore.openPanel(panel, { keepSelection: true })
  }

  // Every cancel of a raw material demand asks what becomes of its lot, the
  // Cancel Demand entry through the cancel route, the status submenu and the
  // bulk cancel through the status route, which manage:demand_items opens.
  const showCancelPrompt = ref(false)
  const cancelPromptTargets = ref<SourceItemDemandResponse[]>([])
  const cancelVia = ref<'cancel' | 'status'>('cancel')

  function requestCancel(targets: SourceItemDemandResponse[], via: 'cancel' | 'status'): void {
    const applicable = targets.filter((d) => hasAction(d, 'cancel'))
    if (applicable.length === 0) return
    cancelPromptTargets.value = applicable
    cancelVia.value = via
    showCancelPrompt.value = true
  }

  function cancelDemand(demand: SourceItemDemandResponse): void {
    requestCancel([demand], 'cancel')
  }

  // One demand shows its own error, several the bulk failure count.
  async function onCancelChosen(cancelLot: boolean): Promise<void> {
    const targets = cancelPromptTargets.value
    const cancelOne = (id: number) =>
      cancelVia.value === 'cancel'
        ? demandsStore.cancel(id, cancelLot)
        : demandsStore.cancelByStatus(id, cancelLot)
    if (targets.length === 1) {
      try {
        await cancelOne(targets[0]!.id)
      } catch (e) {
        toast.error('', extractApiError(e) ?? t('sourceItems.demands.detail.errors.unknown'))
      }
    } else {
      const results = await Promise.allSettled(targets.map((d) => cancelOne(d.id)))
      const failures = results.filter((r) => r.status === 'rejected').length
      if (failures > 0) reportBulkStatusFailures(failures, targets.length)
    }
    deps.fetchItems()
  }

  async function setStatus(
    demand: SourceItemDemandResponse,
    status: SourceItemDemandStatus,
  ): Promise<void> {
    try {
      await demandsStore.updateStatus(demand.id, status)
      deps.fetchItems()
    } catch (e) {
      toast.error('', extractApiError(e) ?? t('sourceItems.demands.detail.errors.unknown'))
    }
  }

  const { setStatusForTargets, fulfilTargets, requestFulfil } = rowActions

  // One demand goes through setStatus, so its own error shows; several get
  // the bulk failure count.
  function confirmFulfil(): void {
    const targets = fulfilTargets.value
    if (targets.length === 1) void setStatus(targets[0]!, 'fulfilled')
    else void setStatusForTargets(targets, 'fulfilled', reportBulkStatusFailures)
  }

  function bucketSubmenuItems(targets: SourceItemDemandResponse[]): MenuItem[] {
    return demandBucketMenuItems(
      bucketsStore.items.source_item_demand,
      (bucketId) => rowActions.assignBucket(targets, bucketId),
      t('sourceItems.demands.buckets.noBucket'),
    )
  }

  async function autoAllocateFor(demand: SourceItemDemandResponse): Promise<void> {
    try {
      const result = await allocationsStore.autoAllocate(demand.id)
      toast.success(
        `#${demand.id}`,
        result.allocations_created === 0 && result.allocations_updated === 0
          ? t('sourceItems.demands.detail.autoAllocateNone')
          : t('sourceItems.demands.detail.autoAllocateSuccess', {
              createdPhrase: t(
                'sourceItems.demands.detail.allocationsCountPhrase',
                result.allocations_created,
              ),
              updatedPhrase: t(
                'sourceItems.demands.detail.allocationsCountPhrase',
                result.allocations_updated,
              ),
            }),
      )
      if (result.unit_mismatches > 0) toast.warn(`#${demand.id}`, t('procurement.unitMismatchSummary'))
      if (result.demand_status_changed_to) {
        deps.fetchItems()
      }
    } catch (e) {
      toast.error(`#${demand.id}`, extractApiError(e) ?? t('sourceItems.demands.detail.errors.unknown'))
    }
  }

  // The same reason the detail dialog's Cancel Demand button shows.
  function cancelBlockedText(demand: SourceItemDemandResponse, reason: CancelBlockedReason): string {
    return reason
      ? t(`sourceItems.demands.detail.cancelBlocked.${reason}`, { lot: demand.lot_number })
      : ''
  }

  // The allocation entries need the demand's allocate action: a fulfilled or
  // canceled demand takes no more allocations, so they leave the menu, while
  // a missing permission keeps them disabled with the reason.
  function allocationEntries(demand: SourceItemDemandResponse): MenuItem[] {
    if (!hasAction(demand, 'allocate')) return []
    const reason = missing(Permission.WRITE_ALLOCATIONS) || undefined
    return [
      {
        label: t('sourceItems.demands.detail.autoAllocate'),
        icon: 'mdi mdi-auto-fix',
        disabled: !canWriteAllocations.value,
        title: reason,
        command: () => void autoAllocateFor(demand),
      },
      {
        label: t('sourceItems.demands.contextMenu.manageAllocations'),
        icon: 'mdi mdi-sitemap',
        disabled: !canWriteAllocations.value,
        title: reason,
        command: () => deps.openManageAllocations(demand),
      },
      {
        label: t('sourceItems.demands.detail.fulfillFromStock'),
        icon: 'mdi mdi-package-variant-closed',
        disabled: !canWriteAllocations.value,
        title: reason,
        command: () => deps.openFulfillFromStock(demand),
      },
    ]
  }

  const contextMenuItems = computed<MenuItem[]>(() =>
    demandContextMenu({
      t,
      keyPrefix: 'sourceItems.demands',
      targets: rowActions.contextMenuTargets.value,
      canEdit: canWrite.value,
      canSetStatus: canSetStatus.value,
      setStatusDisabledReason: missing(Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS),
      // The status submenu has its own permission, so only the state speaks here.
      cancelDisabledReason: (demand) => cancelBlockedText(demand, cancelBlockedReason(demand, true)),
      canWriteBuckets: canWriteBuckets.value,
      canWriteAllocations: canWriteAllocations.value,
      showCopyPlaceholder: false,
      bucketItems: bucketSubmenuItems,
      openDetail: deps.openDetail,
      setStatus: (demand, status) => {
        if (status === 'fulfilled') requestFulfil([demand])
        else if (status === 'canceled') requestCancel([demand], 'status')
        else void setStatus(demand, status)
      },
      fulfilTargets: requestFulfil,
      requestBulkCancel: (targets) => requestCancel(targets, 'status'),
      panel: {
        label: t('sourceItems.demands.contextMenu.addToOrder'),
        icon: 'mdi mdi-cart-arrow-right',
        disabled: !canWriteOrders.value,
        disabledReason: missing(Permission.WRITE_ORDERS),
        action: 'allocate',
        open: () => filtersStore.openPanel('orders', { keepSelection: true }),
        addDemand: (demand) => addToPanel(demand, 'orders'),
      },
      quotePanel: {
        label: t('sourceItems.demands.contextMenu.addToQuote'),
        icon: 'mdi mdi-scale-balance',
        disabled: !canWriteOrders.value,
        disabledReason: missing(Permission.WRITE_ORDERS),
        action: 'allocate',
        open: () => filtersStore.openPanel('quotes', { keepSelection: true }),
        addDemand: (demand) => addToPanel(demand, 'quotes'),
      },
      openStockPanel: () => filtersStore.openPanel('stock', { keepSelection: true }),
      singleEntries: allocationEntries,
      // Source demands also offer Cancel, through the cancel route behind the
      // prompt for the lot.
      trailingEntries: (demand) => {
        const reason = cancelBlockedReason(demand, canWrite.value)
        return [
          {
            label: t('sourceItems.demands.contextMenu.cancel'),
            icon: 'mdi mdi-close-circle-outline',
            disabled: reason !== '',
            title: cancelBlockedText(demand, reason) || undefined,
            command: () => cancelDemand(demand),
          },
          { separator: true },
        ]
      },
      copyToClipboard,
    }),
  )

  return {
    onTableClickCapture: rowActions.onTableClickCapture,
    onRowClick: rowActions.onRowClick,
    onRowSelect: rowActions.onRowSelect,
    contextMenuItem: rowActions.contextMenuItem,
    contextMenuItems,
    showBulkCancel: rowActions.showBulkCancel,
    bulkCancelTargets: rowActions.bulkCancelTargets,
    showFulfil: rowActions.showFulfil,
    fulfilTargets,
    confirmFulfil,
    showCancelPrompt,
    cancelPromptTargets,
    onCancelChosen,
    addToPanel,
    canWriteAllocations,
  }
}
