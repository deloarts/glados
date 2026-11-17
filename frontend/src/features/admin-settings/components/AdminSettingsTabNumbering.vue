<script setup lang="ts">
import { computed, reactive, ref, toRef, useId, watch, type ComputedRef, type WritableComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import SettingsToggleRow from './SettingsToggleRow.vue'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useSettingsSave } from '../composables/useSettingsSave'
import { renderNumberFormatExample } from '../utils/numberingFormatExample'
import { mergeRevisionFieldPolicy } from '../utils/itemFieldOwnership'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'
import NumberPatternInput from './NumberPatternInput.vue'
import type {
  ItemFieldOwnership,
  RevisionPredecessorStatusPdm,
  RevisionPredecessorStatusWeb,
} from '../types/adminSettingsTypes'
import { matchesNumberPattern } from '@/shared/utils/numberPattern'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

const REVISION_START_OPTIONS = ['A', '0', '1'] as const

// "ask" lets the New Revision form choose the predecessor status, a web-only
// option.
const revisionPredecessorWebOptions = computed(() => [
  { label: t('adminSettings.numbering.revisionPredecessorAsk'), value: 'ask' as const },
  { label: t('madeItems.catalogue.status.active'), value: 'active' as const },
  { label: t('madeItems.catalogue.status.inactive'), value: 'inactive' as const },
  { label: t('madeItems.catalogue.status.replaced'), value: 'replaced' as const },
])

const revisionPredecessorPdmOptions = computed(() => [
  { label: t('madeItems.catalogue.status.active'), value: 'active' as const },
  { label: t('madeItems.catalogue.status.inactive'), value: 'inactive' as const },
  { label: t('madeItems.catalogue.status.replaced'), value: 'replaced' as const },
])

interface OrdersForm {
  order_number_format: string
  quote_request_number_format: string
  part_number_format: string
  part_number_auto: boolean
  part_number_editable: boolean
  web_creation_allowed: boolean
  pdm_part_number_pattern: string
}

interface MadeItemsForm {
  item_number_format: string
  part_number_auto: boolean
  part_number_editable: boolean
  web_creation_allowed: boolean
  pdm_part_number_pattern: string
  revision_start: string
  revision_separator: string
  revision_skip_ambiguous_letters: boolean
  revision_only_newest_editable: boolean
  revision_predecessor_status_web: RevisionPredecessorStatusWeb
  revision_predecessor_status_pdm: RevisionPredecessorStatusPdm
}

interface LotsForm {
  lot_number_format: string
}

interface ProductionForm {
  production_order_number_format: string
}

interface PatternsForm {
  product_number_pattern: string
  project_number_pattern: string
}

const ordersForm = reactive<OrdersForm>({
  order_number_format: 'ORD-{yy}-{seq:05d}',
  quote_request_number_format: 'RFQ-{yy}-{seq:05d}',
  part_number_format: 'PUR-{yy}-{seq:05d}',
  part_number_auto: true,
  part_number_editable: false,
  web_creation_allowed: true,
  pdm_part_number_pattern: '',
})

// This tab owns only web_requires_revision; mergeRevisionFieldPolicy keeps the
// SolidWorks PDM tab's pdm_update_in_place column intact on save.
const webRequiresRevision = reactive<Record<string, boolean>>({})

const madeItemsForm = reactive<MadeItemsForm>({
  item_number_format: 'FAB-{yy}-{seq:05d}',
  part_number_auto: true,
  part_number_editable: false,
  web_creation_allowed: true,
  pdm_part_number_pattern: '',
  revision_start: '0',
  revision_separator: ':',
  revision_skip_ambiguous_letters: false,
  revision_only_newest_editable: true,
  revision_predecessor_status_web: 'ask',
  revision_predecessor_status_pdm: 'replaced',
})

const lotsForm = reactive<LotsForm>({
  lot_number_format: 'LOT-{yy}-{seq:05d}',
})

// Calculations, checklists and flow sequences, numbered once per document;
// every revision keeps the number. Meetings are numbered once each.
const documentsForm = reactive({
  calculation_number_format: 'CAL-{yy}-{seq:04d}',
  checklist_number_format: 'CHK-{yy}-{seq:04d}',
  sequence_number_format: 'SEQ-{yy}-{seq:04d}',
  meeting_number_format: 'MTG-{yy}-{seq:04d}',
})

const productionForm = reactive<ProductionForm>({
  production_order_number_format: 'PON-{yy}-{seq:05d}',
})

// Validation regexes for numbers users type, not generation templates. An
// empty string means no enforcement.
const patternsForm = reactive<PatternsForm>({
  product_number_pattern: '',
  project_number_pattern: '',
})

watch(
  () => store.settings?.orders,
  (s) => {
    if (!s) return
    ordersForm.order_number_format = s.order_number_format
    ordersForm.quote_request_number_format = s.quote_request_number_format
    ordersForm.part_number_format = s.part_number_format
    ordersForm.part_number_auto = s.part_number_auto
    ordersForm.part_number_editable = s.part_number_editable
    ordersForm.web_creation_allowed = s.web_creation_allowed
    ordersForm.pdm_part_number_pattern = s.pdm_part_number_pattern
  },
  { immediate: true },
)

watch(
  () => store.settings?.made_items,
  (s) => {
    if (!s) return
    madeItemsForm.item_number_format = s.item_number_format
    madeItemsForm.part_number_auto = s.part_number_auto
    madeItemsForm.part_number_editable = s.part_number_editable
    madeItemsForm.web_creation_allowed = s.web_creation_allowed
    madeItemsForm.pdm_part_number_pattern = s.pdm_part_number_pattern
    madeItemsForm.revision_start = s.revision_start
    madeItemsForm.revision_separator = s.revision_separator
    madeItemsForm.revision_skip_ambiguous_letters = s.revision_skip_ambiguous_letters
    madeItemsForm.revision_only_newest_editable = s.revision_only_newest_editable
    madeItemsForm.revision_predecessor_status_web = s.revision_predecessor_status_web
    madeItemsForm.revision_predecessor_status_pdm = s.revision_predecessor_status_pdm
    for (const entry of s.revision_field_policy) {
      webRequiresRevision[entry.field] = entry.web_requires_revision
    }
    lotsForm.lot_number_format = s.lot_number_format
    for (const key of Object.keys(documentsForm) as (keyof typeof documentsForm)[]) {
      documentsForm[key] = s[key]
    }
  },
  { immediate: true },
)

// The ownership table, not the stored policy, lists which fields have a
// revision policy, since a newly applicable field may have no stored row yet.
const revisionPolicyFields = computed<ItemFieldOwnership[]>(
  () => store.settings?.pdm?.item_fields.made.filter((row) => row.policy_applicable) ?? [],
)

watch(
  () => store.settings?.production,
  (s) => {
    if (!s) return
    productionForm.production_order_number_format = s.production_order_number_format
  },
  { immediate: true },
)

watch(
  () => store.settings?.general,
  (s) => {
    if (!s) return
    patternsForm.product_number_pattern = s.product_number_pattern
    patternsForm.project_number_pattern = s.project_number_pattern
  },
  { immediate: true },
)

// Not stored: initialized once from whether the formats match, then driven by
// the toggle, since an equality-based getter could never be switched off.
const sharedSchema = ref(false)
let sharedSchemaInitialized = false

watch(
  () => [store.settings?.orders, store.settings?.made_items] as const,
  ([orders, madeItems]) => {
    if (sharedSchemaInitialized || !orders || !madeItems) return
    sharedSchema.value = orders.part_number_format === madeItems.item_number_format
    sharedSchemaInitialized = true
  },
)

watch(sharedSchema, (checked) => {
  if (checked) {
    madeItemsForm.item_number_format = ordersForm.part_number_format
  }
})

// Same idiom as sharedSchema, for the external pattern.
const sharePattern = ref(false)
let sharePatternInitialized = false

watch(
  () => [store.settings?.orders, store.settings?.made_items] as const,
  ([orders, madeItems]) => {
    if (sharePatternInitialized || !orders || !madeItems) return
    sharePattern.value = orders.pdm_part_number_pattern === madeItems.pdm_part_number_pattern
    sharePatternInitialized = true
  },
)

watch(sharePattern, (checked) => {
  if (checked) {
    madeItemsForm.pdm_part_number_pattern = ordersForm.pdm_part_number_pattern
  }
})

// Part number auto-generation applies equally to bought and made items, so
// one control drives both domains. Web creation and the external pattern stay
// per kind unless sharePattern is on.
const partNumberAuto = computed<boolean>({
  get: () => ordersForm.part_number_auto,
  set: (value) => {
    ordersForm.part_number_auto = value
    madeItemsForm.part_number_auto = value
  },
})

const partNumberEditable = computed<boolean>({
  get: () => ordersForm.part_number_editable,
  set: (value) => {
    ordersForm.part_number_editable = value
    madeItemsForm.part_number_editable = value
  },
})

// The general toggle rows, each labelled and explained under
// adminSettings.numbering by its key.
const generalToggles = [
  { key: 'sharedSchema', model: sharedSchema },
  { key: 'partNumberAuto', model: partNumberAuto },
  { key: 'partNumberEditable', model: partNumberEditable },
  { key: 'webCreationMade', model: toRef(madeItemsForm, 'web_creation_allowed') },
  { key: 'webCreationBought', model: toRef(ordersForm, 'web_creation_allowed') },
]

// While shared, one input edits both identical formats.
const sharedItemFormat = computed<string>({
  get: () => ordersForm.part_number_format,
  set: (value) => {
    ordersForm.part_number_format = value
    madeItemsForm.item_number_format = value
  },
})

// Same idiom as sharedItemFormat, for the external pattern.
const sharedExternalPattern = computed<string>({
  get: () => ordersForm.pdm_part_number_pattern,
  set: (value) => {
    ordersForm.pdm_part_number_pattern = value
    madeItemsForm.pdm_part_number_pattern = value
  },
})

interface NumberFormatField {
  /** Key under adminSettings.numbering for the label. */
  labelKey: string
  /** The default format, shown next to the label as a hint. */
  hint: string
  model: WritableComputedRef<string>
  /** Live preview from the current value, not the last saved example. */
  example: ComputedRef<string | null>
  testId?: string
}

function formField<K extends string>(form: Record<K, string>, key: K): WritableComputedRef<string> {
  return computed({
    get: () => form[key],
    set: (value) => {
      form[key] = value
    },
  })
}

function numberFormatField(
  labelKey: string,
  hint: string,
  model: WritableComputedRef<string>,
  testId?: string,
): NumberFormatField {
  return {
    labelKey,
    hint,
    model,
    example: computed(() => renderNumberFormatExample(model.value)),
    testId,
  }
}

const sharedItemFormatField = numberFormatField('itemFormat', 'FAB-{yy}-{seq:05d}', sharedItemFormat)
const itemNumberFormatField = numberFormatField(
  'itemNumberFormat',
  'FAB-{yy}-{seq:05d}',
  formField(madeItemsForm, 'item_number_format'),
)
const partNumberFormatField = numberFormatField(
  'partNumberFormat',
  'PUR-{yy}-{seq:05d}',
  formField(ordersForm, 'part_number_format'),
)

// One shared format for both item kinds, or one per kind.
const internalFormatFields = computed(() =>
  sharedSchema.value ? [sharedItemFormatField] : [itemNumberFormatField, partNumberFormatField],
)

/** The sections after the revisions, each with its number formats. */
const formatSections: { labelKey: string; hintKey?: string; fields: NumberFormatField[] }[] = [
  {
    labelKey: 'procurementSection',
    fields: [
      numberFormatField(
        'orderNumberFormat',
        'ORD-{yy}-{seq:05d}',
        formField(ordersForm, 'order_number_format'),
      ),
      numberFormatField(
        'quoteRequestNumberFormat',
        'RFQ-{yy}-{seq:05d}',
        formField(ordersForm, 'quote_request_number_format'),
      ),
    ],
  },
  {
    labelKey: 'lotsSection',
    fields: [
      numberFormatField('lotNumberFormat', 'LOT-{yy}-{seq:05d}', formField(lotsForm, 'lot_number_format')),
    ],
  },
  {
    labelKey: 'productionOrdersSection',
    fields: [
      numberFormatField(
        'productionOrderNumberFormat',
        'PON-{yy}-{seq:05d}',
        formField(productionForm, 'production_order_number_format'),
      ),
    ],
  },
  {
    labelKey: 'documentsSection',
    hintKey: 'documentsHint',
    fields: [
      numberFormatField(
        'calculationNumberFormat',
        'CAL-{yy}-{seq:04d}',
        formField(documentsForm, 'calculation_number_format'),
        'numbering-calculation-format',
      ),
      numberFormatField(
        'checklistNumberFormat',
        'CHK-{yy}-{seq:04d}',
        formField(documentsForm, 'checklist_number_format'),
        'numbering-checklist-format',
      ),
      numberFormatField(
        'sequenceNumberFormat',
        'SEQ-{yy}-{seq:04d}',
        formField(documentsForm, 'sequence_number_format'),
        'numbering-sequence-format',
      ),
      numberFormatField(
        'meetingNumberFormat',
        'MTG-{yy}-{seq:04d}',
        formField(documentsForm, 'meeting_number_format'),
        'numbering-meeting-format',
      ),
    ],
  },
]

const itemFormatExample = sharedItemFormatField.example
const itemNumberFormatExample = itemNumberFormatField.example
const partNumberFormatExample = partNumberFormatField.example

// The internal example the external pattern is checked against, to warn when
// PDM patterns overlap internal numbering.
const madeInternalExample = computed(() =>
  sharedSchema.value ? itemFormatExample.value : itemNumberFormatExample.value,
)
const boughtInternalExample = computed(() =>
  sharedSchema.value ? itemFormatExample.value : partNumberFormatExample.value,
)

function overlaps(example: string | null, pattern: string): boolean {
  return !!example && !!pattern && matchesNumberPattern(example, pattern)
}

const madeExternalOverlap = computed(() =>
  overlaps(madeInternalExample.value, madeItemsForm.pdm_part_number_pattern),
)
const boughtExternalOverlap = computed(() =>
  overlaps(boughtInternalExample.value, ordersForm.pdm_part_number_pattern),
)

const { saving, onSave } = useSettingsSave(() =>
  Promise.all([
    store.saveOrders({ ...ordersForm }),
    store.saveMadeItems({
      item_number_format: madeItemsForm.item_number_format,
      lot_number_format: lotsForm.lot_number_format,
      ...documentsForm,
      part_number_auto: madeItemsForm.part_number_auto,
      part_number_editable: madeItemsForm.part_number_editable,
      web_creation_allowed: madeItemsForm.web_creation_allowed,
      pdm_part_number_pattern: madeItemsForm.pdm_part_number_pattern,
      revision_start: madeItemsForm.revision_start,
      revision_separator: madeItemsForm.revision_separator,
      revision_skip_ambiguous_letters: madeItemsForm.revision_skip_ambiguous_letters,
      revision_only_newest_editable: madeItemsForm.revision_only_newest_editable,
      revision_predecessor_status_web: madeItemsForm.revision_predecessor_status_web,
      revision_predecessor_status_pdm: madeItemsForm.revision_predecessor_status_pdm,
      // pdm_update_in_place survives untouched, see mergeRevisionFieldPolicy.
      revision_field_policy: mergeRevisionFieldPolicy(
        revisionPolicyFields.value,
        store.settings?.made_items?.revision_field_policy ?? [],
        webRequiresRevision,
        'web_requires_revision',
      ),
    }),
    store.saveProduction({
      production_order_number_format: productionForm.production_order_number_format,
    }),
    // The PUT is partial and sends only the pattern fields the General tab
    // does not own.
    store.saveGeneral({
      product_number_pattern: patternsForm.product_number_pattern,
      project_number_pattern: patternsForm.project_number_pattern,
    }),
  ]),
)
</script>

<template>
  <AdminSettingsTabShell>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.save')"
            icon="mdi mdi-content-save"
            text
            severity="contrast"
            :loading="saving"
            :disabled="!canWrite"
            @click="onSave"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="hint">{{ t('adminSettings.numbering.formatPlaceholdersHint') }}</p>

      <p class="section-label">{{ t('adminSettings.numbering.internalSection') }}</p>
      <div v-for="field in internalFormatFields" :key="field.labelKey" class="field-row">
        <label :for="`${uid}-value-${field.labelKey}`">
          {{ t(`adminSettings.numbering.${field.labelKey}`) }}
          <small class="hint"><code>{{ field.hint }}</code></small>
        </label>
        <div class="field-input-row">
          <InputText v-model="field.model.value" :id="`${uid}-value-${field.labelKey}`" :disabled="!canWrite" :data-testid="field.testId" />
          <span v-if="field.example.value" class="field-example">
            {{ t('adminSettings.numbering.example') }}: {{ field.example.value }}
          </span>
        </div>
      </div>
      <SettingsToggleRow
        v-for="toggle in generalToggles"
        :key="toggle.key"
        v-model="toggle.model.value"
        :label="t(`adminSettings.numbering.${toggle.key}`)"
        :hint="t(`adminSettings.numbering.${toggle.key}Hint`)"
        :disabled="!canWrite"
      />

      <Divider />

      <p class="section-label">{{ t('adminSettings.numbering.externalSection') }}</p>
      <p class="hint">{{ t('adminSettings.numbering.externalPatternHint') }}</p>
      <template v-if="sharePattern">
        <div class="field-row">
          <label for="pattern-external-shared">
            {{ t('adminSettings.numbering.externalPatternShared') }}
          </label>
          <NumberPatternInput
            v-model="sharedExternalPattern"
            input-id="pattern-external-shared"
            :disabled="!canWrite"
          />
          <Message v-if="madeExternalOverlap || boughtExternalOverlap" severity="warn" :closable="false">
            {{
              t('adminSettings.numbering.externalOverlapWarning', {
                example: madeExternalOverlap ? madeInternalExample : boughtInternalExample,
              })
            }}
          </Message>
        </div>
      </template>
      <template v-else>
        <div class="field-row">
          <label for="pattern-external-made">
            {{ t('adminSettings.numbering.externalPatternMade') }}
          </label>
          <NumberPatternInput
            v-model="madeItemsForm.pdm_part_number_pattern"
            input-id="pattern-external-made"
            :disabled="!canWrite"
          />
          <Message v-if="madeExternalOverlap" severity="warn" :closable="false">
            {{ t('adminSettings.numbering.externalOverlapWarning', { example: madeInternalExample }) }}
          </Message>
        </div>
        <div class="field-row">
          <label for="pattern-external-bought">
            {{ t('adminSettings.numbering.externalPatternBought') }}
          </label>
          <NumberPatternInput
            v-model="ordersForm.pdm_part_number_pattern"
            input-id="pattern-external-bought"
            :disabled="!canWrite"
          />
          <Message v-if="boughtExternalOverlap" severity="warn" :closable="false">
            {{ t('adminSettings.numbering.externalOverlapWarning', { example: boughtInternalExample }) }}
          </Message>
        </div>
      </template>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-share-pattern`">{{ t('adminSettings.numbering.sharePattern') }}</label>
        <ToggleSwitch v-model="sharePattern" :input-id="`${uid}-share-pattern`" :disabled="!canWrite" />
        <small class="hint">{{ t('adminSettings.numbering.sharePatternHint') }}</small>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.numbering.revisionsSection') }}</p>
      <div class="field-row field-row--toggle">
        <label :id="`${uid}-revision-start-label`" :for="`${uid}-revision-start`">{{ t('adminSettings.numbering.revisionStart') }}</label>
        <Select
          v-model="madeItemsForm.revision_start"
          :input-id="`${uid}-revision-start`"
          :aria-labelledby="`${uid}-revision-start-label`"
          :options="[...REVISION_START_OPTIONS]"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.numbering.revisionStartHint') }}</small>
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-skip-ambiguous`">{{ t('adminSettings.numbering.revisionSkipAmbiguousLetters') }}</label>
        <ToggleSwitch v-model="madeItemsForm.revision_skip_ambiguous_letters" :input-id="`${uid}-skip-ambiguous`" :disabled="!canWrite" />
        <small class="hint">{{ t('adminSettings.numbering.revisionSkipAmbiguousLettersHint') }}</small>
      </div>
      <div class="field-row">
        <label :for="`${uid}-revision-separator`">{{ t('adminSettings.numbering.revisionSeparator') }}</label>
        <div class="field-input-row">
          <InputText
            v-model="madeItemsForm.revision_separator"
            :id="`${uid}-revision-separator`"
            :maxlength="10"
            :disabled="!canWrite"
            style="max-width: 8rem"
          />
          <span class="field-example">
            {{ t('adminSettings.numbering.example') }}: PN-1{{ madeItemsForm.revision_separator
            }}{{ madeItemsForm.revision_start }}
          </span>
        </div>
        <small class="hint">{{ t('adminSettings.numbering.revisionSeparatorHint') }}</small>
      </div>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-newest-editable`">{{ t('adminSettings.numbering.revisionOnlyNewestEditable') }}</label>
        <ToggleSwitch v-model="madeItemsForm.revision_only_newest_editable" :input-id="`${uid}-newest-editable`" :disabled="!canWrite" />
        <small class="hint">{{ t('adminSettings.numbering.revisionOnlyNewestEditableHint') }}</small>
      </div>
      <div class="field-row field-row--toggle">
        <label :id="`${uid}-revision-predecessor-status-web-label`" :for="`${uid}-revision-predecessor-status-web`">
          {{ t('adminSettings.numbering.revisionPredecessorStatusWeb') }}
        </label>
        <Select
          v-model="madeItemsForm.revision_predecessor_status_web"
          :input-id="`${uid}-revision-predecessor-status-web`"
          :aria-labelledby="`${uid}-revision-predecessor-status-web-label`"
          :options="revisionPredecessorWebOptions"
          option-label="label"
          option-value="value"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.numbering.revisionPredecessorStatusWebHint') }}</small>
      </div>
      <div class="field-row field-row--toggle">
        <label :id="`${uid}-revision-predecessor-status-pdm-label`" :for="`${uid}-revision-predecessor-status-pdm`">
          {{ t('adminSettings.numbering.revisionPredecessorStatusPdm') }}
        </label>
        <Select
          v-model="madeItemsForm.revision_predecessor_status_pdm"
          :input-id="`${uid}-revision-predecessor-status-pdm`"
          :aria-labelledby="`${uid}-revision-predecessor-status-pdm-label`"
          :options="revisionPredecessorPdmOptions"
          option-label="label"
          option-value="value"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.numbering.revisionPredecessorStatusPdmHint') }}</small>
      </div>

      <p class="subsection-label">{{ t('adminSettings.numbering.revisionFieldsLabel') }}</p>
      <p class="hint">{{ t('adminSettings.numbering.revisionFieldsHint') }}</p>
      <div v-for="row in revisionPolicyFields" :key="row.field" class="field-row field-row--toggle">
        <label :for="`${uid}-field-${row.field}`">{{ t(`adminSettings.itemFields.fields.${row.field}`) }}</label>
        <Checkbox v-model="webRequiresRevision[row.field]" :input-id="`${uid}-field-${row.field}`" binary :disabled="!canWrite" />
      </div>

      <Divider />

      <template v-for="section in formatSections" :key="section.labelKey">
        <p class="section-label">{{ t(`adminSettings.numbering.${section.labelKey}`) }}</p>
        <p v-if="section.hintKey" class="hint">
          {{ t(`adminSettings.numbering.${section.hintKey}`) }}
        </p>
        <div v-for="field in section.fields" :key="field.labelKey" class="field-row">
          <label :for="`${uid}-value-2-${section.labelKey}-${field.labelKey}`">
            {{ t(`adminSettings.numbering.${field.labelKey}`) }}
            <small class="hint"><code>{{ field.hint }}</code></small>
          </label>
          <div class="field-input-row">
            <InputText
              v-model="field.model.value"
              :id="`${uid}-value-2-${section.labelKey}-${field.labelKey}`"
              :disabled="!canWrite"
              :data-testid="field.testId"
            />
            <span v-if="field.example.value" class="field-example">
              {{ t('adminSettings.numbering.example') }}: {{ field.example.value }}
            </span>
          </div>
        </div>

        <Divider />
      </template>

      <p class="section-label">{{ t('adminSettings.numbering.projectsProductsSection') }}</p>
      <p class="hint">{{ t('adminSettings.numbering.patternHint') }}</p>

      <div class="field-row">
        <label for="pattern-project">
          {{ t('adminSettings.numbering.projectNumberPattern') }}
          <small class="hint"><code>P-\d{4}</code></small>
        </label>
        <NumberPatternInput
          v-model="patternsForm.project_number_pattern"
          input-id="pattern-project"
          :disabled="!canWrite"
        />
      </div>

      <div class="field-row">
        <label for="pattern-product">
          {{ t('adminSettings.numbering.productNumberPattern') }}
          <small class="hint"><code>PRD-\d{4}</code></small>
        </label>
        <NumberPatternInput
          v-model="patternsForm.product_number_pattern"
          input-id="pattern-product"
          :disabled="!canWrite"
        />
      </div>
    </div>
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
// Introduces a list within the Revisions section, lighter than .section-label.
.subsection-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--p-text-color);
  margin-top: var(--space-1);
}

.field-input-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.field-example {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  white-space: nowrap;
}
</style>
