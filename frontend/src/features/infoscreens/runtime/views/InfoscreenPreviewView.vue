<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import type { LiveSignal } from '@/core/realtime/types'
import { setDisplayTimezone } from '@/core/utils/dates'

import { getInfoscreenPreviewFeed } from '../api/getInfoscreenPreviewFeed'
import InfoscreenScreen from '../components/InfoscreenScreen.vue'
import KioskNotice from '../components/KioskNotice.vue'
import TerminalMessageFrame from '../components/TerminalMessageFrame.vue'
import { useInfoscreenLanguage } from '../composables/useInfoscreenLanguage'
import { useInfoscreenTheme } from '../composables/useInfoscreenTheme'
import type { InfoscreenFeedResponse } from '../types/infoscreenFeed'

// The builder's preview: the screen exactly as a wall display renders it,
// read with the viewer's own session instead of device credentials. It
// follows changes to the screen, to the data its widgets show and to the
// messages to terminals, wears the screen's theme and language while open
// and gives the viewer's own back on leave. The message shown is the newest
// one sent to all terminals or to this screen.
const route = useRoute()
const { t } = useI18n()
const theme = useInfoscreenTheme({ restoreOnDispose: true })
const language = useInfoscreenLanguage({ restoreOnDispose: true })

const INFOSCREENS_RESOURCE: string = 'infoscreens'

const infoscreenId = computed(() => Number(route.params.id))
const feed = ref<InfoscreenFeedResponse | null>(null)
const staleSince = ref<Date | null>(null)
const failure = ref<'not_found' | 'failed' | null>(null)
let sequence = 0

async function load(): Promise<void> {
  const id = infoscreenId.value
  const current = ++sequence
  try {
    const next = await getInfoscreenPreviewFeed(id)
    if (current !== sequence) return
    // The same zone the device takes from its feed, so the preview matches.
    setDisplayTimezone(next.timezone)
    feed.value = next
    staleSince.value = null
    failure.value = null
    theme.apply(next.infoscreen)
    language.apply(next.language)
  } catch (error) {
    if (current !== sequence) return
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      feed.value = null
      failure.value = 'not_found'
    } else if (feed.value) {
      staleSince.value ??= new Date()
    } else {
      failure.value = 'failed'
    }
  }
}

watch(
  infoscreenId,
  () => {
    feed.value = null
    failure.value = null
    void load()
  },
  { immediate: true },
)

// Only this screen's own row matters among the screens; every change to the
// data behind the widgets refreshes the feed.
function acceptsSignal(signal: LiveSignal): boolean {
  return signal.resource !== INFOSCREENS_RESOURCE || signal.id === infoscreenId.value
}

useLiveRefresh(
  [
    INFOSCREENS_RESOURCE,
    LiveResource.TERMINAL_BROADCASTS,
    LiveResource.PRODUCTION_ORDERS,
    LiveResource.PRODUCTION_LOTS,
    LiveResource.PRODUCTION_MACHINES,
    LiveResource.MACHINE_POOLS,
    LiveResource.ORDERS,
  ],
  load,
  { debounceMs: 1000, filter: acceptsSignal },
)
</script>

<template>
  <div class="infoscreen-preview">
    <TerminalMessageFrame v-if="feed" :message="feed.broadcast">
      <InfoscreenScreen :feed="feed" :stale-since="staleSince" />
    </TerminalMessageFrame>
    <KioskNotice
      v-else-if="failure === 'not_found'"
      :title="t('infoscreenRuntime.preview.notFound')"
      icon="mdi mdi-monitor-off"
    />
    <KioskNotice
      v-else-if="failure === 'failed'"
      :title="t('infoscreenRuntime.preview.loadFailed')"
      icon="mdi mdi-alert-circle-outline"
      tone="danger"
    />
    <KioskNotice v-else :title="t('infoscreenRuntime.loadingScreen')" icon="mdi mdi-loading mdi-spin" />
  </div>
</template>

<style scoped lang="scss">
.infoscreen-preview {
  height: 100%;
}
</style>
