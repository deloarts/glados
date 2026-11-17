<script setup lang="ts" generic="TItem extends { article_name: string }">
// The changelog dialog of the bought and made item catalogues. The family
// passes its changelog store and the i18n namespace of its texts, so every
// key stays with the family.
import { watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { ItemChangelogStore } from '@/shared/stores/createItemChangelogStore'

const props = defineProps<{
  item: TItem | null
  store: ItemChangelogStore<TItem>
  /** The family's changelog namespace, such as `madeItems.catalogue.changelog`. */
  i18nPrefix: string
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

watch(visible, (open) => {
  if (open) {
    props.store.select(props.item)
  } else {
    props.store.clear()
  }
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    :header="
      item ? `${t(`${i18nPrefix}.title`)}, ${item.article_name}` : t(`${i18nPrefix}.title`)
    "
    modal
    :style="{ width: 'var(--dialog-width-lg)' }"
    :draggable="false"
  >
    <div v-if="store.loading" class="loading-state">
      <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
    </div>
    <DataTable
      v-else
      :value="store.entries"
      size="small"
      scrollable
      scroll-height="60vh"
      resizable-columns
      column-resize-mode="fit"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
    >
      <template #empty>
        <EmptyState :message="t(`${i18nPrefix}.noEntries`)" />
      </template>
      <Column
        field="timestamp"
        :header="t(`${i18nPrefix}.columns.timestamp`)"
        style="min-width: 11rem; white-space: nowrap"
      />
      <Column
        field="username"
        :header="t(`${i18nPrefix}.columns.user`)"
        style="min-width: 8rem"
      />
      <Column
        field="message"
        :header="t(`${i18nPrefix}.columns.message`)"
        style="width: 100%"
      />
    </DataTable>
  </Dialog>
</template>

<style scoped lang="scss">
.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  font-size: var(--font-size-2xl);
  color: var(--p-text-muted-color);
}
</style>
