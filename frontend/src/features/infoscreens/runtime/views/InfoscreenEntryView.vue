<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import IdentifyOverlay from '../components/IdentifyOverlay.vue'
import InfoscreenPairingCode from '../components/InfoscreenPairingCode.vue'
import InfoscreenScreen from '../components/InfoscreenScreen.vue'
import InfoscreenSignInReport from '../components/InfoscreenSignInReport.vue'
import TerminalMessageFrame from '../components/TerminalMessageFrame.vue'
import { useInfoscreenLanguage } from '../composables/useInfoscreenLanguage'
import { useInfoscreenRuntime } from '../composables/useInfoscreenRuntime'
import { useInfoscreenTheme } from '../composables/useInfoscreenTheme'
import { useSignInReport } from '../composables/useSignInReport'

// The page every wall display opens (its KIOSK_URL). It runs the device
// runtime and shows the infoscreen once its feed is there. Until then one
// sign-in report stands in for every waiting state, from booting and
// loading the screen to a failed sign-in and a display without a screen,
// so a booting display never jumps between different pages. A display
// waiting for approval moves to its own route with the pairing code. The
// screen's theme and language are applied and remembered as its feed
// arrives, and a message to terminals is shown over whatever is on screen.
const { t } = useI18n()
const router = useRouter()
const runtime = useInfoscreenRuntime()
const { phase, feed, staleSince, deviceState, identifying } = runtime
const report = useSignInReport(runtime)
const theme = useInfoscreenTheme({ restoreOnDispose: false, remember: true })
const language = useInfoscreenLanguage({ restoreOnDispose: false, remember: true })

watch(
  feed,
  (current) => {
    if (!current) return
    theme.apply(current.infoscreen)
    language.apply(current.language)
  },
  { immediate: true },
)

watch(
  phase,
  (current) => {
    if (current === 'pending') void router.replace({ name: 'InfoscreenRegister' })
  },
  { immediate: true },
)

const deviceName = computed(() => deviceState.value?.name || t('infoscreenRuntime.unnamedDisplay'))
</script>

<template>
  <div class="infoscreen-entry" :data-phase="phase">
    <TerminalMessageFrame :message="deviceState?.broadcast ?? null">
      <InfoscreenScreen v-if="phase === 'showing' && feed" :feed="feed" :stale-since="staleSince" />

      <InfoscreenSignInReport v-else :report="report">
        <template v-if="phase === 'pending'" #side>
          <InfoscreenPairingCode
            :code="deviceState?.pairing_code ?? null"
            :expires-at="deviceState?.pairing_expires_at ?? null"
          />
        </template>
      </InfoscreenSignInReport>
    </TerminalMessageFrame>

    <IdentifyOverlay v-if="identifying" :name="deviceName" :location="deviceState?.location ?? null" />
  </div>
</template>

<style scoped lang="scss">
.infoscreen-entry {
  height: 100%;
}
</style>
