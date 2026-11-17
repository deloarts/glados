<script setup lang="ts">
// Marks a catalogue row (table cell or detail field) whose linked PDM file
// has a release newer than what was last ingested for it. This is purely
// informational; the item itself is unaffected until someone re-ingests
// (or the next poll does).
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'

import type { PdmPreviewNewerResponse } from './api'

const props = defineProps<{
  preview: PdmPreviewNewerResponse
}>()

const { t } = useI18n()

const label = computed(() =>
  t('pdmPreview.badge.label', { version: props.preview.version, state: props.preview.state }),
)

const tooltip = computed(() =>
  props.preview.modified_at
    ? t('pdmPreview.badge.tooltip', { date: formatISODateTime(props.preview.modified_at) })
    : undefined,
)
</script>

<template>
  <Tag :value="label" severity="info" v-tooltip.top="tooltip" />
</template>
