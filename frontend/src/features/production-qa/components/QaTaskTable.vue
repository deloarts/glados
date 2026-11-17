<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { formatISODate } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { productionOrderStatusSeverity } from '@/features/production'
import { MadeItemThumbnailCell } from '@/features/made-items'
import { MadeItemDetailDialog } from '@/features/made-items'
import { MadeItemFilesCell } from '@/features/made-items'
import QaEvidenceCell from './QaEvidenceCell.vue'
import FilePreviewDialog from '@/core/components/FilePreviewDialog.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import { getMadeItemFileBlob } from '@/features/made-items'
import { getProductionOrderFileBlob } from '@/features/production'
import { useMadeItemDetail } from '@/features/made-items'
import { useMadeItemLabel } from '@/features/made-items'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useQaTasksStore } from '../stores/qaTasksStore'
import { useQaFiltersStore } from '../stores/qaFiltersStore'
import { useRowOpenGuard } from '@/core/composables/useRowOpenGuard'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useNumberRangeFilter } from '@/shared/composables/useNumberRangeFilter'
import EmptyState from '@/shared/components/EmptyState.vue'
import NumberRangeFilter from '@/shared/components/table-filters/NumberRangeFilter.vue'
import { FilterMatchMode } from '@openvue/core/api'

import type {
  DataTableFilterMeta,
  DataTablePageEvent,
  DataTableRowClickEvent,
  DataTableRowSelectEvent,
} from 'openvue/datatable'
import type { QaTaskResponse } from '../types/qaTaskResponse'
import type { MadeItemFile } from '@/features/made-items'
import type { QaEvidenceFile } from '../types/qaTaskResponse'
import type { ProductionOrderStatus } from '@/features/production'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const { t } = useI18n()
const router = useRouter()
const hostStore = useHostStore()
const tasksStore = useQaTasksStore()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const filtersStore = useQaFiltersStore()
const inspectionMethodsStore = useInspectionMethodsStore()
const {
  statuses,
  inspectionMethodIds,
  lotNumber,
  projectNumber,
  itemText,
  quantityMin,
  quantityMax,
  plannedStartFrom,
  plannedStartTo,
  finishedFrom,
  finishedTo,
  finishedByIds,
} = storeToRefs(filtersStore)
const madeItemDetail = useMadeItemDetail()
const { format: madeItemLabel } = useMadeItemLabel()

const previewFile = ref<MadeItemFile | QaEvidenceFile | null>(null)
const previewItemId = ref<number | null>(null)
const showFilePreview = ref(false)
const previewFetch = ref<() => Promise<Blob>>(() => Promise.reject(new Error('no file')))

function openFilePreview(itemId: number, file: MadeItemFile): void {
  previewItemId.value = itemId
  previewFile.value = file
  previewFetch.value = () => getMadeItemFileBlob(itemId, file.id)
  showFilePreview.value = true
}

// The row id is the production order id, so evidence previews use the
// order's file route.
function openEvidencePreview(productionOrderId: number, file: QaEvidenceFile): void {
  previewFile.value = file
  previewFetch.value = () => getProductionOrderFileBlob(productionOrderId, file.id)
  showFilePreview.value = true
}

// Paging and sorting are server-side; the view owns the page window.
const props = defineProps<{
  first: number
  rows: number
}>()

const emit = defineEmits<{
  page: [event: DataTablePageEvent]
}>()

// Filtering is server-side; this object only exists because
// filterDisplay="row" throws without an entry per filterable column.
const filters: DataTableFilterMeta = {
  status: { value: null, matchMode: FilterMatchMode.IN },
  lot_number: { value: null, matchMode: FilterMatchMode.CONTAINS },
  project_number: { value: null, matchMode: FilterMatchMode.CONTAINS },
  quantity: { value: null, matchMode: FilterMatchMode.EQUALS },
  made_item_part_number: { value: null, matchMode: FilterMatchMode.CONTAINS },
  inspection_method_id: { value: null, matchMode: FilterMatchMode.IN },
  planned_start: { value: null, matchMode: FilterMatchMode.CONTAINS },
  actual_end: { value: null, matchMode: FilterMatchMode.CONTAINS },
}

const STATUSES: ProductionOrderStatus[] = [
  'queued',
  'in_progress',
  'paused',
  'completed',
  'canceled',
]
const statusOptions = computed(() =>
  STATUSES.map((value) => ({ value, label: t(`productionQueue.status.${value}`) })),
)

// Method catalogues load the first time a picker opens.
function ensureMethodsLoaded(): void {
  if (inspectionMethodsStore.items.length === 0) void inspectionMethodsStore.refresh()
}

const quantityRange = useNumberRangeFilter(quantityMin, quantityMax)
const plannedStartRange = useDateRangeFilter(plannedStartFrom, plannedStartTo)
const finishedRange = useDateRangeFilter(finishedFrom, finishedTo)

// Server order is authoritative: it already puts actionable work first and
// applies whichever column the views bar selected.
const tableRows = computed<QaTaskResponse[]>(() => tasksStore.tasks)

function openTask(task: QaTaskResponse): void {
  void router.push(`/production/qa/${task.id}`)
}

// selection stays unbound for keyboard access, see the OpenVue pitfalls in
// docs/reference/frontend-conventions.md.
const { guard: guardRowOpen } = useRowOpenGuard<number>()

function onRowClick(event: DataTableRowClickEvent): void {
  const task = event.data as QaTaskResponse
  guardRowOpen(task.id, () => openTask(task))
}

function onRowSelect(event: DataTableRowSelectEvent): void {
  const task = event.data as QaTaskResponse
  guardRowOpen(task.id, () => openTask(task))
}

// Can this be worked now, and can it be finished?
function readinessSeverity(task: QaTaskResponse): string {
  if (task.status === 'completed') return 'success'
  if (task.status === 'canceled') return 'danger'
  if (!task.can_start) return 'secondary'
  return 'info'
}

function readinessLabel(task: QaTaskResponse): string {
  if (task.status === 'completed') return t('productionQa.readiness.done')
  if (task.status === 'canceled') return t('productionQa.readiness.canceled')
  if (task.status === 'in_progress') return t('productionQa.readiness.running')
  if (task.status === 'paused') return t('productionQa.readiness.paused')
  if (!task.can_start) return t('productionQa.readiness.waiting')
  return t('productionQa.readiness.ready')
}
</script>

<template>
  <DataTable
    :value="tableRows"
    data-key="id"
    size="small"
    :loading="tasksStore.loading"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    lazy
    paginator
    :total-records="tasksStore.total"
    :first="props.first"
    :rows="props.rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    always-show-paginator
    filter-display="row"
    :filters="filters"
    @page="emit('page', $event)"
    scrollable
    scroll-height="flex"
    class="phone-columns qa-table clickable-rows"
    selection-mode="single"
    @row-click="onRowClick"
    @row-select="onRowSelect"
  >
    <template #empty>
      <EmptyState icon="mdi mdi-clipboard-check-outline" :message="t('productionQa.empty.title')">
        <span class="hint">{{ t('productionQa.empty.hint') }}</span>
      </EmptyState>
    </template>

    <Column
      :header="t('productionQa.columns.rowNumber')"
      class="phone-row-number column-fit"
      body-class="row-number"
      :show-filter-menu="false"
    >
      <!-- Continues across pages: page 2 starts at 26, not back at 1. -->
      <template #body="{ index }">{{ props.first + index + 1 }}</template>
    </Column>

    <Column :header="t('productionQa.columns.readiness')" class="column-fit">
      <template #body="{ data }: { data: QaTaskResponse }">
        <Tag :value="readinessLabel(data)" :severity="readinessSeverity(data)" />
      </template>
    </Column>

    <Column
      class="phone-col column-fit"
      filter-field="status"
      :header="t('productionQa.columns.status')"
      style="min-width: 9rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: QaTaskResponse }">
        <Tag
          :value="t(`productionQueue.status.${data.status}`)"
          :severity="productionOrderStatusSeverity[data.status]"
        />
      </template>
      <template #filter>
        <MultiSelect
          v-model="statuses"
          :aria-label="t('productionQa.columns.status')"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('productionQa.filters.any')"
          show-clear
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      class="phone-col column-fit"
      filter-field="lot_number"
      :header="t('productionQa.columns.lotNumber')"
      style="min-width: 10rem"
      :show-filter-menu="false"
    >
      <template #filter>
        <InputText
          v-model="lotNumber"
          :placeholder="t('productionQa.filters.searchBy')"
          size="small"
          fluid
        />
      </template>
      <template #body="{ data }: { data: QaTaskResponse }">
        <div class="lot-cell">
          <span>{{ data.lot_number }}</span>
          <span class="lot-sub">
            {{ t('productionQa.columns.posShort') }}
            {{ data.lot_position_sequence }}/{{ data.lot_position_count }}
          </span>
        </div>
      </template>
    </Column>

    <Column
      class="column-fit"
      filter-field="project_number"
      :header="t('productionQa.columns.project')"
      style="min-width: 10rem"
      :show-filter-menu="false"
    >
      <template #filter>
        <InputText
          v-model="projectNumber"
          :placeholder="t('productionQa.filters.searchBy')"
          size="small"
          fluid
        />
      </template>
      <template #body="{ data }: { data: QaTaskResponse }">
        <div v-if="data.project_number" class="lot-cell">
          <span>{{ data.project_number }}</span>
          <span v-if="data.project_customer" class="lot-sub">{{ data.project_customer }}</span>
        </div>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>

    <Column
      class="column-fit"
      filter-field="quantity"
      :header="t('productionQa.columns.quantity')"
      style="min-width: 8rem"
      :show-filter-menu="false"
    >
      <template #filter>
        <NumberRangeFilter
          v-model="quantityRange"
          :fraction-digits="2"
          :column="t('productionQa.columns.quantity')"
          :placeholder="t('productionQa.filters.any')"
        />
      </template>
      <template #body="{ data }: { data: QaTaskResponse }">
        {{ data.quantity_completed }} / {{ data.quantity }}
      </template>
    </Column>

    <!-- A narrow, unlabelled thumbnail column. -->
    <Column
      v-if="hostStore.storageEnabled"
      column-key="thumbnail"
      class="phone-thumbnail"
      style="width: 3.25rem; min-width: 3.25rem; padding: var(--space-1) var(--space-2)"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: QaTaskResponse }">
        <MadeItemThumbnailCell
          :item-id="data.made_item_id"
          :item-name="data.made_item_article_name"
        />
      </template>
    </Column>

    <Column
      class="phone-col column-fit"
      filter-field="made_item_part_number"
      :header="t('productionQa.columns.item')"
      style="min-width: 12rem"
      :show-filter-menu="false"
    >
      <template #filter>
        <InputText
          v-model="itemText"
          :placeholder="t('productionQa.filters.searchBy')"
          size="small"
          fluid
        />
      </template>
      <template #body="{ data }: { data: QaTaskResponse }">
        <!-- Part number with revision leads and opens the item; the article name
             sits under it. -->
        <div class="item-cell">
          <span
            v-if="data.made_item_part_number"
            class="item-name item-link"
            role="button"
            tabindex="0"
            @click.stop="madeItemDetail.openDetailById(data.made_item_id)"
            @keydown.enter="madeItemDetail.openDetailById(data.made_item_id)"
            >{{ madeItemLabel(data.made_item_part_number, data.made_item_revision) }}</span
          >
          <span
            v-else
            class="item-name-warning item-link"
            role="button"
            tabindex="0"
            @click.stop="madeItemDetail.openDetailById(data.made_item_id)"
            @keydown.enter="madeItemDetail.openDetailById(data.made_item_id)"
          >
            <i class="mdi mdi-alert" aria-hidden="true" />
            {{ t('production.lots.noPartNumber') }}
          </span>
          <span class="item-code">{{ data.made_item_article_name }}</span>
        </div>
      </template>
    </Column>

    <!-- The part's own documents, which QA measures against. -->
    <Column
      v-if="hostStore.storageEnabled"
      :header="t('productionQa.columns.documents')"
      class="column-fit"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: QaTaskResponse }">
        <MadeItemFilesCell
          :item-id="data.made_item_id"
          @preview="(file) => openFilePreview(data.made_item_id, file)"
        />
      </template>
    </Column>

    <!-- The reports produced by this inspection. Files ride on the row, so
         opening one only fetches the blob. -->
    <Column
      v-if="hostStore.storageEnabled"
      :header="t('productionQa.columns.evidence')"
      class="column-fit"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: QaTaskResponse }">
        <QaEvidenceCell
          :files="data.evidence_files"
          @preview="(file) => openEvidencePreview(data.id, file)"
        />
      </template>
    </Column>

    <Column
      class="column-fit"
      filter-field="inspection_method_id"
      :header="t('productionQa.columns.method')"
      style="min-width: 11rem"
      :show-filter-menu="false"
    >
      <template #filter>
        <MultiSelect
          v-model="inspectionMethodIds"
          :aria-label="t('productionQa.columns.method')"
          :options="inspectionMethodsStore.activeItems"
          :option-label="labelName"
          option-value="id"
          :loading="inspectionMethodsStore.loading"
          :placeholder="t('productionQa.filters.any')"
          filter
          show-clear
          size="small"
          fluid
          @before-show="ensureMethodsLoaded"
        />
      </template>
      <template #body="{ data }: { data: QaTaskResponse }">
        <div class="method-cell">
          <span>{{ localizeLabel(data.inspection_method_name) || getEmptyPlaceholder() }}</span>
          <!-- Evidence state blocks submission, so it sits next to the method. -->
          <Tag
            v-if="data.requires_evidence && !data.has_evidence"
            :value="t('productionQa.evidence.missing')"
            icon="mdi mdi-file-alert-outline"
            severity="warn"
            v-tooltip.top="t('productionQa.evidence.missingTooltip')"
          />
          <Tag
            v-else-if="data.requires_evidence"
            :value="t('productionQa.evidence.present')"
            icon="mdi mdi-file-check-outline"
            severity="success"
          />
        </div>
      </template>
    </Column>

    <Column
      class="column-fit"
      filter-field="planned_start"
      :header="t('productionQa.columns.plannedStart')"
      style="min-width: 10rem"
      :show-filter-menu="false"
    >
      <template #filter>
        <DatePicker
          v-model="plannedStartRange"
          selection-mode="range"
          show-button-bar
          show-clear
          :placeholder="t('productionQa.filters.filterBy')"
          size="small"
          fluid
        />
      </template>
      <template #body="{ data }: { data: QaTaskResponse }">
        <span v-if="data.planned_start">{{ formatISODate(data.planned_start) }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>

    <Column
      class="column-fit"
      filter-field="actual_end"
      :header="t('productionQa.columns.finished')"
      style="min-width: 10rem"
      :show-filter-menu="false"
    >
      <template #filter>
        <UserDateFilter
          v-model:user-ids="finishedByIds"
          v-model:range="finishedRange"
          :column="t('productionQa.columns.finished')"
          :placeholder="t('productionQa.filters.any')"
        />
      </template>
      <template #body="{ data }: { data: QaTaskResponse }">
        <UserDateCell :date="data.actual_end" :user="data.finished_by" />
      </template>
    </Column>

    <Column class="column-fit">
      <template #body="{ data }: { data: QaTaskResponse }">
        <Button
          :label="t('productionQa.actions.inspect')"
          icon="mdi mdi-clipboard-check-outline"
          size="small"
          severity="secondary"
          outlined
          @click.stop="openTask(data)"
        />
      </template>
    </Column>

    <!-- Takes the width the content-wide columns leave, so the table spans
         its card without stretching them. -->
    <Column />
  </DataTable>

  <MadeItemDetailDialog
    v-model:visible="madeItemDetail.showDetail.value"
    :item="madeItemDetail.detailItem.value"
  />

  <FilePreviewDialog
    v-if="previewFile"
    v-model:visible="showFilePreview"
    :filename="previewFile.file_name"
    :mime-type="previewFile.mime_type"
    :fetch-blob="previewFetch"
  />
</template>

<style scoped lang="scss">
.qa-table {
  width: 100%;
  // Claims the card's leftover height, so scrollHeight="flex" has a definite
  // height and only the rows scroll.
  flex: 1 1 0;
  min-height: 0;
}

.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.item-link {
  cursor: pointer;
  color: inherit;
  width: fit-content;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.item-name {
  font-size: var(--font-size-md);
  font-weight: 600;
}

.item-name-warning {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 500;
  font-size: var(--font-size-sm);
  color: var(--p-orange-500);
}

.item-code,
.lot-sub {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.method-cell,
.lot-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  align-items: flex-start;
}
</style>
