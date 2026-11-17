<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePageRotation } from '../composables/usePageRotation'
import { LAYOUT_SLOT_COUNT } from '../types/infoscreenFeed'
import type { InfoscreenFeedResponse, InfoscreenWidgetConfig } from '../types/infoscreenFeed'
import { formatClockTime } from '../utils/infoscreenFormat'
import InfoscreenBar from './InfoscreenBar.vue'
import InfoscreenWidget from './InfoscreenWidget.vue'

// Renders one feed: the banner on top, the header bar, the current page in
// its layout preset (rotating through the pages when there is more than
// one) and the footer bar. Used by the wall display and by the builder's
// preview alike.
const props = withDefaults(
  defineProps<{
    feed: InfoscreenFeedResponse
    staleSince?: Date | null
  }>(),
  { staleSince: null },
)

const { t } = useI18n()

const pages = computed(() => props.feed.infoscreen.pages)
const pageCount = computed(() => pages.value.length)
const rotationSeconds = computed(() => props.feed.infoscreen.rotation_seconds)
const { pageIndex } = usePageRotation(pageCount, rotationSeconds)

const page = computed(() => pages.value[pageIndex.value] ?? null)

interface SlotView {
  key: string
  config: InfoscreenWidgetConfig | null
  data: InfoscreenFeedResponse['widgets'][number][number]
}

// `widgets[p][s]` is the data for `pages[p].slots[s]`. A layout always gets
// its full number of slots, so a short slot list leaves the rest blank.
const cells = computed<SlotView[]>(() => {
  const current = page.value
  if (!current) return []
  const data = props.feed.widgets[pageIndex.value] ?? []
  return Array.from({ length: LAYOUT_SLOT_COUNT[current.layout] ?? 1 }, (_, index) => ({
    key: `${pageIndex.value}-${index}`,
    config: current.slots[index] ?? null,
    data: data[index] ?? null,
  }))
})

const banner = computed(() => props.feed.banner)
const screen = computed(() => props.feed.infoscreen)
const nextHoliday = computed(() => props.feed.next_holiday ?? null)
const staleLabel = computed(() =>
  props.staleSince
    ? t('infoscreenRuntime.staleSince', { time: formatClockTime(props.staleSince) })
    : null,
)
</script>

<template>
  <div class="infoscreen-screen">
    <div
      v-if="banner"
      class="infoscreen-banner"
      :class="`infoscreen-banner--${banner.severity}`"
      role="status"
      data-testid="infoscreen-banner"
    >
      {{ banner.text }}
    </div>

    <InfoscreenBar
      v-if="screen.show_header"
      :bar="screen.header"
      position="header"
      :screen-name="screen.name"
      :next-holiday="nextHoliday"
      :generated-at="feed.generated_at"
    />

    <!-- Banner, header and footer run edge to edge like the app's own bars;
         only the pages keep a margin to the screen edge. -->
    <div class="infoscreen-body">
      <main
        v-if="page"
        class="infoscreen-page"
        :class="`infoscreen-page--${page.layout}`"
        :data-page="pageIndex"
        data-testid="infoscreen-page"
      >
        <div v-for="cell in cells" :key="cell.key" class="infoscreen-slot">
          <InfoscreenWidget :config="cell.config" :data="cell.data" />
        </div>
      </main>
      <div v-else class="infoscreen-no-pages">
        {{ t('infoscreenRuntime.preview.noPages') }}
      </div>

      <div v-if="pageCount > 1" class="infoscreen-dots" aria-hidden="true">
        <span
          v-for="index in pageCount"
          :key="index"
          class="infoscreen-dot"
          :class="{ 'infoscreen-dot--active': index - 1 === pageIndex }"
        />
      </div>
    </div>

    <!-- With a footer the stale badge closes the footer, otherwise it floats
         in the corner. -->
    <InfoscreenBar
      v-if="screen.show_footer"
      :bar="screen.footer"
      position="footer"
      :screen-name="screen.name"
      :next-holiday="nextHoliday"
      :generated-at="feed.generated_at"
    >
      <span v-if="staleLabel" class="infoscreen-stale" role="status" data-testid="infoscreen-stale">
        <i class="mdi mdi-cloud-off-outline" aria-hidden="true" />
        {{ staleLabel }}
      </span>
    </InfoscreenBar>
    <div
      v-else-if="staleLabel"
      class="infoscreen-stale infoscreen-stale--floating"
      role="status"
      data-testid="infoscreen-stale"
    >
      <i class="mdi mdi-cloud-off-outline" aria-hidden="true" />
      {{ staleLabel }}
    </div>
  </div>
</template>

<style scoped lang="scss">
.infoscreen-screen {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

// Positioned, so the page dots sit above the footer, not on it.
.infoscreen-body {
  position: relative;
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 1.2vmin;
  padding: 1.5vmin;
}

.infoscreen-banner {
  --banner-accent: var(--p-blue-500);
  flex: 0 0 auto;
  padding: 0.5em 0.9em;
  background: var(--banner-accent);
  color: var(--on-accent);
  font-size: clamp(1.1rem, 3.2vmin, 3.5rem);
  font-weight: 700;
  line-height: 1.25;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.infoscreen-banner--success {
  --banner-accent: var(--p-green-600);
}

.infoscreen-banner--warning,
.infoscreen-banner--warn {
  --banner-accent: var(--p-orange-600);
}

.infoscreen-banner--danger,
.infoscreen-banner--error {
  --banner-accent: var(--p-red-600);
}

.infoscreen-page {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  gap: 1.2vmin;
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
}

.infoscreen-page--two_columns {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.infoscreen-page--grid_2x2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
}

.infoscreen-page--main_side {
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
}

.infoscreen-page--two_rows {
  grid-template-rows: repeat(2, minmax(0, 1fr));
}

.infoscreen-page--three_rows {
  grid-template-rows: repeat(3, minmax(0, 1fr));
}

// Two columns by three rows, for screens mounted upright.
.infoscreen-page--grid_2x3 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(3, minmax(0, 1fr));
}

.infoscreen-page--grid_3x2 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
}

.infoscreen-slot {
  min-width: 0;
  min-height: 0;
}

.infoscreen-no-pages {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: clamp(1.4rem, 4vmin, 4rem);
  color: var(--p-text-muted-color);
}

.infoscreen-dots {
  position: absolute;
  left: 50%;
  bottom: 0.5vmin;
  transform: translateX(-50%);
  display: flex;
  gap: 0.8vmin;
}

.infoscreen-dot {
  width: 1vmin;
  height: 1vmin;
  border-radius: 50%;
  background: var(--p-content-border-color);
}

.infoscreen-dot--active {
  background: var(--p-primary-color);
}

.infoscreen-stale {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 0.4em;
  padding: 0.35em 0.7em;
  border-radius: var(--p-content-border-radius);
  background: var(--p-orange-500);
  color: var(--on-light-accent);
  font-size: clamp(1rem, 2.4vmin, 2.4rem);
  font-weight: 700;
  white-space: nowrap;
}

// Inside the footer the badge takes the footer's size, so it never makes
// the strip taller.
.infoscreen-stale:not(.infoscreen-stale--floating) {
  padding: 0 0.5em;
  font-size: inherit;
}

.infoscreen-stale--floating {
  position: absolute;
  right: 2vmin;
  bottom: 2vmin;
}
</style>
