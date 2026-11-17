<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import ManagementCrudShell from '@/shared/components/management/ManagementCrudShell.vue'
import { HelpButton } from '@/shared/help'
import type { ManagementCrudShellConfig } from '@/shared/components/management/ManagementCrudShell.vue'
import ProjectManagementTable from '../components/ProjectManagementTable.vue'
import ProjectFormDialog from '../components/ProjectFormDialog.vue'
import { useProjectsStore } from '../stores/projectsStore'
import { Permission } from '@/core/auth/permissions'
import type { ProjectResponse } from '../types/projectResponse'

import type { MenuItem } from 'openvue/menuitem'

const { t } = useI18n()
const toast = useAppToast()
const store = useProjectsStore()

const showCreateForm = ref(false)

const sortByItems = computed<MenuItem[]>(() => [
  {
    label: t('resources.projects.views.sortByItems.projectNumberAsc'),
    icon: 'mdi mdi-sort-alphabetical-ascending',
    command: () => store.setSort('project_number', 'asc'),
  },
  {
    label: t('resources.projects.views.sortByItems.projectNumberDesc'),
    icon: 'mdi mdi-sort-alphabetical-descending',
    command: () => store.setSort('project_number', 'desc'),
  },
  {
    label: t('resources.projects.views.sortByItems.createdDesc'),
    icon: 'mdi mdi-sort-clock-descending',
    command: () => store.setSort('created', 'desc'),
  },
  {
    label: t('resources.projects.views.sortByItems.createdAsc'),
    icon: 'mdi mdi-sort-clock-ascending',
    command: () => store.setSort('created', 'asc'),
  },
])

const groupByItems = computed<MenuItem[]>(() => [
  {
    label: t('resources.projects.views.groupByItems.customer'),
    icon: 'mdi mdi-domain',
    command: () => store.setGroupBy('customer'),
  },
  {
    label: t('resources.projects.views.groupByItems.status'),
    icon: 'mdi mdi-check-circle-outline',
    command: () => store.setGroupBy('status'),
  },
])

const shellConfig = computed<ManagementCrudShellConfig>(() => ({
  store,
  idPrefix: 'projects',
  createLabel: t('resources.projects.createProject'),
  createPermission: Permission.WRITE_PROJECTS,
  sortByItems: sortByItems.value,
  groupByItems: groupByItems.value,
}))

function onSaved(project: ProjectResponse): void {
  toast.success(project.project_number, t('resources.projects.createProject'))
}
</script>

<template>
  <ManagementCrudShell :config="shellConfig" v-model:search="store.search" @create="showCreateForm = true">
    <ProjectManagementTable />
    <template #handbook>
      <HelpButton rounded slug="workspace/projects" />
    </template>
  </ManagementCrudShell>

  <ProjectFormDialog v-model:visible="showCreateForm" @saved="onSaved" />
</template>
