<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'

/** Says who edits the document now, with take over and end editing for managers. */

withDefaults(
  defineProps<{
    name: string
    since: string | null
    canTakeOver: boolean
    /**
     * The missing permission that keeps the user from ending or taking over
     * the editing. While set, both buttons show disabled with it as tooltip.
     */
    takeOverBlocked?: string
    busy?: boolean
  }>(),
  { takeOverBlocked: '', busy: false },
)

const emit = defineEmits<{ 'take-over': []; end: [] }>()

const { t } = useI18n()
</script>

<template>
  <Message severity="warn" data-testid="document-locked">
    <div class="lock-notice">
      <span>
        {{
          since
            ? t('documents.lock.editedBySince', { name, since: formatISODateTime(since) })
            : t('documents.lock.editedBy', { name })
        }}
      </span>
      <div
        v-if="canTakeOver || takeOverBlocked"
        class="lock-actions"
        v-tooltip.top="takeOverBlocked || undefined"
        data-testid="document-lock-actions"
      >
        <Button
          :label="t('documents.lock.end')"
          icon="mdi mdi-lock-open-variant-outline"
          size="small"
          severity="warn"
          text
          :disabled="!canTakeOver"
          :loading="busy"
          data-testid="document-end-editing"
          @click="emit('end')"
        />
        <Button
          :label="t('documents.lock.takeOver')"
          icon="mdi mdi-account-switch-outline"
          size="small"
          severity="warn"
          outlined
          :disabled="!canTakeOver"
          :loading="busy"
          data-testid="document-take-over"
          @click="emit('take-over')"
        />
      </div>
    </div>
  </Message>
</template>

<style scoped lang="scss">
.lock-actions {
  display: flex;
  gap: var(--space-1);
}

.lock-notice {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
</style>
