<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { MenuItem } from 'openvue/menuitem'

import { useClipboard } from '@/core/composables/useClipboard'

/**
 * Opens a menu that copies the record's lasting link or its UUID. The link
 * goes through `/resolve` with the record's public id, the same link a QR
 * code on a report holds. The address bar's link carries the database id,
 * which is short but points at another record after a restore or a move to
 * another instance. The UUID is the public id as plain text, for pasting it
 * into a search or a message. Sits next to the handbook button at the end of
 * a detail page's controls bar, and shows only once the record is loaded.
 */
const props = defineProps<{ publicId?: string | null }>()

const { t } = useI18n()
const { copyToClipboard } = useClipboard()
const menu = ref<{ toggle(event: Event): void }>()

// The Resolve route's address under the app's base, the shape the backend
// writes into QR codes.
const link = computed(() =>
  props.publicId ? new URL(`${import.meta.env.BASE_URL}resolve/${props.publicId}`, window.location.origin).href : null,
)

const items = computed<MenuItem[]>(() => [
  {
    key: 'link',
    label: t('common.share.copyLink'),
    icon: 'mdi mdi-link-variant',
    command: () => {
      if (link.value) void copyToClipboard(link.value, t('common.share.copied'))
    },
  },
  {
    key: 'uuid',
    label: t('common.copyUuid'),
    icon: 'mdi mdi-content-copy',
    command: () => {
      if (props.publicId) void copyToClipboard(props.publicId)
    },
  },
])

const menuPt = {
  itemLink: (options: { context: { item: MenuItem } }) => ({
    'data-testid': `share-copy-${String(options.context.item.key)}`,
  }),
}
</script>

<template>
  <template v-if="link">
    <Button
      v-tooltip.top="t('common.share.tooltip')"
      icon="mdi mdi-share-variant-outline"
      severity="secondary"
      size="small"
      rounded
      text
      aria-haspopup="true"
      :aria-label="t('common.share.tooltip')"
      data-testid="share-button"
      @click="menu?.toggle($event)"
    />
    <Menu ref="menu" :model="items" popup :pt="menuPt" />
  </template>
</template>
