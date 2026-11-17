<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useSourceItemTypesStore } from '../stores/sourceItemTypesStore'
import SimpleNamedEntityFormDialog from '@/shared/components/management/SimpleNamedEntityFormDialog.vue'
import type { SourceItemTypeResponse } from '../types/sourceItemTypeResponse'

interface Props {
  type?: SourceItemTypeResponse
  /**
   * Lightweight prefill for the type name when creating from elsewhere
   * (e.g. a batch import row), ignored when editing an existing type.
   */
  prefillName?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [type: SourceItemTypeResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = useSourceItemTypesStore()
</script>

<template>
  <SimpleNamedEntityFormDialog
    localized
    v-model:visible="visible"
    :entity="props.type"
    :prefill-name="props.prefillName"
    id-prefix="bit"
    i18n-prefix="settings.sourceItemTypes"
    :create-title="t('settings.sourceItemTypes.createType')"
    :edit-title="t('settings.sourceItemTypes.editType')"
    :store="store"
    @saved="(type) => emit('saved', type)"
  />
</template>
