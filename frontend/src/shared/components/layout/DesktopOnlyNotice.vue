<script setup lang="ts">
/**
 * Shown on a phone in place of a page that is built for the desktop. The page
 * stays reachable through links, so the notice offers it in full anyway.
 */
import { useI18n } from 'vue-i18n'

import EmptyState from '@/shared/components/EmptyState.vue'

defineEmits<{ (e: 'show-anyway'): void }>()

const { t } = useI18n()
</script>

<template>
  <div class="desktop-only-notice" data-testid="desktop-only-notice">
    <EmptyState icon="mdi mdi-monitor" :message="t('main.desktopOnly.message')">
      <Button
        :label="t('main.desktopOnly.showAnyway')"
        icon="mdi mdi-eye"
        variant="outlined"
        data-testid="desktop-only-show-anyway"
        @click="$emit('show-anyway')"
      />
    </EmptyState>
  </div>
</template>

<style scoped lang="scss">
.desktop-only-notice {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}
</style>
