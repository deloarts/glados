import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { useClipboard } from '@/core/composables/useClipboard'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useBucketsStore } from '@/features/buckets'
import { demandBucketMenuItems } from '@/shared/components/demands/demandBucketMenu'
import { demandContextMenu } from '@/shared/components/demands/demandContextMenu'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import {
  bulkStatusFailureToast,
  useDemandRowActions,
} from '@/shared/composables/useDemandRowActions'
import { useBoughtItemsAllocationsStore } from '../stores/boughtItemsAllocationsStore'
import { useBoughtItemsDemandsFiltersStore } from '../stores/boughtItemsDemandsFiltersStore'
import { useBoughtItemsProcurementStore } from '../stores/boughtItemsProcurementStore'

import type { MenuItem } from 'openvue/menuitem'
import { useBoughtItemsDemandsStore } from '@/features/bought-items'
import type { BoughtItemDemandResponse, BoughtItemDemandStatus } from '@/features/bought-items'

/** What the table hands in: its dialogs, its row-open guard and its refetch. */
export interface BoughtItemsDemandsRowActionsDeps {
  openDetail: (demand: BoughtItemDemandResponse) => void
  openManageAllocations: (demand: BoughtItemDemandResponse) => void
  openFulfillFromStock: (demand: BoughtItemDemandResponse) => void
  guardRowOpen: (id: number, open: () => void) => void
  fetchItems: () => void
}

/**
 * The row interactions of the bought item demands table: row clicks and
 * selection, the context menu with its status, bucket, allocation and panel
 * entries, the fulfil and bulk cancel confirmations, and adding a demand to
 * one of the Manage panels.
 */
export function useBoughtItemsDemandsRowActions(deps: BoughtItemsDemandsRowActionsDeps) {
  const { t } = useI18n()
  const { copyToClipboard } = useClipboard()
  const toast = useAppToast()
  const { withErrorToast } = useErrorToast()
  const { hasPermission } = usePermissions()
  const { missing } = useMissingPermission()

  const demandsStore = useBoughtItemsDemandsStore()
  const filtersStore = useBoughtItemsDemandsFiltersStore()
  const allocationsStore = useBoughtItemsAllocationsStore()
  const procurementStore = useBoughtItemsProcurementStore()
  const bucketsStore = useBucketsStore()

  const canWrite = computed(() => hasPermission(Permission.WRITE_DEMAND_ITEMS))
  const canWriteAllocations = computed(() => hasPermission(Permission.WRITE_ALLOCATIONS))
  const canWriteOrders = computed(() => hasPermission(Permission.WRITE_ORDERS))
  // The status submenus offer only fulfilled and canceled, which are
  // irreversible, so the backend's demand status rule reserves them for
  // holders of both write:demand_items and manage:demand_items.
  const canSetStatus = computed(
    () =>
      hasPermission(Permission.WRITE_DEMAND_ITEMS) &&
      hasPermission(Permission.MANAGE_DEMAND_ITEMS),
  )

  // Row actions shared with the made and source item demand tables.
  const rowActions = useDemandRowActions<BoughtItemDemandStatus, BoughtItemDemandResponse>({
    getSelection: () => procurementStore.selectedDemands,
    setSelection: (demands) => {
      procurementStore.selectedDemands = demands
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

  const reportBulkStatusFailures = bulkStatusFailureToast(toast, t, 'boughtItems.demands')

  async function setStatus(
    demand: BoughtItemDemandResponse,
    status: BoughtItemDemandStatus,
  ): Promise<void> {
    await withErrorToast(
      async () => {
        await demandsStore.updateStatus(demand.id, status)
        deps.fetchItems()
      },
      {
        summary: demand.item_article_name,
        fallbackMessage: t('boughtItems.demands.detail.errors.unknown'),
      },
    )
  }

  const { setStatusForTargets, requestBulkCancel, fulfilTargets, requestFulfil } = rowActions

  // One demand goes through setStatus, so its own error shows; several get
  // the bulk failure count.
  function confirmFulfil(): void {
    const targets = fulfilTargets.value
    if (targets.length === 1) void setStatus(targets[0]!, 'fulfilled')
    else void setStatusForTargets(targets, 'fulfilled', reportBulkStatusFailures)
  }

  function confirmBulkCancel(): void {
    rowActions.confirmBulkCancel(reportBulkStatusFailures)
  }

  function bucketSubmenuItems(targets: BoughtItemDemandResponse[]): MenuItem[] {
    return demandBucketMenuItems(
      bucketsStore.items.bought_item_demand,
      (bucketId) => rowActions.assignBucket(targets, bucketId),
      t('boughtItems.demands.buckets.noBucket'),
    )
  }

  async function autoAllocateFor(demand: BoughtItemDemandResponse): Promise<void> {
    await withErrorToast(
      async () => {
        const result = await allocationsStore.autoAllocate(demand.id)
        toast.success(
          demand.item_article_name,
          result.allocations_created === 0 && result.allocations_updated === 0
            ? t('boughtItems.demands.detail.autoAllocateNone')
            : t('boughtItems.demands.detail.autoAllocateSuccess', {
                createdPhrase: t(
                  'boughtItems.demands.detail.allocationsCountPhrase',
                  result.allocations_created,
                ),
                updatedPhrase: t(
                  'boughtItems.demands.detail.allocationsCountPhrase',
                  result.allocations_updated,
                ),
              }),
        )
        if (result.unit_mismatches > 0) {
          toast.warn(demand.item_article_name, t('procurement.unitMismatchSummary'))
        }
        if (result.demand_status_changed_to) {
          deps.fetchItems()
        }
      },
      {
        summary: demand.item_article_name,
        fallbackMessage: t('boughtItems.demands.detail.errors.unknown'),
      },
    )
  }

  function addToPanel(demand: BoughtItemDemandResponse, panel: 'orders' | 'stock' | 'quotes'): void {
    if (!procurementStore.selectedDemands.some((d) => d.id === demand.id)) {
      procurementStore.selectedDemands = [...procurementStore.selectedDemands, demand]
    }
    filtersStore.openPanel(panel, { keepSelection: true })
  }

  // The allocation entries need the demand's allocate action: a fulfilled or
  // canceled demand takes no more allocations, so they leave the menu, while
  // a missing permission keeps them disabled with the reason.
  function allocationEntries(demand: BoughtItemDemandResponse): MenuItem[] {
    if (!hasAction(demand, 'allocate')) return []
    const reason = missing(Permission.WRITE_ALLOCATIONS) || undefined
    return [
      {
        label: t('boughtItems.demands.detail.autoAllocate'),
        icon: 'mdi mdi-auto-fix',
        disabled: !canWriteAllocations.value,
        title: reason,
        command: () => void autoAllocateFor(demand),
      },
      {
        label: t('boughtItems.demands.contextMenu.manageAllocations'),
        icon: 'mdi mdi-sitemap',
        disabled: !canWriteAllocations.value,
        title: reason,
        command: () => deps.openManageAllocations(demand),
      },
      {
        label: t('boughtItems.demands.detail.fulfillFromStock'),
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
      keyPrefix: 'boughtItems.demands',
      targets: rowActions.contextMenuTargets.value,
      canEdit: canWrite.value,
      canSetStatus: canSetStatus.value,
      setStatusDisabledReason: missing(
        Permission.WRITE_DEMAND_ITEMS,
        Permission.MANAGE_DEMAND_ITEMS,
      ),
      canWriteBuckets: canWrite.value,
      canWriteAllocations: canWriteAllocations.value,
      showCopyPlaceholder: true,
      bucketItems: bucketSubmenuItems,
      openDetail: deps.openDetail,
      setStatus: (demand, status) =>
        status === 'fulfilled' ? requestFulfil([demand]) : setStatus(demand, status),
      fulfilTargets: requestFulfil,
      requestBulkCancel,
      panel: {
        label: t('boughtItems.demands.contextMenu.addToOrder'),
        icon: 'mdi mdi-cart-arrow-right',
        disabled: !canWriteOrders.value,
        disabledReason: missing(Permission.WRITE_ORDERS),
        action: 'allocate',
        open: () => filtersStore.openPanel('orders', { keepSelection: true }),
        addDemand: (demand) => addToPanel(demand, 'orders'),
      },
      quotePanel: {
        label: t('boughtItems.demands.contextMenu.addToQuote'),
        icon: 'mdi mdi-scale-balance',
        disabled: !canWriteOrders.value,
        disabledReason: missing(Permission.WRITE_ORDERS),
        action: 'allocate',
        open: () => filtersStore.openPanel('quotes', { keepSelection: true }),
        addDemand: (demand) => addToPanel(demand, 'quotes'),
      },
      openStockPanel: () => filtersStore.openPanel('stock', { keepSelection: true }),
      singleEntries: allocationEntries,
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
    confirmBulkCancel,
    showFulfil: rowActions.showFulfil,
    fulfilTargets,
    confirmFulfil,
    addToPanel,
    canWriteAllocations,
  }
}
