<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useProductDevicesViewStore } from '../stores/productDevicesViewStore'

/**
 * The Devices tab's views bar on the product page: how the devices are
 * looked at, the list or the overview, completeness and PLC tag modes, the
 * completeness filter, in the list the names with product number, and the
 * archived devices. The actions on the devices sit in the controls bar
 * (ProductDevicesControls).
 */
const { t } = useI18n()
const { mode, onlyIncomplete, showArchived, showFullNames } = storeToRefs(useProductDevicesViewStore())
</script>

<template>
  <Toolbar data-testid="product-devices-views">
    <template #start>
      <Button
        :label="t('productDevices.devices.modes.overview')"
        icon="mdi mdi-map-marker-radius-outline"
        severity="contrast"
        :text="mode !== 'overview'"
        data-testid="product-devices-overview"
        @click="mode = mode === 'overview' ? 'list' : 'overview'"
      />
      <Button
        :label="t('productDevices.completeness.title')"
        icon="mdi mdi-checkbox-marked-outline"
        severity="contrast"
        :text="mode !== 'completeness'"
        data-testid="product-devices-completeness"
        @click="mode = mode === 'completeness' ? 'list' : 'completeness'"
      />
      <Button
        :label="t('productDevices.tags.title')"
        icon="mdi mdi-tag-multiple-outline"
        severity="contrast"
        :text="mode !== 'tags'"
        data-testid="product-devices-tags"
        @click="mode = mode === 'tags' ? 'list' : 'tags'"
      />
      <Divider layout="vertical" />
      <Button
        v-if="mode === 'completeness'"
        :label="t('productDevices.completeness.onlyIncomplete')"
        icon="mdi mdi-filter-outline"
        severity="contrast"
        :text="!onlyIncomplete"
        data-testid="product-devices-only-incomplete"
        @click="onlyIncomplete = !onlyIncomplete"
      />
      <Button
        v-if="mode === 'list'"
        :label="t('productDevices.devices.showFullNames')"
        icon="mdi mdi-pound"
        severity="contrast"
        :text="!showFullNames"
        data-testid="product-devices-full-names"
        @click="showFullNames = !showFullNames"
      />
      <Button
        :label="t('common.showArchived')"
        icon="mdi mdi-archive-outline"
        severity="contrast"
        :text="!showArchived"
        data-testid="product-devices-archived"
        @click="showArchived = !showArchived"
      />
    </template>
  </Toolbar>
</template>
