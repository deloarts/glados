<script setup lang="ts">
// Rendered for every signed-in user, but only ever visible to the exempt
// ones: a non-exempt user's session was already torn down and bounced to
// /login by the api interceptor's maintenanceLockout() the moment
// hostStore.maintenanceEnabled would have gone true for them. This exists so
// an admin (or a whitelisted-IP user) working through maintenance doesn't
// forget the switch is still on.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { useHostStore } from '@/core/host/stores/hostStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

const { t } = useI18n()
const router = useRouter()
const hostStore = useHostStore()
const currentUserStore = useCurrentUserStore()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

// The link stays visible to every signed-in user; without write:settings it
// is disabled and its tooltip names the missing permission.
const canOpenSettings = computed(() => hasPermission(Permission.WRITE_SETTINGS))
const openSettingsBlocked = computed(() => missing(Permission.WRITE_SETTINGS))
</script>

<template>
  <Message
    v-if="hostStore.maintenanceEnabled"
    severity="warn"
    :pt="{ text: { class: 'banner-text' } }"
    :closable="false"
    class="maintenance-banner"
    data-testid="maintenance-banner"
  >
    <span class="maintenance-banner-text">
      <strong>{{ t('main.maintenanceBanner.title') }}</strong>
      <span v-if="hostStore.maintenanceMessage">{{ hostStore.maintenanceMessage }}</span>
    </span>

    <span v-if="currentUserStore.user" v-tooltip.bottom="openSettingsBlocked || undefined">
      <button
        type="button"
        class="maintenance-banner-link"
        :disabled="!canOpenSettings"
        data-testid="maintenance-banner-link"
        @click="router.push('/settings/maintenance')"
      >
        {{ t('main.maintenanceBanner.openSettings') }}
      </button>
    </span>
  </Message>
</template>

<style scoped lang="scss">
// Sits between the header and .shell-body, both fixed-height flex items in
// the app-shell column; this must not grow or shrink the space between
// them, hence flex-shrink: 0. .shell-body already keeps its own flex: 1;
// min-height: 0, unaffected by this element being inserted next to it.
.maintenance-banner {
  flex-shrink: 0;
  border-radius: 0;

  // The default slot renders in the Message's text element (given the
  // banner-text class through pt) beside its icon: stretch it across the row
  // and lay the banner's own text and "Open settings" link out inside it,
  // text left, link right.
  :deep(.banner-text) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    flex: 1;
  }
}

.maintenance-banner-text {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  flex-wrap: wrap;
  font-size: var(--font-size-sm);
}

.maintenance-banner-link {
  flex: none;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: inherit;
  text-decoration: underline;

  &:hover:not(:disabled) {
    opacity: 0.8;
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }
}
</style>
