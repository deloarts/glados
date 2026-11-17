<script setup lang="ts">
// Mounted once in AppLayout. Only its button closes it (no Escape, mask
// click or close icon), so a one-way :visible binding suffices.
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useAnnouncementsStore } from '../stores/announcementsStore'
import type { AnnouncementSeverity } from '../types/announcementsTypes'

const { t } = useI18n()
const appToast = useAppToast()
const store = useAnnouncementsStore()

const acknowledging = ref(false)

const SEVERITY_ICONS: Record<AnnouncementSeverity, string> = {
  info: 'mdi mdi-information',
  warning: 'mdi mdi-alert',
  danger: 'mdi mdi-alert-octagon',
}

// Reuses the Message severity colours for the header icon.
const SEVERITY_ICON_COLORS: Record<AnnouncementSeverity, string> = {
  info: 'var(--p-blue-500)',
  warning: 'var(--p-orange-500)',
  danger: 'var(--p-red-500)',
}

async function onAcknowledge(): Promise<void> {
  const current = store.currentAcknowledgement
  if (!current) return

  acknowledging.value = true
  try {
    await store.acknowledge(current.public_id)
  } catch {
    appToast.error(t('announcements.acknowledge.error'))
  } finally {
    acknowledging.value = false
  }
}
</script>

<template>
  <Dialog
    :visible="!!store.currentAcknowledgement"
    modal
    :closable="false"
    :close-on-escape="false"
    :dismissable-mask="false"
    :draggable="false"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <!-- The header is the severity icon alone; a title would only repeat the
         button. -->
    <template v-if="store.currentAcknowledgement" #header>
      <div class="acknowledge-header">
        <i
          :class="['acknowledge-icon', SEVERITY_ICONS[store.currentAcknowledgement.severity]]"
          :style="{ color: SEVERITY_ICON_COLORS[store.currentAcknowledgement.severity] }"
          aria-hidden="true"
        />
      </div>
    </template>

    <p v-if="store.currentAcknowledgement" class="acknowledge-text">
      {{ store.currentAcknowledgement.text }}
    </p>

    <template #footer>
      <div class="acknowledge-footer">
        <Button
          :label="t('announcements.acknowledge.button')"
          icon="mdi mdi-check"
          :loading="acknowledging"
          @click="onAcknowledge"
        />
      </div>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
// Stretching the wrapper is what centres the icon in OpenVue's
// space-between header.
.acknowledge-header {
  flex: 1;
  display: flex;
  justify-content: center;
  padding-top: var(--space-2);
}

.acknowledge-icon {
  font-size: var(--font-size-5xl);
  line-height: 1;
}

.acknowledge-text {
  white-space: pre-line;
  margin: 0;
  padding: 0 var(--space-2);
  font-size: var(--font-size-lg);
  line-height: 1.5;
}

.acknowledge-footer {
  width: 100%;
  display: flex;
  justify-content: center;
  padding-bottom: var(--space-1);
}
</style>
