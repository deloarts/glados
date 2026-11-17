<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'

import { FilterMatchMode } from '@openvue/core/api'
import type { DataTableFilterMeta, DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { deleteWebhookSubscription } from '../api/deleteWebhookSubscription'
import { getWebhookEventTypes } from '../api/getWebhookEventTypes'
import { getWebhookSubscriptions } from '../api/getWebhookSubscriptions'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useClipboard } from '@/core/composables/useClipboard'
import type { WebhookSubscription } from '../types/webhookTypes'
import { WEBHOOK_EVENT_MATCH_MODE } from '../utils/webhookEventFilter'
import WebhookDeliveriesDialog from './WebhookDeliveriesDialog.vue'
import WebhookFormDialog from './WebhookFormDialog.vue'
import EmptyState from '@/shared/components/EmptyState.vue'

const { t } = useI18n()
const confirm = useConfirm()
const appToast = useAppToast()
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

defineProps<{ canWrite: boolean }>()

const subscriptions = ref<WebhookSubscription[]>([])
const eventTypes = ref<string[]>([])
const loading = ref(false)
watchLoadingBar(loading)

const formVisible = ref(false)
const editingSubscription = ref<WebhookSubscription | undefined>(undefined)

// The subscription list is loaded whole, so its row filters narrow the rows
// in the browser through OpenVue's own filters meta.
const filters = ref<DataTableFilterMeta>({
  name: { value: null, matchMode: FilterMatchMode.CONTAINS },
  url: { value: null, matchMode: FilterMatchMode.CONTAINS },
  event_types: { value: null, matchMode: WEBHOOK_EVENT_MATCH_MODE },
  is_active: { value: null, matchMode: FilterMatchMode.EQUALS },
})

const statusOptions = computed(() => [
  { value: true, label: t('adminSettings.notifications.webhooks.active') },
  { value: false, label: t('adminSettings.notifications.webhooks.inactive') },
])

const eventTypeOptions = computed(() => eventTypes.value.filter((type) => type !== '*'))

const deliveriesVisible = ref(false)
const deliveriesSubscription = ref<WebhookSubscription | null>(null)

async function load(): Promise<void> {
  loading.value = true
  try {
    subscriptions.value = await getWebhookSubscriptions()
  } catch {
    appToast.error(t('adminSettings.notifications.webhooks.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await load()
  eventTypes.value = await getWebhookEventTypes()
})

function onAdd(): void {
  editingSubscription.value = undefined
  formVisible.value = true
}

function onEdit(subscription: WebhookSubscription): void {
  editingSubscription.value = subscription
  formVisible.value = true
}

function onShowDeliveries(subscription: WebhookSubscription): void {
  deliveriesSubscription.value = subscription
  deliveriesVisible.value = true
}

function onDelete(subscription: WebhookSubscription): void {
  async function onAccept(): Promise<void> {
    try {
      await deleteWebhookSubscription(subscription.id)
      appToast.success(subscription.name, t('adminSettings.notifications.webhooks.deleted'))
      await load()
    } catch {
      appToast.error(t('adminSettings.notifications.webhooks.saveFailed'))
    }
  }

  confirm.require({
    message: t('adminSettings.notifications.webhooks.deleteConfirm', {
      name: subscription.name,
    }),
    header: t('common.delete'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('common.delete'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

const cm = ref()
const contextMenuItem = ref<WebhookSubscription | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const subscription = contextMenuItem.value
  if (!subscription) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(subscription.public_id),
    },
  ]
})

// The "Add Webhook" button sits in the Notifications tab's controls bar next
// to Save, like every other tab's actions, so the tab drives this panel's
// create dialog through this handle.
defineExpose({ openCreate: onAdd })
</script>

<template>
  <div class="webhooks-panel">
    <p class="panel-description">
      {{ t('adminSettings.notifications.webhooks.description') }}
    </p>

    <DataTable
      :value="subscriptions"
      v-model:context-menu-selection="contextMenuItem"
      data-key="id"
      size="small"
      v-model:filters="filters"
      filter-display="row"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      @row-contextmenu="onRowContextMenu"
    >
      <template #empty>
        <EmptyState :message="t('adminSettings.notifications.webhooks.noSubscriptions')" />
      </template>

      <Column
        field="name"
        :header="t('adminSettings.notifications.webhooks.name')"
        :show-filter-menu="false"
        style="width: 12rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            :aria-label="t('common.filterBy', { column: t('adminSettings.notifications.webhooks.name') })"
            size="small"
            fluid
            @input="filterCallback()"
          />
        </template>
      </Column>
      <Column
        field="url"
        :header="t('adminSettings.notifications.webhooks.url')"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: WebhookSubscription }">
          <span class="url-cell">{{ data.url }}</span>
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            :aria-label="t('common.filterBy', { column: t('adminSettings.notifications.webhooks.url') })"
            size="small"
            fluid
            @input="filterCallback()"
          />
        </template>
      </Column>
      <Column
        field="event_types"
        :header="t('adminSettings.notifications.webhooks.events')"
        :show-filter-menu="false"
        style="width: 16rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="eventTypeOptions"
            :aria-label="t('common.filterBy', { column: t('adminSettings.notifications.webhooks.events') })"
            show-clear
            filter
            size="small"
            fluid
            @change="filterCallback()"
          />
        </template>
        <template #body="{ data }: { data: WebhookSubscription }">
          <div class="event-tags">
            <Tag
              v-for="eventType in data.event_types"
              :key="eventType"
              severity="secondary"
              :value="
                eventType === '*' ? t('adminSettings.notifications.webhooks.allEvents') : eventType
              "
            />
          </div>
        </template>
      </Column>
      <Column
        field="is_active"
        :header="t('adminSettings.notifications.webhooks.status')"
        :show-filter-menu="false"
        style="width: 9rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            :aria-label="t('common.filterBy', { column: t('adminSettings.notifications.webhooks.status') })"
            show-clear
            size="small"
            fluid
            @change="filterCallback()"
          />
        </template>
        <template #body="{ data }: { data: WebhookSubscription }">
          <Tag
            :severity="data.is_active ? 'success' : 'secondary'"
            :value="
              data.is_active
                ? t('adminSettings.notifications.webhooks.active')
                : t('adminSettings.notifications.webhooks.inactive')
            "
          />
        </template>
      </Column>
      <Column style="width: 8rem">
        <template #body="{ data }: { data: WebhookSubscription }">
          <div class="row-actions">
            <Button
              icon="mdi mdi-pencil"
              size="small"
              severity="secondary"
              text
              :disabled="!canWrite"
              v-tooltip.top.focus="t('adminSettings.notifications.webhooks.edit')"
              :aria-label="t('adminSettings.notifications.webhooks.edit')"
              @click="onEdit(data)"
            />
            <Button
              icon="mdi mdi-format-list-bulleted"
              size="small"
              severity="secondary"
              text
              v-tooltip.top.focus="t('adminSettings.notifications.webhooks.deliveries')"
              :aria-label="t('adminSettings.notifications.webhooks.deliveries')"
              @click="onShowDeliveries(data)"
            />
            <Button
              icon="mdi mdi-delete-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canWrite"
              v-tooltip.top.focus="t('common.delete')"
              :aria-label="t('common.delete')"
              @click="onDelete(data)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

    <WebhookFormDialog
      v-model:visible="formVisible"
      :subscription="editingSubscription"
      :event-types="eventTypes"
      @saved="load"
    />

    <WebhookDeliveriesDialog
      v-model:visible="deliveriesVisible"
      :subscription="deliveriesSubscription"
      :can-write="canWrite"
      :event-types="eventTypes"
    />
  </div>
</template>

<style scoped lang="scss">
.webhooks-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.panel-description {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.url-cell {
  font-family: monospace;
  font-size: var(--font-size-sm);
  word-break: break-all;
}

.event-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
