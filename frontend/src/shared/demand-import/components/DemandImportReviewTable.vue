<script
  setup
  lang="ts"
  generic="K extends string, TRow extends DemandImportRow, TItem, R extends ImportRowValidation<TItem>"
>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import DemandImportRowFormDialog from './DemandImportRowFormDialog.vue'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EmptyState from '@/shared/components/EmptyState.vue'

import type { DemandImportDraftStore } from '../stores/createDemandImportDraftStore'
import type {
  DemandImportAdapter,
  DemandImportRow,
  DraftRow,
  ImportDivergence,
  ImportRowStatus,
  ImportRowValidation,
  ReviewColumnSpec,
} from '../types/demandImport'

const props = defineProps<{
  adapter: DemandImportAdapter<K, TRow, TItem, R>
  store: DemandImportDraftStore<K, TRow, TItem, R>
}>()

const { t } = useI18n()

const hostStore = useHostStore()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const showAddRow = ref(false)

type DisplayStatus = ImportRowStatus | 'unvalidated'

function statusSeverity(status: DisplayStatus): string {
  switch (status) {
    case 'matched':
      return 'success'
    case 'not_found':
    case 'ambiguous':
    case 'unresolved_reference':
    case 'invalid':
      return 'danger'
    default:
      return 'secondary'
  }
}

function validationResult(row: DraftRow<TRow>): R | undefined {
  return props.store.validationResults[row.clientId]
}

function rowStatus(row: DraftRow<TRow>): DisplayStatus {
  const result = validationResult(row)
  if (!result || props.store.validationStale) return 'unvalidated'
  return result.row_status
}

function divergences(row: DraftRow<TRow>) {
  return validationResult(row)?.divergences ?? []
}

// One human-readable line per divergence. A divergence with no file value
// (e.g. a catalogue-status warning, since the sheet has no such column) shows
// only the catalogue side, so the user never reads an empty `File ""`.
function divergenceValue(field: string, value: string | null): string {
  if (value === null) return getEmptyPlaceholder()
  return props.adapter.divergenceValue ? props.adapter.divergenceValue(field, value, t) : value
}

function divergenceText(divergence: ImportDivergence): string {
  const label = props.adapter.divergenceLabel(divergence.field, t)
  const dbText = `${t(`${props.adapter.i18nPrefix}.review.dbValue`)} "${divergenceValue(divergence.field, divergence.db_value)}"`
  if (divergence.file_value === null) return `${label}: ${dbText}`
  const fileText = `${t(`${props.adapter.i18nPrefix}.review.fileValue`)} "${divergenceValue(divergence.field, divergence.file_value)}"`
  return `${label}: ${fileText} · ${dbText}`
}

function hasDivergenceWarning(row: DraftRow<TRow>): boolean {
  return rowStatus(row) === 'matched' && divergences(row).length > 0
}

function matchedItem(row: DraftRow<TRow>): TItem | null {
  return validationResult(row)?.matched_item ?? null
}

function hintKey(row: DraftRow<TRow>): string | null {
  const status = rowStatus(row)
  if (status === 'unvalidated') return null
  return props.adapter.blockedHintKey(status, validationResult(row))
}

function quantityUnit(row: DraftRow<TRow>): string | null {
  return props.adapter.quantityUnit?.(row.data) ?? null
}

// A column's primary()/secondary() may return an embedded '\n' to stack more
// than one line inside the same cell slot (e.g. article name + order code):
// this is the one convention that lets ReviewColumnSpec stay a plain
// primary/secondary pair instead of growing a third render hook.
function splitLines(value: string | null): string[] {
  return value ? value.split('\n') : []
}

function headerKey(column: ReviewColumnSpec<TRow, R>): string {
  const prefix = `${props.adapter.i18nPrefix}.`
  return column.headerKey.startsWith(prefix) ? column.headerKey : `${prefix}${column.headerKey}`
}

function onRowAdded(data: TRow): void {
  props.store.addRow(data)
}
</script>

<template>
  <div class="card">
    <div
      v-if="store.blockedRowCount > 0 || store.warningRowCount > 0"
      class="review-summary"
    >
      <span v-if="store.blockedRowCount > 0" class="summary-item summary-item-danger">
        <i class="mdi mdi-alert-circle-outline" aria-hidden="true" />
        {{ t(`${adapter.i18nPrefix}.review.blockedCount`, { count: store.blockedRowCount }) }}
      </span>
      <span v-if="store.warningRowCount > 0" class="summary-item summary-item-warn">
        <i class="mdi mdi-alert-outline" aria-hidden="true" />
        {{ t(`${adapter.i18nPrefix}.review.warningCount`, { count: store.warningRowCount }) }}
      </span>
    </div>

    <DataTable
      :value="store.rows"
      data-key="clientId"
      size="small"
      scrollable
      scroll-height="flex"
      table-style="min-width: 72rem"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
    >
      <Column style="width: 3.5rem" frozen>
        <template #body="{ data }">
          <Button
            icon="mdi mdi-delete-outline"
            size="small"
            severity="danger"
            text
            rounded
            v-tooltip.focus="t(`${adapter.i18nPrefix}.actions.removeRow`)"
            :aria-label="t(`${adapter.i18nPrefix}.actions.removeRow`)"
            @click="store.removeRow((data as DraftRow<TRow>).clientId)"
          />
        </template>
      </Column>

      <Column :header="t(`${adapter.i18nPrefix}.review.row`)" style="width: 3rem" body-class="row-number">
        <template #body="{ index }">{{ index + 1 }}</template>
      </Column>

      <Column :header="t(`${adapter.i18nPrefix}.review.status`)" style="width: 11rem">
        <template #body="{ data }">
          <div class="status-cell">
            <Tag
              :value="t(`${adapter.i18nPrefix}.status.${rowStatus(data as DraftRow<TRow>)}`)"
              :severity="statusSeverity(rowStatus(data as DraftRow<TRow>))"
            />
            <i
              v-if="hasDivergenceWarning(data as DraftRow<TRow>)"
              class="mdi mdi-alert status-warn-icon"
              aria-hidden="true"
              v-tooltip="t(`${adapter.i18nPrefix}.review.divergenceWarning`)"
            />
          </div>
        </template>
      </Column>

      <Column :header="t(`${adapter.i18nPrefix}.review.project`)" style="width: 8rem">
        <template #body="{ data }">{{ (data as DraftRow<TRow>).data.project_number }}</template>
      </Column>

      <Column :header="t(`${adapter.i18nPrefix}.review.quantity`)" style="width: 8rem">
        <template #body="{ data }">
          {{ (data as DraftRow<TRow>).data.quantity }} {{ quantityUnit(data as DraftRow<TRow>) }}
        </template>
      </Column>

      <Column
        v-if="hostStore.storageEnabled && adapter.thumbnail"
        style="width: 3.25rem; min-width: 3.25rem; padding: var(--space-1) var(--space-2)"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <component
            :is="adapter.thumbnail!.component"
            v-if="matchedItem(data as DraftRow<TRow>) !== null"
            :item-id="adapter.thumbnail!.itemId(matchedItem(data as DraftRow<TRow>)!)"
            :item-name="adapter.thumbnail!.itemName(matchedItem(data as DraftRow<TRow>)!)"
          />
        </template>
      </Column>

      <Column
        v-for="column in adapter.reviewColumns"
        :key="column.key"
        :header="t(headerKey(column))"
        :style="column.width ? `width: ${column.width}` : undefined"
      >
        <template #body="{ data }">
          <div class="review-col">
            <template v-if="column.primary((data as DraftRow<TRow>).data)">
              <span v-for="(line, i) in splitLines(column.primary((data as DraftRow<TRow>).data))" :key="`p-${i}`">
                {{ line }}
              </span>
            </template>
            <span v-else>{{ getEmptyPlaceholder() }}</span>
            <template v-if="column.secondary">
              <span
                v-for="(line, i) in splitLines(
                  column.secondary!((data as DraftRow<TRow>).data, validationResult(data as DraftRow<TRow>)),
                )"
                :key="`s-${i}`"
                class="review-col-muted"
              >
                {{ line }}
              </span>
            </template>
          </div>
        </template>
      </Column>

      <Column :header="t(`${adapter.i18nPrefix}.review.details`)" style="min-width: 16rem">
        <template #body="{ data }">
          <div class="details-cell">
            <template v-if="hasDivergenceWarning(data as DraftRow<TRow>)">
              <span
                v-for="divergence in divergences(data as DraftRow<TRow>)"
                :key="divergence.field"
                class="divergence-label"
              >
                {{ divergenceText(divergence) }}
              </span>
            </template>
            <template v-else-if="!['matched', 'unvalidated'].includes(rowStatus(data as DraftRow<TRow>))">
              <span class="error-text">
                {{ validationResult(data as DraftRow<TRow>)?.errors.join('; ') }}
              </span>
              <span v-if="hintKey(data as DraftRow<TRow>)" class="error-hint">
                {{ t(hintKey(data as DraftRow<TRow>)!) }}
              </span>
            </template>
          </div>
        </template>
      </Column>

      <template #empty>
        <EmptyState />
      </template>

      <template #footer>
        <Button
          :label="t(`${adapter.i18nPrefix}.addRow.add`)"
          icon="mdi mdi-plus"
          size="small"
          text
          @click="showAddRow = true"
        />
      </template>
    </DataTable>
  </div>

  <DemandImportRowFormDialog :adapter="adapter" v-model:visible="showAddRow" @added="onRowAdded" />
</template>

<style scoped lang="scss">
.card {
  display: flex;
  flex-direction: column;
  flex: 1 1 0%;
  min-width: 0;
  min-height: 0;
}

.review-summary {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  padding: 0 0 var(--space-2);
}

.summary-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.summary-item-danger {
  color: var(--p-red-500);
}

.summary-item-warn {
  color: var(--p-orange-500);
}

.status-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.status-warn-icon {
  color: var(--p-orange-500);
}

.review-col {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.review-col-muted {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.details-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.divergence-label {
  font-size: var(--font-size-sm);
}

.error-text {
  font-size: var(--font-size-sm);
  color: var(--p-red-500);
}

.error-hint {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
