<script setup lang="ts">
import { DemandImportDialog } from '@/shared/demand-import'
import { useMadeItemsDemandsBatchDraftStore } from '../stores/madeItemsDemandsBatchDraftStore'
import { madeItemsDemandImportAdapter } from '../utils/madeItemsDemandImportAdapter'

// Thin made-items wrapper around the generic demand-import dialog (src/shared/demand-import), mirroring BoughtItemBatchCreateDemandsDialog.vue.
const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: []
}>()

const draftStore = useMadeItemsDemandsBatchDraftStore()
</script>

<template>
  <DemandImportDialog
    v-model:visible="visible"
    :adapter="madeItemsDemandImportAdapter"
    :store="draftStore"
    @created="emit('created')"
  />
</template>
