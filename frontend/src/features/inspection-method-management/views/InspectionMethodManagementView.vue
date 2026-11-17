<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import InspectionMethodManagementTable from '../components/InspectionMethodManagementTable.vue'
import InspectionMethodFormDialog from '../components/InspectionMethodFormDialog.vue'
import { Permission } from '@/core/auth/permissions'

import type { MenuItem } from 'openvue/menuitem'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import type { InspectionMethodResponse } from '@/features/inspection-methods'

const { t } = useI18n()
const { localize } = useLocalizedText()
const toast = useAppToast()
const store = useInspectionMethodsStore()

const showCreateForm = ref(false)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('resources.inspectionMethods.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('name', 'asc'),
  },
  {
    label: t('resources.inspectionMethods.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('name', 'desc'),
  },
  {
    label: t('resources.inspectionMethods.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('resources.inspectionMethods.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'inspection-methods',
  createLabel: t('resources.inspectionMethods.createMethod'),
  createPermission: Permission.WRITE_INSPECTION_METHODS,
  sortByItems: sortByItems.value,
}))

function onSaved(method: InspectionMethodResponse): void {
  toast.success(localize(method.name), t('resources.inspectionMethods.createMethod'))
}
</script>

<template>
  <ManagementCrudShell :config="shellConfig" v-model:search="store.search" @create="showCreateForm = true">
    <template #handbook>
      <HelpButton rounded />
    </template>
    <InspectionMethodManagementTable />
  </ManagementCrudShell>

  <InspectionMethodFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
