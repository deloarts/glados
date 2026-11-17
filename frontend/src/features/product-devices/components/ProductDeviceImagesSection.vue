<script setup lang="ts">
/**
 * A device's two images, the CAD rendering and the rendering of the parent
 * assembly it is installed in, in the shared file slots the catalogue items
 * use. Each slot holds one image; an upload replaces it.
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import FilesSection from '@/shared/components/files/FilesSection.vue'
import type { SingletonCategorySpec } from '@/shared/components/files/fileCategorySpec'
import { getDeviceImageBlob } from '../api/deviceImagesApi'
import { useProductDeviceImagesStore } from '../stores/productDeviceImagesStore'

const props = defineProps<{
  productId: number
  /** null while the device has not been created yet; picked images wait. */
  deviceId: number | null
  canEdit: boolean
}>()

const { t } = useI18n()
const filesStore = useProductDeviceImagesStore()

const SINGLETONS: SingletonCategorySpec[] = [
  {
    key: 'device_rendering',
    labelKey: 'productDevices.devices.images.rendering',
    accent: 'blue',
    accept: 'image/jpeg,image/png,image/webp',
    render: 'image',
  },
  {
    key: 'device_assembly',
    labelKey: 'productDevices.devices.images.assembly',
    accent: 'teal',
    accept: 'image/jpeg,image/png,image/webp',
    render: 'image',
  },
]

function fetchBlob(_deviceId: number, fileId: number): Promise<Blob> {
  return getDeviceImageBlob(props.productId, fileId)
}

const filesSection = ref<InstanceType<typeof FilesSection> | null>(null)

defineExpose({
  flushPendingUploads: (id: number) => filesSection.value?.flushPendingUploads(id) ?? true,
})
</script>

<template>
  <fieldset class="dialog-section" data-testid="device-images">
    <legend>{{ t('productDevices.devices.images.title') }}</legend>
    <FilesSection
      ref="filesSection"
      :item-id="deviceId"
      :files-store="filesStore"
      :singletons="SINGLETONS"
      :can-edit="canEdit"
      :fetch-blob="fetchBlob"
    />
  </fieldset>
</template>
