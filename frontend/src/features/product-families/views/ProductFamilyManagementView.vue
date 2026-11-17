<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import ProductFamilyManagementTable from '../components/ProductFamilyManagementTable.vue'
import ProductFamilyFormDialog from '../components/ProductFamilyFormDialog.vue'
import { useProductFamiliesStore } from '../stores/productFamiliesStore'
import { Permission } from '@/core/auth/permissions'
import type { ProductFamilyResponse } from '../types/productFamilyResponse'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const toast = useAppToast()
const store = useProductFamiliesStore()

const showCreateForm = ref(false)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('settings.productFamilies.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('name', 'asc'),
  },
  {
    label: t('settings.productFamilies.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('name', 'desc'),
  },
  {
    label: t('settings.productFamilies.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('settings.productFamilies.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'product-families',
  createLabel: t('settings.productFamilies.createFamily'),
  createPermission: Permission.WRITE_ARTICLE_GROUPS,
  sortByItems: sortByItems.value,
}))

function onSaved(family: ProductFamilyResponse): void {
  toast.success(family.name, t('settings.productFamilies.createFamily'))
}
</script>

<template>
  <ManagementCrudShell :config="shellConfig" v-model:search="store.search" @create="showCreateForm = true">
    <template #handbook>
      <HelpButton rounded />
    </template>
    <ProductFamilyManagementTable />
  </ManagementCrudShell>

  <ProductFamilyFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
