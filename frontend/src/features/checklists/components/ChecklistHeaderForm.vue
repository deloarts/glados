<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODate, getPickerDateFormat, toDateKey, toLocalDayStart } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { legalBasisOutdated } from '@/features/products'
import type { OwnerData } from '../composables/useOwnerData'
import type { ChecklistOwner } from '../types/checklist'
import type { Verdict } from '../utils/evaluation'
import { isIsoDate, MAX_FIELD_LENGTH, MAX_TEXT_LENGTH } from '../utils/state'
import type { HeaderTextField } from '../utils/state'
import type { ChecklistHeader } from '../utils/types'

/**
 * The data at the top of a checklist. What it belongs to and the machine
 * data come from its owner and its product and cannot be typed in here; the
 * assessment and the notes are filled in here. Who checked the checklist is
 * its release.
 */

const props = defineProps<{
  header: ChecklistHeader
  owner: ChecklistOwner
  ownerFields: OwnerData
  verdict: Verdict
  readOnly?: boolean
  /** Whether this checklist's type is released by a second person. */
  releaseRequired: boolean
  /** "Name, date" of the release, or null while it is not released. */
  releasedBy: string | null
}>()

const emit = defineEmits<{
  update: [field: HeaderTextField, value: string]
}>()

const { t } = useI18n()

const MACHINE_FIELDS = ['designation', 'machineType', 'installationSite', 'installationLocation'] as const
const TEXT_FIELDS = ['reason', 'notes'] as const

const ownerRows = computed(() => {
  const fields = props.ownerFields
  if (props.owner.kind === 'personal') return []
  const rows = [
    { key: 'number', label: t(`checklists.header.owner.${props.owner.kind}`), value: fields.ownerNumber },
    { key: 'customer', label: t('checklists.header.owner.customer'), value: fields.ownerCustomer },
  ]
  if (props.owner.kind === 'project') {
    rows.push({ key: 'product', label: t('checklists.header.owner.product'), value: fields.ownerProduct })
  }
  rows.push({ key: 'manager', label: t('checklists.header.owner.manager'), value: fields.ownerManager })
  return rows
})

const machineRows = computed(() => {
  const fields = props.ownerFields
  return [
    ...MACHINE_FIELDS.map((field) => ({ key: field, value: fields[field] })),
    {
      key: 'placingOnMarket',
      value: isIsoDate(fields.placingOnMarket) ? formatISODate(fields.placingOnMarket) : '',
    },
    { key: 'legalBasis', value: t(`checklists.legalBases.${fields.legalBasis}`) },
  ]
})

const legalBasisWarning = computed(() =>
  legalBasisOutdated(props.ownerFields.legalBasis, props.ownerFields.placingOnMarket || null),
)

function dateValue(iso: string): Date | null {
  return isIsoDate(iso) ? toLocalDayStart(iso) : null
}

function updateDate(field: 'assessedOn', value: unknown) {
  emit('update', field, value instanceof Date ? toDateKey(value) : '')
}

function shown(value: string): string {
  return value.trim() === '' ? getEmptyPlaceholder() : value
}

const inputId = (field: string) => `cl-header-${field}`
</script>

<template>
  <section class="clh" data-testid="cl-header">
    <h3 class="clh-heading">{{ t('checklists.header.title') }}</h3>
    <div v-if="ownerRows.length" class="clh-grid clh-owner" data-testid="cl-header-owner">
      <div v-for="row in ownerRows" :key="row.key" class="clh-field">
        <span class="clh-label">{{ row.label }}</span>
        <span class="clh-value" :data-testid="`cl-header-owner-${row.key}`">{{ shown(row.value) }}</span>
      </div>
    </div>
    <p v-else class="clh-hint">{{ t('checklists.header.owner.personal') }}</p>

    <div class="clh-grid clh-machine" data-testid="cl-header-machine">
      <div v-for="row in machineRows" :key="row.key" class="clh-field">
        <span class="clh-label">{{ t(`checklists.header.${row.key}`) }}</span>
        <span class="clh-value" :data-testid="`cl-header-machine-${row.key}`">{{ shown(row.value) }}</span>
      </div>
      <Message v-if="legalBasisWarning" severity="warn" size="small" data-testid="cl-legal-basis-warning">
        {{ t('checklists.header.legalBasisOutdated') }}
      </Message>
      <small v-if="!readOnly" class="clh-hint">{{ t('checklists.header.machineDataHint') }}</small>
    </div>

    <h3 class="clh-heading">{{ t('checklists.header.confirmationTitle') }}</h3>
    <p class="clh-confirmation">{{ t('checklists.header.confirmation') }}</p>
    <div class="clh-grid">
      <div class="clh-field">
        <label :for="inputId('assessedBy')" class="clh-label">{{ t('checklists.header.assessedBy') }}</label>
        <span v-if="readOnly" class="clh-value">{{ shown(header.assessedBy) }}</span>
        <InputText
          v-else
          :id="inputId('assessedBy')"
          :model-value="header.assessedBy"
          :maxlength="MAX_FIELD_LENGTH"
          fluid
          @update:model-value="emit('update', 'assessedBy', $event ?? '')"
        />
      </div>
      <div class="clh-field">
        <label :for="inputId('assessedOn')" class="clh-label">{{ t('checklists.header.assessedOn') }}</label>
        <span v-if="readOnly" class="clh-value">{{ shown(header.assessedOn) }}</span>
        <DatePicker
          v-else
          :model-value="dateValue(header.assessedOn)"
          :input-id="inputId('assessedOn')"
          :date-format="getPickerDateFormat()"
          show-button-bar
          show-clear
          fluid
          @update:model-value="updateDate('assessedOn', $event)"
        />
      </div>
      <div v-if="releaseRequired" class="clh-field">
        <span class="clh-label">{{ t('checklists.header.checkedBy') }}</span>
        <span class="clh-value" data-testid="cl-header-checked-by">
          {{ releasedBy ?? t('checklists.header.notReleased') }}
        </span>
      </div>
      <div class="clh-field">
        <span class="clh-label">{{ t('checklists.summaryCard.title') }}</span>
        <span class="clh-verdict" :class="`clh-verdict--${verdict}`" data-testid="cl-header-verdict">
          {{ t(`checklists.verdicts.${verdict}`) }}
        </span>
      </div>
    </div>
    <div class="clh-grid">
      <div v-for="field in TEXT_FIELDS" :key="field" class="clh-field">
        <label :for="inputId(field)" class="clh-label">{{ t(`checklists.header.${field}`) }}</label>
        <span v-if="readOnly" class="clh-value clh-value--text">{{ shown(header[field]) }}</span>
        <Textarea
          v-else
          :id="inputId(field)"
          :model-value="header[field]"
          :maxlength="MAX_TEXT_LENGTH"
          rows="2"
          auto-resize
          fluid
          @update:model-value="emit('update', field, $event ?? '')"
        />
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss">
.clh {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.clh-heading {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

// The form sits in the narrow column beside the checklist, so every field
// gets a row of its own.
.clh-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-3);
}

.clh-owner,
.clh-machine {
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--p-content-border-color);
}

.clh-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.clh-label {
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.clh-value {
  overflow-wrap: anywhere;

  &--text {
    white-space: pre-wrap;
  }
}

.clh-hint {
  margin: 0;
  color: var(--p-text-muted-color);
}

.clh-confirmation {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.clh-verdict {
  align-self: flex-start;
  padding: var(--space-1) var(--space-3);
  font-weight: 600;
  border: 1px solid currentcolor;
  border-radius: var(--p-content-border-radius);

  &--passed {
    color: var(--p-green-500);
  }

  &--open {
    color: var(--p-text-muted-color);
  }

  &--failed {
    color: var(--p-red-500);
  }
}
</style>
