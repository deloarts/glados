<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import SourceItemDemandCreateDialog from '../../lots/components/SourceItemDemandCreateDialog.vue'
import { useSourceItemDemandsFiltersStore } from '../stores/sourceItemDemandsFiltersStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import ItemDemandsControlsBar from '@/shared/components/resource-view/ItemDemandsControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useSourceItemDemandsStore } from '@/features/source-items'
import { SpreadsheetExportButton } from '@/shared/spreadsheet-export'
import { useSourceItemDemandsExport } from '../composables/useSourceItemDemandsExport'
import { useSourceItemDemandsSelectionStore } from '../stores/sourceItemDemandsSelectionStore'

const { t } = useI18n()

const demandsStore = useSourceItemDemandsStore()
const filtersStore = useSourceItemDemandsFiltersStore()
const selectionStore = useSourceItemDemandsSelectionStore()

const spreadsheetExport = useSourceItemDemandsExport()
const { exporting, loaded: exportLoaded, total: exportTotal } = spreadsheetExport
const { hasPermission } = usePermissions()

const showCreateForm = ref(false)

// Creating a source item demand links input_demand_id on the lot, so the backend
// gates it on write:lots (LotRules.assert_can_update), not write:demand_items.
const canCreateDemand = computed(() => hasPermission(Permission.WRITE_LOTS))
const canWriteOrders = computed(() => hasPermission(Permission.WRITE_ORDERS))
const canWriteAllocations = computed(() => hasPermission(Permission.WRITE_ALLOCATIONS))
const { missing } = useMissingPermission()
// A missing permission names itself; otherwise the panel's filter is the hint.
const ordersHint = computed(
  () =>
    missing(Permission.WRITE_ORDERS) ||
    (filtersStore.notFullyAllocatedOnly
      ? t('sourceItems.demands.controls.manageOrdersFilterHint')
      : ''),
)

// The store's create() does not refresh, and the table watches refreshTrigger.
function onDemandCreated(): void {
  demandsStore.triggerRefresh()
}
</script>

<template>
  <ItemDemandsControlsBar
    i18n-prefix="sourceItems.demands.controls"
    :can-create="canCreateDemand"
    :create-blocked="missing(Permission.WRITE_LOTS)"
    @create="showCreateForm = true"
  >
    <template #actions>
      <SpreadsheetExportButton
        :total="demandsStore.total"
        :selected-count="selectionStore.selectedDemands.length"
        :exporting="exporting"
        :loaded="exportLoaded"
        :export-total="exportTotal"
        @export="(scope) => void spreadsheetExport.run(scope)"
        @cancel="spreadsheetExport.cancel()"
      />
      <Divider layout="vertical" />
      <span v-tooltip="ordersHint || undefined">
        <Button
          :label="t('sourceItems.demands.controls.manageOrders')"
          icon="mdi mdi-cart-arrow-right"
          severity="contrast"
          :text="!filtersStore.showManageOrderPanel"
          :disabled="!canWriteOrders"
          @click="filtersStore.togglePanel('orders')"
        />
      </span>
      <span v-tooltip="missing(Permission.WRITE_ORDERS) || undefined">
        <Button
          :label="t('sourceItems.demands.controls.manageQuotes')"
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
          :label="t('sourceItems.demands.controls.manageStock')"
          icon="mdi mdi-package-variant-closed"
          severity="contrast"
          :text="!filtersStore.showManageStockPanel"
          :disabled="!canWriteAllocations"
          @click="filtersStore.togglePanel('stock')"
        />
      </span>
    </template>
    <template #handbook>
      <HelpButton slug="procurement/source-item-demand-lifecycle" rounded />
    </template>
  </ItemDemandsControlsBar>

  <SourceItemDemandCreateDialog v-model:visible="showCreateForm" @created="onDemandCreated" />
</template>
