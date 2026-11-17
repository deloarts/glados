<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useClipboard } from '@/core/composables/useClipboard'

/**
 * Copies a link to the record that keeps working, the record's public id
 * through `/resolve`, the same link a QR code on a report holds. The
 * address bar's link carries the database id, which is short but points at
 * another record after a restore or a move to another instance. Sits next
 * to the handbook button at the end of a detail page's controls bar, and
 * shows only once the record is loaded.
 */
const props = defineProps<{ publicId?: string | null }>()

const { t } = useI18n()
const { copyToClipboard } = useClipboard()

// The Resolve route's address under the app's base, the shape the backend
// writes into QR codes.
const link = computed(() =>
  props.publicId ? new URL(`${import.meta.env.BASE_URL}resolve/${props.publicId}`, window.location.origin).href : null,
)

function share(): void {
  if (link.value) void copyToClipboard(link.value, t('common.share.copied'))
}
</script>

<template>
  <Button
    v-if="link"
    v-tooltip.top="t('common.share.tooltip')"
    icon="mdi mdi-share-variant-outline"
    severity="secondary"
    size="small"
    rounded
    text
    :aria-label="t('common.share.tooltip')"
    data-testid="share-button"
    @click="share"
  />
</template>
