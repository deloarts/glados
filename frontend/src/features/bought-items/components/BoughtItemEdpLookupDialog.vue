<script setup lang="ts">
// Lookup in Data Portal, on the bought-item detail page. It finds the item's
// portal part (the linked one, else by its order code), lets the user pick
// when the number is ambiguous, and compares the item with the part field
// by field. Fields where the portal differs and that the user may change are
// preselected; a field PDM owns on this item is only shown, since it is
// changed in the SolidWorks file. Applying takes the chosen values, links
// the item to the part and requests its picture for empty image slots.
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { HelpDrawer } from '@/shared/help'
import { extractApiError } from '@/core/utils/errors'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import EdpPartPicture from './EdpPartPicture.vue'
import { applyEdpLookup, lookupItemInEdp } from '../api/boughtItemsEdpApi'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'
import type { EdpItemLookup, EdpLookupField, EdpPartSummary } from '../types/boughtItemsEdpTypes'

const props = defineProps<{
  item: BoughtItemResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  applied: [item: BoughtItemResponse]
}>()

const { t } = useI18n()
const toast = useAppToast()

const loading = ref(false)
const explainVisible = ref(false)
const applying = ref(false)
const lookup = ref<EdpItemLookup | null>(null)
const chosen = ref<EdpLookupField[]>([])
const errorMessage = ref<string | null>(null)

const fields = computed(() => lookup.value?.fields ?? [])
const candidates = computed<EdpPartSummary[]>(() => lookup.value?.candidates ?? [])
const lockedDiffers = computed(() => fields.value.some((f) => f.differs && !f.applicable))

async function load(partId?: number): Promise<void> {
  if (!props.item) return
  loading.value = true
  errorMessage.value = null
  try {
    lookup.value = await lookupItemInEdp(props.item.id, partId)
    chosen.value = (lookup.value.fields ?? []).filter((f) => f.applicable).map((f) => f.field)
  } catch (error) {
    lookup.value = null
    errorMessage.value = extractApiError(error) ?? t('boughtItems.edpLookup.failed')
  } finally {
    loading.value = false
  }
}

watch(visible, (isVisible) => {
  if (isVisible) void load()
})

function candidateLabel(part: EdpPartSummary): string {
  return [part.manufacturer_code, part.order_number ?? part.part_number, part.designation]
    .filter((v) => !!v)
    .join(' · ')
}

function onPickCandidate(value: unknown): void {
  if (typeof value === 'number') void load(value)
}

async function onApply(onlyLink: boolean): Promise<void> {
  const part = lookup.value?.part
  if (!props.item || !part) return
  applying.value = true
  errorMessage.value = null
  try {
    const saved = await applyEdpLookup(props.item.id, part.part_id, onlyLink ? [] : chosen.value)
    toast.success(t('boughtItems.edpLookup.title'), t('boughtItems.edpLookup.applied'))
    emit('applied', saved)
    visible.value = false
  } catch (error) {
    errorMessage.value = extractApiError(error) ?? t('boughtItems.edpLookup.failed')
  } finally {
    applying.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('boughtItems.edpLookup.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('boughtItems.edpLookup.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('boughtItems.edpLookup.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div class="lookup-body">
      <ProgressBar v-if="loading" mode="indeterminate" style="height: 4px" />

      <div v-if="lookup?.part" class="part">
        <EdpPartPicture :part-id="lookup.part.part_id" size="4rem" />
        <div class="part-text">
          <strong>{{ lookup.part.designation }}</strong>
          <span>{{ lookup.part.manufacturer_name }} · {{ lookup.part.order_number }}</span>
          <a
            v-if="lookup.part.part_page_url"
            :href="lookup.part.part_page_url"
            target="_blank"
            rel="noopener noreferrer"
            >{{ lookup.part.part_number }}</a
          >
        </div>
      </div>

      <div v-else-if="candidates.length > 0" class="field">
        <label id="edp-lookup-candidate-label" for="edp-lookup-candidate">{{ t('boughtItems.edpLookup.pickCandidate') }}</label>
        <Select
          input-id="edp-lookup-candidate"
          aria-labelledby="edp-lookup-candidate-label"
          :options="candidates"
          :option-label="candidateLabel"
          option-value="part_id"
          fluid
          data-testid="edp-lookup-candidate"
          @update:model-value="onPickCandidate"
        />
      </div>

      <Message
        v-for="(line, index) in lookup?.errors ?? []"
        :key="index"
        severity="warn"
        :closable="false"
        >{{ line }}</Message
      >

      <DataTable v-if="fields.length > 0" :value="fields" data-key="field" size="small">
        <Column style="width: 3rem">
          <template #body="{ data }">
            <Checkbox
              v-model="chosen"
              :value="data.field"
              :disabled="!data.applicable"
              :aria-label="t(`boughtItems.edpLookup.fields.${data.field}`)"
            />
          </template>
        </Column>
        <Column :header="t('boughtItems.edpLookup.columns.field')">
          <template #body="{ data }">{{ t(`boughtItems.edpLookup.fields.${data.field}`) }}</template>
        </Column>
        <Column :header="t('boughtItems.edpLookup.columns.item')">
          <template #body="{ data }">{{ data.item_value ?? getEmptyPlaceholder() }}</template>
        </Column>
        <Column :header="t('boughtItems.edpLookup.columns.portal')">
          <template #body="{ data }">
            <span :class="{ differs: data.differs }">{{
              data.portal_value ?? getEmptyPlaceholder()
            }}</span>
          </template>
        </Column>
      </DataTable>

      <Message v-if="lockedDiffers" severity="info" :closable="false">
        {{ t('boughtItems.edpLookup.pdmOwned') }}
      </Message>
      <Message v-if="errorMessage" severity="error" :closable="false">{{ errorMessage }}</Message>
    </div>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="t('boughtItems.edpLookup.linkOnly')"
        severity="secondary"
        :disabled="!lookup?.part"
        :loading="applying"
        data-testid="edp-lookup-link"
        @click="onApply(true)"
      />
      <Button
        :label="t('boughtItems.edpLookup.apply', { count: chosen.length })"
        :disabled="!lookup?.part || chosen.length === 0"
        :loading="applying"
        data-testid="edp-lookup-apply"
        @click="onApply(false)"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="catalogue/eplan-data-portal" />
</template>

<style scoped lang="scss">
.dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.lookup-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.part {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.part-text {
  display: flex;
  flex-direction: column;
}

.differs {
  font-weight: 600;
}
</style>
