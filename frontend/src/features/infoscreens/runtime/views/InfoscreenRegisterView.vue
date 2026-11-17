<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

import IdentifyOverlay from '../components/IdentifyOverlay.vue'
import InfoscreenPairingCode from '../components/InfoscreenPairingCode.vue'
import InfoscreenSignInReport from '../components/InfoscreenSignInReport.vue'
import { useInfoscreenRuntime } from '../composables/useInfoscreenRuntime'
import { useSignInReport } from '../composables/useSignInReport'

// Where a display waiting for approval shows its pairing code, in the same
// sign-in report as every other waiting state. It shares the device runtime
// with the entry page and goes back there as soon as the device is anything
// other than pending, approved or not.
const { t } = useI18n()
const router = useRouter()
const runtime = useInfoscreenRuntime()
const { phase, deviceState, identifying } = runtime
const report = useSignInReport(runtime)

watch(
  phase,
  (current) => {
    if (current !== 'pending' && current !== 'booting') void router.replace({ name: 'Infoscreen' })
  },
  { immediate: true },
)

const deviceName = computed(() => deviceState.value?.name || t('infoscreenRuntime.unnamedDisplay'))
</script>

<template>
  <div class="infoscreen-register" :data-phase="phase">
    <InfoscreenSignInReport :report="report">
      <template v-if="phase === 'pending'" #side>
        <InfoscreenPairingCode
          :code="deviceState?.pairing_code ?? null"
          :expires-at="deviceState?.pairing_expires_at ?? null"
        />
      </template>
    </InfoscreenSignInReport>
    <IdentifyOverlay v-if="identifying" :name="deviceName" :location="deviceState?.location ?? null" />
  </div>
</template>

<style scoped lang="scss">
.infoscreen-register {
  height: 100%;
}
</style>
