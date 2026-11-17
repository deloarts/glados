<script setup lang="ts">
// Marks a demand or lot position that an open quote request asks suppliers
// for; it covers nothing yet. Clicking it opens the (first) request.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import type { OpenQuoteRequestRef } from '../types/quoteRequestsResponse'

const props = defineProps<{ requests: OpenQuoteRequestRef[] | undefined }>()

const { t } = useI18n()
const router = useRouter()

const tooltip = computed(() =>
  t('quoteRequests.marker.tooltip', {
    numbers: (props.requests ?? []).map((r) => r.request_number).join(', '),
  }),
)

function open(event: Event): void {
  event.stopPropagation()
  const first = props.requests?.[0]
  if (first) void router.push(`/procurement/quotes/${first.id}`)
}
</script>

<template>
  <Tag
    v-if="props.requests && props.requests.length > 0"
    class="in-quotation-tag"
    :value="t('quoteRequests.marker.label')"
    severity="help"
    icon="mdi mdi-scale-balance"
    v-tooltip.top="tooltip"
    data-testid="in-quotation-tag"
    @click="open"
  />
</template>

<style scoped lang="scss">
.in-quotation-tag {
  cursor: pointer;
  white-space: nowrap;
}
</style>
