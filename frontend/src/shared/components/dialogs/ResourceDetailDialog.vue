<script setup lang="ts">
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
export interface DetailField {
  label: string
  value: string | null | undefined
}

defineProps<{
  visible: boolean
  title: string
  fields: DetailField[]
}>()

defineEmits<{ 'update:visible': [boolean] }>()
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    :header="title"
    modal
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div class="detail-grid">
      <div v-for="field in fields" :key="field.label" class="detail-row">
        <span class="detail-label">{{ field.label }}</span>
        <span class="detail-value">{{ field.value ?? getEmptyPlaceholder() }}</span>
      </div>
    </div>
  </Dialog>
</template>

<style scoped lang="scss">
.detail-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-2) var(--space-5);
  align-items: start;
}

.detail-label {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
  white-space: nowrap;
}

.detail-value {
  font-weight: 500;
  overflow-wrap: anywhere;
}
</style>
