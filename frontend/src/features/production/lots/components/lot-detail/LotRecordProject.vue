<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useUsersStore } from '@/core/stores/usersStore'
import { getProjectChangelog, projectStatusSeverity } from '@/features/projects'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { useChangedByUser } from '../../composables/useChangedByUser'
import LotRecordMeta from './LotRecordMeta.vue'

import type { LotResponse } from '../../../types/productionLotsResponse'
import type { ProjectResponse, ProjectChangelogEntry } from '@/features/projects'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

const props = defineProps<{
  lot: LotResponse
  project: ProjectResponse | null
}>()

const { t } = useI18n()
const usersStore = useUsersStore()

const changelogEntries = ref<ProjectChangelogEntry[]>([])

watch(
  () => props.project?.id ?? null,
  async (id) => {
    changelogEntries.value = []
    if (id === null) return
    changelogEntries.value = await getProjectChangelog(id)
  },
  { immediate: true },
)

const { resolve } = useChangedByUser()
const changedBy = computed(() => resolve(changelogEntries.value))
</script>

<template>
  <Panel
    :header="t('production.lots.detail.record.project.title')"
    :pt="{ header: { 'data-testid': 'record-card-header' } }"
  >
    <!-- Everything above LotRecordMeta scrolls; the meta footer is a sibling
         so it stays pinned to the card's bottom edge. -->
    <div class="card-scroll-body">
      <div class="detail-grid">
        <div class="field">
          <span class="field-label">{{ t('production.lots.detail.record.project.number') }}</span>
          <RouterLink class="field-value field-link" :to="`/workspace/projects/${lot.project_id}`">
            {{ lot.project_number }}
          </RouterLink>
        </div>
        <div class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.project.container')
          }}</span>
          <span class="field-value">{{
            project?.product?.product_number ?? getEmptyPlaceholder()
          }}</span>
        </div>
        <div class="field">
          <span class="field-label">{{ t('production.lots.detail.record.project.customer') }}</span>
          <span class="field-value">{{ project?.customer?.name ?? lot.project_customer }}</span>
        </div>
        <div v-if="project" class="field">
          <span class="field-label">{{
            t('production.lots.detail.record.project.assignedUser')
          }}</span>
          <UserAvatarPreview :user="usersStore.getById(project.designated_user_id) ?? null" />
        </div>
        <div v-if="project" class="field">
          <span class="field-label">{{ t('production.lots.detail.record.project.status') }}</span>
          <Tag
            :value="t(`production.lots.detail.record.project.statusValues.${project.status}`)"
            :severity="projectStatusSeverity[project.status]"
          />
        </div>
        <div class="field field-wide">
          <span class="field-label">{{
            t('production.lots.detail.record.project.description')
          }}</span>
          <span class="field-value">{{ project?.description || getEmptyPlaceholder() }}</span>
        </div>
      </div>
    </div>

    <LotRecordMeta
      v-if="project"
      :creator="project.creator"
      :created="project.created.slice(0, 10)"
      :changed="project.changed?.slice(0, 10) ?? null"
      :changed-by="changedBy"
    />
  </Panel>
</template>

<style scoped lang="scss">
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
  gap: var(--space-3) var(--space-5);
}

.field {
  min-width: 0;
}

.field-wide {
  grid-column: 1 / -1;
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-link {
  color: var(--p-primary-color);
  text-decoration: none;
  width: fit-content;

  &:hover {
    text-decoration: underline;
  }
}
</style>
