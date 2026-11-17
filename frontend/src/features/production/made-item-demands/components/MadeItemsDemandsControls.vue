<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import BatchCreateMadeItemDemandsDialog from './BatchCreateMadeItemDemandsDialog.vue'
import MadeItemsAutoAssignLotsDialog from './MadeItemsAutoAssignLotsDialog.vue'
import { useMadeItemsDemandsBatchDraftStore } from '../stores/madeItemsDemandsBatchDraftStore'
import { useMadeItemsDemandsFiltersStore } from '../stores/madeItemsDemandsFiltersStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useProductionPlanning } from '@/core/composables/useProductionPlanning'
import ItemDemandsControlsBar from '@/shared/components/resource-view/ItemDemandsControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { MadeItemDemandCreateForm, useMadeItemsDemandsStore } from '@/features/made-items'
import { SpreadsheetExportButton } from '@/shared/spreadsheet-export'
import { useMadeItemDemandsExport } from '../composables/useMadeItemDemandsExport'
import { useMadeItemsProcurementStore } from '../stores/madeItemsProcurementStore'

const { t } = useI18n()

const demandsStore = useMadeItemsDemandsStore()
const filtersStore = useMadeItemsDemandsFiltersStore()
const batchDraftStore = useMadeItemsDemandsBatchDraftStore()
const procurementStore = useMadeItemsProcurementStore()
const { hasPermission } = usePermissions()

const spreadsheetExport = useMadeItemDemandsExport()
const { exporting, loaded: exportLoaded, total: exportTotal } = spreadsheetExport
const { productionPlanningEnabled } = useProductionPlanning()

const showCreateForm = ref(false)
const showAutoAssign = ref(false)
const showBatchImport = ref(false)
const canWrite = computed(() => hasPermission(Permission.WRITE_DEMAND_ITEMS))
const canWriteLots = computed(() => hasPermission(Permission.WRITE_LOTS))
const canWriteAllocations = computed(() => hasPermission(Permission.WRITE_ALLOCATIONS))
const { missing } = useMissingPermission()
// A missing permission names itself; otherwise a kept draft is the hint.
const batchCreateHint = computed(
  () =>
    missing(Permission.WRITE_DEMAND_ITEMS) ||
    (batchDraftStore.hasDraft ? t('madeItems.demands.batchCreate.draftIndicator') : ''),
)
// A missing permission names itself; otherwise the panel's filter is the hint.
const lotsHint = computed(
  () =>
    missing(Permission.WRITE_LOTS) ||
    (filtersStore.notFullyAllocatedOnly ? t('madeItems.demands.controls.manageLotsFilterHint') : ''),
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
    i18n-prefix="madeItems.demands.controls"
    :can-create="canWrite"
    :create-blocked="missing(Permission.WRITE_DEMAND_ITEMS)"
    @create="showCreateForm = true"
  >
    <template #actions>
      <span v-tooltip="batchCreateHint || undefined">
        <Button
          :label="t('madeItems.demands.controls.batchCreate')"
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
      <span v-if="productionPlanningEnabled" v-tooltip="lotsHint || undefined">
        <Button
          :label="t('madeItems.demands.controls.manageLots')"
          icon="mdi mdi-ticket-outline"
          severity="contrast"
          :text="!filtersStore.showManageLotsPanel"
          :disabled="!canWriteLots"
          @click="filtersStore.togglePanel('lots')"
        />
      </span>
      <span v-if="productionPlanningEnabled" v-tooltip="missing(Permission.WRITE_LOTS) || undefined">
        <Button
          :label="t('madeItems.demands.controls.autoAssign')"
          icon="mdi mdi-auto-fix"
          severity="contrast"
          text
          :disabled="!canWriteLots"
          @click="showAutoAssign = true"
        />
      </span>
      <span v-tooltip="missing(Permission.WRITE_ALLOCATIONS) || undefined">
        <Button
          :label="t('madeItems.demands.controls.manageStock')"
          icon="mdi mdi-package-variant-closed"
          severity="contrast"
          :text="!filtersStore.showManageStockPanel"
          :disabled="!canWriteAllocations"
          @click="filtersStore.togglePanel('stock')"
        />
      </span>
    </template>
    <template #handbook>
      <HelpButton slug="procurement/made-item-demand-lifecycle" rounded />
    </template>
  </ItemDemandsControlsBar>

  <MadeItemDemandCreateForm v-model:visible="showCreateForm" @created="onDemandCreated" />
  <MadeItemsAutoAssignLotsDialog v-model:visible="showAutoAssign" />
  <BatchCreateMadeItemDemandsDialog v-model:visible="showBatchImport" @created="onBatchCreated" />
</template>
