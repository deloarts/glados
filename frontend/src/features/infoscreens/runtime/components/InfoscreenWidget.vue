<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type {
  InfoscreenWidgetConfig,
  InfoscreenWidgetData,
  InfoscreenWidgetType,
  WidgetConfigOf,
  WidgetDataOf,
} from '../types/infoscreenFeed'
import ClockWidget from './widgets/ClockWidget.vue'
import DeliveriesExpectedWidget from './widgets/DeliveriesExpectedWidget.vue'
import LateLotsWidget from './widgets/LateLotsWidget.vue'
import LotsDueWidget from './widgets/LotsDueWidget.vue'
import MachineBoardWidget from './widgets/MachineBoardWidget.vue'
import MachineDetailWidget from './widgets/MachineDetailWidget.vue'
import MessageWidget from './widgets/MessageWidget.vue'
import ProductsWidget from './widgets/ProductsWidget.vue'
import ProjectsWidget from './widgets/ProjectsWidget.vue'
import QaQueueWidget from './widgets/QaQueueWidget.vue'
import WeatherWidget from './widgets/WeatherWidget.vue'
import WidgetFrame from './widgets/WidgetFrame.vue'

// One slot of a page: the slot's config with the feed's data for it. An
// empty slot stays blank. The clock and the message need nothing from the
// feed, so they render from their config alone; any other widget without
// matching data says so.
const props = defineProps<{
  config: InfoscreenWidgetConfig | null
  data: InfoscreenWidgetData | null
}>()

const { t } = useI18n()

type WidgetPair = {
  [T in InfoscreenWidgetType]: { type: T; config: WidgetConfigOf<T>; data: WidgetDataOf<T> }
}[InfoscreenWidgetType]

const pair = computed<WidgetPair | null>(() => {
  const { config, data } = props
  if (!config || !data || config.type !== data.type) return null
  return { type: config.type, config, data } as WidgetPair
})

const clockConfig = computed(() => (props.config?.type === 'clock' ? props.config : null))
const messageConfig = computed(() => (props.config?.type === 'message' ? props.config : null))
</script>

<template>
  <div v-if="!config" class="infoscreen-widget-empty" />
  <MachineBoardWidget
    v-else-if="pair?.type === 'machine_board'"
    :config="pair.config"
    :data="pair.data"
  />
  <LotsDueWidget v-else-if="pair?.type === 'lots_due'" :config="pair.config" :data="pair.data" />
  <LateLotsWidget v-else-if="pair?.type === 'late_lots'" :config="pair.config" :data="pair.data" />
  <QaQueueWidget v-else-if="pair?.type === 'qa_queue'" :config="pair.config" :data="pair.data" />
  <DeliveriesExpectedWidget
    v-else-if="pair?.type === 'deliveries_expected'"
    :config="pair.config"
    :data="pair.data"
  />
  <WeatherWidget v-else-if="pair?.type === 'weather'" :config="pair.config" :data="pair.data" />
  <ProductsWidget v-else-if="pair?.type === 'products'" :config="pair.config" :data="pair.data" />
  <ProjectsWidget v-else-if="pair?.type === 'projects'" :config="pair.config" :data="pair.data" />
  <MachineDetailWidget
    v-else-if="pair?.type === 'machine_detail'"
    :config="pair.config"
    :data="pair.data"
  />
  <ClockWidget
    v-else-if="clockConfig"
    :config="clockConfig"
    :data="data?.type === 'clock' ? data : null"
  />
  <MessageWidget
    v-else-if="messageConfig"
    :config="messageConfig"
    :data="data?.type === 'message' ? data : null"
  />
  <WidgetFrame v-else :title="config.title">
    <p class="infoscreen-widget-no-data">{{ t('infoscreenRuntime.widgets.noData') }}</p>
  </WidgetFrame>
</template>

<style scoped lang="scss">
.infoscreen-widget-empty {
  height: 100%;
}

.infoscreen-widget-no-data {
  margin: 0;
  color: var(--p-text-muted-color);
}
</style>
