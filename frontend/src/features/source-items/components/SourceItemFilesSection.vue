<script setup lang="ts">
/**
 * Source item file management on the shared FilesSection: an optional
 * stand-in mesh and accumulating documents. A photo of the stock is a
 * picture (SourceItemPicturesSection), not a file.
 */
import { computed, ref } from 'vue'

import FilesSection from '@/shared/components/files/FilesSection.vue'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { MESH_ACCEPT } from '@/core/utils/meshFile'
import { getSourceItemFileBlob } from '../api/sourceItemFilesApi'
import { useSourceItemFilesStore } from '../stores/sourceItemFilesStore'
import type {
  MultiCategorySpec,
  SingletonCategorySpec,
} from '@/shared/components/files/fileCategorySpec'

const props = withDefaults(
  defineProps<{
    itemId: number | null
    readonly?: boolean
    /** Restricts the shown categories by key; omit for all. */
    categories?: string[]
  }>(),
  { readonly: false },
)

const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const filesStore = useSourceItemFilesStore()

const canEdit = computed(() => hasPermission(Permission.WRITE_SOURCE_ITEMS))
const missingHint = computed(() => missing(Permission.WRITE_SOURCE_ITEMS))

// accept values mirror the backend's per-category validation.
const SINGLETONS: SingletonCategorySpec[] = [
  {
    key: 'mesh',
    labelKey: 'sourceItems.catalogue.files.categories.mesh',
    accent: 'orange',
    accept: MESH_ACCEPT,
    render: 'mesh',
  },
]

const MULTI: MultiCategorySpec[] = [
  {
    key: 'pdf',
    labelKey: 'sourceItems.catalogue.files.categories.pdf',
    accent: 'red',
    accept: 'application/pdf',
    icon: 'mdi mdi-file-pdf-box',
  },
]

const visibleSingletons = computed(() =>
  props.categories ? SINGLETONS.filter((s) => props.categories!.includes(s.key)) : SINGLETONS,
)
const visibleMulti = computed(() =>
  props.categories ? MULTI.filter((m) => props.categories!.includes(m.key)) : MULTI,
)

// Forwarded so a create form can await staged uploads once it has an id.
const filesSection = ref<InstanceType<typeof FilesSection> | null>(null)

defineExpose({
  flushPendingUploads: (id: number) => filesSection.value?.flushPendingUploads(id) ?? true,
})
</script>

<template>
  <FilesSection
    ref="filesSection"
    :item-id="itemId"
    :files-store="filesStore"
    :singletons="visibleSingletons"
    :multi="visibleMulti"
    :can-edit="canEdit"
    :missing-hint="missingHint"
    :readonly="readonly"
    title-key="sourceItems.catalogue.files.title"
    :fetch-blob="getSourceItemFileBlob"
  />
</template>
