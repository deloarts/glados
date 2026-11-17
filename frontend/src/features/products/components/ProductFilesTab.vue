<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import ItemImageSection from '@/shared/components/files/ItemImageSection.vue'
import { getProductFileBlob } from '../api/getProductFileBlob'
import { useProductFilesStore } from '../stores/productFilesStore'
import type { ProductResponse } from '../types/productResponse'

const props = defineProps<{
  product: ProductResponse
}>()

const { t } = useI18n()
const { hasPermission } = usePermissions()
const currentUserStore = useCurrentUserStore()
const filesStore = useProductFilesStore()

// Same rule as the product form dialog: a product's designated user may
// attach files without manage:projects, as the backend allows.
const canEditFiles = computed(
  () =>
    hasPermission(Permission.MANAGE_PROJECTS) ||
    props.product.designated_user_id === currentUserStore.user?.id,
)
const missingHint = computed(() =>
  canEditFiles.value ? '' : t('resources.products.detail.editDesignatedOnly'),
)
</script>

<template>
  <div class="files-tab">
    <ItemImageSection
      :item-id="product.id"
      :files-store="filesStore"
      :can-edit="canEditFiles"
      :missing-hint="missingHint"
      i18n-prefix="resources.products.files"
      :fetch-blob="getProductFileBlob"
    />
  </div>
</template>

<style scoped lang="scss">
.files-tab {
  height: 100%;
  overflow-y: auto;
  padding: var(--space-2) 0;
}
</style>
