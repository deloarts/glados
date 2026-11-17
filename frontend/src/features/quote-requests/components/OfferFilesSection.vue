<script setup lang="ts">
/**
 * The documents a supplier sent with its offer, such as the offer PDF, on
 * the shared FilesSection. Both categories accumulate.
 */
import FilesSection from '@/shared/components/files/FilesSection.vue'
import { offerFilesApi } from '../api/offerFilesApi'
import { useOfferFilesStore } from '../stores/offerFilesStore'
import type { MultiCategorySpec } from '@/shared/components/files/fileCategorySpec'

const props = defineProps<{ supplierRowId: number; canWrite: boolean }>()

const filesStore = useOfferFilesStore()

const MULTI: MultiCategorySpec[] = [
  {
    key: 'offer',
    labelKey: 'quoteRequests.files.offer',
    accent: 'blue',
    icon: 'mdi mdi-file-document-outline',
  },
  {
    key: 'general',
    labelKey: 'quoteRequests.files.general',
    accent: 'grey',
    icon: 'mdi mdi-paperclip',
  },
]
</script>

<template>
  <FilesSection
    :item-id="props.supplierRowId"
    :files-store="filesStore"
    :multi="MULTI"
    :can-edit="props.canWrite"
    multi-layout="row"
    :fetch-blob="offerFilesApi.getBlob"
  />
</template>
