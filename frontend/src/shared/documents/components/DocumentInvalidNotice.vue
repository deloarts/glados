<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { formatISODateTime } from '@/core/utils/dates'
import type { ControlledDocument } from '../types'

/** The banner of a released revision marked invalid, with its reason. */

defineProps<{
  document: Pick<ControlledDocument, 'invalid_at' | 'invalid_by_full_name' | 'invalid_reason'>
}>()

const { t } = useI18n()
</script>

<template>
  <Message v-if="document.invalid_at" severity="error" data-testid="document-invalid">
    {{
      t('documents.invalid.notice', {
        name: document.invalid_by_full_name ?? '',
        date: formatISODateTime(document.invalid_at),
        reason: document.invalid_reason ?? '',
      })
    }}
  </Message>
</template>
