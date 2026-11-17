<script setup lang="ts">
import { computed, inject, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, routerKey } from 'vue-router'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { useArticleGroupsStore } from '@/features/article-groups'
import { ProductFamilySelect } from '@/features/product-families'
import { useSuppliersStore } from '@/features/suppliers'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'
import { getBoughtItems } from '../api/getBoughtItems'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { isPdmLocked } from '@/shared/utils/pdmOwnedFields'
import BoughtItemDetailFields from './BoughtItemDetailFields.vue'
import BoughtItemFilesSection from './BoughtItemFilesSection.vue'
import BoughtItemPicturesSection from './BoughtItemPicturesSection.vue'

import type { BoughtItemUpdateRequest } from '../types/boughtItemsRequest'
import type { BoughtItemCatalogueStatus, BoughtItemResponse } from '../types/boughtItemsResponse'
import { useSuccessorItem } from '@/shared/composables/useSuccessorItem'
import { useCadClaimGuard } from '@/shared/composables/useCadClaimGuard'
import CadClaimDialog from '@/shared/components/items/CadClaimDialog.vue'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'

const props = withDefaults(
  defineProps<{
    item: BoughtItemResponse | null
    editOnOpen?: boolean
  }>(),
  { editOnOpen: false },
)

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Injected with a default, since the dialog also mounts without a router;
// the open-in-page link then simply does not render.
const router = inject(routerKey, null)

const boughtItemsStore = useBoughtItemsStore()
const suppliersStore = useSuppliersStore()
const articleGroupsStore = useArticleGroupsStore()
const hostStore = useHostStore()

// Archived suppliers and article groups stay selectable, sorted last.
const { sortedOptions: supplierOptions, isArchived: isSupplierArchived } = useArchivableOptions(
  computed(() => suppliersStore.items),
)
const selectedSupplier = computed(
  () => suppliersStore.getById(form.manufacturer_id) ?? null,
)
const { sortedOptions: articleGroupOptions, isArchived: isArticleGroupArchived } =
  useArchivableOptions(computed(() => articleGroupsStore.items))
const selectedArticleGroups = computed(() =>
  articleGroupsStore.items.filter((g) => form.article_group_ids.includes(g.id)),
)

const STATUS_OPTIONS: BoughtItemCatalogueStatus[] = ['active', 'inactive', 'replaced']

const displayItem = ref<BoughtItemResponse | null>(props.item)
const editing = ref(false)
const cadClaim = useCadClaimGuard()

watch(
  () => props.item,
  (item) => {
    displayItem.value = item
  },
)

watch(visible, (isVisible) => {
  if (!isVisible) {
    editing.value = false
    cadClaim.reset()
    return
  }
  displayItem.value = props.item
  if (props.editOnOpen) void onEdit()
})

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


// The link replaces the close button, so following it closes the dialog
// first.
function closeAndNavigate(navigate: (event: MouseEvent) => void, event: MouseEvent): void {
  visible.value = false
  navigate(event)
}

interface EditFormState {
  order_code_1: string
  order_code_2: string
  gtin: string
  ean: string
  tariff_number: string
  article_name: string
  article_group_ids: number[]
  status: BoughtItemCatalogueStatus
  part_number: string
  mass: number | null
  note: string
  weblink: string
  manufacturer_id: number | null
  product_family_id: number | null
  successor_item_id: number | null
}

const form = reactive<EditFormState>({
  order_code_1: '',
  order_code_2: '',
  gtin: '',
  ean: '',
  tariff_number: '',
  article_name: '',
  article_group_ids: [],
  status: 'active',
  part_number: '',
  mass: null,
  note: '',
  weblink: '',
  manufacturer_id: null,
  product_family_id: null,
  successor_item_id: null,
})

const { submitting, errorMessage, run } = useSubmitAction()

// The backend refuses part number changes unless the numbering settings
// allow editing.
const partNumberEditDisabled = computed(() => !hostStore.boughtItemPartNumbers.editable)

// The server computes pdm_locked_fields from the rule the write path
// enforces (docs/FIELD_OWNERSHIP.md). Bought items have no revision field
// policy, so this is the only field lock here.
function isPdmLockedField(field: string): boolean {
  return isPdmLocked(displayItem.value, field)
}

const {
  successorItem,
  successorSuggestions,
  resolveSuccessorItem,
  searchSuccessorItems,
} = useSuccessorItem<BoughtItemResponse>({
  getById: (id) => boughtItemsStore.getById(id),
  list: (params) => getBoughtItems(params),
})

function onSuccessorItemSelect(selected: BoughtItemResponse | null): void {
  form.successor_item_id = selected?.id ?? null
}

async function onEdit(): Promise<void> {
  const item = displayItem.value
  if (!item) return
  cadClaim.reset()
  if (item.data_source === 'CAD' && !(await cadClaim.confirmOpen([item]))) return
  // The dialog may have closed or switched items while it asked.
  if (!visible.value || displayItem.value?.id !== item.id) return

  form.order_code_1 = item.order_code_1
  form.order_code_2 = item.order_code_2 ?? ''
  form.gtin = item.gtin ?? ''
  form.ean = item.ean ?? ''
  form.tariff_number = item.tariff_number ?? ''
  form.article_name = item.article_name
  form.article_group_ids = (item.article_groups ?? []).map((group) => group.id)
  form.status = item.status
  form.part_number = item.part_number ?? ''
  form.mass = item.mass
  form.note = item.note ?? ''
  form.weblink = item.weblink ?? ''
  form.manufacturer_id = item.manufacturer_id
  form.product_family_id = item.product_family_id ?? null
  form.successor_item_id = item.successor_item_id
  resolveSuccessorItem(item.successor_item_id)

  errorMessage.value = null
  if (suppliersStore.items.length === 0) void suppliersStore.refresh()
  if (articleGroupsStore.items.length === 0) void articleGroupsStore.refresh()
  editing.value = true
}

function onCancelEdit(): void {
  editing.value = false
  errorMessage.value = null
}

function isFormValid(): boolean {
  return (
    form.order_code_1.trim().length > 0 &&
    form.article_name.trim().length > 0 &&
    !!form.manufacturer_id &&
    form.manufacturer_id > 0
  )
}

function buildPayload(item: BoughtItemResponse): BoughtItemUpdateRequest {
  return {
    expected_edit_version: item.edit_version,
    status: form.status,
    order_code_1: form.order_code_1.trim(),
    order_code_2: form.order_code_2.trim() || null,
    gtin: form.gtin.trim() || null,
    ean: form.ean.trim() || null,
    tariff_number: form.tariff_number.trim() || null,
    article_name: form.article_name.trim(),
    article_group_ids: form.article_group_ids,
    part_number: form.part_number.trim() || null,
    mass: form.mass,
    note: form.note.trim() || null,
    weblink: form.weblink.trim() || null,
    manufacturer_id: form.manufacturer_id as number,
    product_family_id: form.product_family_id,
    successor_item_id: form.successor_item_id,
  }
}

async function onSave(): Promise<void> {
  const item = displayItem.value
  if (!item) return

  if (!isFormValid()) {
    errorMessage.value = t('boughtItems.edit.errors.required')
    return
  }

  if (!(await cadClaim.confirmSave([item], getBoughtItems))) return

  await run(async () => {
    const updated = await boughtItemsStore.update(item.id, buildPayload(item))
    boughtItemsStore.replaceItems([updated])
    displayItem.value = updated
    editing.value = false
  }, t('boughtItems.edit.errors.unknown'))
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="displayItem ? `#${displayItem.id} - ${displayItem.article_name}` : ''"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <!-- Replaces the native close button, since OpenVue has no slot for an
         extra header icon. RouterLink is imported explicitly so router-less
         mounts do not warn about an unresolved component. -->
    <template #closebutton="{ closeCallback }">
      <RouterLink
        v-if="router && displayItem"
        v-slot="{ navigate }"
        :to="`/catalogue/bought-items/${displayItem.id}`"
        custom
      >
        <Button
          icon="mdi mdi-open-in-new"
          size="small"
          severity="secondary"
          text
          rounded
          v-tooltip.bottom.focus="t('boughtItems.catalogue.page.open')"
          :aria-label="t('boughtItems.catalogue.page.open')"
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
        <BoughtItemDetailFields :item="displayItem" :show-meta="false" />

        <template v-if="hostStore.storageEnabled">
          <BoughtItemPicturesSection :item-id="displayItem.id" readonly />
          <BoughtItemFilesSection :item-id="displayItem.id" readonly />
        </template>
      </template>

      <form v-else class="edit-form" @submit.prevent="onSave">
        <Message v-if="errorMessage" severity="error" :closable="false">
          {{ errorMessage }}
        </Message>

        <div class="edit-grid">
          <div class="field">
            <label id="bid-status-label" for="bid-status">{{ t('boughtItems.edit.fields.status') }}</label>
            <Select
              id="bid-status"
              aria-labelledby="bid-status-label"
              v-model="form.status"
              :options="STATUS_OPTIONS"
              :option-label="(s) => t(`boughtItems.catalogue.status.${s}`)"
              fluid
              :disabled="isPdmLockedField('status')"
              v-tooltip.top="isPdmLockedField('status') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label for="bid-part-number">{{ t('boughtItems.edit.fields.partNumber') }}</label>
            <InputText
              id="bid-part-number"
              v-model="form.part_number"
              fluid
              :disabled="partNumberEditDisabled || isPdmLockedField('part_number')"
              v-tooltip.top="isPdmLockedField('part_number') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div v-if="form.status === 'replaced'" class="field field-wide">
            <label for="bid-successor-item">
              {{ t('boughtItems.edit.fields.successorItemId') }}
            </label>
            <AutoComplete
              id="bid-successor-item"
              v-model="successorItem"
              :suggestions="successorSuggestions"
              :option-label="(i) => `#${i.id}: ${i.order_code_1} – ${i.article_name}`"
              :placeholder="t('boughtItems.edit.fields.successorItemPlaceholder')"
              force-selection
              fluid
              @complete="searchSuccessorItems"
              @update:model-value="onSuccessorItemSelect"
            />
          </div>
          <!-- A successor can only be assigned once the file is replaced in PDM, so a
               hint replaces the picker on a PDM-owned row. -->
          <div v-else-if="isPdmLockedField('status')" class="field field-wide">
            <span class="field-caption">{{ t('boughtItems.edit.fields.successorItemId') }}</span>
            <Message severity="info" :closable="false">
              {{ t('boughtItems.edit.pdmManagedStatusHint') }}
            </Message>
          </div>

          <div class="field">
            <label for="bid-article-name">{{ t('boughtItems.edit.fields.articleName') }} *</label>
            <InputText
              id="bid-article-name"
              v-model="form.article_name"
              fluid
              :disabled="isPdmLockedField('article_name')"
              v-tooltip.top="isPdmLockedField('article_name') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label id="bid-manufacturer-label" for="bid-manufacturer">{{ t('boughtItems.edit.fields.manufacturer') }} *</label>
            <Select
              id="bid-manufacturer"
              aria-labelledby="bid-manufacturer-label"
              v-model="form.manufacturer_id"
              :options="supplierOptions"
              option-label="name"
              option-value="id"
              :loading="suppliersStore.loading"
              :placeholder="t('boughtItems.edit.fields.manufacturerPlaceholder')"
              filter
              show-clear
              fluid
              :disabled="isPdmLockedField('manufacturer_id')"
              v-tooltip.top="isPdmLockedField('manufacturer_id') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            >
              <template #option="{ option }">
                <span>{{ option.name }}</span>
                <ArchivedOptionTag v-if="option.archived" />
              </template>
              <template #value="{ value }">
                <span v-if="value">{{ selectedSupplier?.name }}</span>
                <ArchivedOptionTag v-if="selectedSupplier?.archived" />
              </template>
            </Select>
            <ArchivedSelectionWarning v-if="isSupplierArchived(selectedSupplier)" />
          </div>

          <div class="field">
            <label for="bid-order-code-1">{{ t('boughtItems.edit.fields.orderCode1') }} *</label>
            <InputText
              id="bid-order-code-1"
              v-model="form.order_code_1"
              fluid
              :disabled="isPdmLockedField('order_code_1')"
              v-tooltip.top="isPdmLockedField('order_code_1') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label for="bid-order-code-2">{{ t('boughtItems.edit.fields.orderCode2') }}</label>
            <InputText
              id="bid-order-code-2"
              v-model="form.order_code_2"
              fluid
              :disabled="isPdmLockedField('order_code_2')"
              v-tooltip.top="isPdmLockedField('order_code_2') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label id="bid-article-groups-label" for="bid-article-groups">{{ t('boughtItems.edit.fields.articleGroups') }}</label>
            <MultiSelect
              id="bid-article-groups"
              aria-labelledby="bid-article-groups-label"
              v-model="form.article_group_ids"
              :options="articleGroupOptions"
              :option-label="labelName"
              option-value="id"
              :loading="articleGroupsStore.loading"
              :placeholder="t('boughtItems.edit.fields.articleGroupsPlaceholder')"
              display="chip"
              filter
              fluid
              :disabled="isPdmLockedField('article_group_ids')"
              v-tooltip.top="isPdmLockedField('article_group_ids') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            >
              <template #option="{ option }">
                <span>{{ localizeLabel(option.name) }}</span>
                <ArchivedOptionTag v-if="option.archived" />
              </template>
            </MultiSelect>
            <ArchivedSelectionWarning v-if="isArticleGroupArchived(selectedArticleGroups)" />
          </div>

          <div class="field">
            <label id="bid-product-family-label" for="bid-product-family">{{ t('boughtItems.edit.fields.productFamily') }}</label>
            <ProductFamilySelect v-model="form.product_family_id" input-id="bid-product-family" aria-labelledby="bid-product-family-label" />
          </div>

          <div class="field">
            <label for="bid-mass">{{ t('boughtItems.edit.fields.mass') }}</label>
            <InputNumber
              id="bid-mass"
              v-model="form.mass"
              :min="0"
              fluid
              :disabled="isPdmLockedField('mass')"
              v-tooltip.top="isPdmLockedField('mass') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field field-wide">
            <label for="bid-note">{{ t('boughtItems.edit.fields.note') }}</label>
            <Textarea
              id="bid-note"
              v-model="form.note"
              rows="3"
              auto-resize
              fluid
              :disabled="isPdmLockedField('note')"
              v-tooltip.top="isPdmLockedField('note') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label for="bid-weblink">{{ t('boughtItems.edit.fields.weblink') }}</label>
            <InputText
              id="bid-weblink"
              v-model="form.weblink"
              type="url"
              fluid
              :disabled="isPdmLockedField('weblink')"
              v-tooltip.top="isPdmLockedField('weblink') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label for="bid-gtin">{{ t('boughtItems.edit.fields.gtin') }}</label>
            <InputText
              id="bid-gtin"
              v-model="form.gtin"
              fluid
              :disabled="isPdmLockedField('gtin')"
              v-tooltip.top="isPdmLockedField('gtin') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label for="bid-ean">{{ t('boughtItems.edit.fields.ean') }}</label>
            <InputText
              id="bid-ean"
              v-model="form.ean"
              fluid
              :disabled="isPdmLockedField('ean')"
              v-tooltip.top="isPdmLockedField('ean') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

          <div class="field">
            <label for="bid-tariff-number">{{ t('boughtItems.edit.fields.tariffNumber') }}</label>
            <InputText
              id="bid-tariff-number"
              v-model="form.tariff_number"
              fluid
              :disabled="isPdmLockedField('tariff_number')"
              v-tooltip.top="isPdmLockedField('tariff_number') ? t('boughtItems.edit.pdmOwnedTooltip') : undefined"
            />
          </div>

        </div>

        <template v-if="hostStore.storageEnabled">
          <BoughtItemPicturesSection :item-id="displayItem.id" />
          <BoughtItemFilesSection :item-id="displayItem.id" />
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
            <span class="field-label">{{ t('boughtItems.catalogue.columns.created') }}</span>
            <span class="field-value">{{ displayItem.created }}</span>
          </div>
          <div v-if="displayItem.changed" class="meta-item">
            <span class="field-label">{{ t('boughtItems.catalogue.columns.changed') }}</span>
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
              :label="t('boughtItems.catalogue.controls.edit')"
              icon="mdi mdi-pencil"
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
            <Button :label="t('common.save')" :loading="submitting" @click="onSave" />
          </template>
        </div>
      </div>
    </template>
  </Dialog>

  <CadClaimDialog :guard="cadClaim" />
</template>

<style scoped lang="scss">
.detail-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
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
