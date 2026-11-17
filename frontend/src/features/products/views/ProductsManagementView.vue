<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import ProductManagementTable from '../components/ProductManagementTable.vue'
import ProductFormDialog from '../components/ProductFormDialog.vue'
import { useProductsStore } from '../stores/productsStore'
import { Permission } from '@/core/auth/permissions'
import type { ProductResponse } from '../types/productResponse'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const toast = useAppToast()
const store = useProductsStore()

const showCreateForm = ref(false)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('resources.products.views.sortByItems.productNumberAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('product_number', 'asc'),
  },
  {
    label: t('resources.products.views.sortByItems.productNumberDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('product_number', 'desc'),
  },
  {
    label: t('resources.products.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('resources.products.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
])

const groupByItems = computed<MenuItem[]>(() => [
  {
    label: t('resources.products.views.groupByItems.customer'),
    icon: 'mdi mdi-domain',
    command: () => store.setGroupBy('customer'),
  },
  {
    label: t('resources.products.views.groupByItems.active'),
    icon: 'mdi mdi-check-circle-outline',
    command: () => store.setGroupBy('is_active'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'products',
  createLabel: t('resources.products.createProduct'),
  createPermission: Permission.WRITE_PROJECTS,
  sortByItems: sortByItems.value,
  groupByItems: groupByItems.value,
}))

function onSaved(product: ProductResponse): void {
  toast.success(product.product_number, t('resources.products.createProduct'))
}
</script>

<template>
  <ManagementCrudShell :config="shellConfig" v-model:search="store.search" @create="showCreateForm = true">
    <ProductManagementTable />
    <template #handbook>
      <HelpButton rounded slug="workspace/products" />
    </template>
  </ManagementCrudShell>

  <ProductFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
