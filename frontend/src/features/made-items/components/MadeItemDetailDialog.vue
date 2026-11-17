<script setup lang="ts">
import { computed, inject, reactive, ref, toRef, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, routerKey } from 'vue-router'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { articleGroupLabel, useArticleGroupsStore } from '@/features/article-groups'
import { CustomerSelect, useCustomerById } from '@/features/customers'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { getMadeItems } from '../api/getMadeItems'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import MaterialSourceSelect from './MaterialSourceSelect.vue'
import { isPdmLocked } from '@/shared/utils/pdmOwnedFields'
import MadeItemDetailFields from './MadeItemDetailFields.vue'
import MadeItemFilesSection from './MadeItemFilesSection.vue'
import MadeItemPicturesSection from './MadeItemPicturesSection.vue'
import MadeItemProcessEditor from './MadeItemProcessEditor.vue'
import MadeItemProcessGrouping from './MadeItemProcessGrouping.vue'
import MadeItemCreateForm from './MadeItemCreateForm.vue'

import type { MadeItemUpdateRequest } from '../types/madeItemsRequest'
import type {
  MadeItemCatalogueStatus,
  MadeItemProcessResponse,
  MadeItemResponse,
  MadeItemRevisionsResponse,
} from '../types/madeItemsResponse'
import type { MaterialSource } from '../types/materialSource'
import { catalogueStatusTagSeverity } from '@/shared/utils/catalogueStatus'
import { useSuccessorItem } from '@/shared/composables/useSuccessorItem'
import { useCadClaimGuard } from '@/shared/composables/useCadClaimGuard'
import CadClaimDialog from '@/shared/components/items/CadClaimDialog.vue'

const props = withDefaults(
  defineProps<{
    item: MadeItemResponse | null
    editOnOpen?: boolean
  }>(),
  { editOnOpen: false },
)

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Injected with a default, since the dialog also mounts without a router;
// the open-in-page link then simply does not render.
const router = inject(routerKey, null)

const madeItemsStore = useMadeItemsStore()
const articleGroupsStore = useArticleGroupsStore()

// Archived article groups stay selectable, sorted last.
const { sortedOptions: articleGroupOptions, isArchived: isArticleGroupArchived } =
  useArchivableOptions(computed(() => articleGroupsStore.items))
const selectedArticleGroups = computed(() =>
  articleGroupsStore.items.filter((g) => form.article_group_ids.includes(g.id)),
)
const hostStore = useHostStore()

const STATUS_OPTIONS: MadeItemCatalogueStatus[] = ['active', 'inactive', 'replaced']

const displayItem = ref<MadeItemResponse | null>(props.item)
const editing = ref(false)
const cadClaim = useCadClaimGuard()

// ── Revisions ──────────────────────────────────────────────────────────
// Backs the header's revision Select and the newest-revision edit gate.
// Refetched whenever the displayed item changes.

const revisionsResponse = ref<MadeItemRevisionsResponse | null>(null)

// Set only on a failed request, so canEdit can tell "pending" (not yet
// editable) from "failed" (permissive; the server still enforces the rule).
const revisionsFailed = ref(false)

async function loadRevisions(item: MadeItemResponse): Promise<void> {
  try {
    const result = await madeItemsStore.getRevisions(item.id)
    if (displayItem.value?.id !== item.id) return
    revisionsResponse.value = result
    revisionsFailed.value = false
  } catch {
    if (displayItem.value?.id !== item.id) return
    revisionsResponse.value = null
    revisionsFailed.value = true
  }
}

watch(
  () => props.item,
  (item) => {
    displayItem.value = item
  },
)

// editOnOpen waits for the revision lookup, so an old revision never opens
// an editable form that turns read-only a moment later.
watch(visible, (isVisible) => {
  if (!isVisible) {
    editing.value = false
    cadClaim.reset()
    return
  }
  displayItem.value = props.item
  revisionsResponse.value = null
  revisionsFailed.value = false
  const item = props.item
  if (!item) {
    if (props.editOnOpen) void onEdit()
    return
  }
  const loaded = loadRevisions(item)
  if (props.editOnOpen) {
    void loaded.then(() => {
      // The dialog may have closed or switched items meanwhile.
      if (displayItem.value?.id === item.id) void onEdit()
    })
  }
})

const currentRevisionSummary = computed(() => {
  const item = displayItem.value
  if (!item || !revisionsResponse.value) return null
  return revisionsResponse.value.items.find((r) => r.id === item.id) ?? null
})

// With the policy on, only the newest revision is editable. Gates both
// entering edit mode and Save. Permissive when the policy is off, the
// lookup failed (the server still enforces the rule) or the item is the
// newest; not while the lookup is pending.
const canEdit = computed(() => {
  if (!hostStore.madeItemPartNumbers.revision.only_newest_editable) return true
  if (revisionsFailed.value) return true
  return currentRevisionSummary.value?.is_newest === true
})

const editDisabledHint = computed(() =>
  canEdit.value ? undefined : t('madeItems.edit.notNewestHint'),
)

// Only claimed once the lookup succeeded.
const isNotNewest = computed(() => {
  if (!hostStore.madeItemPartNumbers.revision.only_newest_editable) return false
  return currentRevisionSummary.value !== null && currentRevisionSummary.value.is_newest === false
})

const newestRevisionLabel = computed(
  () => revisionsResponse.value?.items.find((r) => r.is_newest)?.revision ?? '',
)

// The web field policy applies to WEB items only.
const fieldPolicyMap = computed(() => {
  const map = new Map<string, boolean>()
  for (const entry of hostStore.madeItemPartNumbers.revision.field_policy) {
    map.set(entry.field, entry.web_requires_revision)
  }
  return map
})

function isFieldLocked(field: string): boolean {
  if (displayItem.value?.data_source !== 'WEB') return false
  return fieldPolicyMap.value.get(field) === true
}

// The server computes pdm_locked_fields from the rule the write path
// enforces (docs/FIELD_OWNERSHIP.md). source_item_id is dual-owned and never
// locked.
function isPdmLockedField(field: string): boolean {
  return isPdmLocked(displayItem.value, field)
}

// Locks the whole control only when both fields are locked;
// MaterialSourceSelect handles a single locked field itself.
const materialSourceLocked = computed(
  () =>
    (isFieldLocked('bought_item_id') || isPdmLockedField('bought_item_id')) &&
    isFieldLocked('source_item_id'),
)
const materialSourceFieldLocks = computed(() => ({
  bought: isFieldLocked('bought_item_id') || isPdmLockedField('bought_item_id'),
  source: isFieldLocked('source_item_id'),
}))
const processesLocked = computed(() => isFieldLocked('processes') || isPdmLockedField('processes'))

const MAPPED_POLICY_FIELDS = [
  'article_name',
  'material',
  'mass',
  'base_size',
  'note',
  'weblink',
  'article_group_ids',
  'customer_id',
  'customer_part_number',
  'customer_revision',
] as const

const isCadItem = computed(() => displayItem.value?.data_source === 'CAD')

const anyFieldLocked = computed(
  () =>
    MAPPED_POLICY_FIELDS.some((field) => isFieldLocked(field)) ||
    materialSourceLocked.value ||
    processesLocked.value,
)

// ── Revision Select (header) ──────────────────────────────────────────────

async function onRevisionSelect(id: number): Promise<void> {
  if (!displayItem.value || id === displayItem.value.id) return

  editing.value = false
  const cached = madeItemsStore.getById(id)
  if (cached) {
    displayItem.value = cached
  } else {
    const result = await getMadeItems({ id, limit: 1 })
    const found = result.items[0]
    if (found) displayItem.value = found
  }
  if (displayItem.value) void loadRevisions(displayItem.value)
}

// ── New revision ──────────────────────────────────────────────────────────

const showRevisionForm = ref(false)
const revisionOfItem = ref<MadeItemResponse | null>(null)

// While editing, the new revision carries the unsaved values. Nothing is
// persisted by building this snapshot.
function buildRevisionSourceItem(): MadeItemResponse | null {
  const item = displayItem.value
  if (!item) return null
  if (!editing.value) return item

  return {
    ...item,
    article_name: form.article_name,
    material: form.material || null,
    mass: form.mass,
    base_size: form.base_size || null,
    note: form.note || null,
    weblink: form.weblink || null,
    bought_item_id: form.materialSource.bought_item_id,
    source_item_id: form.materialSource.source_item_id,
    customer_id: form.customer_id,
    customer_name: customer.value?.name ?? null,
    customer_part_number: form.customer_part_number.trim() || null,
    customer_revision: form.customer_revision.trim() || null,
    article_groups: articleGroupsStore.items.filter((group) =>
      form.article_group_ids.includes(group.id),
    ),
  }
}

function openRevisionForm(): void {
  revisionOfItem.value = buildRevisionSourceItem()
  showRevisionForm.value = true
}

async function onRevisionCreated(): Promise<void> {
  showRevisionForm.value = false
  editing.value = false

  const id = revisionOfItem.value?.id
  if (id === undefined) return

  // The dialog keeps its own copy outside the store, so it refetches the
  // predecessor's status and successor link.
  const result = await getMadeItems({ id, limit: 1 })
  const refreshed = result.items[0]
  if (refreshed) {
    displayItem.value = refreshed
    madeItemsStore.replaceItems([refreshed])
    void loadRevisions(refreshed)
  }
  madeItemsStore.triggerRefresh()
}

function onProcessesUpdated(processes: MadeItemProcessResponse[]): void {
  if (displayItem.value) displayItem.value.processes = processes
}

// Only the editable grouping instance is driven from here.
const grouping = useTemplateRef<InstanceType<typeof MadeItemProcessGrouping>>('grouping')

// The link replaces the close button, so following it closes the dialog
// first.
function closeAndNavigate(navigate: (event: MouseEvent) => void, event: MouseEvent): void {
  visible.value = false
  navigate(event)
}

interface EditFormState {
  article_name: string
  article_group_ids: number[]
  status: MadeItemCatalogueStatus
  part_number: string
  material: string
  mass: number | null
  base_size: string
  note: string
  weblink: string
  materialSource: MaterialSource
  successor_item_id: number | null
  customer_id: number | null
  customer_part_number: string
  customer_revision: string
}

const form = reactive<EditFormState>({
  article_name: '',
  article_group_ids: [],
  status: 'active',
  part_number: '',
  material: '',
  mass: null,
  base_size: '',
  note: '',
  weblink: '',
  materialSource: { bought_item_id: null, source_item_id: null, made_item_id: null },
  successor_item_id: null,
  customer_id: null,
  customer_part_number: '',
  customer_revision: '',
})

const { customer, selectCustomer } = useCustomerById(toRef(form, 'customer_id'))

const { submitting, errorMessage, run } = useSubmitAction()

const {
  successorItem,
  successorSuggestions,
  resolveSuccessorItem,
  searchSuccessorItems,
} = useSuccessorItem<MadeItemResponse>({
  getById: (id) => madeItemsStore.getById(id),
  list: (params) => getMadeItems(params),
})

function onSuccessorItemSelect(selected: MadeItemResponse | null): void {
  form.successor_item_id = selected?.id ?? null
}

// A live update can show the item claimed by PDM while the form is open.
watch(
  () => displayItem.value?.data_source,
  (source) => {
    const item = displayItem.value
    if (!editing.value || source !== 'CAD' || !item) return
    void cadClaim.confirmLive([item]).then((proceed) => {
      if (!proceed) onCancelEdit()
    })
  },
)


async function onEdit(): Promise<void> {
  const item = displayItem.value
  if (!item || !canEdit.value) return
  cadClaim.reset()
  if (item.data_source === 'CAD' && !(await cadClaim.confirmOpen([item]))) return
  // The dialog may have closed or switched items while it asked.
  if (!visible.value || displayItem.value?.id !== item.id) return

  form.article_name = item.article_name
  form.article_group_ids = (item.article_groups ?? []).map((group) => group.id)
  form.status = item.status
  form.part_number = item.part_number ?? ''
  form.material = item.material ?? ''
  form.mass = item.mass
  form.base_size = item.base_size ?? ''
  form.note = item.note ?? ''
  form.weblink = item.weblink ?? ''
  form.materialSource = {
    bought_item_id: item.bought_item_id,
    source_item_id: item.source_item_id,
    made_item_id: null,
  }
  form.successor_item_id = item.successor_item_id
  form.customer_id = item.customer_id
  form.customer_part_number = item.customer_part_number ?? ''
  form.customer_revision = item.customer_revision ?? ''
  resolveSuccessorItem(item.successor_item_id)

  errorMessage.value = null
  if (articleGroupsStore.items.length === 0) void articleGroupsStore.refresh()
  editing.value = true
}

function onCancelEdit(): void {
  editing.value = false
  errorMessage.value = null
  grouping.value?.reset()
}

function isFormValid(): boolean {
  return form.article_name.trim().length > 0
}

// A customer item names the customer's part number, and customer data
// never stands without a customer; the server enforces the same rule.
function customerDataComplete(): boolean {
  const hasData = form.customer_part_number.trim() !== '' || form.customer_revision.trim() !== ''
  if (form.customer_id === null) return !hasData
  return form.customer_part_number.trim() !== ''
}

// Blocks save when a locked material field's staged value differs from the
// item, so the UI avoids a round trip for the server's 409.
function materialSourceViolatesPolicy(item: MadeItemResponse): boolean {
  if (isFieldLocked('bought_item_id') && form.materialSource.bought_item_id !== item.bought_item_id) {
    return true
  }
  if (isFieldLocked('source_item_id') && form.materialSource.source_item_id !== item.source_item_id) {
    return true
  }
  return false
}

function buildPayload(item: MadeItemResponse): MadeItemUpdateRequest {
  return {
    expected_edit_version: item.edit_version,
    status: form.status,
    article_name: form.article_name.trim(),
    article_group_ids: form.article_group_ids,
    part_number: form.part_number.trim() || null,
    material: form.material.trim() || null,
    mass: form.mass,
    base_size: form.base_size.trim() || null,
    note: form.note.trim() || null,
    weblink: form.weblink.trim() || null,
    bought_item_id: form.materialSource.bought_item_id,
    source_item_id: form.materialSource.source_item_id,
    successor_item_id: form.successor_item_id,
    customer_id: form.customer_id,
    customer_part_number: form.customer_part_number.trim() || null,
    customer_revision: form.customer_revision.trim() || null,
  }
}

async function onSave(): Promise<void> {
  const item = displayItem.value
  // Guards other submit paths, like Enter on the form.
  if (!item || !canEdit.value) return

  if (!isFormValid()) {
    errorMessage.value = t('madeItems.edit.errors.required')
    return
  }

  if (!customerDataComplete()) {
    errorMessage.value = t('madeItems.edit.errors.customerDataIncomplete')
    return
  }

  if (materialSourceViolatesPolicy(item)) {
    errorMessage.value = t('madeItems.edit.fieldPolicy.hint')
    return
  }

  if (!(await cadClaim.confirmSave([item], getMadeItems))) return

  await run(async () => {
    // Regroup first, so the field update response already reflects it.
    if (grouping.value?.isDirty) await grouping.value.save()
    const updated = await madeItemsStore.update(item.id, buildPayload(item))
    madeItemsStore.replaceItems([updated])
    displayItem.value = updated
    editing.value = false
  }, t('madeItems.edit.errors.unknown'))
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <!-- Own header row so the revision Select sits next to the title. -->
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{
          displayItem ? `#${displayItem.id} - ${displayItem.article_name}` : ''
        }}</span>
        <template v-if="displayItem">
          <Select
            v-if="(revisionsResponse?.items.length ?? 0) > 1"
            :aria-label="t('madeItems.catalogue.columns.revision')"
            class="revision-select"
            :model-value="displayItem.id"
            :options="revisionsResponse?.items ?? []"
            option-label="revision"
            option-value="id"
            @update:model-value="onRevisionSelect"
            @click.stop
          >
            <template #option="{ option }">
              <div class="revision-option">
                <span>{{ option.revision }}</span>
                <Tag
                  :value="t(`madeItems.catalogue.status.${option.status}`)"
                  :severity="catalogueStatusTagSeverity(option.status)"
                />
              </div>
            </template>
          </Select>
          <span v-else class="revision-plain">{{ displayItem.revision }}</span>
        </template>
      </div>
    </template>

    <!-- Replaces the native close button, since OpenVue has no slot for an
         extra header icon. RouterLink is imported explicitly so router-less
         mounts do not warn about an unresolved component. -->
    <template #closebutton="{ closeCallback }">
      <RouterLink
        v-if="router && displayItem"
        v-slot="{ navigate }"
        :to="`/catalogue/made-items/${displayItem.id}`"
        custom
      >
        <Button
          icon="mdi mdi-open-in-new"
          size="small"
          severity="secondary"
          text
          rounded
          v-tooltip.bottom.focus="t('madeItems.catalogue.page.open')"
          :aria-label="t('madeItems.catalogue.page.open')"
          @click="closeAndNavigate(navigate, $event)"
        />
      </RouterLink>
      <Button
        icon="mdi mdi-close"
        size="small"
        severity="secondary"
        text
        rounded
        v-tooltip.bottom.focus="t('common.close')"
        :aria-label="t('common.close')"
        @click="closeCallback"
      />
    </template>

    <div v-if="displayItem" class="detail-layout">
      <template v-if="!editing">
        <Message v-if="isNotNewest" severity="info" :closable="false" class="not-newest-notice">
          {{ t('madeItems.edit.notNewestNotice', { revision: newestRevisionLabel }) }}
        </Message>

        <MadeItemDetailFields :item="displayItem" :show-meta="false" />

        <Divider />

        <MadeItemProcessEditor :item="displayItem" readonly @updated="onProcessesUpdated" />

        <MadeItemProcessGrouping
          :item-id="displayItem.id"
          :processes="displayItem.processes ?? []"
          readonly
        />

        <template v-if="hostStore.storageEnabled">
          <MadeItemPicturesSection :item-id="displayItem.id" readonly />
          <MadeItemFilesSection :item-id="displayItem.id" readonly />
        </template>
      </template>

      <form v-else class="edit-form" @submit.prevent="onSave">
        <Message v-if="errorMessage" severity="error" :closable="false">
          {{ errorMessage }}
        </Message>

        <!-- One shared hint and button for the fields the revision policy locks on
             a WEB item. -->
        <Message v-if="anyFieldLocked" severity="info" :closable="false" class="revision-policy-hint">
          <div class="revision-policy-hint-content">
            <span>{{ t('madeItems.edit.fieldPolicy.hint') }}</span>
            <Button
              :label="t('madeItems.catalogue.contextMenu.newRevision')"
              icon="mdi mdi-source-branch-plus"
              size="small"
              text
              @click="openRevisionForm"
            />
          </div>
        </Message>
        <Message v-else-if="isCadItem" severity="info" :closable="false">
          {{ t('madeItems.catalogue.contextMenu.newRevisionManagedByPdm') }}
        </Message>

        <div class="edit-grid">
          <div class="field">
            <label id="mid-status-label" for="mid-status">{{ t('madeItems.edit.fields.status') }}</label>
            <Select
              id="mid-status"
              aria-labelledby="mid-status-label"
              v-model="form.status"
              :options="STATUS_OPTIONS"
              :option-label="(s) => t(`madeItems.catalogue.status.${s}`)"
              fluid
              :disabled="isPdmLockedField('status')"
              v-tooltip.top="isPdmLockedField('status') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div v-if="form.status === 'replaced'" class="field">
            <label for="mid-successor-item">
              {{ t('madeItems.edit.fields.successorItemId') }}
            </label>
            <AutoComplete
              id="mid-successor-item"
              v-model="successorItem"
              :suggestions="successorSuggestions"
              :option-label="(i) => `#${i.id}: ${i.article_name}`"
              :placeholder="t('madeItems.edit.fields.successorItemPlaceholder')"
              force-selection
              fluid
              @complete="searchSuccessorItems"
              @update:model-value="onSuccessorItemSelect"
            />
          </div>
          <!-- A successor can only be assigned once the file is replaced in PDM, so a
               hint replaces the picker on a PDM-owned row. -->
          <div v-else-if="isPdmLockedField('status')" class="field">
            <span class="field-caption">{{ t('madeItems.edit.fields.successorItemId') }}</span>
            <Message severity="info" :closable="false">
              {{ t('madeItems.edit.pdmManagedStatusHint') }}
            </Message>
          </div>

          <div class="field">
            <label for="mid-article-name">{{ t('madeItems.edit.fields.articleName') }} *</label>
            <InputText
              id="mid-article-name"
              v-model="form.article_name"
              fluid
              :disabled="isFieldLocked('article_name') || isPdmLockedField('article_name')"
              v-tooltip.top="isPdmLockedField('article_name') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label for="mid-part-number">{{ t('madeItems.edit.fields.partNumber') }}</label>
            <InputText
              id="mid-part-number"
              v-model="form.part_number"
              fluid
              :disabled="isPdmLockedField('part_number')"
              v-tooltip.top="isPdmLockedField('part_number') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label for="mid-material">{{ t('madeItems.edit.fields.material') }}</label>
            <InputText
              id="mid-material"
              v-model="form.material"
              fluid
              :disabled="isFieldLocked('material') || isPdmLockedField('material')"
              v-tooltip.top="isPdmLockedField('material') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label for="mid-mass">{{ t('madeItems.edit.fields.mass') }}</label>
            <InputNumber
              id="mid-mass"
              v-model="form.mass"
              :min="0"
              fluid
              :disabled="isFieldLocked('mass') || isPdmLockedField('mass')"
              v-tooltip.top="isPdmLockedField('mass') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label id="mid-article-groups-label" for="mid-article-groups">{{ t('madeItems.edit.fields.articleGroups') }}</label>
            <MultiSelect
              id="mid-article-groups"
              aria-labelledby="mid-article-groups-label"
              v-model="form.article_group_ids"
              :options="articleGroupOptions"
              :option-label="articleGroupLabel"
              option-value="id"
              :loading="articleGroupsStore.loading"
              :placeholder="t('madeItems.edit.fields.articleGroupsPlaceholder')"
              display="chip"
              filter
              fluid
              :disabled="isFieldLocked('article_group_ids') || isPdmLockedField('article_group_ids')"
              v-tooltip.top="isPdmLockedField('article_group_ids') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            >
              <template #option="{ option }">
                <span>{{ articleGroupLabel(option) }}</span>
                <ArchivedOptionTag v-if="option.archived" />
              </template>
            </MultiSelect>
            <ArchivedSelectionWarning v-if="isArticleGroupArchived(selectedArticleGroups)" />
          </div>

          <div class="field">
            <label for="mid-base-size">{{ t('madeItems.edit.fields.baseSize') }}</label>
            <InputText
              id="mid-base-size"
              v-model="form.base_size"
              fluid
              :disabled="isFieldLocked('base_size') || isPdmLockedField('base_size')"
              v-tooltip.top="isPdmLockedField('base_size') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field field-wide">
            <label for="mid-source-item">{{ t('madeItems.edit.fields.sourceItem') }}</label>
            <div
              :class="{ 'field-locked': materialSourceLocked }"
              v-tooltip.top="
                materialSourceFieldLocks.bought && !materialSourceFieldLocks.source
                  ? t('madeItems.edit.pdmOwnedTooltip')
                  : undefined
              "
            >
              <MaterialSourceSelect
                id="mid-source-item"
                v-model="form.materialSource"
                inline
                :locked-fields="materialSourceFieldLocks"
              />
            </div>
          </div>

          <div class="field">
            <label id="mid-customer-label" for="mid-customer">{{ t('madeItems.edit.fields.customer') }}</label>
            <CustomerSelect
              :model-value="customer"
              input-id="mid-customer"
              aria-labelledby="mid-customer-label"
              :disabled="isFieldLocked('customer_id') || isPdmLockedField('customer_id')"
              v-tooltip.top="isPdmLockedField('customer_id') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
              @update:model-value="selectCustomer"
            />
          </div>

          <div class="field">
            <label for="mid-customer-part-number">
              {{ t('madeItems.edit.fields.customerPartNumber') }}{{ form.customer_id !== null ? ' *' : '' }}
            </label>
            <InputText
              id="mid-customer-part-number"
              v-model="form.customer_part_number"
              fluid
              :disabled="isFieldLocked('customer_part_number') || isPdmLockedField('customer_part_number')"
              v-tooltip.top="isPdmLockedField('customer_part_number') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label for="mid-customer-revision">{{ t('madeItems.edit.fields.customerRevision') }}</label>
            <InputText
              id="mid-customer-revision"
              v-model="form.customer_revision"
              fluid
              :disabled="isFieldLocked('customer_revision') || isPdmLockedField('customer_revision')"
              v-tooltip.top="isPdmLockedField('customer_revision') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field field-wide">
            <label for="mid-weblink">{{ t('madeItems.edit.fields.weblink') }}</label>
            <InputText
              id="mid-weblink"
              v-model="form.weblink"
              type="url"
              fluid
              :disabled="isFieldLocked('weblink') || isPdmLockedField('weblink')"
              v-tooltip.top="isPdmLockedField('weblink') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field field-wide">
            <label for="mid-note">{{ t('madeItems.edit.fields.note') }}</label>
            <Textarea
              id="mid-note"
              v-model="form.note"
              rows="3"
              auto-resize
              fluid
              :disabled="isFieldLocked('note') || isPdmLockedField('note')"
              v-tooltip.top="isPdmLockedField('note') ? t('madeItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

        </div>

        <MadeItemProcessEditor
          :item="displayItem"
          :readonly="processesLocked"
          @updated="onProcessesUpdated"
        />

        <MadeItemProcessGrouping
          ref="grouping"
          :item-id="displayItem.id"
          :processes="displayItem.processes ?? []"
          :readonly="processesLocked"
        />

        <template v-if="hostStore.storageEnabled">
          <MadeItemPicturesSection :item-id="displayItem.id" />
          <MadeItemFilesSection :item-id="displayItem.id" />
        </template>
      </form>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <div v-if="displayItem" class="detail-footer-meta">
          <div class="meta-item">
            <UserAvatarPreview :user="displayItem.creator" />
          </div>
          <div class="meta-item">
            <span class="field-label">{{ t('madeItems.catalogue.columns.created') }}</span>
            <span class="field-value">{{ displayItem.created }}</span>
          </div>
          <div v-if="displayItem.changed" class="meta-item">
            <span class="field-label">{{ t('madeItems.catalogue.columns.changed') }}</span>
            <span class="field-value">{{ displayItem.changed }}</span>
          </div>
        </div>
        <div class="footer-actions">
          <template v-if="!editing">
            <Button
              :label="t('common.close')"
              severity="secondary"
              outlined
              @click="visible = false"
            />
            <Button
              :label="t('madeItems.catalogue.controls.edit')"
              icon="mdi mdi-pencil"
              :disabled="!canEdit"
              v-tooltip.top="editDisabledHint"
              @click="onEdit"
            />
          </template>
          <template v-else>
            <Button
              :label="t('common.cancel')"
              severity="secondary"
              outlined
              :disabled="submitting"
              @click="onCancelEdit"
            />
            <Button
              :label="t('common.save')"
              :loading="submitting"
              :disabled="!canEdit"
              @click="onSave"
            />
          </template>
        </div>
      </div>
    </template>
  </Dialog>

  <MadeItemCreateForm
    v-model:visible="showRevisionForm"
    :revision-of="revisionOfItem"
    @created="onRevisionCreated"
  />

  <CadClaimDialog :guard="cadClaim" />
</template>

<style scoped lang="scss">
.detail-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.revision-select {
  width: auto;
  min-width: 6rem;
}

.revision-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.revision-plain {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.revision-policy-hint-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.field-locked {
  opacity: 0.6;
  pointer-events: none;
}

.field-wide {
  grid-column: 1 / -1;
}

.field-value {
  font-size: var(--font-size-sm);
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: var(--space-4);
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.detail-footer-meta {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.edit-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3) var(--space-5);
}

.edit-grid .field label,
.edit-grid .field .field-caption {
  font-size: var(--font-size-sm);
  color: var(--p-text-color);
}

.edit-form :deep(.item-files) {
  padding-top: var(--space-4);
  border-top: 1px solid var(--p-content-border-color);
}
</style>
