<script setup lang="ts">
// The Reopen action in a quote request's header. It shows only while the
// request is closed and an award on it was voided since, which left that
// line open; without the permission to change quote requests it stays
// visible, disabled, and names the missing permission.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { reopenOffered } from '../utils/quoteRequestFormat'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

const props = defineProps<{
  request: QuoteRequestResponse
  /** Why the user may not change the request, '' when they may. */
  writeBlocked: string
}>()

const emit = defineEmits<{ reopen: [] }>()

const { t } = useI18n()

const shown = computed(() => reopenOffered(props.request))
/** Why the reopen is disabled, '' when it is not. */
const blocked = computed(() => {
  if (props.writeBlocked) return props.writeBlocked
  if (props.request.actions.includes('reopen')) return ''
  const status = t(`quoteRequests.status.${props.request.status}`).toLowerCase()
  return t('quoteRequests.blocked.ended', { status })
})
</script>

<template>
  <span v-if="shown" v-tooltip.bottom="blocked">
    <Button
      icon="mdi mdi-lock-open-variant-outline"
      :label="t('quoteRequests.actions.reopen')"
      severity="contrast"
      text
      :disabled="blocked !== ''"
      data-testid="reopen-request"
      @click="emit('reopen')"
    />
  </span>
</template>
