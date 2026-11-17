<script setup lang="ts">
// Popover summarising a made item's successor, opened from the catalogue's
// successor tag. The item comes from the store when it is on the current
// page, otherwise it is fetched by id.
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { getMadeItems } from '../api/getMadeItems'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { useMadeItemLabel } from '../utils/madeItemLabel'

import type { MadeItemResponse } from '../types/madeItemsResponse'

const { t } = useI18n()
const madeItemsStore = useMadeItemsStore()
const { format: madeItemLabel } = useMadeItemLabel()

const popover = ref()
const item = ref<MadeItemResponse | null>(null)
const loading = ref(false)

async function show(event: Event, id: number): Promise<void> {
  item.value = null
  loading.value = true
  popover.value.show(event)

  const cached = madeItemsStore.getById(id)
  if (cached) {
    item.value = cached
    loading.value = false
    return
  }

  const result = await getMadeItems({ id, limit: 1 })
  item.value = result.items[0] ?? null
  loading.value = false
}

defineExpose({ show })
</script>

<template>
  <Popover ref="popover">
    <div class="successor-popover">
      <div v-if="loading" class="successor-popover-loading">
        <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
      </div>
      <template v-else-if="item">
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{ t('madeItems.catalogue.columns.id') }}</span>
          <span>{{ item.id }}</span>
        </div>
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{
            t('madeItems.catalogue.columns.articleName')
          }}</span>
          <span>{{ item.article_name }}</span>
        </div>
        <div class="successor-popover-row">
          <span class="successor-popover-label">{{
            t('madeItems.catalogue.columns.partNumber')
          }}</span>
          <span>{{ madeItemLabel(item.part_number, item.revision) }}</span>
        </div>
      </template>
    </div>
  </Popover>
</template>

<style lang="scss" scoped>
.successor-popover {
  min-width: 16rem;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.successor-popover-loading {
  display: flex;
  justify-content: center;
  padding: var(--space-2);
}

.successor-popover-row {
  display: flex;
  gap: var(--space-3);
  align-items: baseline;
}

.successor-popover-label {
  flex-shrink: 0;
  width: 7rem;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}
</style>
