<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { HelpButton } from '@/shared/help'
import { useExternalWorkStore } from '../stores/externalWorkStore'

const { t } = useI18n()
const store = useExternalWorkStore()

// The button names the grouping in use rather than filling up.
const groupByLabel = computed(() =>
  store.groupBy
    ? t('procurement.externalWork.groupBy.active', {
        group: t(`procurement.externalWork.groupBy.${store.groupBy}`),
      })
    : t('common.groupBy'),
)

const groupByItems = computed(() => [
  {
    label: t('procurement.externalWork.groupBy.method'),
    icon: 'mdi mdi-cog-outline',
    command: () => (store.groupBy = 'method'),
  },
  {
    label: t('procurement.externalWork.groupBy.supplier'),
    icon: 'mdi mdi-truck-outline',
    command: () => (store.groupBy = 'supplier'),
  },
])
</script>

<template>
  <ViewsBar
    id-prefix="external-work"
    hide-views-toggle
    :syncing="store.loading"
    :group-by-items="groupByItems"
    :group-by-active="!!store.groupBy"
    :group-by-label="groupByLabel"
    :has-active-filters="store.hasActiveFilters"
    v-model:search="store.search"
    :search-placeholder="t('procurement.externalWork.search')"
    @sync="void store.fetch()"
    @clear-group-by="store.groupBy = null"
    @clear="void store.clearAll()"
  >
    <template #extra>
      <Divider layout="vertical" />
      <Button
        :label="t('procurement.externalWork.onlyWithSupplier')"
        icon="mdi mdi-truck-outline"
        severity="contrast"
        :text="!store.onlyWithSupplier"
        :aria-pressed="store.onlyWithSupplier"
        data-testid="external-work-only-with-supplier"
        @click="void store.toggleOnlyWithSupplier()"
      />
      <Button
        :label="t('procurement.externalWork.onlyCritical')"
        icon="mdi mdi-alert-outline"
        severity="contrast"
        :text="!store.onlyCritical"
        :aria-pressed="store.onlyCritical"
        data-testid="external-work-only-critical"
        @click="void store.toggleOnlyCritical()"
      />
    </template>
    <template #end>
      <HelpButton slug="procurement/external-work" rounded />
    </template>
  </ViewsBar>
</template>
