<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { AppLocale } from '@/core/i18n'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'

import { useTickingNow } from '../composables/useTickingNow'
import type {
  InfoscreenBar,
  InfoscreenBarArea,
  InfoscreenBarItem,
  InfoscreenHoliday,
} from '../types/infoscreenFeed'
import {
  clockParts,
  formatInstantTime,
  holidayLabel,
  longDateLabel,
} from '../utils/infoscreenFormat'

// The header or footer of a screen, in three areas: left items start at the
// left edge, right items end at the right edge, and the center area sits in
// the middle of the screen however wide the other two are. Within an area
// the items run in the order the screen lists them. Anything passed in the
// default slot, the footer's stale badge, closes the right area. The logo,
// the app name and the company name come from the public branding, which
// the app reads without a session; clock and date tick on the device; the
// update time is when the backend built the feed.
const props = withDefaults(
  defineProps<{
    bar: InfoscreenBar
    position: 'header' | 'footer'
    screenName: string
    nextHoliday?: InfoscreenHoliday | null
    generatedAt?: string | null
  }>(),
  { nextHoliday: null, generatedAt: null },
)

const { t, locale } = useI18n()
const brandingStore = usePublicBrandingStore()
const now = useTickingNow()

const clock = computed(() => clockParts(now.value).hoursMinutes)
const date = computed(() => longDateLabel(now.value, locale.value as AppLocale))
const holiday = computed(() =>
  props.nextHoliday ? holidayLabel(props.nextHoliday, now.value, t) : null,
)
const updated = computed(() => {
  const time = formatInstantTime(props.generatedAt)
  return time ? t('infoscreenRuntime.bar.updated', { time }) : null
})

// An item without anything to show (no logo uploaded, no text, no holiday)
// is left out instead of leaving a gap.
function hasContent(item: InfoscreenBarItem): boolean {
  switch (item) {
    case 'logo':
      return !!brandingStore.logoUrl
    case 'app_name':
      return !!brandingStore.appName.trim()
    case 'company_name':
      return !!brandingStore.companyName?.trim()
    case 'text':
      return !!props.bar.text
    case 'next_holiday':
      return !!holiday.value
    case 'last_updated':
      return !!updated.value
    default:
      return true
  }
}

const AREAS: InfoscreenBarArea[] = ['left', 'center', 'right']

const areas = computed(() =>
  AREAS.map((area) => ({ area, items: (props.bar[area] ?? []).filter(hasContent) })),
)
</script>

<template>
  <div
    class="infoscreen-bar"
    :class="`infoscreen-bar--${position}`"
    :data-testid="`infoscreen-${position}`"
  >
    <div
      v-for="{ area, items } in areas"
      :key="area"
      class="bar-area"
      :class="`bar-area--${area}`"
      :data-testid="`bar-area-${area}`"
    >
      <template v-for="item in items" :key="item">
        <img
          v-if="item === 'logo'"
          class="bar-item bar-item--logo"
          :src="brandingStore.logoUrl ?? undefined"
          :alt="brandingStore.appName"
          data-testid="bar-logo"
        />
        <span
          v-else-if="item === 'app_name'"
          class="bar-item bar-item--app-name"
          data-testid="bar-app-name"
        >
          {{ brandingStore.appName }}
        </span>
        <span
          v-else-if="item === 'company_name'"
          class="bar-item bar-item--company-name"
          data-testid="bar-company-name"
        >
          {{ brandingStore.companyName }}
        </span>
        <span v-else-if="item === 'title'" class="bar-item bar-item--title" data-testid="bar-title">
          {{ screenName }}
        </span>
        <span v-else-if="item === 'clock'" class="bar-item bar-item--clock" data-testid="bar-clock">
          {{ clock }}
        </span>
        <span v-else-if="item === 'date'" class="bar-item bar-item--date" data-testid="bar-date">
          {{ date }}
        </span>
        <span
          v-else-if="item === 'next_holiday' && holiday"
          class="bar-item bar-item--holiday"
          data-testid="bar-holiday"
        >
          <span class="bar-item-muted">{{ t('infoscreenRuntime.widgets.clock.nextHoliday') }}</span>
          {{ holiday.name }} · {{ holiday.date }} · {{ holiday.when }}
        </span>
        <span
          v-else-if="item === 'last_updated'"
          class="bar-item bar-item--updated"
          data-testid="bar-updated"
        >
          {{ updated }}
        </span>
        <span v-else-if="item === 'text'" class="bar-item bar-item--text" data-testid="bar-text">
          {{ bar.text }}
        </span>
      </template>
      <slot v-if="area === 'right'" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.infoscreen-bar {
  flex: 0 0 auto;
  // Equal outer columns keep the center area centred on the screen; an
  // empty area is an empty column that only holds the centring.
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 1.2em;
  min-width: 0;
  padding: 0.35em 0.8em;
  // The app's header and footer: primary bar, white text in every theme.
  color: var(--on-accent);
  background-color: var(--p-primary-500);
  font-size: clamp(1.1rem, 3.6vmin, 4.5rem);
  line-height: 1.2;
}

// The header text matches the app topbar's wordmark (AppHeader .brand):
// the brand face, unbolded, with the same tracking. Only the size is
// scaled up for reading across a hall.
.infoscreen-bar--header {
  font-family: var(--font-brand);
  letter-spacing: 1px;
  line-height: 1;

  .bar-item {
    font-weight: normal;
  }
}

// A thin strip like the app's footer.
.infoscreen-bar--footer {
  padding: 0.15em 0.8em;
  font-size: clamp(0.8rem, 1.8vmin, 2rem);
}

.bar-area {
  display: flex;
  align-items: center;
  gap: 1.2em;
  min-width: 0;
}

.bar-area--left {
  justify-content: flex-start;
}

.bar-area--center {
  justify-content: center;
}

.bar-area--right {
  justify-content: flex-end;
}

.bar-item {
  flex: 0 0 auto;
  white-space: nowrap;
}

// The title and a free text shrink with an ellipsis when their area runs
// out of room.
.bar-item--title,
.bar-item--company-name,
.bar-item--text {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.bar-item--title,
.bar-item--company-name {
  font-weight: 700;
}

.bar-item--logo {
  height: 1.6em;
  max-width: 8em;
  object-fit: contain;
}

.bar-item--clock {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.bar-item--date,
.bar-item--updated,
.bar-item-muted {
  color: var(--on-accent-muted);
}

.bar-item-muted {
  margin-right: 0.4em;
}

.bar-item--updated {
  font-variant-numeric: tabular-nums;
}
</style>
