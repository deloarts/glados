<script setup lang="ts">
import { computed, ref } from 'vue'
import { useResizeObserver } from '@vueuse/core'

import { usePhoneLayout } from '@/core/composables/usePhoneLayout'

import LotsViewsBar from './LotsViewsBar.vue'

// The lots views bar, compact when the full bar would wrap onto a second
// row. A hidden copy of the full bar, laid out at its natural width, says
// how wide one row has to be, so the bar expands again as soon as the room
// is back rather than only guessing from the compact bar's own width.
const { phoneMode } = usePhoneLayout()

const barEl = ref<HTMLElement | null>(null)
const measureEl = ref<HTMLElement | null>(null)
const availableWidth = ref(0)
const neededWidth = ref(0)

useResizeObserver(barEl, (entries) => {
  availableWidth.value = entries[0]?.contentRect.width ?? 0
})
useResizeObserver(measureEl, (entries) => {
  neededWidth.value = entries[0]?.contentRect.width ?? 0
})

const compact = computed(
  () => availableWidth.value > 0 && neededWidth.value > availableWidth.value,
)
</script>

<template>
  <div ref="barEl" class="lots-views">
    <LotsViewsBar :compact="compact" />
    <!-- The measuring copy: invisible, inert and out of the layout. -->
    <div v-if="!phoneMode" class="lots-views-measure" aria-hidden="true" inert>
      <div ref="measureEl" class="lots-views-measure-bar">
        <LotsViewsBar />
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.lots-views {
  position: relative;
  min-width: 0;
}

.lots-views-measure {
  position: absolute;
  top: 0;
  left: 0;
  height: 0;
  overflow: hidden;
  visibility: hidden;
  pointer-events: none;
}

.lots-views-measure-bar {
  width: max-content;
}
</style>
