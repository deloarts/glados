<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { WidgetConfigOf, WidgetDataOf } from '../../types/infoscreenFeed'
import LotRows from './LotRows.vue'
import WidgetFrame from './WidgetFrame.vue'

defineProps<{
  config: WidgetConfigOf<'late_lots'>
  data: WidgetDataOf<'late_lots'>
}>()

const { t } = useI18n()
</script>

<template>
  <WidgetFrame
    :title="config.title || t('infoscreenRuntime.widgets.lateLots.title')"
    :count="data.lots.length"
  >
    <LotRows
      v-if="data.lots.length > 0"
      :lots="data.lots"
      :show-customer="config.show_customer"
    />
    <p v-else class="widget-empty">{{ t('infoscreenRuntime.widgets.lateLots.empty') }}</p>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.widget-empty {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
