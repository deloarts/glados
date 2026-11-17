<script setup lang="ts">
// The Data Portal column of the import review: the part a row resolved to,
// a picker for an ambiguous row's candidates, or the action that creates a
// row the portal does not know from the file alone.
import { useI18n } from 'vue-i18n'

import EdpPartPicture from './EdpPartPicture.vue'

import type { BoughtItemImportResult } from '../types/boughtItemsImportTypes'
import type { EdpPartSummary } from '../types/boughtItemsEdpTypes'

const props = defineProps<{
  result: BoughtItemImportResult | undefined
  fromFile: boolean
}>()

const emit = defineEmits<{
  pin: [partId: number]
  skip: []
}>()

const { t } = useI18n()

function candidateLabel(part: EdpPartSummary): string {
  return [part.manufacturer_code, part.order_number ?? part.part_number, part.designation]
    .filter((v) => !!v)
    .join(' · ')
}

function onPin(value: unknown): void {
  if (typeof value === 'number') emit('pin', value)
}
</script>

<template>
  <div v-if="props.result?.edp_part" class="portal-cell">
    <EdpPartPicture :part-id="props.result.edp_part.part_id" size="2.5rem" />
    <div class="part">
      <span>{{ props.result.edp_part.designation }}</span>
      <a
        v-if="props.result.edp_part.part_page_url"
        :href="props.result.edp_part.part_page_url"
        target="_blank"
        rel="noopener noreferrer"
        >{{ props.result.edp_part.part_number }}</a
      >
      <small v-else>{{ props.result.edp_part.part_number }}</small>
    </div>
  </div>
  <Select
    v-else-if="(props.result?.candidates ?? []).length > 0"
    :aria-label="t('boughtItems.import.pickCandidate')"
    :options="props.result?.candidates ?? []"
    :option-label="candidateLabel"
    option-value="part_id"
    :placeholder="t('boughtItems.import.pickCandidate')"
    size="small"
    fluid
    data-testid="bought-item-import-candidate"
    @update:model-value="onPin"
  />
  <Button
    v-else-if="props.result?.row_status === 'not_found'"
    :label="t('boughtItems.import.createFromFile')"
    icon="mdi mdi-file-document-outline"
    size="small"
    text
    data-testid="bought-item-import-skip-lookup"
    @click="emit('skip')"
  />
  <span v-else-if="props.fromFile" class="muted">{{ t('boughtItems.import.fromFile') }}</span>
</template>

<style scoped lang="scss">
.portal-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.part {
  display: flex;
  flex-direction: column;
}

.muted {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}
</style>
