<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import FabricationMethodManagementTable from '../components/FabricationMethodManagementTable.vue'
import FabricationMethodFormDialog from '../components/FabricationMethodFormDialog.vue'
import { Permission } from '@/core/auth/permissions'

import type { MenuItem } from 'openvue/menuitem'
import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import type { FabricationMethodResponse } from '@/features/fabrication-methods'

const { t } = useI18n()
const { localize } = useLocalizedText()
const toast = useAppToast()
const store = useFabricationMethodsStore()

const showCreateForm = ref(false)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('resources.fabricationMethods.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('name', 'asc'),
  },
  {
    label: t('resources.fabricationMethods.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('name', 'desc'),
  },
  {
    label: t('resources.fabricationMethods.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('resources.fabricationMethods.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'fabrication-methods',
  createLabel: t('resources.fabricationMethods.createMethod'),
  createPermission: Permission.WRITE_FABRICATION_METHODS,
  sortByItems: sortByItems.value,
}))

function onSaved(method: FabricationMethodResponse): void {
  toast.success(localize(method.name), t('resources.fabricationMethods.createMethod'))
}
</script>

<template>
  <ManagementCrudShell :config="shellConfig" v-model:search="store.search" @create="showCreateForm = true">
    <template #handbook>
      <HelpButton rounded />
    </template>
    <FabricationMethodManagementTable />
  </ManagementCrudShell>

  <FabricationMethodFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
