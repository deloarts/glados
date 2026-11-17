<script setup lang="ts">
// The maintenance notice above the login card's sign-in forms, with the
// administrator's message or a default one.
import { useI18n } from 'vue-i18n'

import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'

const { t } = useI18n()
const publicBrandingStore = usePublicBrandingStore()
</script>

<template>
  <Message
    v-if="publicBrandingStore.maintenanceEnabled"
    severity="warn"
    :closable="false"
    data-testid="login-maintenance-banner"
  >
    <strong>{{ t('login.maintenance.title') }}</strong>
    {{ publicBrandingStore.maintenanceMessage || t('login.maintenance.defaultMessage') }}
  </Message>
</template>
