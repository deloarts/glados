<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { SequenceSummaryResponse } from '../types/sequence'
import { sequenceStatus, STATUS_SEVERITY } from '../utils/status'

/** Draft, released or superseded, with an invalid mark beside a revision marked invalid. */
const props = defineProps<{
  sequence: Pick<SequenceSummaryResponse, 'released_at' | 'superseded_at' | 'invalid_at'>
}>()

const { t } = useI18n()
const status = computed(() => sequenceStatus(props.sequence))
</script>

<template>
  <span class="status-tags">
    <Tag :value="t(`sequences.status.${status}`)" :severity="STATUS_SEVERITY[status]" />
    <Tag v-if="sequence.invalid_at" :value="t('documents.status.invalid')" severity="danger" />
  </span>
</template>

<style scoped lang="scss">
.status-tags {
  display: inline-flex;
  gap: var(--space-1);
}
</style>
