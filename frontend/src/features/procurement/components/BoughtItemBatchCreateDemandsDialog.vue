<script setup lang="ts">
import { DemandImportDialog } from '@/shared/demand-import'
import { useBoughtItemsDemandsBatchDraftStore } from '../stores/boughtItemsDemandsBatchDraftStore'
import { boughtItemsDemandImportAdapter } from '../utils/boughtItemsDemandImportAdapter'

// Thin bought-items wrapper around the generic demand-import dialog
// (src/shared/demand-import).
const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: []
}>()

const draftStore = useBoughtItemsDemandsBatchDraftStore()
</script>

<template>
  <DemandImportDialog
    v-model:visible="visible"
    :adapter="boughtItemsDemandImportAdapter"
    :store="draftStore"
    @created="emit('created')"
  />
</template>
