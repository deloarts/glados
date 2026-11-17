<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import type {
  DataTableFilterMeta,
  DataTablePageEvent,
  DataTableRowContextMenuEvent,
} from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { formatISODateTime } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { getWebhookDeliveries } from '../api/getWebhookDeliveries'
import { retryWebhookDelivery } from '../api/retryWebhookDelivery'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useClipboard } from '@/core/composables/useClipboard'
import type { WebhookDelivery, WebhookSubscription } from '../types/webhookTypes'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { buildWebhookDeliveryParams, type WebhookDeliveryOutcome } from '../utils/webhookDeliveryParams'
import EmptyState from '@/shared/components/EmptyState.vue'
import DemandDateRangeFilter from '@/shared/components/demands/DemandDateRangeFilter.vue'

const PAGE_SIZE = 10

const { t } = useI18n()
const appToast = useAppToast()
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const visible = defineModel<boolean>('visible', { required: true })

const props = withDefaults(
  defineProps<{
    subscription: WebhookSubscription | null
    canWrite: boolean
    /** Every event type name, the options of the event row filter. */
    eventTypes?: string[]
  }>(),
  { eventTypes: () => [] },
)

// The table filters on the server, so the row filter cells bind these refs
// directly. OpenVue still reads each cell's model from a filters object,
// so the table gets this empty one.
const NO_FILTER_META: DataTableFilterMeta = {}

const outcome = ref<WebhookDeliveryOutcome | null>(null)
const eventType = ref<string | null>(null)
const attemptedFrom = ref<Date | null>(null)
const attemptedTo = ref<Date | null>(null)
const attemptedRange = useDateRangeFilter(attemptedFrom, attemptedTo)

const outcomeOptions = computed(() => [
  { value: 'success', label: t('adminSettings.notifications.webhooks.filters.succeeded') },
  { value: 'failed', label: t('adminSettings.notifications.webhooks.filters.failed') },
])

// A subscription listening to "*" still records concrete event types, so
// the wildcard itself is never a useful filter value.
const eventTypeOptions = computed(() => props.eventTypes.filter((type) => type !== '*'))

const deliveries = ref<WebhookDelivery[]>([])
const total = ref(0)
const skip = ref(0)
const loading = ref(false)
watchLoadingBar(loading)
const retryingId = ref<number | null>(null)

async function load(): Promise<void> {
  if (!props.subscription) return
  loading.value = true
  try {
    const page = await getWebhookDeliveries(
      props.subscription.id,
      buildWebhookDeliveryParams(
        { skip: skip.value, limit: PAGE_SIZE },
        {
          outcome: outcome.value,
          eventType: eventType.value,
          attemptedFrom: attemptedFrom.value,
          attemptedTo: attemptedTo.value,
        },
      ),
    )
    deliveries.value = page.items
    total.value = page.total
  } catch (e) {
    appToast.error(t('adminSettings.notifications.webhooks.loadFailed'), extractApiError(e) ?? undefined)
  } finally {
    loading.value = false
  }
}

watch(visible, (open) => {
  if (open) {
    // Filters from a previously opened subscription do not carry over.
    outcome.value = null
    eventType.value = null
    attemptedFrom.value = null
    attemptedTo.value = null
    skip.value = 0
    void load()
  }
})

watch([outcome, eventType, attemptedFrom, attemptedTo], () => {
  if (!visible.value) return
  skip.value = 0
  void load()
})

function onPage(event: DataTablePageEvent): void {
  skip.value = event.first
  void load()
}

async function onRetry(delivery: WebhookDelivery): Promise<void> {
  retryingId.value = delivery.id
  try {
    const result = await retryWebhookDelivery(delivery.id)
    if (result.success) {
      appToast.success(t('adminSettings.notifications.webhooks.retrySuccess', { status: result.http_status }))
    } else {
      appToast.warn(t('adminSettings.notifications.webhooks.retryFailed'))
    }
    await load()
  } catch {
    appToast.error(t('adminSettings.notifications.webhooks.retryFailed'))
  } finally {
    retryingId.value = null
  }
}

const cm = ref()
const contextMenuItem = ref<WebhookDelivery | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const delivery = contextMenuItem.value
  if (!delivery) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(delivery.public_id),
    },
  ]
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      t('adminSettings.notifications.webhooks.deliveriesFor', { name: subscription?.name ?? '' })
    "
    style="width: var(--dialog-width-lg)"
  >
    <DataTable
      :value="deliveries"
      v-model:context-menu-selection="contextMenuItem"
      lazy
      paginator
      :rows="PAGE_SIZE"
      :total-records="total"
      :first="skip"
      data-key="id"
      size="small"
      :filters="NO_FILTER_META"
      filter-display="row"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      @page="onPage"
      @row-contextmenu="onRowContextMenu"
    >
      <template #empty>
        <EmptyState :message="t('adminSettings.notifications.webhooks.noDeliveries')" />
      </template>

      <Column
        column-key="status"
        :header="t('adminSettings.notifications.webhooks.status')"
        :show-filter-menu="false"
        style="width: 9rem"
      >
        <template #filter>
          <Select
            v-model="outcome"
            :options="outcomeOptions"
            option-label="label"
            option-value="value"
            :aria-label="t('common.filterBy', { column: t('adminSettings.notifications.webhooks.status') })"
            show-clear
            size="small"
            fluid
          />
        </template>
        <template #body="{ data }: { data: WebhookDelivery }">
          <Tag
            :severity="data.success ? 'success' : 'danger'"
            :value="
              data.http_status !== null
                ? `HTTP ${data.http_status}`
                : (data.error ?? getEmptyPlaceholder())
            "
          />
        </template>
      </Column>
      <Column
        field="event_type"
        :header="t('adminSettings.notifications.webhooks.event')"
        :show-filter-menu="false"
        style="width: 14rem"
      >
        <template #filter>
          <Select
            v-model="eventType"
            :options="eventTypeOptions"
            :aria-label="t('common.filterBy', { column: t('adminSettings.notifications.webhooks.event') })"
            show-clear
            filter
            size="small"
            fluid
          />
        </template>
      </Column>
      <Column
        column-key="attempted_at"
        :header="t('adminSettings.notifications.webhooks.attemptedAt')"
        :show-filter-menu="false"
        style="width: 13rem"
      >
        <template #body="{ data }: { data: WebhookDelivery }">
          {{ formatISODateTime(data.attempted_at) }}
        </template>
        <template #filter>
          <DemandDateRangeFilter
            v-model="attemptedRange"
            :placeholder="t('adminSettings.notifications.webhooks.filters.dateRange')"
            @clear-click="attemptedRange = null"
          />
        </template>
      </Column>
      <Column :header="t('adminSettings.notifications.webhooks.duration')" style="width: 6rem">
        <template #body="{ data }: { data: WebhookDelivery }">
          <span v-if="data.duration_ms !== null">{{ data.duration_ms }} ms</span>
          <span v-else>{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
      <Column style="width: 4rem">
        <template #body="{ data }: { data: WebhookDelivery }">
          <Button
            icon="mdi mdi-refresh"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            :loading="retryingId === data.id"
            v-tooltip.top.focus="t('adminSettings.notifications.webhooks.retry')"
            :aria-label="t('adminSettings.notifications.webhooks.retry')"
            @click="onRetry(data)"
          />
        </template>
      </Column>
    </DataTable>

    <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
  </Dialog>
</template>
