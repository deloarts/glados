<script setup lang="ts">
/**
 * Made-item file management. All behaviour lives in the shared FilesSection;
 * this only declares which categories a made item has and wires its store.
 */
import { computed, ref } from 'vue'

import FilesSection from '@/shared/components/files/FilesSection.vue'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { MESH_ACCEPT } from '@/core/utils/meshFile'
import { getMadeItemFileBlob } from '../api/madeItemFilesApi'
import { useMadeItemFilesStore } from '../stores/madeItemFilesStore'
import type {
  MultiCategorySpec,
  SingletonCategorySpec,
} from '@/shared/components/files/fileCategorySpec'

withDefaults(defineProps<{ itemId: number | null; readonly?: boolean }>(), {
  readonly: false,
})

const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const filesStore = useMadeItemFilesStore()

const canEdit = computed(() => hasPermission(Permission.WRITE_MADE_ITEMS))
const missingHint = computed(() => missing(Permission.WRITE_MADE_ITEMS))

// accept values mirror the backend's per-category validation in
// upload_made_item_file.py.
const SINGLETONS: SingletonCategorySpec[] = [
  {
    key: 'step',
    labelKey: 'madeItems.catalogue.files.categories.step',
    accent: 'teal',
    accept: '.step,.stp',
    render: 'file',
  },
  {
    key: 'mesh',
    labelKey: 'madeItems.catalogue.files.categories.mesh',
    accent: 'orange',
    accept: MESH_ACCEPT,
    render: 'mesh',
  },
  {
    key: 'drawing',
    labelKey: 'madeItems.catalogue.files.categories.drawing',
    accent: 'red',
    accept: 'application/pdf',
    render: 'file',
  },
  {
    key: 'dxf',
    labelKey: 'madeItems.catalogue.files.categories.dxf',
    accent: 'green',
    accept: '.dxf',
    render: 'file',
  },
]

const MULTI: MultiCategorySpec[] = [
  {
    key: 'pdf',
    labelKey: 'madeItems.catalogue.files.categories.pdf',
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
    title-key="madeItems.catalogue.files.title"
    :fetch-blob="getMadeItemFileBlob"
  />
</template>
