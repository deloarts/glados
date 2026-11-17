<script setup lang="ts">
// Shown under a picker control when its current value is an archived row;
// referencing one is allowed, this just makes the choice visible. Pair with
// useArchivableOptions.ts's `isArchived()` for the `v-if` condition.
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <small class="archived-selection-warning">
    <i class="mdi mdi-alert-outline" aria-hidden="true" />
    {{ t('common.archivedSelectionWarning') }}
  </small>
</template>

<style scoped lang="scss">
.archived-selection-warning {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--p-orange-500);
}
</style>
