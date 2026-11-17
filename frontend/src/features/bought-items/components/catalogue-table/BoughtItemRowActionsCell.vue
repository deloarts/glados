<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { BoughtItemResponse } from '../../types/boughtItemsResponse'

defineProps<{
  item: BoughtItemResponse
  canWrite: boolean
  canDelete: boolean
  canCreateDemand: boolean
  canWriteOrders: boolean
}>()

const emit = defineEmits<{
  edit: [item: BoughtItemResponse]
  copy: [item: BoughtItemResponse]
  merge: [item: BoughtItemResponse]
  'create-demand': [item: BoughtItemResponse]
  'add-to-order': [item: BoughtItemResponse]
  'view-order-history': [item: BoughtItemResponse]
  'show-changelog': [item: BoughtItemResponse]
}>()

const { t } = useI18n()
</script>

<template>
  <div class="row-actions">
    <Button
      icon="mdi mdi-pencil"
      size="small"
      severity="secondary"
      text
      rounded
      :disabled="!canWrite"
      v-tooltip.focus="t('boughtItems.catalogue.controls.edit')"
      :aria-label="t('boughtItems.catalogue.controls.edit')"
      @click="emit('edit', item)"
    />
    <Button
      icon="mdi mdi-content-copy"
      size="small"
      severity="secondary"
      text
      rounded
      :disabled="!canWrite"
      v-tooltip.focus="t('boughtItems.catalogue.controls.copy')"
      :aria-label="t('boughtItems.catalogue.controls.copy')"
      @click="emit('copy', item)"
    />
    <Button
      icon="mdi mdi-source-merge"
      size="small"
      severity="secondary"
      text
      rounded
      :disabled="!canDelete"
      v-tooltip.focus="t('boughtItems.catalogue.controls.merge')"
      :aria-label="t('boughtItems.catalogue.controls.merge')"
      @click="emit('merge', item)"
    />
    <Button
      icon="mdi mdi-cart-plus"
      size="small"
      severity="secondary"
      text
      rounded
      :disabled="!canCreateDemand"
      v-tooltip.focus="t('boughtItems.catalogue.contextMenu.createDemand')"
      :aria-label="t('boughtItems.catalogue.contextMenu.createDemand')"
      @click="emit('create-demand', item)"
    />
    <Button
      icon="mdi mdi-cart-arrow-right"
      size="small"
      severity="secondary"
      text
      rounded
      :disabled="!canWriteOrders"
      v-tooltip.focus="t('boughtItems.catalogue.contextMenu.addToOrder')"
      :aria-label="t('boughtItems.catalogue.contextMenu.addToOrder')"
      @click="emit('add-to-order', item)"
    />
    <Button
      icon="mdi mdi-receipt-text-outline"
      size="small"
      severity="secondary"
      text
      rounded
      v-tooltip.focus="t('boughtItems.catalogue.orderHistory.viewOrders')"
      :aria-label="t('boughtItems.catalogue.orderHistory.viewOrders')"
      @click="emit('view-order-history', item)"
    />
    <Button
      icon="mdi mdi-history"
      size="small"
      severity="secondary"
      text
      rounded
      v-tooltip.focus="t('boughtItems.catalogue.contextMenu.showChangelog')"
      :aria-label="t('boughtItems.catalogue.contextMenu.showChangelog')"
      @click="emit('show-changelog', item)"
    />
  </div>
</template>
