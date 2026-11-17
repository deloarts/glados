<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import PrinterManagementTable from '../components/PrinterManagementTable.vue'
import PrinterFormDialog from '../components/PrinterFormDialog.vue'
import PrinterStatusDialog from '../components/PrinterStatusDialog.vue'
import PrinterPrintHistoryDialog from '../components/PrinterPrintHistoryDialog.vue'
import { usePrintersStore } from '../stores/printersStore'
import { Permission } from '@/core/auth/permissions'

import type { MenuItem } from 'openvue/menuitem'
import type { PrinterResponse } from '../types/printerResponse'

const { t } = useI18n()
const store = usePrintersStore()
const { search } = storeToRefs(store)

const tableRef = ref<InstanceType<typeof PrinterManagementTable> | null>(null)
const showFormDialog = ref(false)
const editingPrinter = ref<PrinterResponse | null>(null)
const showStatusDialog = ref(false)
const statusPrinter = ref<PrinterResponse | null>(null)
const showHistoryDialog = ref(false)
const historyPrinter = ref<PrinterResponse | null>(null)

function openCreate(): void {
  editingPrinter.value = null
  showFormDialog.value = true
}

function openEdit(printer: PrinterResponse): void {
  editingPrinter.value = printer
  showFormDialog.value = true
}

function openStatus(printer: PrinterResponse): void {
  statusPrinter.value = printer
  showStatusDialog.value = true
}

function openHistory(printer: PrinterResponse): void {
  historyPrinter.value = printer
  showHistoryDialog.value = true
}

function onSaved(): void {
  tableRef.value?.refresh()
}

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('printers.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('name', 'asc'),
  },
  {
    label: t('printers.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('name', 'desc'),
  },
  {
    label: t('printers.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('printers.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
])

const groupByItems = computed<MenuItem[]>(() => [
  {
    label: t('printers.views.groupByItems.kind'),
    icon: 'mdi mdi-printer-outline',
    command: () => store.setGroupBy('kind'),
  },
  {
    label: t('printers.views.groupByItems.location'),
    icon: 'mdi mdi-map-marker-outline',
    command: () => store.setGroupBy('location'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'printers',
  createLabel: t('printers.controls.new'),
  createPermission: Permission.WRITE_PRINTERS,
  sortByItems: sortByItems.value,
  groupByItems: groupByItems.value,
  searchPlaceholder: t('printers.controls.search'),
}))
</script>

<template>
  <ManagementCrudShell :config="shellConfig" v-model:search="search" @create="openCreate">
    <template #handbook>
      <HelpButton rounded />
    </template>
    <PrinterManagementTable
      ref="tableRef"
      @edit="openEdit"
      @status="openStatus"
      @history="openHistory"
    />
  </ManagementCrudShell>

  <PrinterFormDialog v-model:visible="showFormDialog" :printer="editingPrinter" @saved="onSaved" />
  <PrinterStatusDialog v-model:visible="showStatusDialog" :printer="statusPrinter" />
  <PrinterPrintHistoryDialog v-model:visible="showHistoryDialog" :printer="historyPrinter" />
</template>
