<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import CustomerManagementTable from '../components/CustomerManagementTable.vue'
import CustomerFormDialog from '../components/CustomerFormDialog.vue'
import { useCustomersStore } from '../stores/customersStore'
import { Permission } from '@/core/auth/permissions'
import type { CustomerResponse } from '../types/customerResponse'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const toast = useAppToast()
const store = useCustomersStore()

const showCreateForm = ref(false)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('resources.customers.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('name', 'asc'),
  },
  {
    label: t('resources.customers.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('name', 'desc'),
  },
  {
    label: t('resources.customers.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('resources.customers.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
  {
    label: t('resources.customers.views.sortByItems.changedDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('changed', 'desc'),
  },
  {
    label: t('resources.customers.views.sortByItems.changedAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('changed', 'asc'),
  },
])

const groupByItems = computed<MenuItem[]>(() => [
  {
    label: t('resources.customers.views.groupByItems.country'),
    icon: 'mdi mdi-earth',
    command: () => store.setGroupBy('country'),
  },
  {
    label: t('resources.customers.views.groupByItems.level'),
    icon: 'mdi mdi-star-outline',
    command: () => store.setGroupBy('level'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'customers',
  createLabel: t('resources.customers.createCustomer'),
  createPermission: Permission.WRITE_PROJECTS,
  sortByItems: sortByItems.value,
  groupByItems: groupByItems.value,
}))

function onSaved(customer: CustomerResponse): void {
  toast.success(customer.name, t('resources.customers.createCustomer'))
}
</script>

<template>
  <ManagementCrudShell :config="shellConfig" v-model:search="store.search" @create="showCreateForm = true">
    <template #handbook>
      <HelpButton rounded />
    </template>
    <CustomerManagementTable />
  </ManagementCrudShell>

  <CustomerFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
