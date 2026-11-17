<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAppToast } from '@/core/composables/useAppToast'
import QrScanner from 'qr-scanner'

import { resolvePublicId } from '../api/resolvePublicId'
import { publicIdFromCode } from '../publicId'
import { routeForResolved } from '../resourceRoutes'

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const router = useRouter()
const toast = useAppToast()

const videoEl = ref<HTMLVideoElement | null>(null)
const error = ref<string | null>(null)
let scanner: QrScanner | null = null
// Guards against firing resolve() repeatedly while the same code is still
// in frame, qr-scanner keeps decoding every frame, not just on change.
let processing = false

watch(visible, async (open) => {
  if (open) await start()
  else stop()
})

onUnmounted(stop)

async function start(): Promise<void> {
  error.value = null

  if (!(await QrScanner.hasCamera())) {
    error.value = t('scan.errors.noCamera')
    return
  }

  scanner = new QrScanner(videoEl.value!, (result) => void onDecode(result), {
    preferredCamera: 'environment',
    highlightScanRegion: true,
    highlightCodeOutline: true,
  })

  try {
    await scanner.start()
  } catch {
    error.value = t('scan.errors.permissionDenied')
  }
}

function stop(): void {
  scanner?.stop()
  scanner?.destroy()
  scanner = null
  processing = false
}

async function onDecode(result: { data: string }): Promise<void> {
  if (processing) return

  const publicId = publicIdFromCode(result.data)
  if (!publicId) return // not a recognized code, keep scanning

  processing = true
  try {
    const resolved = await resolvePublicId(publicId)
    visible.value = false // triggers stop() via the watcher above

    const path = routeForResolved(resolved)
    if (path) {
      void router.push(path)
      toast.success(t('scan.found', { resource: resolved.resource }))
    } else {
      toast.info(t('scan.foundNoRoute'))
    }
  } catch {
    toast.error(t('scan.errors.notFound'))
    processing = false // let them try another code without closing the dialog
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    :header="t('scan.title')"
    modal
    :style="{ width: 'var(--dialog-width-sm)', maxWidth: '92vw' }"
  >
    <div class="scan-body">
      <!-- A live camera picture for scanning a code, it has no speech to caption. -->
      <!-- eslint-disable-next-line vuejs-accessibility/media-has-caption -->
      <video v-show="!error" ref="videoEl" class="scan-video" />

      <div v-if="error" class="scan-state scan-state--error">
        <i class="mdi mdi-alert-circle-outline scan-state-icon" aria-hidden="true" />
        <span>{{ error }}</span>
        <Button :label="t('scan.errors.tryAgain')" size="small" @click="start" />
      </div>
    </div>
  </Dialog>
</template>

<style scoped lang="scss">
.scan-body {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 20rem;
}

.scan-video {
  width: 100%;
  border-radius: 6px;
  // The camera picture is letterboxed in black in both themes.
  // stylelint-disable-next-line scale-unlimited/declaration-strict-value, declaration-property-value-disallowed-list
  background-color: #000;
}

.scan-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  text-align: center;
  color: var(--p-text-muted-color);
}

.scan-state--error {
  color: var(--p-red-500);
}

.scan-state-icon {
  font-size: var(--font-size-4xl);
}
</style>
