<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { MenuItem } from 'openvue/menuitem'

import { usePhoneLayout } from '@/core/composables/usePhoneLayout'

const { t } = useI18n()

// A phone keeps only sync, clear and search, as icon buttons beside a search
// box that takes the rest of the row. Views, grouping, sorting and the
// caller's extra buttons are for the desktop table.
const { phoneMode } = usePhoneLayout()

withDefaults(
  defineProps<{
    /** Prefixes the "show actions" toggle's inputId so it stays unique when several ViewsBars share a page. */
    idPrefix: string
    syncing?: boolean
    showActions?: boolean
    /** Hide the Views button + popover entirely, for resources with no show-actions toggle or #popover-extra content. */
    hideViewsToggle?: boolean
    /** Omit (or leave empty) to hide the Group By button entirely, since not every resource has a meaningful grouping. */
    groupByItems?: MenuItem[]
    groupByActive?: boolean
    /** Omit (or leave empty) to hide the Sort By button entirely. */
    sortByItems?: MenuItem[]
    sortByActive?: boolean
    hasActiveFilters: boolean
    /** Placeholder for the built-in search box, falls back to common.search. Ignored if `search` isn't bound. */
    searchPlaceholder?: string
    /**
     * Omit (leave `undefined`) for a resource that isn't archivable. The
     * Show Archived toggle is hidden entirely in that case. Pass the
     * resource's actual `showArchived` state to render it.
     */
    showArchived?: boolean
  }>(),
  {
    syncing: false,
    showActions: false,
    hideViewsToggle: false,
    groupByItems: () => [],
    groupByActive: false,
    sortByItems: () => [],
    sortByActive: false,
    searchPlaceholder: undefined,
    showArchived: undefined,
  },
)

const emit = defineEmits<{
  sync: []
  'toggle-show-actions': []
  'clear-group-by': []
  'clear-sort-by': []
  clear: []
  'toggle-show-archived': []
}>()

/** Bind with `v-model:search` to get the far-right search box, omit entirely to leave it out. */
const search = defineModel<string>('search')

const viewsPopover = ref()

function toggleViewsPopover(event: Event) {
  viewsPopover.value.toggle(event)
}
</script>

<template>
  <Toolbar
    v-if="phoneMode"
    class="views-bar--phone"
    :pt="{ end: { class: 'views-bar-phone-end' } }"
  >
    <template #start>
      <Button
        icon="mdi mdi-sync"
        severity="contrast"
        text
        :loading="syncing"
        :aria-label="t('common.sync')"
        @click="emit('sync')"
      />
      <Button
        icon="mdi mdi-filter-off-outline"
        severity="contrast"
        text
        :disabled="!hasActiveFilters"
        :aria-label="t('common.clear')"
        @click="emit('clear')"
      />
      <!-- Filter toggles a page cannot do without on a phone, as icon
           buttons, for a page whose list has no desktop table to fall back on. -->
      <template v-if="$slots['phone-extra']">
        <Divider layout="vertical" />
        <slot name="phone-extra" />
      </template>
    </template>
    <template v-if="search !== undefined" #end>
      <IconField class="views-bar-phone-search">
        <InputIcon class="mdi mdi-magnify" />
        <InputText
          v-model="search"
          class="views-bar-phone-search-input"
          type="search"
          :placeholder="searchPlaceholder ?? t('common.search')"
          :aria-label="searchPlaceholder ?? t('common.search')"
        />
      </IconField>
    </template>
  </Toolbar>

  <Toolbar v-else>
    <template #start>
      <Button
        :label="t('common.sync')"
        icon="mdi mdi-sync"
        severity="contrast"
        text
        :loading="syncing"
        @click="emit('sync')"
      />
      <Button
        v-if="!hideViewsToggle"
        :label="t('common.views')"
        icon="mdi mdi-table-eye"
        severity="contrast"
        text
        @click="toggleViewsPopover"
      />
      <slot name="start-extra" />
      <Divider layout="vertical" />
      <SplitButton
        v-if="groupByItems.length > 0"
        :label="t('common.groupBy')"
        :model="groupByItems"
        severity="contrast"
        :text="!groupByActive"
        @click="emit('clear-group-by')"
      />
      <SplitButton
        v-if="sortByItems.length > 0"
        :label="t('common.sortBy')"
        :model="sortByItems"
        severity="contrast"
        :text="!sortByActive"
        @click="emit('clear-sort-by')"
      />
      <slot name="extra" />
      <Divider layout="vertical" />
      <Button
        v-if="showArchived !== undefined"
        :label="t('common.showArchived')"
        icon="mdi mdi-archive-outline"
        severity="contrast"
        :text="!showArchived"
        @click="emit('toggle-show-archived')"
      />
      <Button
        :label="t('common.clear')"
        icon="mdi mdi-filter-off-outline"
        severity="contrast"
        text
        :disabled="!hasActiveFilters"
        @click="emit('clear')"
      />
    </template>
    <template v-if="search !== undefined || $slots.end" #end>
      <IconField v-if="search !== undefined">
        <InputIcon class="mdi mdi-magnify" />
        <InputText v-model="search" :placeholder="searchPlaceholder ?? t('common.search')" />
      </IconField>
      <slot name="end" />
    </template>
  </Toolbar>

  <Popover v-if="!hideViewsToggle && !phoneMode" ref="viewsPopover">
    <div class="views-toggle-item">
      <ToggleSwitch
        :input-id="`${idPrefix}-show-actions-toggle`"
        :model-value="showActions"
        @update:model-value="emit('toggle-show-actions')"
      />
      <label :for="`${idPrefix}-show-actions-toggle`">
        {{ t('common.showActions') }}
      </label>
    </div>
    <slot name="popover-extra" />
  </Popover>
</template>

<style lang="css" scoped>
.views-bar--phone {
  flex-wrap: nowrap;
}

.views-bar--phone :deep(.views-bar-phone-end) {
  flex: 1 1 auto;
  min-width: 0;
}

.views-bar-phone-search {
  flex: 1 1 auto;
  min-width: 0;
}

.views-bar-phone-search-input {
  width: 100%;
}

.views-toggle-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  & + & {
    margin-top: var(--space-2);
  }

  label {
    cursor: pointer;
  }
}
</style>
