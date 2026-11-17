<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import SupplierManagementTable from '../components/SupplierManagementTable.vue'
import SupplierFormDialog from '../components/SupplierFormDialog.vue'
import { useSuppliersStore } from '../stores/suppliersStore'
import { Permission } from '@/core/auth/permissions'
import type { SupplierResponse } from '../types/supplierResponse'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const toast = useAppToast()
const store = useSuppliersStore()

const showCreateForm = ref(false)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('resources.suppliers.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('name', 'asc'),
  },
  {
    label: t('resources.suppliers.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('name', 'desc'),
  },
  {
    label: t('resources.suppliers.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('resources.suppliers.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
  {
    label: t('resources.suppliers.views.sortByItems.changedDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('changed', 'desc'),
  },
  {
    label: t('resources.suppliers.views.sortByItems.changedAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('changed', 'asc'),
  },
])

const groupByItems = computed<MenuItem[]>(() => [
  {
    label: t('resources.suppliers.views.groupByItems.country'),
    icon: 'mdi mdi-earth',
    command: () => store.setGroupBy('country'),
  },
  {
    label: t('resources.suppliers.views.groupByItems.capability'),
    icon: 'mdi mdi-wrench-outline',
    command: () => store.setGroupBy('capability'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'suppliers',
  createLabel: t('resources.suppliers.createSupplier'),
  createPermission: Permission.WRITE_SUPPLIERS,
  sortByItems: sortByItems.value,
  groupByItems: groupByItems.value,
}))

function onSaved(supplier: SupplierResponse): void {
  toast.success(supplier.name, t('resources.suppliers.createSupplier'))
}
</script>

<template>
  <ManagementCrudShell :config="shellConfig" v-model:search="store.search" @create="showCreateForm = true">
    <template #handbook>
      <HelpButton rounded />
    </template>
    <SupplierManagementTable />
  </ManagementCrudShell>

  <SupplierFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
