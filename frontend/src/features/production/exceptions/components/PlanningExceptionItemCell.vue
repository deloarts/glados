<script setup lang="ts">
// The item of an exception row in the look of the lots table: the part
// number or order code as a link that opens the item, the article name or
// material below it. A raw material without a dimension shows its material
// as the link instead, so the cell never has an empty first line.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMadeItemLabel } from '@/features/made-items'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

import type { PlanningExceptionResponse } from '../types/planningExceptionResponse'

const props = defineProps<{
  row: PlanningExceptionResponse
}>()

const emit = defineEmits<{
  open: [row: PlanningExceptionResponse]
}>()

const { t } = useI18n()
const { format: madeItemLabel } = useMadeItemLabel()

const number = computed(() => {
  const { item_kind, item_number, item_revision } = props.row
  if (!item_number) return ''
  return item_kind === 'made' ? madeItemLabel(item_number, item_revision || null) : item_number
})

const title = computed(() => number.value || props.row.item_name)
const subtitle = computed(() => (number.value ? props.row.item_name : ''))
const missingPartNumber = computed(() => props.row.item_kind === 'made' && !number.value)

function open(): void {
  if (props.row.item_id !== null) emit('open', props.row)
}
</script>

<template>
  <div class="item-cell">
    <span
      v-if="missingPartNumber"
      class="item-name-warning item-link"
      role="button"
      tabindex="0"
      @click.stop="open"
      @keydown.enter="open"
    >
      <i class="mdi mdi-alert" aria-hidden="true" />
      {{ t('productionExceptions.noPartNumber') }}
    </span>
    <span
      v-else-if="title && row.item_id !== null"
      class="item-name item-link"
      role="button"
      tabindex="0"
      @click.stop="open"
      @keydown.enter="open"
      >{{ title }}</span
    >
    <span v-else-if="title" class="item-name">{{ title }}</span>
    <span v-else class="item-muted">{{ getEmptyPlaceholder() }}</span>
    <span v-if="missingPartNumber ? row.item_name : subtitle" class="item-code">{{
      missingPartNumber ? row.item_name : subtitle
    }}</span>
  </div>
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.item-link {
  cursor: pointer;
  color: inherit;
  width: fit-content;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.item-name {
  font-size: var(--font-size-md);
  font-weight: 600;
}

.item-code,
.item-muted {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.item-name-warning {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 500;
  font-size: var(--font-size-sm);
  color: var(--p-orange-500);
}
</style>
