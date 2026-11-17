<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import type {
  DataTableRowClickEvent,
  DataTableRowContextMenuEvent,
} from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { localeEndonym } from '@/core/i18n/localeMessages'
import { TABLE_DEFAULT_ROWS, TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import { scheduleSummary } from '../utils/displaySchedule'

import type { InfoscreenResponse } from '../types/infoscreenResponse'

/**
 * The infoscreens, with the terminals each one is shown on and when their
 * displays are on. Clicking a row opens the editor, and the row context
 * menu offers every action; the actions column shows only while Show
 * Actions is on. The display schedule, archiving and restoring need the
 * permission to write infoscreens and stay visible but disabled without it.
 */
const props = defineProps<{
  infoscreens: InfoscreenResponse[]
  showArchived: boolean
  /** Whether the actions column is shown, the Show Actions switch of the views bar. */
  showActions: boolean
  canWrite: boolean
  /** The tooltip of a disabled button, naming the missing permission. */
  missingHint: string
}>()

const emit = defineEmits<{
  open: [infoscreen: InfoscreenResponse]
  preview: [infoscreen: InfoscreenResponse]
  schedule: [infoscreen: InfoscreenResponse]
  archive: [infoscreen: InfoscreenResponse]
  restore: [infoscreen: InfoscreenResponse]
}>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

// The page shown; a search or a live change that leaves fewer rows than the
// page starts at goes back to the first page.
const first = ref(0)
const pageRows = ref(TABLE_DEFAULT_ROWS)
watch(
  () => props.infoscreens.length,
  (count) => {
    if (first.value >= count) first.value = 0
  },
)
const branding = usePublicBrandingStore()

/**
 * The language a screen shows its built-in words in: its own, or the
 * default of this installation together with the language that resolves to
 * today, since changing the default changes such a screen too.
 */
function languageText(infoscreen: InfoscreenResponse): string {
  if (infoscreen.language) return localeEndonym(infoscreen.language)
  const fallback = branding.branding?.default_language
  return fallback
    ? t('infoscreens.languageDefaultResolved', { language: localeEndonym(fallback) })
    : t('infoscreens.editor.tenantDefault')
}

// A click on the action buttons, disabled ones included, is not a click on the row.
function onRowClick(event: DataTableRowClickEvent): void {
  const target = event.originalEvent.target
  if (target instanceof Element && target.closest('.row-actions')) return
  emit('open', event.data as InfoscreenResponse)
}

const cm = ref()
const contextMenuTarget = ref<InfoscreenResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

// The fixed shape: opening first, then editing, then archiving or restoring.
const contextMenuItems = computed<MenuItem[]>(() => {
  const infoscreen = contextMenuTarget.value
  if (!infoscreen) return []
  const title = props.canWrite ? undefined : props.missingHint
  return [
    {
      label: t('infoscreens.actions.edit'),
      icon: 'mdi mdi-pencil',
      command: () => emit('open', infoscreen),
    },
    {
      label: t('infoscreens.actions.preview'),
      icon: 'mdi mdi-open-in-new',
      command: () => emit('preview', infoscreen),
    },
    { separator: true },
    {
      label: t('infoscreens.actions.schedule'),
      icon: 'mdi mdi-calendar-clock',
      disabled: !props.canWrite,
      title,
      command: () => emit('schedule', infoscreen),
    },
    { separator: true },
    infoscreen.archived
      ? {
          label: t('common.restore'),
          icon: 'mdi mdi-archive-arrow-up-outline',
          disabled: !props.canWrite,
          title,
          command: () => emit('restore', infoscreen),
        }
      : {
          label: t('common.archive'),
          icon: 'mdi mdi-archive-outline',
          disabled: !props.canWrite,
          title,
          command: () => emit('archive', infoscreen),
        },
  ]
})
</script>

<template>
  <DataTable
    :value="infoscreens"
    data-key="id"
    v-model:first="first"
    v-model:rows="pageRows"
    paginator
    always-show-paginator
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    scrollable
    scroll-height="flex"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    row-hover
    class="clickable-rows"
    v-model:context-menu-selection="contextMenuTarget"
    data-testid="infoscreens-table"
    @row-click="onRowClick"
    @row-contextmenu="onRowContextMenu"
  >
    <template #empty>
      <EmptyState :message="t('infoscreens.table.empty')" />
    </template>

    <Column header="#" class="column-fit" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column v-if="showActions" :header="t('infoscreens.columns.actions')" class="column-fit">
      <template #body="{ data }: { data: InfoscreenResponse }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            v-tooltip.top="t('infoscreens.actions.edit')"
            :aria-label="t('infoscreens.actions.edit')"
            @click="emit('open', data)"
          />
          <Button
            icon="mdi mdi-open-in-new"
            size="small"
            severity="secondary"
            text
            v-tooltip.top="t('infoscreens.actions.preview')"
            :aria-label="t('infoscreens.actions.preview')"
            data-testid="infoscreen-preview"
            @click="emit('preview', data)"
          />
          <span v-tooltip.top="canWrite ? t('infoscreens.actions.schedule') : missingHint">
            <Button
              icon="mdi mdi-calendar-clock"
              size="small"
              severity="secondary"
              text
              :disabled="!canWrite"
              :aria-label="t('infoscreens.actions.schedule')"
              data-testid="infoscreen-display-schedule"
              @click="emit('schedule', data)"
            />
          </span>
          <span
            v-if="data.archived"
            v-tooltip.top="canWrite ? t('common.restore') : missingHint"
          >
            <Button
              icon="mdi mdi-archive-arrow-up-outline"
              size="small"
              severity="secondary"
              text
              :disabled="!canWrite"
              :aria-label="t('common.restore')"
              data-testid="infoscreen-restore"
              @click="emit('restore', data)"
            />
          </span>
          <span v-else v-tooltip.top="canWrite ? t('common.archive') : missingHint">
            <Button
              icon="mdi mdi-archive-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canWrite"
              :aria-label="t('common.archive')"
              data-testid="infoscreen-archive"
              @click="emit('archive', data)"
            />
          </span>
        </div>
      </template>
    </Column>
    <Column field="name" :header="t('infoscreens.columns.name')" class="column-fit">
      <template #body="{ data }: { data: InfoscreenResponse }">
        <div class="name-cell">
          <span>{{ data.name }}</span>
          <span v-if="data.description" class="description">{{ data.description }}</span>
        </div>
      </template>
    </Column>
    <Column :header="t('infoscreens.columns.pages')" class="column-fit">
      <template #body="{ data }: { data: InfoscreenResponse }">{{ data.pages.length }}</template>
    </Column>
    <Column :header="t('infoscreens.columns.rotation')" class="column-fit">
      <template #body="{ data }: { data: InfoscreenResponse }">
        {{ t('infoscreens.seconds', { seconds: data.rotation_seconds }) }}
      </template>
    </Column>
    <Column :header="t('infoscreens.columns.language')" class="column-fit">
      <template #body="{ data }: { data: InfoscreenResponse }">
        <span data-testid="infoscreen-language">{{ languageText(data) }}</span>
      </template>
    </Column>
    <Column :header="t('infoscreens.columns.colorMode')" class="column-fit">
      <template #body="{ data }: { data: InfoscreenResponse }">
        {{ t(`infoscreens.colorModes.${data.color_mode}`) }}
      </template>
    </Column>
    <Column :header="t('infoscreens.columns.schedule')" class="column-fit">
      <template #body="{ data }: { data: InfoscreenResponse }">
        <span data-testid="infoscreen-schedule-summary">
          {{ t(`infoscreens.scheduleSummary.${scheduleSummary(data)}`) }}
        </span>
      </template>
    </Column>
    <Column :header="t('infoscreens.columns.shownOn')" class="column-fit">
      <template #body="{ data }: { data: InfoscreenResponse }">
        <div v-if="data.shown_on.length > 0" class="tags" data-testid="infoscreen-shown-on">
          <Tag
            v-for="terminal in data.shown_on"
            :key="terminal.id"
            :value="terminal.name ?? t('infoscreens.unnamedTerminal')"
            severity="secondary"
            icon="mdi mdi-monitor-dashboard"
          />
        </div>
        <span v-else class="text-muted">{{ t('infoscreens.notShown') }}</span>
      </template>
    </Column>
    <Column v-if="showArchived" :header="t('common.archivedTag')" class="column-fit">
      <template #body="{ data }: { data: InfoscreenResponse }">
        <Tag
          v-if="data.archived"
          :value="t('common.archivedTag')"
          severity="warn"
          icon="mdi mdi-archive-outline"
        />
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('infoscreens.columns.changed')" class="column-fit">
      <template #body="{ data }: { data: InfoscreenResponse }">
        {{ formatISODateTime(data.changed ?? data.created) }}
      </template>
    </Column>
    <!-- Takes the width the content-wide columns leave, so the table spans
         its card without stretching them. -->
    <Column />
  </DataTable>

  <ContextMenu
    ref="cm"
    :model="contextMenuItems"
    :pt="disabledItemTooltipPt"
    @hide="contextMenuTarget = null"
  />
</template>

<style scoped lang="scss">
.name-cell {
  display: flex;
  flex-direction: column;
}

.description {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
