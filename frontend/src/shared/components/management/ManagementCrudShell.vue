<script setup lang="ts">
// The shared page chrome of a management view: the layout, a create button
// and a ViewsBar wired to the feature's store. The table comes in through
// the default slot, and the create dialog stays with the caller, which
// handles the emitted `create`.
import { computed } from 'vue'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { usePermissions } from '@/core/composables/usePermissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

import type { MenuItem } from 'openvue/menuitem'

/**
 * The store surface the shell drives the ViewsBar with. `search` is not
 * part of it, because writing through a prop is forbidden; the caller binds
 * `v-model:search` instead.
 */
export interface ManagementCrudShellStore {
  hasActiveFilters: boolean
  showActions: boolean
  /** Optional, since some resources cannot be sorted. */
  sortBy?: unknown
  groupBy?: unknown
  /**
   * Omit for a resource that isn't archivable. ViewsBar hides its Show
   * Archived toggle entirely when this stays `undefined`.
   */
  showArchived?: boolean
  triggerRefresh: () => void
  toggleShowActions: () => void
  clearSort?: () => void
  clearGroupBy?: () => void
  /**
   * Required alongside `showArchived` for an archivable resource; omit
   * for one that isn't.
   */
  toggleShowArchived?: () => void
  clearAll: () => void
}

export interface ManagementCrudShellConfig {
  store: ManagementCrudShellStore
  /**
   * Prefixes ViewsBar's "show actions" toggle id, so it stays unique when
   * several bars share a page. The convention is the feature's kebab-case
   * name, e.g. `'article-groups'`.
   */
  idPrefix: string
  /** `false` hides the create button, for resources whose rows are seeded. */
  showCreate?: boolean
  /** Translated create-button label; required unless `showCreate` is false. */
  createLabel?: string
  /** Gates the create button. Required unless `showCreate` is `false`. */
  createPermission?: string
  /**
   * Omit to hide the Sort By button. Not every resource has one (see the
   * note on `ManagementCrudShellStore.sortBy`).
   */
  sortByItems?: MenuItem[]
  /** Omit to hide the Group By button. Not every resource has one. */
  groupByItems?: MenuItem[]
  /** Forwarded to ViewsBar; defaults to `common.search`. */
  searchPlaceholder?: string
}

const props = defineProps<{ config: ManagementCrudShellConfig }>()

const emit = defineEmits<{ create: [] }>()

/** Forwarded to ViewsBar; bind `v-model:search` to the caller's store. */
const search = defineModel<string>('search')

const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const showCreate = computed(() => props.config.showCreate ?? true)
const canCreate = computed(
  () => !!props.config.createPermission && hasPermission(props.config.createPermission),
)
/** Names the missing create permission, shown on the disabled button. */
const createBlocked = computed(() =>
  props.config.createPermission ? missing(props.config.createPermission) : '',
)
</script>

<template>
  <PageLayout>
    <template #controls>
      <ControlsBar>
        <template #start>
          <!-- The span carries the tooltip, since a disabled button
               shows none of its own. -->
          <span v-if="showCreate" v-tooltip.bottom="createBlocked || undefined">
            <Button
              :label="config.createLabel"
              icon="mdi mdi-plus"
              severity="contrast"
              text
              :disabled="!canCreate"
              data-testid="management-create"
              @click="emit('create')"
            />
          </span>
          <!-- Escape hatch: a couple of features (products, projects)
               put one more button next to Create in their controls bar,
               kept feature-owned rather than added to `config`, since its
               markup/behaviour (an Export button today) isn't uniform.
               `print-labels`/`print-dockets` go further and set
               `showCreate: false`, using this same slot for their two
               bulk-action buttons in place of Create entirely. -->
          <slot name="extra-controls" />
        </template>
        <template #handbook>
          <!-- Forwarded rather than rendered here: each caller supplies its
               own HelpButton, which opens the handbook page of its route. -->
          <slot name="handbook" />
        </template>
      </ControlsBar>
    </template>
    <template #views>
      <ViewsBar
        :id-prefix="config.idPrefix"
        :show-actions="config.store.showActions"
        :sort-by-items="config.sortByItems"
        :sort-by-active="!!config.store.sortBy"
        :group-by-items="config.groupByItems"
        :group-by-active="!!config.store.groupBy"
        :has-active-filters="config.store.hasActiveFilters"
        :search-placeholder="config.searchPlaceholder"
        :show-archived="config.store.showArchived"
        v-model:search="search"
        @sync="config.store.triggerRefresh()"
        @toggle-show-actions="config.store.toggleShowActions()"
        @clear-group-by="config.store.clearGroupBy?.()"
        @clear-sort-by="config.store.clearSort?.()"
        @clear="config.store.clearAll()"
        @toggle-show-archived="config.store.toggleShowArchived?.()"
      />
    </template>
    <slot />
  </PageLayout>
</template>
