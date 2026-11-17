<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import type { LocalDraftOffer } from '../composables/useLocalDraft'

/**
 * Offers the unsaved changes this browser kept of a document, after a
 * reload, a closed tab or an expired session. Restore puts them back on
 * screen, Discard drops them, and closing the dialog keeps them for later.
 * A copy the document has been saved over since is restored only with a
 * warning, and one that can no longer be applied is only discarded.
 */

const props = defineProps<{
  offer: LocalDraftOffer<unknown> | null
  /** Why the changes cannot be restored now, or null when they can. */
  blocked?: string | null
  /** When the document was saved after the copy was written, for a stale copy. */
  savedSince?: string | null
  busy?: boolean
}>()

const emit = defineEmits<{ restore: []; discard: []; dismiss: [] }>()

const { t } = useI18n()

const visible = computed({
  get: () => props.offer !== null,
  set: (open: boolean) => {
    if (!open) emit('dismiss')
  },
})

const savedAt = computed(() => (props.offer ? formatISODateTime(props.offer.draft.savedAt) : ''))
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('documents.draft.header')"
    :style="{ width: 'var(--dialog-width-md)' }"
    :breakpoints="{ '640px': '95vw' }"
    data-testid="document-draft-dialog"
  >
    <p class="draft-text">{{ t('documents.draft.message', { date: savedAt }) }}</p>
    <Message v-if="blocked" severity="secondary" :closable="false" data-testid="document-draft-blocked">
      {{ blocked }}
    </Message>
    <Message v-else-if="offer?.stale" severity="warn" :closable="false" data-testid="document-draft-stale">
      {{ savedSince ? t('documents.draft.staleSince', { date: formatISODateTime(savedSince) }) : t('documents.draft.stale') }}
    </Message>
    <template #footer>
      <Button
        :label="t('documents.draft.discard')"
        icon="mdi mdi-delete-outline"
        severity="secondary"
        text
        :disabled="busy"
        data-testid="document-draft-discard"
        @click="emit('discard')"
      />
      <Button
        v-if="!blocked"
        :label="t('documents.draft.restore')"
        icon="mdi mdi-restore"
        :severity="offer?.stale ? 'warn' : undefined"
        :loading="busy"
        data-testid="document-draft-restore"
        @click="emit('restore')"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.draft-text {
  margin: 0 0 var(--space-4);
}
</style>
