<script setup lang="ts">
import { extractApiError } from '@/core/utils/errors'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { computed, reactive, ref, toRef, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useArticleGroupsStore } from '@/features/article-groups'
import { CustomerSelect, useCustomerById } from '@/features/customers'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import MadeItemFilesSection from './MadeItemFilesSection.vue'
import MadeItemPicturesSection from './MadeItemPicturesSection.vue'
import MadeItemProcessEditor from './MadeItemProcessEditor.vue'
import MadeItemProcessGrouping from './MadeItemProcessGrouping.vue'
import MadeItemProcessStagedEditor from './MadeItemProcessStagedEditor.vue'
import MadeItemProcessStagedGrouping from './MadeItemProcessStagedGrouping.vue'
import MaterialSourceSelect from './MaterialSourceSelect.vue'

import type {
  MadeItemCreateRequest,
  MadeItemCreateRevisionRequest,
  MadeItemProcessCreateRequest,
  RevisionPredecessorStatus,
} from '../types/madeItemsRequest'
import type {
  MadeItemProcessResponse,
  MadeItemResponse,
  MadeItemRevisionsResponse,
} from '../types/madeItemsResponse'
import type { MaterialSource } from '../types/materialSource'
import { dateToParam, todayStart } from '@/core/utils/dates'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const props = defineProps<{
  copyFrom?: MadeItemResponse | null
  /**
   * "New revision" mode: part number and revision are fixed, every other
   * field is prefilled from this item, and submit posts to the revisions
   * endpoint. copyFrom wins if both are set.
   */
  revisionOf?: MadeItemResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: [item: MadeItemResponse]
}>()

const { t } = useI18n()

const madeItemsStore = useMadeItemsStore()
const articleGroupsStore = useArticleGroupsStore()
const hostStore = useHostStore()

// Archived article groups stay selectable, sorted last.
const { sortedOptions: articleGroupOptions, isArchived: isArticleGroupArchived } =
  useArchivableOptions(computed(() => articleGroupsStore.items))
const selectedArticleGroups = computed(() =>
  articleGroupsStore.items.filter((g) => form.article_group_ids.includes(g.id)),
)

const createdItem = ref<MadeItemResponse | null>(null)
const filesSection = ref<InstanceType<typeof MadeItemFilesSection> | null>(null)
const picturesSection = ref<InstanceType<typeof MadeItemPicturesSection> | null>(null)
// Remounts the files section per session, dropping unsaved staged files.
const filesSectionKey = ref(0)

interface MadeItemCreateFormState {
  revision: string
  revision_date: Date | null
  revision_note: string
  article_name: string
  article_group_ids: number[]
  part_number: string
  material: string
  mass: number | null
  base_size: string
  note: string
  weblink: string
  materialSource: MaterialSource
  customer_id: number | null
  customer_part_number: string
  customer_revision: string
  processes: MadeItemProcessCreateRequest[]
}

function createEmptyForm(): MadeItemCreateFormState {
  return {
    revision: '',
    revision_date: todayStart(),
    revision_note: '',
    article_name: '',
    article_group_ids: [],
    part_number: '',
    material: '',
    mass: null,
    base_size: '',
    note: '',
    weblink: '',
    materialSource: { bought_item_id: null, source_item_id: null, made_item_id: null },
    customer_id: null,
    customer_part_number: '',
    customer_revision: '',
    processes: [],
  }
}

const form = reactive(createEmptyForm())

const { customer, selectCustomer } = useCustomerById(toRef(form, 'customer_id'))

const { submitting, errorMessage, run } = useSubmitAction()

// With auto numbering the backend generates the part number, so manual
// entry is only offered otherwise.
const partNumbers = computed(() => hostStore.madeItemPartNumbers)
const partNumberEntryDisabled = computed(() => partNumbers.value.auto)
const partNumberHint = computed(() => {
  // Fixed in revision mode; the numbering hint only applies to new numbers.
  if (props.revisionOf) return null
  if (partNumbers.value.auto) {
    return partNumbers.value.example
      ? t('madeItems.create.partNumber.autoWithExample', { example: partNumbers.value.example })
      : t('madeItems.create.partNumber.auto')
  }
  return null
})

// Callers set the revision themselves.
function copyItemToForm(item: MadeItemResponse): void {
  form.article_name = item.article_name
  form.part_number = item.part_number ?? ''
  form.material = item.material ?? ''
  form.mass = item.mass
  form.base_size = item.base_size ?? ''
  form.note = item.note ?? ''
  form.weblink = item.weblink ?? ''
  form.article_group_ids = (item.article_groups ?? []).map((g) => g.id)
  // Shared with the plain Copy action.
  form.materialSource = {
    bought_item_id: item.bought_item_id,
    source_item_id: item.source_item_id,
    made_item_id: null,
  }
  form.customer_id = item.customer_id
  form.customer_part_number = item.customer_part_number ?? ''
  form.customer_revision = item.customer_revision ?? ''
  form.processes = (item.processes ?? []).map((p) => ({
    role: p.role,
    fabrication_method_id: p.fabrication_method_id,
    inspection_method_id: p.inspection_method_id,
    note: p.note,
    estimated_setup_minutes: p.estimated_setup_minutes,
    estimated_minutes_per_piece: p.estimated_minutes_per_piece,
    group_index: p.group_index,
  }))
}

function onCreatedProcessesUpdated(processes: MadeItemProcessResponse[]): void {
  if (createdItem.value) createdItem.value.processes = processes
}

const grouping = useTemplateRef<InstanceType<typeof MadeItemProcessGrouping>>('grouping')
const closing = ref(false)

// ── Revision mode (revisionOf) ───────────────────────────────────────────
// The revisions lookup drives the next revision value, whether submit is
// allowed and the predecessor status options.

const revisionsResponse = ref<MadeItemRevisionsResponse | null>(null)
const revisionsLoading = ref(false)

const PREDECESSOR_STATUS_OPTIONS: RevisionPredecessorStatus[] = ['replaced', 'inactive', 'active']
const predecessorStatus = ref<RevisionPredecessorStatus>('replaced')

// 'ask' is resolved by the form; the payload carries a concrete status.
const predecessorStatusIsAsk = computed(
  () => hostStore.madeItemPartNumbers.revision.predecessor_status_web === 'ask',
)

const effectivePredecessorStatus = computed<RevisionPredecessorStatus>(() => {
  const configured = hostStore.madeItemPartNumbers.revision.predecessor_status_web
  return configured === 'ask' ? predecessorStatus.value : configured
})

async function loadRevisionsFor(item: MadeItemResponse): Promise<void> {
  revisionsResponse.value = null
  revisionsLoading.value = true
  try {
    const result = await madeItemsStore.getRevisions(item.id)
    // The dialog may have closed or switched items meanwhile.
    if (!visible.value || props.revisionOf?.id !== item.id) return
    revisionsResponse.value = result
    form.revision = result.next_revision ?? ''
  } catch (e) {
    if (!visible.value || props.revisionOf?.id !== item.id) return
    errorMessage.value = extractApiError(e) ?? t('madeItems.create.errors.unknown')
  } finally {
    if (visible.value && props.revisionOf?.id === item.id) revisionsLoading.value = false
  }
}

const cannotCreateReasonMessage = computed(() => {
  const reason = revisionsResponse.value?.reason
  if (reason === 'cad') return t('madeItems.create.revision.reasons.cad')
  if (reason === 'no_write') return t('madeItems.create.revision.reasons.no_write')
  return t('madeItems.create.revision.cannotCreate')
})

// Blocked until a usable next revision is resolved.
const canSubmitRevision = computed(() => {
  if (!props.revisionOf) return true
  if (revisionsLoading.value || !revisionsResponse.value) return false
  if (revisionsResponse.value.next_revision_error) return false
  return revisionsResponse.value.can_create
})

const revisionFieldHint = computed(() => {
  if (props.revisionOf) {
    return revisionsLoading.value
      ? t('madeItems.create.revision.loading')
      : t('madeItems.create.revision.nextHint')
  }
  return t('madeItems.create.revision.startHint')
})

watch(visible, (isVisible) => {
  if (!isVisible) {
    return
  }

  Object.assign(form, createEmptyForm())
  form.revision = hostStore.madeItemPartNumbers.revision.start
  errorMessage.value = null
  createdItem.value = null
  filesSectionKey.value += 1
  revisionsResponse.value = null
  predecessorStatus.value = 'replaced'

  if (props.copyFrom) {
    copyItemToForm(props.copyFrom)
    form.article_name = `${props.copyFrom.article_name} ${t('madeItems.create.copySuffix')}`
  } else if (props.revisionOf) {
    copyItemToForm(props.revisionOf)
    void loadRevisionsFor(props.revisionOf)
  }

  if (articleGroupsStore.items.length === 0) {
    void articleGroupsStore.refresh()
  }
})

function isFormValid(): boolean {
  return form.revision.trim().length > 0 && form.article_name.trim().length > 0
}

// A customer item names the customer's part number, and customer data
// never stands without a customer; the server enforces the same rule.
function customerDataComplete(): boolean {
  const hasData = form.customer_part_number.trim() !== '' || form.customer_revision.trim() !== ''
  if (form.customer_id === null) return !hasData
  return form.customer_part_number.trim() !== ''
}

function buildCreatePayload(): MadeItemCreateRequest {
  return {
    revision: form.revision.trim(),
    revision_date: dateToParam(form.revision_date),
    revision_note: form.revision_note.trim() || null,
    status: 'active',
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
    customer_id: form.customer_id,
    customer_part_number: form.customer_part_number.trim() || null,
    customer_revision: form.customer_revision.trim() || null,
    processes: form.processes,
  }
}

// The server fills in revision, part number and data source.
function buildRevisionPayload(): MadeItemCreateRevisionRequest {
  return {
    predecessor_status: effectivePredecessorStatus.value,
    item: {
      revision_date: dateToParam(form.revision_date),
      revision_note: form.revision_note.trim() || null,
      article_name: form.article_name.trim(),
      article_group_ids: form.article_group_ids,
      material: form.material.trim() || null,
      mass: form.mass,
      base_size: form.base_size.trim() || null,
      note: form.note.trim() || null,
      weblink: form.weblink.trim() || null,
      bought_item_id: form.materialSource.bought_item_id,
      source_item_id: form.materialSource.source_item_id,
      customer_id: form.customer_id,
      customer_part_number: form.customer_part_number.trim() || null,
      customer_revision: form.customer_revision.trim() || null,
      processes: form.processes,
    },
  }
}

async function onSubmit(): Promise<void> {
  if (!isFormValid()) {
    errorMessage.value = t('madeItems.create.errors.required')

    return
  }

  if (!customerDataComplete()) {
    errorMessage.value = t('madeItems.create.errors.customerDataIncomplete')
    return
  }

  if (props.revisionOf && !canSubmitRevision.value) {
    return
  }

  await run(async () => {
    const created = props.revisionOf
      ? await madeItemsStore.createRevision(props.revisionOf.id, buildRevisionPayload())
      : await madeItemsStore.create(buildCreatePayload())

    // Explicit rather than watcher-driven, so a failed upload is visible.
    await picturesSection.value?.flushPendingUpload(created.id)
    await filesSection.value?.flushPendingUploads(created.id)

    emit('created', created)
    createdItem.value = created
  }, t('madeItems.create.errors.unknown'))
}

function onCancel(): void {
  visible.value = false
}

async function onDone(): Promise<void> {
  closing.value = true
  try {
    // Grouping is the only thing that stays local, so Close flushes it.
    if (grouping.value?.isDirty) await grouping.value.save()
  } finally {
    closing.value = false
  }
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="revisionOf ? t('madeItems.create.revisionOf.title') : t('madeItems.create.title')"
    :style="{ width: 'var(--dialog-width-full)', maxWidth: '1200px' }"
  >
    <div class="dialog-body">
      <form class="create-form" @submit.prevent="onSubmit">
        <Message
          v-if="revisionOf && revisionsResponse?.next_revision_error"
          severity="warn"
          :closable="false"
        >
          {{ revisionsResponse.next_revision_error }}
        </Message>
        <Message
          v-else-if="revisionOf && revisionsResponse && !revisionsResponse.can_create"
          severity="warn"
          :closable="false"
        >
          {{ cannotCreateReasonMessage }}
        </Message>

        <div class="form-grid">
          <div class="field">
            <label for="mi-part-number">{{ t('madeItems.create.fields.partNumber') }}</label>
            <InputText
              id="mi-part-number"
              v-model="form.part_number"
              fluid
              :disabled="!!revisionOf || partNumberEntryDisabled"
            />
            <small v-if="partNumberHint" class="field-hint">{{ partNumberHint }}</small>
          </div>

          <div class="field field-span-2">
            <label for="mi-article-name">{{ t('madeItems.create.fields.articleName') }} *</label>
            <InputText id="mi-article-name" v-model="form.article_name" fluid />
          </div>

          <div class="field">
            <label for="mi-revision">{{ t('madeItems.create.fields.revision') }}</label>
            <InputText id="mi-revision" v-model="form.revision" fluid disabled />
            <small class="field-hint">{{ revisionFieldHint }}</small>
          </div>

          <div class="field">
            <label for="mi-revision-date">{{ t('madeItems.create.fields.revisionDate') }}</label>
            <DatePicker id="mi-revision-date" v-model="form.revision_date" show-icon fluid />
          </div>

          <div class="field">
            <label for="mi-revision-note">{{ t('madeItems.create.fields.revisionNote') }}</label>
            <InputText id="mi-revision-note" v-model="form.revision_note" fluid />
          </div>

          <div class="field">
            <label for="mi-material">{{ t('madeItems.create.fields.material') }}</label>
            <InputText id="mi-material" v-model="form.material" fluid />
          </div>

          <div class="field">
            <label for="mi-base-size">{{ t('madeItems.create.fields.baseSize') }}</label>
            <InputText id="mi-base-size" v-model="form.base_size" fluid />
          </div>

          <div class="field">
            <label for="mi-mass">{{ t('madeItems.create.fields.mass') }}</label>
            <InputNumber id="mi-mass" v-model="form.mass" :min="0" fluid />
          </div>

          <div class="field">
            <label id="mi-customer-label" for="mi-customer">{{ t('madeItems.create.fields.customer') }}</label>
            <CustomerSelect
              :model-value="customer"
              input-id="mi-customer"
              aria-labelledby="mi-customer-label"
              @update:model-value="selectCustomer"
            />
          </div>

          <div class="field">
            <label for="mi-customer-part-number">
              {{ t('madeItems.create.fields.customerPartNumber') }}{{ form.customer_id !== null ? ' *' : '' }}
            </label>
            <InputText id="mi-customer-part-number" v-model="form.customer_part_number" fluid />
          </div>

          <div class="field">
            <label for="mi-customer-revision">{{ t('madeItems.create.fields.customerRevision') }}</label>
            <InputText id="mi-customer-revision" v-model="form.customer_revision" fluid />
          </div>

          <div class="field field-wide">
            <label for="mi-source-item">{{ t('madeItems.create.fields.sourceItem') }}</label>
            <MaterialSourceSelect id="mi-source-item" v-model="form.materialSource" />
          </div>

          <div class="field field-wide">
            <label id="mi-article-groups-label" for="mi-article-groups">{{ t('madeItems.create.fields.articleGroups') }}</label>
            <MultiSelect
              id="mi-article-groups"
              aria-labelledby="mi-article-groups-label"
              v-model="form.article_group_ids"
              :options="articleGroupOptions"
              :option-label="labelName"
              option-value="id"
              :loading="articleGroupsStore.loading"
              :placeholder="t('madeItems.create.fields.articleGroupsPlaceholder')"
              display="chip"
              filter
              fluid
            >
              <template #option="{ option }">
                <span>{{ localizeLabel(option.name) }}</span>
                <ArchivedOptionTag v-if="option.archived" />
              </template>
            </MultiSelect>
            <ArchivedSelectionWarning v-if="isArticleGroupArchived(selectedArticleGroups)" />
          </div>

          <div class="field field-wide">
            <label for="mi-note">{{ t('madeItems.create.fields.note') }}</label>
            <Textarea id="mi-note" v-model="form.note" rows="3" auto-resize fluid />
          </div>
        </div>

        <!-- What happens to the superseded revision: a Select when the setting is
             "ask", otherwise a note of the fixed outcome. -->
        <div v-if="revisionOf" class="field field-wide revision-predecessor">
          <label id="mi-predecessor-status-label" for="mi-predecessor-status">
            {{ t('madeItems.create.revision.predecessorStatus.label') }}
          </label>
          <Select
            v-if="predecessorStatusIsAsk"
            id="mi-predecessor-status"
            aria-labelledby="mi-predecessor-status-label"
            v-model="predecessorStatus"
            :options="PREDECESSOR_STATUS_OPTIONS"
            :option-label="(s) => t(`madeItems.create.revision.predecessorStatus.options.${s}`)"
            fluid
          />
          <Message v-else severity="info" :closable="false">
            {{
              t('madeItems.create.revision.predecessorStatus.fixedNote', {
                status: t(
                  `madeItems.create.revision.predecessorStatus.options.${effectivePredecessorStatus}`,
                ),
              })
            }}
          </Message>
          <small class="field-hint">{{
            t(`madeItems.create.revision.predecessorStatus.sideEffects.${effectivePredecessorStatus}`)
          }}</small>
        </div>

        <Message v-if="errorMessage" severity="error" :closable="false">
          {{ errorMessage }}
        </Message>
      </form>

      <template v-if="!createdItem">
        <Divider />
        <MadeItemProcessStagedEditor v-model="form.processes" />
        <MadeItemProcessStagedGrouping v-model="form.processes" />
      </template>

      <template v-if="hostStore.storageEnabled">
        <Divider />
        <MadeItemPicturesSection
          ref="picturesSection"
          :key="`pictures-${filesSectionKey}`"
          :item-id="createdItem?.id ?? null"
        />
        <MadeItemFilesSection
          ref="filesSection"
          :key="filesSectionKey"
          :item-id="createdItem?.id ?? null"
        />
      </template>

      <template v-if="createdItem">
        <Divider />
        <MadeItemProcessEditor :item="createdItem" @updated="onCreatedProcessesUpdated" />
        <MadeItemProcessGrouping
          ref="grouping"
          :item-id="createdItem.id"
          :processes="createdItem.processes ?? []"
        />
      </template>
    </div>

    <template #footer>
      <Button
        v-if="!createdItem"
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="onCancel"
      />
      <Button
        v-if="!createdItem"
        :label="t('common.save')"
        :loading="submitting"
        :disabled="!!revisionOf && !canSubmitRevision"
        @click="onSubmit"
      />
      <Button v-if="createdItem" :label="t('common.close')" :loading="closing" @click="onDone" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.create-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding-top: var(--space-1);
}

.form-grid {
  grid-template-columns: repeat(3, 1fr);
}

.field label {
  color: var(--p-text-color);
}

.field-wide {
  grid-column: 1 / -1;
}

.field-span-2 {
  grid-column: span 2;
}
</style>
