<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import SourceItemTypeManagementTable from '../components/SourceItemTypeManagementTable.vue'
import SourceItemTypeFormDialog from '../components/SourceItemTypeFormDialog.vue'
import { useSourceItemTypesStore } from '../stores/sourceItemTypesStore'
import { Permission } from '@/core/auth/permissions'
import type { SourceItemTypeResponse } from '../types/sourceItemTypeResponse'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const { localize } = useLocalizedText()
const toast = useAppToast()
const store = useSourceItemTypesStore()

const showCreateForm = ref(false)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('settings.sourceItemTypes.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('name', 'asc'),
  },
  {
    label: t('settings.sourceItemTypes.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('name', 'desc'),
  },
  {
    label: t('settings.sourceItemTypes.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('settings.sourceItemTypes.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'source-item-types',
  createLabel: t('settings.sourceItemTypes.createType'),
  createPermission: Permission.WRITE_SOURCE_ITEM_TYPES,
  sortByItems: sortByItems.value,
}))

function onSaved(type: SourceItemTypeResponse): void {
  toast.success(localize(type.name), t('settings.sourceItemTypes.createType'))
}
</script>

<template>
  <ManagementCrudShell :config="shellConfig" v-model:search="store.search" @create="showCreateForm = true">
    <template #handbook>
      <HelpButton rounded />
    </template>
    <SourceItemTypeManagementTable />
  </ManagementCrudShell>

  <SourceItemTypeFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
