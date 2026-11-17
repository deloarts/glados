<script setup lang="ts">
// Rendered for every signed-in user (see AppLayout.vue), same as
// MaintenanceBanner/AnnouncementBanner alongside it, but unlike those two
// this needs no admin flag or store: useVersionCheck runs its one-shot
// /health check at mount and either sets `mismatch` or leaves it null for
// good. Deliberately not dismissable and not tied to any store, since only
// a reload (picking up whichever build the server is actually serving) can
// resolve the disagreement; there is nothing here for a user to acknowledge.
import { useI18n } from 'vue-i18n'

import { useVersionCheck } from '@/core/composables/useVersionCheck'

const { t } = useI18n()
const { mismatch } = useVersionCheck()
</script>

<template>
  <Message v-if="mismatch" severity="error" :closable="false" class="version-mismatch-banner">
    <span class="version-mismatch-banner-text">
      {{
        t('main.versionMismatchBanner.message', {
          server: mismatch.server,
          client: mismatch.client,
        })
      }}
    </span>
  </Message>
</template>

<style scoped lang="scss">
// Same flex-shrink:0 guarantee as MaintenanceBanner/AnnouncementBanner; this
// sits in .app-shell's column (see AppLayout.vue) and must not grow/shrink
// that layout.
.version-mismatch-banner {
  flex-shrink: 0;
  border-radius: 0;
}

.version-mismatch-banner-text {
  font-size: var(--font-size-sm);
}
</style>
