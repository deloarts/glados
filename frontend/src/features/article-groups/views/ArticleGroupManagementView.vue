<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import ArticleGroupManagementTable from '../components/ArticleGroupManagementTable.vue'
import ArticleGroupFormDialog from '../components/ArticleGroupFormDialog.vue'
import { useArticleGroupsStore } from '../stores/articleGroupsStore'
import { Permission } from '@/core/auth/permissions'
import type { ArticleGroupResponse } from '../types/articleGroupResponse'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const { localize } = useLocalizedText()
const toast = useAppToast()
const store = useArticleGroupsStore()

const showCreateForm = ref(false)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('settings.articleGroups.views.sortByItems.nameAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('name', 'asc'),
  },
  {
    label: t('settings.articleGroups.views.sortByItems.nameDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('name', 'desc'),
  },
  {
    label: t('settings.articleGroups.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('settings.articleGroups.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'article-groups',
  createLabel: t('settings.articleGroups.createGroup'),
  createPermission: Permission.WRITE_ARTICLE_GROUPS,
  sortByItems: sortByItems.value,
}))

function onSaved(group: ArticleGroupResponse): void {
  toast.success(localize(group.name), t('settings.articleGroups.createGroup'))
}
</script>

<template>
  <ManagementCrudShell :config="shellConfig" v-model:search="store.search" @create="showCreateForm = true">
    <template #handbook>
      <HelpButton rounded />
    </template>
    <ArticleGroupManagementTable />
  </ManagementCrudShell>

  <ArticleGroupFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
