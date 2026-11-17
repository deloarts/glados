<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { WRITEBACK_MAPPABLE_FIELDS, ownerSeverity, validateVariableMap } from '../utils/itemFieldOwnership'
import EmptyState from '@/shared/components/EmptyState.vue'
import type { ItemFieldOwnership } from '../types/adminSettingsTypes'

// Ownership + mapping table, shared by the SolidWorks PDM tab's "Made
// items" and "Bought items" accordion panels (one instance per kind). This
// table shows field ownership and PDM custom property mapping. For made
// items, it also displays the PDM-side revision policy column
// (`pdm_update_in_place`); the web-side column (`web_requires_revision`)
// lives on the Numbering tab instead. A label row (article_group_names,
// manufacturer_name, process_names, source_item_name) is a normal editable
// row like any other here; `label_of` only adds a muted note under it,
// see noteFor below.
const props = withDefaults(
  defineProps<{
    kind: 'made' | 'bought'
    fields: ItemFieldOwnership[]
    canWrite: boolean
    showPdmColumn: boolean
    // Required-field names locked for this kind (AdminPdmSettings.
    // locked_required_fields[kind]), always checked and disabled in the
    // Validation column, never toggled through the `required` model below.
    lockedRequired?: string[]
  }>(),
  { lockedRequired: () => [] },
)

const variableMap = defineModel<Record<string, string>>('variableMap', { required: true })
const updateInPlace = defineModel<Record<string, boolean>>('updateInPlace', { default: () => ({}) })
// Required-field toggle map, keyed by field name, one entry per
// configurable (non-locked) mappable field. A locked field's checkbox
// state is derived from `lockedRequired` instead, never read from here.
const required = defineModel<Record<string, boolean>>('required', { default: () => ({}) })

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

function ownerLabel(owner: string): string {
  return t(`adminSettings.itemFields.owners.${owner}`)
}

// Plain "System" reads as "nobody touches this" for most server-owned
// rows (id, created, data_source, ...), which is misleading for the three
// write-back fields Glados actively writes into the vault after every
// sync; those get an extra tooltip on the same badge instead of a
// separate owner value.
function isWritebackField(field: string): boolean {
  return (WRITEBACK_MAPPABLE_FIELDS as readonly string[]).includes(field)
}

const validation = computed(() => validateVariableMap(variableMap.value))

// Display order only: the backend's own field order (FIELD_OWNERSHIP.md
// §3/§4) and the PAT wire order (get_field_mapping.py) are untouched, this
// only reshuffles what the table renders. A stable sort (guaranteed by the
// spec since ES2019) keeps each group in the backend's original order.
const OWNER_GROUP_ORDER: readonly ItemFieldOwnership['owner'][] = [
  'pdm',
  'addin',
  'addin_web',
  'web',
  'server',
]

const sortedFields = computed(() =>
  [...props.fields].sort(
    (a, b) => OWNER_GROUP_ORDER.indexOf(a.owner) - OWNER_GROUP_ORDER.indexOf(b.owner),
  ),
)

const lockedRequiredSet = computed(() => new Set(props.lockedRequired))

function isLockedRequired(field: string): boolean {
  return lockedRequiredSet.value.has(field)
}

// Locked overrides whatever the model holds; a locked name is never
// seeded into `required` in the first place, but this stays correct even
// if a caller did.
function isRequiredChecked(field: string): boolean {
  return isLockedRequired(field) || !!required.value[field]
}

// The Validation column's warning icon: a checked field (locked or
// configurable) whose own PDM variable mapping is blank, so the check the
// backend runs on ingest can never pass for any file.
function showRequiredWarning(row: ItemFieldOwnership): boolean {
  if (!row.mappable) return false
  return isRequiredChecked(row.field) && (variableMap.value[row.field] ?? '').trim() === ''
}

function noteFor(row: ItemFieldOwnership): string {
  if (row.label_of) {
    return t('adminSettings.itemFields.notes.labelOf', {
      source: t(`adminSettings.itemFields.fields.${row.label_of}`),
    })
  }
  return t(`adminSettings.itemFields.notes.${props.kind}.${row.field}`)
}
</script>

<template>
  <div class="ownership-table">
    <DataTable
      :value="sortedFields"
      data-key="field"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      row-group-mode="subheader"
      group-rows-by="owner"
    >
      <template #groupheader="{ data }: { data: ItemFieldOwnership }">
        <span class="group-header-label">{{ ownerLabel(data.owner) }}</span>
      </template>
      <Column :header="t('adminSettings.itemFields.columns.field')" style="width: 12rem">
        <template #body="{ data }: { data: ItemFieldOwnership }">
          {{ t(`adminSettings.itemFields.fields.${data.field}`) }}
        </template>
      </Column>
      <Column :header="t('adminSettings.itemFields.columns.owner')" style="width: 8rem">
        <template #body="{ data }: { data: ItemFieldOwnership }">
          <Tag
            :severity="ownerSeverity(data.owner)"
            :value="ownerLabel(data.owner)"
            v-tooltip.top="
              isWritebackField(data.field)
                ? t('adminSettings.itemFields.owners.writtenByGladosHint')
                : undefined
            "
          />
        </template>
      </Column>
      <Column :header="t('adminSettings.itemFields.columns.customProperty')" style="width: 14rem">
        <template #body="{ data }: { data: ItemFieldOwnership }">
          <InputText
            v-model="variableMap[data.field]"
            size="small"
            fluid
            :placeholder="t('adminSettings.itemFields.customPropertyPlaceholder')"
            :disabled="!canWrite || !data.mappable"
          />
        </template>
      </Column>
      <Column
        v-if="showPdmColumn"
        :header="t('adminSettings.itemFields.columns.updateInPlacePdm')"
        style="width: 9rem"
        class="checkbox-column"
      >
        <template #body="{ data }: { data: ItemFieldOwnership }">
          <Checkbox
            v-if="data.policy_applicable"
            v-model="updateInPlace[data.field]"
            binary
            :disabled="!canWrite"
            v-tooltip.top="t('adminSettings.itemFields.updateInPlaceHint')"
          />
        </template>
      </Column>
      <Column
        :header="t('adminSettings.itemFields.columns.required')"
        style="width: 8rem"
        class="checkbox-column"
      >
        <template #body="{ data }: { data: ItemFieldOwnership }">
          <div v-if="data.mappable" class="required-cell">
            <Checkbox
              v-if="isLockedRequired(data.field)"
              :model-value="true"
              binary
              disabled
              v-tooltip.top="t('adminSettings.itemFields.requiredLockedHint')"
            />
            <Checkbox v-else v-model="required[data.field]" binary :disabled="!canWrite" />
            <i
              v-if="showRequiredWarning(data)"
              class="mdi mdi-alert warning-icon"
              aria-hidden="true"
              v-tooltip.top="t('adminSettings.itemFields.requiredUnmappedWarning')"
            />
          </div>
        </template>
      </Column>
      <Column :header="t('adminSettings.itemFields.columns.notes')">
        <template #body="{ data }: { data: ItemFieldOwnership }">
          <span class="notes-cell">{{ noteFor(data) }}</span>
        </template>
      </Column>

      <template #empty>
        <EmptyState />
      </template>
    </DataTable>
    <Message v-if="validation.duplicate" severity="error" :closable="false">
      {{ t('adminSettings.itemFields.validation.duplicateVariable') }}
    </Message>
    <Message v-if="validation.missingIdentity" severity="error" :closable="false">
      {{ t('adminSettings.itemFields.validation.missingIdentity') }}
    </Message>
  </div>
</template>

<style scoped lang="scss">
.group-header-label {
  font-weight: bold;
}

.notes-cell {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.checkbox-column {
  text-align: center;
}

.required-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
}

.warning-icon {
  color: var(--p-orange-500);
}
</style>
