<script setup lang="ts">
// The review step of the bought-item import: one line per sheet row with its
// status, the item it describes, and what blocks it or where an existing
// item differs from the file. Rows are edited or removed here before the
// draft is validated again.
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import BoughtItemsImportRowDialog from './BoughtItemsImportRowDialog.vue'
import BoughtItemsImportPortalCell from './BoughtItemsImportPortalCell.vue'
import { useBoughtItemsImportDraftStore } from '../stores/boughtItemsImportDraftStore'

import type { BoughtItemImportDraftRow } from '../stores/boughtItemsImportDraftStore'
import type {
  BoughtItemImportResult,
  BoughtItemImportRow,
  BoughtItemImportRowStatus,
} from '../types/boughtItemsImportTypes'

const { t } = useI18n()
const store = useBoughtItemsImportDraftStore()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const editing = ref<BoughtItemImportDraftRow | null>(null)
const showEdit = ref(false)

type DisplayStatus = BoughtItemImportRowStatus | 'unvalidated'

function resultOf(row: BoughtItemImportDraftRow): BoughtItemImportResult | undefined {
  return store.stale ? undefined : store.results[row.clientId]
}

function statusOf(row: BoughtItemImportDraftRow): DisplayStatus {
  return resultOf(row)?.row_status ?? 'unvalidated'
}

function severity(status: DisplayStatus): string {
  switch (status) {
    case 'ready':
      return 'success'
    case 'exists':
    case 'duplicate_in_file':
      return 'warn'
    case 'unvalidated':
      return 'secondary'
    default:
      return 'danger'
  }
}

function notes(row: BoughtItemImportDraftRow): string[] {
  const result = resultOf(row)
  if (!result) return []
  const lines = [...(result.errors ?? [])]
  if (result.existing_item) {
    lines.push(
      t('boughtItems.import.existingItem', {
        id: result.existing_item.id,
        name: result.existing_item.article_name,
      }),
    )
  }
  for (const d of result.portal_differences ?? []) {
    lines.push(
      t('boughtItems.import.portalDifference', {
        field: t(`boughtItems.import.portalField.${d.field}`),
        portal: d.portal_value ?? getEmptyPlaceholder(),
        file: d.file_value ?? getEmptyPlaceholder(),
      }),
    )
  }
  for (const d of result.divergences ?? []) {
    lines.push(
      t('boughtItems.import.divergence', {
        field: t(`boughtItems.import.divergenceField.${d.field}`),
        db: d.db_value ?? getEmptyPlaceholder(),
        file: d.file_value ?? getEmptyPlaceholder(),
      }),
    )
  }
  return lines
}

function onEdit(row: BoughtItemImportDraftRow): void {
  editing.value = row
  showEdit.value = true
}

function onSave(data: BoughtItemImportRow): void {
  if (editing.value) store.updateRow(editing.value.clientId, data)
}
</script>

<template>
  <DataTable
    :value="store.rows"
    data-key="clientId"
    scrollable
    scroll-height="flex"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    class="import-table"
  >
    <Column :header="t('boughtItems.import.columns.row')" style="width: 4rem" body-class="row-number">
      <template #body="{ index }">{{ index + 1 }}</template>
    </Column>
    <Column :header="t('boughtItems.import.columns.status')" style="width: 10rem">
      <template #body="{ data }">
        <Tag
          :value="t(`boughtItems.import.status.${statusOf(data as BoughtItemImportDraftRow)}`)"
          :severity="severity(statusOf(data as BoughtItemImportDraftRow))"
          data-testid="bought-item-import-status"
        />
      </template>
    </Column>
    <Column :header="t('boughtItems.import.columns.item')">
      <template #body="{ data }">
        <div class="item-cell">
          <span>{{ (data as BoughtItemImportDraftRow).data.article_name ?? getEmptyPlaceholder() }}</span>
          <small>{{ (data as BoughtItemImportDraftRow).data.order_code_1 ?? getEmptyPlaceholder() }}</small>
        </div>
      </template>
    </Column>
    <Column v-if="store.lookup" :header="t('boughtItems.import.columns.portal')" style="width: 22rem">
      <template #body="{ data }">
        <BoughtItemsImportPortalCell
          :result="resultOf(data as BoughtItemImportDraftRow)"
          :from-file="(data as BoughtItemImportDraftRow).data.skip_lookup ?? false"
          @pin="(partId) => store.pinPart((data as BoughtItemImportDraftRow).clientId, partId)"
          @skip="store.skipLookup((data as BoughtItemImportDraftRow).clientId)"
        />
      </template>
    </Column>
    <Column :header="t('boughtItems.import.columns.manufacturer')" style="width: 12rem">
      <template #body="{ data }">
        {{ (data as BoughtItemImportDraftRow).data.manufacturer_name ?? getEmptyPlaceholder() }}
      </template>
    </Column>
    <Column :header="t('boughtItems.import.columns.notes')">
      <template #body="{ data }">
        <ul class="notes">
          <li v-for="(line, i) in notes(data as BoughtItemImportDraftRow)" :key="i">{{ line }}</li>
        </ul>
      </template>
    </Column>
    <Column style="width: 6rem">
      <template #body="{ data }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            text
            rounded
            size="small"
            :aria-label="t('boughtItems.import.editRow')"
            @click="onEdit(data as BoughtItemImportDraftRow)"
          />
          <Button
            icon="mdi mdi-delete-outline"
            text
            rounded
            size="small"
            severity="danger"
            :aria-label="t('boughtItems.import.removeRow')"
            @click="store.removeRow((data as BoughtItemImportDraftRow).clientId)"
          />
        </div>
      </template>
    </Column>
  </DataTable>

  <BoughtItemsImportRowDialog v-model:visible="showEdit" :row="editing?.data ?? null" @save="onSave" />
</template>

<style scoped lang="scss">
.import-table {
  flex: 1 1 0%;
  min-height: 0;
}

.item-cell {
  display: flex;
  flex-direction: column;

  small {
    color: var(--p-text-muted-color);
  }
}

.notes {
  margin: 0;
  padding-left: var(--space-4);
  font-size: var(--font-size-sm);
}
</style>
