<script setup lang="ts">
/**
 * The pictures of a bought item on the shared ItemPicturesSection, with the
 * permission that edits the item.
 */
import { computed, ref } from 'vue'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { ItemPicturesSection } from '@/shared/pictures'
import { useBoughtItemPicturesStore } from '../stores/boughtItemPicturesStore'

withDefaults(defineProps<{ itemId: number | null; readonly?: boolean }>(), {
  readonly: false,
})

const { hasPermission } = usePermissions()
const store = useBoughtItemPicturesStore()
const canEdit = computed(() => hasPermission(Permission.WRITE_BOUGHT_ITEMS))

// Forwarded so a create form can upload a staged photo once it has an id.
const section = ref<InstanceType<typeof ItemPicturesSection> | null>(null)

defineExpose({
  flushPendingUpload: (id: number) => section.value?.flushPendingUpload(id) ?? true,
})
</script>

<template>
  <ItemPicturesSection
    ref="section"
    :item-id="itemId"
    :store="store"
    :can-edit="canEdit"
    :readonly="readonly"
  />
</template>
