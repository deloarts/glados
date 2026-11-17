<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import BoughtItemBatchCreateDemandsDialog from './BoughtItemBatchCreateDemandsDialog.vue'
import { useBoughtItemsDemandsBatchDraftStore } from '../stores/boughtItemsDemandsBatchDraftStore'
import { useBoughtItemsDemandsFiltersStore } from '../stores/boughtItemsDemandsFiltersStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import ItemDemandsControlsBar from '@/shared/components/resource-view/ItemDemandsControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { BoughtItemDemandCreateForm, useBoughtItemsDemandsStore } from '@/features/bought-items'
import { SpreadsheetExportButton } from '@/shared/spreadsheet-export'
import { useBoughtItemDemandsExport } from '../composables/useBoughtItemDemandsExport'
import { useBoughtItemsProcurementStore } from '../stores/boughtItemsProcurementStore'

const { t } = useI18n()

const demandsStore = useBoughtItemsDemandsStore()
const filtersStore = useBoughtItemsDemandsFiltersStore()
const batchDraftStore = useBoughtItemsDemandsBatchDraftStore()
const procurementStore = useBoughtItemsProcurementStore()
const { hasPermission } = usePermissions()

const spreadsheetExport = useBoughtItemDemandsExport()
const { exporting, loaded: exportLoaded, total: exportTotal } = spreadsheetExport

const showCreateForm = ref(false)
const showBatchImport = ref(false)
const canWrite = computed(() => hasPermission(Permission.WRITE_DEMAND_ITEMS))
const canWriteOrders = computed(() => hasPermission(Permission.WRITE_ORDERS))
const canWriteAllocations = computed(() => hasPermission(Permission.WRITE_ALLOCATIONS))
const { missing } = useMissingPermission()
// A missing permission names itself; otherwise the panel's filter is the hint.
const ordersHint = computed(
  () =>
    missing(Permission.WRITE_ORDERS) ||
    (filtersStore.notFullyAllocatedOnly
      ? t('boughtItems.demands.controls.manageOrdersFilterHint')
      : ''),
)

// A missing permission names itself; otherwise a kept draft is the hint.
const batchCreateHint = computed(
  () =>
    missing(Permission.WRITE_DEMAND_ITEMS) ||
    (batchDraftStore.hasDraft ? t('boughtItems.demands.batchCreate.draftIndicator') : ''),
)

function onDemandCreated(): void {
  demandsStore.triggerRefresh()
}

function onBatchCreated(): void {
  demandsStore.triggerRefresh()
}
</script>

<template>
  <ItemDemandsControlsBar
    i18n-prefix="boughtItems.demands.controls"
    :can-create="canWrite"
    :create-blocked="missing(Permission.WRITE_DEMAND_ITEMS)"
    @create="showCreateForm = true"
  >
    <template #actions>
      <span v-tooltip="batchCreateHint || undefined">
        <Button
          :label="t('boughtItems.demands.controls.batchCreate')"
          icon="mdi mdi-file-excel-outline"
          severity="contrast"
          text
          :disabled="!canWrite"
          :badge="batchDraftStore.hasDraft ? ' ' : undefined"
          badge-severity="warn"
          @click="showBatchImport = true"
        />
      </span>
      <SpreadsheetExportButton
        :total="demandsStore.total"
        :selected-count="procurementStore.selectedDemands.length"
        :exporting="exporting"
        :loaded="exportLoaded"
        :export-total="exportTotal"
        @export="(scope) => void spreadsheetExport.run(scope)"
        @cancel="spreadsheetExport.cancel()"
      />
      <Divider layout="vertical" />
      <span v-tooltip="ordersHint || undefined">
        <Button
          :label="t('boughtItems.demands.controls.manageOrders')"
          icon="mdi mdi-cart-arrow-right"
          severity="contrast"
          :text="!filtersStore.showManageOrderPanel"
          :disabled="!canWriteOrders"
          @click="filtersStore.togglePanel('orders')"
        />
      </span>
      <span v-tooltip="missing(Permission.WRITE_ORDERS) || undefined">
        <Button
          :label="t('boughtItems.demands.controls.manageQuotes')"
          icon="mdi mdi-scale-balance"
          severity="contrast"
          :text="!filtersStore.showManageQuotePanel"
          :disabled="!canWriteOrders"
          data-testid="manage-quotes"
          @click="filtersStore.togglePanel('quotes')"
        />
      </span>
      <span v-tooltip="missing(Permission.WRITE_ALLOCATIONS) || undefined">
        <Button
          :label="t('boughtItems.demands.controls.manageStock')"
          icon="mdi mdi-package-variant-closed"
          severity="contrast"
          :text="!filtersStore.showManageStockPanel"
          :disabled="!canWriteAllocations"
          @click="filtersStore.togglePanel('stock')"
        />
      </span>
    </template>
    <template #handbook>
      <HelpButton slug="procurement/bought-item-demand-lifecycle" rounded />
    </template>
  </ItemDemandsControlsBar>

  <BoughtItemDemandCreateForm v-model:visible="showCreateForm" @created="onDemandCreated" />
  <BoughtItemBatchCreateDemandsDialog v-model:visible="showBatchImport" @created="onBatchCreated" />
</template>
