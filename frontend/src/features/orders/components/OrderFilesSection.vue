<script setup lang="ts">
/**
 * Order attachments on the shared FilesSection. Every order category
 * accumulates, so there are no single-file slots.
 */
import { computed } from 'vue'

import { Permission } from '@/core/auth/permissions'
import FilesSection from '@/shared/components/files/FilesSection.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { getOrderFileBlob } from '../api/getOrderFileBlob'
import { useOrderFilesStore } from '../stores/orderFilesStore'
import type { OrderResponse } from '../types/ordersResponse'
import type { MultiCategorySpec } from '@/shared/components/files/fileCategorySpec'

const props = withDefaults(
  defineProps<{
    order: OrderResponse
    canWrite: boolean
    /**
     * row puts categories side by side, for the list's row expansion; stack
     * puts them one below another, for the detail page's side panel.
     */
    multiLayout?: 'stack' | 'row'
  }>(),
  { multiLayout: 'row' },
)

const filesStore = useOrderFilesStore()
const { missing } = useMissingPermission()
// canWrite is write:orders, so a missing right names that permission.
const missingHint = computed(() => (props.canWrite ? '' : missing(Permission.WRITE_ORDERS)))

const MULTI: MultiCategorySpec[] = [
  {
    key: 'proposal',
    labelKey: 'orders.files.categories.proposal',
    accent: 'blue',
    icon: 'mdi mdi-file-document-outline',
  },
  {
    key: 'order_confirmation',
    labelKey: 'orders.files.categories.order_confirmation',
    accent: 'teal',
    icon: 'mdi mdi-file-check-outline',
  },
  {
    key: 'delivery_note',
    labelKey: 'orders.files.categories.delivery_note',
    accent: 'orange',
    icon: 'mdi mdi-truck-outline',
  },
  {
    key: 'invoice',
    labelKey: 'orders.files.categories.invoice',
    accent: 'indigo',
    icon: 'mdi mdi-receipt-text-outline',
  },
  {
    key: 'general',
    labelKey: 'orders.files.categories.general',
    accent: 'grey',
    icon: 'mdi mdi-paperclip',
  },
  {
    key: 'picture',
    labelKey: 'orders.files.categories.picture',
    accent: 'purple',
    icon: 'mdi mdi-image-outline',
  },
]
</script>

<template>
  <FilesSection
    :item-id="props.order.id"
    :files-store="filesStore"
    :multi="MULTI"
    :can-edit="props.canWrite"
    :missing-hint="missingHint"
    :multi-layout="props.multiLayout"
    :fetch-blob="getOrderFileBlob"
  />
</template>
