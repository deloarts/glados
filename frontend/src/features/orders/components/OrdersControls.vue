<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import OrderCreateForm from './OrderCreateForm.vue'
import { useOrdersStore } from '../stores/ordersStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import { HelpButton } from '@/shared/help'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { SpreadsheetExportButton } from '@/shared/spreadsheet-export'
import { useOrdersExport } from '../composables/useOrdersExport'

const { t } = useI18n()

const ordersStore = useOrdersStore()
const { hasPermission } = usePermissions()

const showCreateForm = ref(false)
const canWrite = computed(() => hasPermission(Permission.WRITE_ORDERS))
const { missing } = useMissingPermission()

const spreadsheetExport = useOrdersExport()
const { exporting, loaded: exportLoaded, total: exportTotal } = spreadsheetExport

function onOrderCreated(): void {
  void ordersStore.refresh()
}
</script>

<template>
  <ControlsBar>
    <template #start>
      <span v-tooltip="missing(Permission.WRITE_ORDERS) || undefined">
        <Button
          :label="t('orders.controls.new')"
          icon="mdi mdi-plus"
          severity="contrast"
          text
          :disabled="!canWrite"
          @click="showCreateForm = true"
        />
      </span>
      <SpreadsheetExportButton
        :total="ordersStore.total"
        :exporting="exporting"
        :loaded="exportLoaded"
        :export-total="exportTotal"
        @export="(scope) => void spreadsheetExport.run(scope)"
        @cancel="spreadsheetExport.cancel()"
      />
    </template>
    <template #handbook>
      <!-- Explicit, since the bare /procurement route also shows this tab and
           would otherwise resolve to a slug with no page. -->
      <HelpButton rounded slug="procurement/orders" />
    </template>
  </ControlsBar>

  <OrderCreateForm v-model:visible="showCreateForm" @created="onOrderCreated" />
</template>
