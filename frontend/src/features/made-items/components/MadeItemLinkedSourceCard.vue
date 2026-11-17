<script setup lang="ts">
// The Material Source card of the made item detail page, showing the linked
// bought or source item.
import { computed, inject, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, routerKey } from 'vue-router'

import { BoughtItemDetailFields, getBoughtItems } from '@/features/bought-items'
import { SourceItemDetailFields, sourceItemsApi } from '@/features/source-items'

import type { MadeItemResponse } from '../types/madeItemsResponse'
import type { BoughtItemResponse } from '@/features/bought-items'
import type { SourceItemResponse } from '@/features/source-items'
import { sourceItemDisplayLabel } from '../utils/madeItemLabel'

const props = defineProps<{
  item: MadeItemResponse
}>()

// Injected with a default, since this also mounts without a router.
const router = inject(routerKey, null)

const { t } = useI18n()

// Fallback label while no record is resolved.
const sourceItemLabel = computed(() => sourceItemDisplayLabel(props.item))

// Uses the embedded record when present, else fetches it once by id. A
// counter per kind drops a response that a newer link has superseded, and a
// failed fetch leaves the card on the fallback label.
const linkedBoughtItem = ref<BoughtItemResponse | null>(null)
const linkedSourceItem = ref<SourceItemResponse | null>(null)
let latestBoughtRequest = 0
let latestSourceRequest = 0

watch(
  () => [props.item.bought_item, props.item.bought_item_id] as const,
  ([boughtItem, boughtItemId]) => {
    const request = ++latestBoughtRequest
    if (boughtItem) {
      linkedBoughtItem.value = boughtItem
      return
    }
    linkedBoughtItem.value = null
    if (boughtItemId) {
      getBoughtItems({ id: boughtItemId, limit: 1 })
        .then((result) => {
          if (request === latestBoughtRequest) linkedBoughtItem.value = result.items[0] ?? null
        })
        .catch(() => {})
    }
  },
  { immediate: true },
)

watch(
  () => [props.item.source_item, props.item.source_item_id] as const,
  ([sourceItem, sourceItemId]) => {
    const request = ++latestSourceRequest
    if (sourceItem) {
      linkedSourceItem.value = sourceItem
      return
    }
    linkedSourceItem.value = null
    if (sourceItemId) {
      sourceItemsApi
        .list({ id: sourceItemId, limit: 1 })
        .then((result) => {
          if (request === latestSourceRequest) linkedSourceItem.value = result.items[0] ?? null
        })
        .catch(() => {})
    }
  },
  { immediate: true },
)
</script>

<template>
  <Panel :header="t('madeItems.catalogue.detail.linkedSource')">
    <div class="card-scroll-body">
      <div class="linked-source">
        <template v-if="linkedBoughtItem">
          <div class="linked-source-header">
            <span class="field-label">{{
              t('madeItems.catalogue.detail.linkedSourceKindBought')
            }}</span>
            <RouterLink
              v-if="router"
              :to="`/catalogue/bought-items/${linkedBoughtItem.id}`"
              class="field-link"
              >{{ t('boughtItems.catalogue.page.open') }}</RouterLink
            >
            <span v-else class="field-value">#{{ linkedBoughtItem.id }}</span>
          </div>
          <BoughtItemDetailFields
            :item="linkedBoughtItem"
            :show-status="false"
            :show-meta="false"
          />
        </template>

        <template v-else-if="linkedSourceItem">
          <div class="linked-source-header">
            <span class="field-label">{{
              t('madeItems.catalogue.detail.linkedSourceKindSource')
            }}</span>
            <RouterLink
              v-if="router"
              :to="`/catalogue/source-items/${linkedSourceItem.id}`"
              class="field-link"
              >{{ t('sourceItems.catalogue.page.open') }}</RouterLink
            >
            <span v-else class="field-value">#{{ linkedSourceItem.id }}</span>
          </div>
          <SourceItemDetailFields
            :item="linkedSourceItem"
            :show-status="false"
            :show-meta="false"
          />
        </template>

        <div v-else class="field">
          <span class="field-value">{{ sourceItemLabel }}</span>
        </div>
      </div>
    </div>
  </Panel>
</template>

<style scoped lang="scss">
.linked-source {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.linked-source-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.field-value {
  font-size: var(--font-size-sm);
}

.field-link {
  font-size: var(--font-size-sm);
  color: var(--p-primary-color);
  word-break: break-all;
  min-width: 0;
}
</style>
