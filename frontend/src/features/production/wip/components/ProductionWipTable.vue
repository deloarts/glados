<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useClipboard } from '@/core/composables/useClipboard'

import type {
  DataTableFilterMeta,
  DataTableRowContextMenuEvent,
  DataTableRowSelectEvent,
} from 'openvue/datatable'
import { FilterMatchMode } from '@openvue/core/api'
import type { MenuItem } from 'openvue/menuitem'
import { useRowOpenGuard } from '@/core/composables/useRowOpenGuard'

import {
  lotPositionKindSeverity,
  lotPositionStatusKey,
  lotPositionStatusSeverityFor,
  lotPrioritySeverity,
  lotStatusSeverity,
} from '../../utils/lotStatus'
import { storeToRefs } from 'pinia'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { MadeItemThumbnailCell, useMadeItemLabel } from '@/features/made-items'
import EmptyState from '@/shared/components/EmptyState.vue'
import NumberRangeRowFilter from '@/shared/components/table-filters/NumberRangeRowFilter.vue'
import { RowFilterMatchMode, hasActiveRowFilter } from '@/shared/utils/rowFilterModes'

import type { WipLotResponse, WipStageResponse } from '../types/productionWipResponse'

const props = defineProps<{
  lots: WipLotResponse[]
}>()

const { t } = useI18n()
const { copyToClipboard } = useClipboard()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { openLotDetail } = useLotDetail()
const hostStore = useHostStore()
const { format: madeItemLabel } = useMadeItemLabel()

const expandedRows = ref<Record<string, boolean>>({})

// Every open lot comes in one response, so filtering runs in the browser.
// _itemText joins article name and part number for the text filter.
type WipRow = WipLotResponse & { _itemText: string }

const rows = computed<WipRow[]>(() =>
  props.lots.map((lot) => ({
    ...lot,
    _itemText: [
      lot.made_item_article_name,
      madeItemLabel(lot.made_item_part_number, lot.made_item_revision),
    ].join('\n'),
  })),
)

function emptyFilters(): DataTableFilterMeta {
  return {
    lot_number: { value: null, matchMode: FilterMatchMode.CONTAINS },
    _itemText: { value: null, matchMode: FilterMatchMode.CONTAINS },
    status: { value: null, matchMode: FilterMatchMode.IN },
    priority: { value: null, matchMode: FilterMatchMode.IN },
    raw_count: { value: null, matchMode: RowFilterMatchMode.NUMBER_RANGE },
    finished_count: { value: null, matchMode: RowFilterMatchMode.NUMBER_RANGE },
  }
}

const filters = ref<DataTableFilterMeta>(emptyFilters())

const hasActiveFilters = computed(() => hasActiveRowFilter(filters.value))

/** Called from the view's Clear button. */
function clearFilters(): void {
  filters.value = emptyFilters()
}

const statusOptions = computed(() =>
  [...new Set(props.lots.map((lot) => lot.status))].map((status) => ({
    label: t(`productionWip.status.${status}`),
    value: status,
  })),
)

const priorityOptions = computed(() =>
  [...new Set(props.lots.map((lot) => lot.priority))].map((priority) => ({
    label: t(`productionWip.priority.${priority}`),
    value: priority,
  })),
)

function openLot(lot: WipLotResponse): void {
  openLotDetail(lot.id)
}

// selection stays unbound for keyboard access, see the OpenVue pitfalls in
// docs/reference/frontend-conventions.md.
const { guard: guardRowOpen } = useRowOpenGuard<number>()

function onRowSelect(event: DataTableRowSelectEvent): void {
  const lot = event.data as WipLotResponse
  guardRowOpen(lot.id, () => openLot(lot))
}

const cm = ref()
const contextMenuItem = ref<WipLotResponse | null>(null)

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  cm.value?.show(event.originalEvent)
}

const contextMenuItems = computed<MenuItem[]>(() => {
  const lot = contextMenuItem.value
  if (!lot) return []

  return [
    {
      label: t('common.copyUuid'),
      icon: 'mdi mdi-content-copy',
      command: () => void copyToClipboard(lot.public_id),
    },
  ]
})

function machineOrSupplier(stage: WipStageResponse): string {
  if (stage.kind === 'internal') return (stage.machine_names ?? []).join(', ')
  if (stage.kind === 'external') return stage.supplier_name
  return getEmptyPlaceholder()
}

defineExpose({ clearFilters, hasActiveFilters })
</script>

<template>
  <div class="card">
    <DataTable
      :value="rows"
      data-key="id"
      v-model:filters="filters"
      filter-display="row"
      v-model:expanded-rows="expandedRows"
      v-model:context-menu-selection="contextMenuItem"
      scrollable
      scroll-height="flex"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      selection-mode="single"
      @row-click="(e) => guardRowOpen((e.data as WipLotResponse).id, () => openLot(e.data as WipLotResponse))"
      @row-select="onRowSelect"
      @row-contextmenu="onRowContextMenu"
      class="clickable-rows"
    >
      <template #empty>
        <EmptyState :message="t('productionWip.empty')" />
      </template>

      <Column expander style="width: 3rem" />

      <Column
        field="lot_number"
        :header="t('productionWip.columns.lotNumber')"
        :show-filter-menu="false"
        style="width: 10rem"
      >
        <template #body="{ data }">{{ (data as WipLotResponse).lot_number }}</template>
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            :placeholder="t('productionWip.filters.filterBy')"
            :aria-label="t('common.filterBy', { column: t('productionWip.columns.lotNumber') })"
            size="small"
            fluid
            @input="filterCallback()"
          />
        </template>
      </Column>

      <!-- The thumbnail sits in the item cell, since the table is already wide. -->
      <Column
        field="_itemText"
        :header="t('productionWip.columns.item')"
        :show-filter-menu="false"
        style="width: 16rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            :placeholder="t('productionWip.filters.filterBy')"
            :aria-label="t('common.filterBy', { column: t('productionWip.columns.item') })"
            size="small"
            fluid
            @input="filterCallback()"
          />
        </template>
        <template #body="{ data }">
          <div class="item-cell-row">
            <MadeItemThumbnailCell
              v-if="hostStore.storageEnabled"
              :item-id="(data as WipLotResponse).made_item_id"
              :item-name="(data as WipLotResponse).made_item_article_name"
              size="2rem"
            />
            <div class="item-cell">
              <span class="item-name">{{ (data as WipLotResponse).made_item_article_name }}</span>
              <span class="item-code">{{
                madeItemLabel(
                  (data as WipLotResponse).made_item_part_number,
                  (data as WipLotResponse).made_item_revision,
                )
              }}</span>
            </div>
          </div>
        </template>
      </Column>

      <Column
        field="status"
        :header="t('productionWip.columns.status')"
        :show-filter-menu="false"
        style="width: 9rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <MultiSelect
            v-model="filterModel.value"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('productionWip.filters.any')"
            :aria-label="t('common.filterBy', { column: t('productionWip.columns.status') })"
            size="small"
            fluid
            @change="filterCallback()"
          />
        </template>
        <template #body="{ data }">
          <Tag
            :value="t(`productionWip.status.${(data as WipLotResponse).status}`)"
            :severity="lotStatusSeverity[(data as WipLotResponse).status]"
          />
        </template>
      </Column>

      <Column
        field="priority"
        :header="t('productionWip.columns.priority')"
        :show-filter-menu="false"
        style="width: 8rem"
      >
        <template #filter="{ filterModel, filterCallback }">
          <MultiSelect
            v-model="filterModel.value"
            :options="priorityOptions"
            option-label="label"
            option-value="value"
            :placeholder="t('productionWip.filters.any')"
            :aria-label="t('common.filterBy', { column: t('productionWip.columns.priority') })"
            size="small"
            fluid
            @change="filterCallback()"
          />
        </template>
        <template #body="{ data }">
          <Tag
            :value="t(`productionWip.priority.${(data as WipLotResponse).priority}`)"
            :severity="lotPrioritySeverity[(data as WipLotResponse).priority]"
          />
        </template>
      </Column>

      <Column
        field="raw_count"
        :header="t('productionWip.columns.rawCount')"
        :show-filter-menu="false"
        style="width: 10rem"
      >
        <template #body="{ data }">{{ (data as WipLotResponse).raw_count }}</template>
        <template #filter="{ filterModel, filterCallback }">
          <NumberRangeRowFilter
            :model-value="filterModel.value"
            :column="t('productionWip.columns.rawCount')"
            @update:model-value="
              (value) => {
                filterModel.value = value
                filterCallback()
              }
            "
          />
        </template>
      </Column>

      <Column
        field="finished_count"
        :header="t('productionWip.columns.finishedCount')"
        :show-filter-menu="false"
        style="width: 10rem"
      >
        <template #body="{ data }">{{ (data as WipLotResponse).finished_count }}</template>
        <template #filter="{ filterModel, filterCallback }">
          <NumberRangeRowFilter
            :model-value="filterModel.value"
            :column="t('productionWip.columns.finishedCount')"
            @update:model-value="
              (value) => {
                filterModel.value = value
                filterCallback()
              }
            "
          />
        </template>
      </Column>

      <Column />

      <template #expansion="{ data }">
        <DataTable
          :value="(data as WipLotResponse).stages"
          data-key="position_id"
          size="small"
          :show-gridlines="isTableGridlinesEnabled"
          :striped-rows="isTableStripedEnabled"
        >
          <template #empty>
            <EmptyState :message="t('productionWip.stages.empty')" />
          </template>
          <Column :header="t('productionWip.stages.columns.sequence')" style="width: 5rem">
            <template #body="{ data: stage }">{{ (stage as WipStageResponse).sequence }}</template>
          </Column>
          <Column :header="t('productionWip.stages.columns.kind')" style="width: 9rem">
            <template #body="{ data: stage }">
              <Tag
                :value="t(`productionWip.positionKind.${(stage as WipStageResponse).kind}`)"
                :severity="lotPositionKindSeverity[(stage as WipStageResponse).kind]"
              />
            </template>
          </Column>
          <Column :header="t('productionWip.stages.columns.status')" style="width: 11rem">
            <template #body="{ data: stage }">
              <Tag
                :value="
                  t(
                    `productionWip.positionStatus.${lotPositionStatusKey((stage as WipStageResponse).status, (stage as WipStageResponse).kind)}`,
                  )
                "
                :severity="
                  lotPositionStatusSeverityFor(
                    (stage as WipStageResponse).status,
                    (stage as WipStageResponse).kind,
                  )
                "
              />
            </template>
          </Column>
          <Column :header="t('productionWip.stages.columns.quantity')" style="width: 9rem">
            <template #body="{ data: stage }">
              {{ (stage as WipStageResponse).quantity_completed }} /
              {{ (stage as WipStageResponse).quantity }}
            </template>
          </Column>
          <Column :header="t('productionWip.stages.columns.machineOrSupplier')">
            <template #body="{ data: stage }">{{
              machineOrSupplier(stage as WipStageResponse)
            }}</template>
          </Column>
        </DataTable>
      </template>
    </DataTable>

    <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
  </div>
</template>

<style scoped lang="scss">
.card {
  flex: 1 1 0%;
  min-width: 0;
}

.item-cell-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.item-name {
  font-weight: 500;
}

.item-code {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
