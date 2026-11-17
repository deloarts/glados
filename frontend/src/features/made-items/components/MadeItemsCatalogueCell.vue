<script setup lang="ts">
// Body of the made items catalogue columns that render more than the plain
// field value. Opening a linked item, the successor popover or a file
// preview is emitted, since the dialogs live once on the table.
import { useI18n } from 'vue-i18n'

import { useClipboard } from '@/core/composables/useClipboard'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import { usePdmPreviewStore } from '@/shared/pdm-preview/pdmPreviewStore'
import PdmPreviewBadge from '@/shared/pdm-preview/PdmPreviewBadge.vue'
import MadeItemThumbnailCell from './MadeItemThumbnailCell.vue'
import MadeItemFilesCell from './MadeItemFilesCell.vue'
import {
  groupMethodLabel,
  processGroups,
  processRoutingLabel as groupedProcessRoutingLabel,
} from '../utils/madeItemProcessGroups'
import { useMadeItemLabel } from '../utils/madeItemLabel'

import type { MadeItemFile, MadeItemResponse } from '../types/madeItemsResponse'
import type { SourceItemResponse } from '@/features/source-items'
import type { BoughtItemResponse } from '@/features/bought-items'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'
import LabelTag from '@/shared/components/labels/LabelTag.vue'

const props = defineProps<{
  item: MadeItemResponse
  field: string
}>()

const emit = defineEmits<{
  openBoughtItem: [item: BoughtItemResponse]
  openSourceItem: [item: SourceItemResponse]
  openSuccessor: [event: Event, successorId: number]
  previewFile: [itemId: number, file: MadeItemFile]
}>()

const { t, locale } = useI18n()
const { copyToClipboard } = useClipboard()
const pdmPreviewStore = usePdmPreviewStore()
const { format: madeItemLabel } = useMadeItemLabel()

function openBoughtItem(): void {
  if (props.item.bought_item) emit('openBoughtItem', props.item.bought_item)
}

function openSourceItem(): void {
  if (props.item.source_item) emit('openSourceItem', props.item.source_item)
}

function sourceItemLabel(): string {
  const source = props.item.source_item
  return source ? source.material || `#${source.id}` : ''
}

function openSuccessor(event: Event): void {
  if (props.item.successor_item_id) emit('openSuccessor', event, props.item.successor_item_id)
}

// Steps grouped by group_index in position order; a group of two or more
// becomes one shared lot position when a lot is created from this routing.
function routingGroups() {
  return processGroups(props.item.processes ?? [])
}
</script>

<template>
  <UserDateCell v-if="field === 'created'" :date="item.created" :user="item.creator" />
  <UserDateCell
    v-if="field === 'changed'"
    :date="item.changed"
    :user-id="item.changed_by_id"
    :user="item.changed_by"
  />
  <MadeItemThumbnailCell
    v-if="field === 'image'"
    :item-id="item.id"
    :item-name="item.article_name"
  />
  <div v-if="field === 'article_name'" class="article-name-cell">
    <span>{{ item.article_name }}</span>
    <span
      v-if="item.bought_item"
      class="source-item-name"
      role="button"
      tabindex="0"
      v-tooltip.focus="t('madeItems.catalogue.detail.sourceItem')"
      @click.stop="openBoughtItem"
      @keydown.enter="openBoughtItem"
      @keydown.space.prevent="openBoughtItem"
    >
      {{ item.bought_item?.article_name ?? '' }}
    </span>
    <span
      v-else-if="item.source_item"
      class="source-item-name"
      role="button"
      tabindex="0"
      v-tooltip.focus="t('madeItems.catalogue.detail.sourceItem')"
      @click.stop="openSourceItem"
      @keydown.enter="openSourceItem"
      @keydown.space.prevent="openSourceItem"
    >
      {{ sourceItemLabel() }}
    </span>
  </div>
  <Tag
    v-if="field === 'data_source'"
    :value="t(`madeItems.catalogue.dataSources.${item.data_source}`)"
    :severity="item.data_source === 'CAD' ? 'info' : 'secondary'"
  />
  <div v-if="field === 'status'" class="state-cell">
    <Tag
      :value="t(`madeItems.catalogue.status.${item.status}`)"
      :severity="catalogueStatusTagSeverity(item.status)"
    />
    <Tag
      v-if="item.archived"
      :value="t('common.archivedTag')"
      severity="warn"
      icon="mdi mdi-archive-outline"
      v-tooltip.top="t('common.archivedTagTooltip')"
    />
  </div>
  <div v-if="field === 'article_groups'" class="article-groups-cell">
    <LabelTag
      v-for="group in item.article_groups ?? []"
      :key="group.id"
      :label="group"
    />
  </div>
  <div v-if="field === 'successor_item_id'" class="successor-cell">
    <Tag
      v-if="item.successor_item_id"
      :value="`#${item.successor_item_id}`"
      severity="secondary"
      class="successor-tag"
      role="button"
      tabindex="0"
      @click.stop="openSuccessor($event)"
      @keydown.enter="openSuccessor($event)"
      @keydown.space.prevent="openSuccessor($event)"
    />
  </div>
  <div v-if="field === 'source_label'" class="source-cell">
    <div v-if="item.source_label" class="source-info">
      <span class="source-label">{{ item.source_label }}</span>
      <span v-if="item.source_sublabel" class="source-sublabel">
        {{ item.source_sublabel }}
      </span>
    </div>
    <span v-else class="source-label">{{ getEmptyPlaceholder() }}</span>
  </div>
  <div
    v-if="field === 'processes'"
    class="processes-cell"
    v-tooltip="groupedProcessRoutingLabel(item.processes ?? [], locale)"
  >
    <template v-if="routingGroups().length">
      <Tag
        v-for="group in routingGroups()"
        :key="group.groupIndex"
        :value="
          group.processes.length > 1
            ? `${groupMethodLabel(group, locale)} (${group.processes.length})`
            : groupMethodLabel(group, locale)
        "
        severity="secondary"
      />
    </template>
    <span v-else>{{ getEmptyPlaceholder() }}</span>
  </div>
  <MadeItemFilesCell
    v-if="field === 'files'"
    :item-id="item.id"
    @preview="(file) => emit('previewFile', item.id, file)"
  />
  <div v-if="field === 'public_id'" class="public-id-cell">
    <span>{{ item.public_id }}</span>
    <Button
      icon="mdi mdi-content-copy"
      text
      rounded
      size="small"
      v-tooltip.focus="t('common.copyUuid')"
      :aria-label="t('common.copyUuid')"
      @click.stop="copyToClipboard(item.public_id)"
    />
  </div>
  <div v-if="field === 'part_number'" class="part-number-cell">
    <span>{{ madeItemLabel(item.part_number, item.revision) }}</span>
    <PdmPreviewBadge
      v-if="pdmPreviewStore.isNewer('made', item.public_id)"
      :preview="pdmPreviewStore.isNewer('made', item.public_id)!"
    />
  </div>
</template>

<style lang="scss" scoped>
.state-cell {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.article-name-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.source-item-name {
  font-size: var(--font-size-xs);
  font-style: italic;
  color: var(--p-text-muted-color);
  cursor: pointer;
  width: fit-content;

  &:hover {
    text-decoration: underline;
  }

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}

.article-groups-cell {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.source-cell {
  display: flex;
  align-items: center;
}

.source-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.source-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.source-sublabel {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.part-number-cell {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

// One line, never wrapped: a long routing is clipped and read via the
// cell's tooltip or by widening the column.
.processes-cell {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: var(--space-1);
  overflow: hidden;

  :deep(.p-tag) {
    white-space: nowrap;
  }
}

.public-id-cell {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-family: monospace;
  font-size: var(--font-size-xs);
}

.successor-tag {
  cursor: pointer;

  &:focus-visible {
    outline: var(--p-focus-ring-width) var(--p-focus-ring-style) var(--p-focus-ring-color);
    outline-offset: 2px;
  }
}
</style>
