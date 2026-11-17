<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import type { ChecklistSummaryResponse } from '../types/checklist'
import { checklistStatus, STATUS_SEVERITY } from '../utils/owner'

/** Where a checklist stands, with who released it and when on hover. */

const props = defineProps<{ checklist: ChecklistSummaryResponse }>()

const { t } = useI18n()

const status = computed(() => checklistStatus(props.checklist))

const tooltip = computed(() => {
  const c = props.checklist
  if (status.value === 'released' && c.released_at) {
    return t('checklists.status.releasedBy', {
      name: c.released_by_full_name ?? '',
      date: formatISODateTime(c.released_at),
    })
  }
  if (status.value === 'superseded' && c.superseded_at) {
    return t('checklists.status.supersededOn', { date: formatISODateTime(c.superseded_at) })
  }
  return ''
})
</script>

<template>
  <Tag
    v-tooltip.bottom="tooltip"
    :value="t(`checklists.status.${status}`)"
    :severity="STATUS_SEVERITY[status]"
    :data-testid="`cl-status-${status}`"
  />
</template>
