<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { formatDateOrDash } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { projectStatusSeverity } from '@/features/projects'
import type { ProjectResponse } from '@/features/projects'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'

defineProps<{
  projects: ProjectResponse[]
}>()

const { t } = useI18n()
const router = useRouter()
const usersStore = useUsersStore()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

function projectPath(project: ProjectResponse): string {
  return `/workspace/projects/${project.id}`
}

function openProject(project: ProjectResponse): void {
  void router.push(projectPath(project))
}
</script>

<template>
  <DataTable
    :value="projects"
    data-key="id"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    class="projects-table"
    :pt="{ bodyRow: { 'data-testid': 'product-project-row' } }"
    @row-dblclick="(e) => openProject(e.data)"
  >
    <template #empty>
      <EmptyState
        icon="mdi mdi-folder-outline"
        :message="t('resources.products.detail.projects.empty')"
      />
    </template>
    <Column
      field="project_number"
      :header="t('resources.projects.columns.projectNumber')"
      sortable
      style="width: 11rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        <RouterLink class="project-link" :to="projectPath(data)">{{
          data.project_number
        }}</RouterLink>
      </template>
    </Column>
    <Column field="status" :header="t('resources.projects.columns.status')" sortable style="width: 9rem">
      <template #body="{ data }: { data: ProjectResponse }">
        <Tag
          :value="t(`resources.projects.status.${data.status}`)"
          :severity="projectStatusSeverity[data.status]"
        />
      </template>
    </Column>
    <Column :header="t('resources.projects.columns.customer')" style="width: 12rem">
      <template #body="{ data }: { data: ProjectResponse }">
        {{ data.customer?.name ?? getEmptyPlaceholder() }}
      </template>
    </Column>
    <Column :header="t('resources.projects.columns.designatedUser')" style="width: 12rem">
      <template #body="{ data }: { data: ProjectResponse }">
        <UserAvatarPreview :user="usersStore.getById(data.designated_user_id) ?? null" />
      </template>
    </Column>
    <Column field="description" :header="t('resources.projects.columns.description')">
      <template #body="{ data }: { data: ProjectResponse }">
        <span class="description">{{ data.description ?? getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column
      field="required_delivery_date_made"
      :header="t('resources.projects.fields.requiredDeliveryDateMade')"
      sortable
      style="width: 11rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        {{ formatDateOrDash(data.required_delivery_date_made) }}
      </template>
    </Column>
    <Column
      field="required_delivery_date_bought"
      :header="t('resources.projects.fields.requiredDeliveryDateBought')"
      sortable
      style="width: 11rem"
    >
      <template #body="{ data }: { data: ProjectResponse }">
        {{ formatDateOrDash(data.required_delivery_date_bought) }}
      </template>
    </Column>
  </DataTable>
</template>

<style scoped lang="scss">
.projects-table {
  height: 100%;
}

.project-link {
  font-weight: 600;
  color: inherit;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.description {
  display: block;
  max-width: 30rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
