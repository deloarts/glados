<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import type { MenuItem } from 'openvue/menuitem'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useMeetingNotesViewStore } from '../stores/meetingNotesViewStore'
import type { MeetingSort } from '../stores/meetingNotesViewStore'

/**
 * The views bar of the Meeting Notes tab: Sync, Views, Sort By, Show
 * Invalid and Clear, and on a product Hide Projects and Group By Project,
 * with the Project column switched on in the Views menu.
 */
const props = defineProps<{ ownerKind: 'project' | 'product' }>()

const { t } = useI18n()
const view = useMeetingNotesViewStore()
const { showInvalid, hideProjects, groupByProject, sortBy, showActions, showProjectColumn } = storeToRefs(view)

const SORTS: { key: MeetingSort; icon: string }[] = [
  { key: 'startsDesc', icon: 'mdi-sort-calendar-descending' },
  { key: 'startsAsc', icon: 'mdi-sort-calendar-ascending' },
  { key: 'numberDesc', icon: 'mdi-sort-numeric-descending' },
  { key: 'numberAsc', icon: 'mdi-sort-numeric-ascending' },
  { key: 'nameAsc', icon: 'mdi-sort-alphabetical-ascending' },
  { key: 'nameDesc', icon: 'mdi-sort-alphabetical-descending' },
]

const sortByItems = computed<MenuItem[]>(() =>
  SORTS.map((sort) => ({
    label: t(`meetings.views.sortByItems.${sort.key}`),
    icon: `mdi ${sort.icon}`,
    command: () => view.setSort(sort.key),
  })),
)

const isProduct = computed(() => props.ownerKind === 'product')
</script>

<template>
  <ViewsBar
    id-prefix="meeting-notes"
    :show-actions="showActions"
    :sort-by-items="sortByItems"
    :sort-by-active="sortBy !== 'startsDesc'"
    :has-active-filters="view.hasActiveFilters"
    data-testid="meeting-notes-views"
    @sync="view.triggerRefresh()"
    @toggle-show-actions="showActions = !showActions"
    @clear-sort-by="view.clearSort()"
    @clear="view.clearAll()"
  >
    <template v-if="isProduct" #start-extra>
      <Button
        :label="t('meetings.views.hideProjects')"
        icon="mdi mdi-folder-hidden"
        severity="contrast"
        :text="!hideProjects"
        :aria-pressed="hideProjects"
        data-testid="meeting-notes-hide-projects"
        @click="hideProjects = !hideProjects"
      />
      <Button
        :label="t('meetings.views.groupByProject')"
        icon="mdi mdi-file-tree-outline"
        severity="contrast"
        :text="!groupByProject"
        :disabled="hideProjects"
        :aria-pressed="groupByProject"
        data-testid="meeting-notes-group-by-project"
        @click="groupByProject = !groupByProject"
      />
    </template>
    <template #extra>
      <Button
        :label="t('meetings.views.showInvalid')"
        icon="mdi mdi-cancel"
        severity="contrast"
        :text="!showInvalid"
        :aria-pressed="showInvalid"
        data-testid="meeting-notes-show-invalid"
        @click="showInvalid = !showInvalid"
      />
    </template>
    <template v-if="isProduct" #popover-extra>
      <div class="views-toggle-item">
        <ToggleSwitch
          v-model="showProjectColumn"
          input-id="meeting-notes-project-column-toggle"
          :disabled="hideProjects"
          data-testid="meeting-notes-project-column"
        />
        <label for="meeting-notes-project-column-toggle">{{ t('meetings.views.showProjectColumn') }}</label>
      </div>
    </template>
  </ViewsBar>
</template>

<style lang="css" scoped>
.views-toggle-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  label {
    cursor: pointer;
  }
}
</style>
