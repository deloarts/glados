<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useProductFamiliesStore } from '../stores/productFamiliesStore'
import SimpleNamedEntityFormDialog from '@/shared/components/management/SimpleNamedEntityFormDialog.vue'
import type { ProductFamilyResponse } from '../types/productFamilyResponse'

interface Props {
  family?: ProductFamilyResponse
  /**
   * Lightweight prefill for the family name when creating from elsewhere
   * (e.g. a batch import row), ignored when editing an existing family.
   */
  prefillName?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [family: ProductFamilyResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = useProductFamiliesStore()
</script>

<template>
  <SimpleNamedEntityFormDialog
    v-model:visible="visible"
    :entity="props.family"
    :prefill-name="props.prefillName"
    id-prefix="pf"
    i18n-prefix="settings.productFamilies"
    :create-title="t('settings.productFamilies.createFamily')"
    :edit-title="t('settings.productFamilies.editFamily')"
    show-contrast-warning
    :store="store"
    @saved="(family) => emit('saved', family)"
  />
</template>
