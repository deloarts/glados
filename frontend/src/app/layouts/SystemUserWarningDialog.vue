<script setup lang="ts">
// Shown once per sign-in as the system user (systemUserWarningPending, set
// by currentUserStore.refresh(); see its own comments for the
// once-per-sign-in-not-per-reload sessionStorage logic). No v-model: the
// dialog only ever closes via acknowledgeSystemUserWarning(), never via the
// mask or an Escape key (closable/dismissableMask both off below), so a
// one-way :visible binding is enough.
import { useI18n } from 'vue-i18n'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'

const { t } = useI18n()
const userStore = useCurrentUserStore()
</script>

<template>
  <Dialog
    :visible="userStore.systemUserWarningPending"
    modal
    :closable="false"
    :draggable="false"
    :dismissable-mask="false"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <template #header>
      <div class="warning-header">
        <i class="mdi mdi-alert warning-icon" aria-hidden="true" />
        <span>{{ t('main.systemUserWarning.title') }}</span>
      </div>
    </template>

    <p>{{ t('main.systemUserWarning.body') }}</p>
    <p>{{ t('main.systemUserWarning.countdown') }}</p>

    <template #footer>
      <Button
        :label="t('main.systemUserWarning.acknowledge')"
        severity="warn"
        @click="userStore.acknowledgeSystemUserWarning()"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.warning-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-weight: 600;
}

.warning-icon {
  color: var(--p-orange-500);
  font-size: var(--font-size-lg);
}

p {
  margin: 0 0 var(--space-3);
  line-height: 1.5;

  &:last-child {
    margin-bottom: 0;
  }
}
</style>
