<!--
  The document categories table of PdmSyncSection: one row per exported
  document extension, the item file category it is stored under, and a
  checkbox per item kind that receives it. Split out so the sync section
  stays within the file size limit.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { Permission } from '@/core/auth/permissions'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { normalizeExtension } from '../../utils/pdmSync'
import { PDM_DOCUMENT_CATEGORIES } from '../../types/adminSettingsTypes'
import type { PdmDocumentCategory } from '../../types/adminSettingsTypes'

const props = defineProps<{ canWrite: boolean }>()

const documentCategories = defineModel<Record<string, string>>('documentCategories', {
  required: true,
})
// Extension to the item kinds that do not receive that document.
const documentExcludedKinds = defineModel<Record<string, string[]>>('documentExcludedKinds', {
  required: true,
})

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { missing } = useMissingPermission()
const writeBlocked = computed(() => (props.canWrite ? '' : missing(Permission.WRITE_SETTINGS)))

// documentCategories is a plain Record, but a Select/InputText pair per row
// needs stable row identity while the admin is mid-edit of the extension
// key. An id-keyed local array survives that edit without the row jumping
// around (Object.entries() would re-order it the moment the key changes).
// `syncingCategoriesFromModel` guards the round trip: writing the array back
// into the models re-triggers the model watch, and without the guard that
// would immediately re-seed the array from the records it was just derived
// from. The two kind checkboxes are stored inverted, as the kinds a row
// excludes, so a row without exclusions ingests for both kinds.
interface DocumentCategoryRow {
  id: number
  extension: string
  category: string
  made: boolean
  bought: boolean
}

let nextCategoryRowId = 0
const categoryRows = ref<DocumentCategoryRow[]>([])
let syncingCategoriesFromModel = false

watch(
  [documentCategories, documentExcludedKinds],
  ([record, excluded]) => {
    if (syncingCategoriesFromModel) {
      syncingCategoriesFromModel = false
      return
    }
    categoryRows.value = Object.entries(record).map(([extension, category]) => ({
      id: nextCategoryRowId++,
      extension,
      category,
      made: !excluded[extension]?.includes('made'),
      bought: !excluded[extension]?.includes('bought'),
    }))
  },
  { immediate: true },
)

watch(
  categoryRows,
  (rows) => {
    syncingCategoriesFromModel = true
    const named = rows.filter((row) => row.extension.trim() !== '')
    documentCategories.value = Object.fromEntries(
      named.map((row) => [normalizeExtension(row.extension), row.category]),
    )
    documentExcludedKinds.value = Object.fromEntries(
      named
        .map((row): [string, string[]] => [
          normalizeExtension(row.extension),
          [...(row.made ? [] : ['made']), ...(row.bought ? [] : ['bought'])],
        ])
        .filter(([, kinds]) => kinds.length > 0),
    )
  },
  { deep: true },
)

const DOCUMENT_KINDS = ['made', 'bought'] as const

const documentCategoryOptions = computed(() =>
  PDM_DOCUMENT_CATEGORIES.map((key: PdmDocumentCategory) => ({
    label: t(`adminSettings.solidworksPdm.pdm.sync.documentCategories.categories.${key}`),
    value: key,
  })),
)

function addCategoryRow(): void {
  categoryRows.value = [
    ...categoryRows.value,
    {
      id: nextCategoryRowId++,
      extension: '',
      category: PDM_DOCUMENT_CATEGORIES[0],
      made: true,
      bought: true,
    },
  ]
}

function removeCategoryRow(id: number): void {
  categoryRows.value = categoryRows.value.filter((row) => row.id !== id)
}
</script>

<template>
  <DataTable
    :value="categoryRows"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
  >
    <template #empty>
      {{ t('adminSettings.solidworksPdm.pdm.sync.documentCategories.empty') }}
    </template>

    <Column style="width: 4rem">
      <template #body="{ data }: { data: DocumentCategoryRow }">
        <Button
          icon="mdi mdi-delete-outline"
          size="small"
          severity="danger"
          text
          :disabled="!canWrite"
          v-tooltip.top.focus="t('common.delete')"
          :aria-label="t('common.delete')"
          @click="removeCategoryRow(data.id)"
        />
      </template>
    </Column>
    <Column
      :header="t('adminSettings.solidworksPdm.pdm.sync.documentCategories.columns.extension')"
      style="width: 10rem"
    >
      <template #body="{ data }: { data: DocumentCategoryRow }">
        <InputText
          v-model="data.extension"
          size="small"
          fluid
          :disabled="!canWrite"
          :placeholder="
            t('adminSettings.solidworksPdm.pdm.sync.documentCategories.extensionPlaceholder')
          "
        />
      </template>
    </Column>
    <Column
      :header="t('adminSettings.solidworksPdm.pdm.sync.documentCategories.columns.category')"
      style="min-width: 12rem"
    >
      <template #body="{ data }: { data: DocumentCategoryRow }">
        <Select
          v-model="data.category"
          :aria-label="t('adminSettings.solidworksPdm.pdm.sync.documentCategories.columns.category')"
          :options="documentCategoryOptions"
          option-label="label"
          option-value="value"
          :disabled="!canWrite"
          fluid
        />
      </template>
    </Column>
    <Column
      v-for="kind in DOCUMENT_KINDS"
      :key="kind"
      :header="t(`adminSettings.solidworksPdm.pdm.sync.documentCategories.columns.${kind}`)"
      style="width: 8rem"
    >
      <template #body="{ data }: { data: DocumentCategoryRow }">
        <Checkbox
          v-model="data[kind]"
          binary
          :disabled="!canWrite"
          :aria-label="
            t(`adminSettings.solidworksPdm.pdm.sync.documentCategories.ingestFor.${kind}`, {
              extension: data.extension,
            })
          "
          :data-testid="`pdm-category-${kind}`"
        />
      </template>
    </Column>
  </DataTable>

  <span v-tooltip.top="writeBlocked || undefined">
    <Button
      :label="t('adminSettings.solidworksPdm.pdm.sync.documentCategories.addRow')"
      icon="mdi mdi-plus"
      size="small"
      text
      severity="secondary"
      :disabled="!canWrite"
      data-testid="pdm-category-add"
      @click="addCategoryRow"
    />
  </span>
</template>
