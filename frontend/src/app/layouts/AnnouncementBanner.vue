<script setup lang="ts">
// Rendered above the header (see AppLayout.vue) for every signed-in user,
// deliberately not on the login page (AuthLayout never mounts AppLayout).
// Unlike MaintenanceBanner this one can be closable (the admin decides per
// banner): dismissal is per-browser,
// keyed on the banner's own updated_at (see announcementsStore.dismissBanner),
// so editing a still-enabled banner makes it reappear even for someone who
// already dismissed the old text.
import { useI18n } from 'vue-i18n'

import { useAnnouncementsStore, toMessageSeverity, toSeverityIcon } from '@/features/announcements'

const { t } = useI18n()
const store = useAnnouncementsStore()
</script>

<template>
  <Message
    v-if="store.visibleBanner"
    :severity="toMessageSeverity(store.visibleBanner.severity)"
    :icon="toSeverityIcon(store.visibleBanner.severity)"
    :closable="store.visibleBanner.dismissable"
    :close-button-props="{ 'aria-label': t('announcements.banner.dismissAria') }"
    class="announcement-banner"
    data-testid="announcement-banner"
    :pt="{
      icon: { 'data-testid': 'announcement-banner-icon' },
      closeButton: { 'data-testid': 'announcement-banner-close' },
    }"
    @close="store.dismissBanner()"
  >
    <span class="announcement-banner-text">{{ store.visibleBanner.text }}</span>
  </Message>
</template>

<style scoped lang="scss">
// Same layout guarantee as MaintenanceBanner.vue's own comment: this sits
// above .shell-header, a fixed-height flex item in .app-shell's column, and
// must not grow/shrink that layout, hence flex-shrink: 0.
.announcement-banner {
  flex-shrink: 0;
  border-radius: 0;
}

.announcement-banner-text {
  white-space: pre-line;
}
</style>
