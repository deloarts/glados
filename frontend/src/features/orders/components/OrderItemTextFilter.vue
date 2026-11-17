<script setup lang="ts">
// Text row filter of the order items table. The v-model and the input
// listener fall through to the InputText.
import { useI18n } from 'vue-i18n'

defineProps<{
  column: string
}>()

const { t } = useI18n()
</script>

<template>
  <InputText
    :placeholder="t('orders.filters.filterBy')"
    :aria-label="t('common.filterBy', { column })"
    size="small"
    fluid
  />
</template>
