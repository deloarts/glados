<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useProductDevicesViewStore } from '../stores/productDevicesViewStore'

/**
 * The Devices tab's actions in the product page's controls bar: New
 * Device, and in the PLC tag mode Add Tag and export. Rendered inside the
 * bar's start slot. How the devices are looked at sits in the tab's views
 * bar (ProductDevicesViews).
 */
withDefaults(
  defineProps<{
    canEdit: boolean
    /** An archived product takes no new devices, so New Device is not offered. */
    archived?: boolean
  }>(),
  { archived: false },
)

const { t } = useI18n()
const view = useProductDevicesViewStore()
const { mode } = storeToRefs(view)
</script>

<template>
  <span v-if="!archived" v-tooltip.bottom="canEdit ? '' : t('productDevices.tags.noRights')">
    <Button
      :label="t('productDevices.devices.createDevice')"
      icon="mdi mdi-plus"
      severity="contrast"
      text
      :disabled="!canEdit"
      data-testid="product-device-create"
      @click="view.requestCreate()"
    />
  </span>
  <span v-if="mode === 'tags'" v-tooltip.bottom="canEdit ? '' : t('productDevices.tags.noRights')">
    <Button
      :label="t('productDevices.tags.addTag')"
      icon="mdi mdi-plus"
      severity="contrast"
      text
      :disabled="!canEdit"
      data-testid="product-devices-tags-add"
      @click="view.requestAddTag()"
    />
  </span>
  <Button
    v-if="mode === 'tags'"
    :label="t('productDevices.tags.export')"
    icon="mdi mdi-microsoft-excel"
    severity="contrast"
    text
    data-testid="product-devices-tags-export"
    @click="view.requestExport()"
  />
</template>
