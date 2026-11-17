<script setup lang="ts">
/**
 * Bought-item file management. All behaviour lives in the shared
 * FilesSection; this only declares which categories a bought item has and
 * wires its store.
 */
import { computed, ref } from 'vue'

import FilesSection from '@/shared/components/files/FilesSection.vue'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { MESH_ACCEPT } from '@/core/utils/meshFile'
import { getBoughtItemFileBlob } from '../api/boughtItemFilesApi'
import { useBoughtItemFilesStore } from '../stores/boughtItemFilesStore'
import type {
  MultiCategorySpec,
  SingletonCategorySpec,
} from '@/shared/components/files/fileCategorySpec'

withDefaults(defineProps<{ itemId: number | null; readonly?: boolean }>(), {
  readonly: false,
})

const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const filesStore = useBoughtItemFilesStore()

const canEdit = computed(() => hasPermission(Permission.WRITE_BOUGHT_ITEMS))
const missingHint = computed(() => missing(Permission.WRITE_BOUGHT_ITEMS))

// accept values mirror the backend's per-category validation. A bought item
// can be a purchased assembly with its own drawing and DXF, which PDM ingest
// can attach, so it has the same categories as a made item.
const SINGLETONS: SingletonCategorySpec[] = [
  {
    key: 'mesh',
    labelKey: 'boughtItems.catalogue.files.categories.mesh',
    accent: 'orange',
    accept: MESH_ACCEPT,
    render: 'mesh',
  },
  {
    key: 'step',
    labelKey: 'boughtItems.catalogue.files.categories.step',
    accent: 'teal',
    accept: '.step,.stp',
    render: 'file',
  },
  {
    key: 'drawing',
    labelKey: 'boughtItems.catalogue.files.categories.drawing',
    accent: 'red',
    accept: 'application/pdf',
    render: 'file',
  },
  {
    key: 'dxf',
    labelKey: 'boughtItems.catalogue.files.categories.dxf',
    accent: 'green',
    accept: '.dxf',
    render: 'file',
  },
]

const MULTI: MultiCategorySpec[] = [
  {
    key: 'pdf',
    labelKey: 'boughtItems.catalogue.files.categories.pdf',
    accent: 'red',
    accept: 'application/pdf',
    icon: 'mdi mdi-file-pdf-box',
  },
]

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
    :singletons="SINGLETONS"
    :multi="MULTI"
    :can-edit="canEdit"
    :missing-hint="missingHint"
    :readonly="readonly"
    title-key="boughtItems.catalogue.files.title"
    :fetch-blob="getBoughtItemFileBlob"
  />
</template>
