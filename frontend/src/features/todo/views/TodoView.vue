<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import TodoTaskRow from '../components/TodoTaskRow.vue'
import { useTodoTasks } from '../composables/useTodoTasks'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import EmptyState from '@/shared/components/EmptyState.vue'
import InfoBar from '@/shared/components/resource-view/InfoBar.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { HelpButton } from '@/shared/help'
import { TODO_CATEGORIES, type TodoBucket, type TodoCategory } from '../types/todoTask'

const { t } = useI18n()
const {
  visibleTasks,
  hiddenCount,
  showAll,
  selectedCategories,
  categoryCounts,
  toggleCategory,
  resetCategories,
  overdue,
  today,
  week,
  blockers,
  loading,
  errored,
  refresh,
} = useTodoTasks()

watchLoadingBar(loading)

const CATEGORY_ICONS: Record<TodoCategory, string> = {
  procurement: 'mdi mdi-cart',
  shop_floor: 'mdi mdi-factory',
  planning: 'mdi mdi-calendar-clock',
  meetings: 'mdi mdi-account-group-outline',
}

// Tells "everything filtered out" apart from "nothing to do".
const allCategoriesOff = computed(() => selectedCategories.value.length === 0)

// Any category switched off counts as a filter, which the views bar's Clear
// button resets.
const hasActiveFilters = computed(() => selectedCategories.value.length < TODO_CATEGORIES.length)

// The toggles of the views bar: All Categories first, pressed while every
// category is on, then one per category, pressed while it is on. A phone
// shows the same toggles as icon buttons, with the label as their tooltip.
const categoryToggles = computed(() => [
  {
    key: 'all',
    label: `${t('todo.allCategories')} (${TODO_CATEGORIES.reduce((sum, c) => sum + categoryCounts.value[c], 0)})`,
    icon: 'mdi mdi-checkbox-multiple-marked-outline',
    pressed: !hasActiveFilters.value,
    toggle: resetCategories,
  },
  ...TODO_CATEGORIES.map((category) => ({
    key: category,
    label: `${t(`todo.categories.${category}`)} (${categoryCounts.value[category]})`,
    icon: CATEGORY_ICONS[category],
    pressed: selectedCategories.value.includes(category),
    toggle: () => toggleCategory(category),
  })),
])

// The bucket cards show only when there are tasks; every other state is one
// message in the page's standard content card.
const showSections = computed(
  () => !errored.value && !allCategoriesOff.value && visibleTasks.value.length > 0,
)

// The count tag carries the bucket's urgency, in the colours of its rows.
const BUCKET_SEVERITY: Record<TodoBucket, 'danger' | 'warn' | 'info' | 'secondary'> = {
  overdue: 'danger',
  today: 'warn',
  week: 'info',
  blockers: 'secondary',
}

const sections = computed<{ key: TodoBucket; label: string; tasks: typeof visibleTasks.value }[]>(
  () => [
    { key: 'overdue', label: t('todo.buckets.overdue'), tasks: overdue.value },
    { key: 'today', label: t('todo.buckets.today'), tasks: today.value },
    { key: 'week', label: t('todo.buckets.week'), tasks: week.value },
    { key: 'blockers', label: t('todo.buckets.blockers'), tasks: blockers.value },
  ],
)
</script>

<template>
  <PageLayout :card="!showSections">
    <template #info>
      <InfoBar>
        <span class="info-title">{{ t('todo.title') }}</span>
        <span class="info-sep" />
        <span class="info-muted">{{ t('todo.openCount', { count: visibleTasks.length }) }}</span>
      </InfoBar>
    </template>
    <template #views>
      <ViewsBar
        id-prefix="todo"
        hide-views-toggle
        :syncing="loading"
        :has-active-filters="hasActiveFilters"
        @sync="refresh()"
        @clear="resetCategories()"
      >
        <template #extra>
          <Button
            v-for="toggle in categoryToggles"
            :key="toggle.key"
            :label="toggle.label"
            :icon="toggle.icon"
            severity="contrast"
            :text="!toggle.pressed"
            @click="toggle.toggle()"
          />
          <Divider layout="vertical" />
          <Button
            :label="showAll ? t('todo.showAll') : t('todo.showAllHidden', { count: hiddenCount })"
            icon="mdi mdi-format-list-bulleted"
            severity="contrast"
            :text="!showAll"
            :disabled="!showAll && hiddenCount === 0"
            @click="showAll = !showAll"
          />
        </template>
        <template #phone-extra>
          <Button
            v-for="toggle in categoryToggles"
            :key="toggle.key"
            v-tooltip.top="toggle.label"
            :icon="toggle.icon"
            :aria-label="toggle.label"
            severity="contrast"
            :text="!toggle.pressed"
            @click="toggle.toggle()"
          />
        </template>
        <!-- The page has no actions and so no controls bar, which leaves the
             views bar to close with the handbook button. -->
        <template #end>
          <HelpButton rounded slug="workspace/meeting-todos" />
        </template>
      </ViewsBar>
    </template>

    <div v-if="showSections" class="todo-sections">
      <SectionCard
        v-for="section in sections"
        :key="section.key"
        :title="section.label"
        fill
      >
        <template #title-end>
          <Tag :value="String(section.tasks.length)" :severity="BUCKET_SEVERITY[section.key]" />
        </template>
        <ul v-if="section.tasks.length > 0" class="todo-list">
          <TodoTaskRow v-for="task in section.tasks" :key="task.id" :task="task" />
        </ul>
        <p v-else class="empty-note">{{ t('todo.bucketEmpty') }}</p>
      </SectionCard>
    </div>

    <div v-else-if="loading && visibleTasks.length === 0" class="todo-state">
      <ProgressBar mode="indeterminate" class="todo-state-bar" />
    </div>

    <EmptyState v-else-if="errored" icon="mdi mdi-alert-circle-outline" :message="t('todo.loadError')">
      <Button :label="t('common.reload')" icon="mdi mdi-refresh" size="small" @click="refresh()" />
    </EmptyState>

    <EmptyState
      v-else-if="allCategoriesOff"
      icon="mdi mdi-filter-off-outline"
      :message="t('todo.emptyFiltered')"
    >
      <Button :label="t('todo.resetFilters')" size="small" @click="resetCategories()" />
    </EmptyState>

    <EmptyState
      v-else
      icon="mdi mdi-check-circle-outline"
      :message="hiddenCount > 0 ? t('todo.emptyImportant') : t('todo.empty')"
    >
      <Button
        v-if="hiddenCount > 0"
        :label="t('todo.showAllHidden', { count: hiddenCount })"
        size="small"
        @click="showAll = true"
      />
    </EmptyState>
  </PageLayout>
</template>

<style scoped lang="scss">
.info-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.info-muted {
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

// The four buckets sit side by side down to the bottom edge of the data
// area, and each card scrolls its own list.
.todo-sections {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(20rem, 1fr));
  gap: var(--space-2);
  height: 100%;
  min-height: 0;
}

.todo-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.todo-state-bar {
  width: min(22rem, 60%);
  height: 3px;
}

.todo-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
</style>

