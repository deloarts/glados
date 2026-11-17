<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { BoughtItemSelect } from '@/features/bought-items'
import { SourceItemInlineCreateForm, SourceItemSelect, sourceItemsApi } from '@/features/source-items'
import MadeItemSelect from './MadeItemSelect.vue'

import type { BoughtItemResponse } from '@/features/bought-items'
import type { SourceItemResponse } from '@/features/source-items'
import type { MadeItemResponse } from '../types/madeItemsResponse'
import type { MaterialSource, MaterialSourceFieldLocks } from '../types/materialSource'

type Source = 'source' | 'create-source' | 'bought' | 'made'

const props = withDefaults(
  defineProps<{
    allowMade?: boolean
    allowCreate?: boolean
    inline?: boolean
    /** Per-field revision policy; nothing is locked by default. */
    lockedFields?: MaterialSourceFieldLocks
  }>(),
  {
    allowMade: false,
    allowCreate: false,
    inline: false,
    lockedFields: () => ({ bought: false, source: false }),
  },
)

const model = defineModel<MaterialSource>({
  default: () => ({ bought_item_id: null, source_item_id: null, made_item_id: null }),
})

const { t } = useI18n()

const sourceOptions = computed(() => {
  const options: { label: string; value: Source }[] = [
    { label: t('sourceItems.select.kind.source'), value: 'source' },
  ]
  if (props.allowCreate) {
    options.push({ label: t('sourceItems.select.kind.createSource'), value: 'create-source' })
  }
  options.push({ label: t('sourceItems.select.kind.bought'), value: 'bought' })
  if (props.allowMade) {
    options.push({ label: t('sourceItems.select.kind.made'), value: 'made' })
  }
  return options
})

// null when the model has no source, so the model watcher does not undo a
// tab pick before an item is chosen.
function sourceFromModel(value: MaterialSource): Source | null {
  if (value.source_item_id !== null) return 'source'
  if (value.bought_item_id !== null) return 'bought'
  if (value.made_item_id !== null) return 'made'
  return null
}

const source = ref<Source>(sourceFromModel(model.value) ?? 'source')

// ── Field-level lock ────────────────────────────────────────────────────
// Rule 1: a locked field's Select stays disabled whatever its value, since
// any change, even from null, needs a new revision.
const boughtSelectDisabled = computed(() => props.lockedFields.bought)
const sourceSelectDisabled = computed(() => props.lockedFields.source)

const boughtSelectTooltip = computed(() =>
  boughtSelectDisabled.value ? t('sourceItems.select.fieldLock.bought') : undefined,
)
const sourceSelectTooltip = computed(() =>
  sourceSelectDisabled.value ? t('sourceItems.select.fieldLock.source') : undefined,
)

// Rule 2: switching kind clears the other fields, so when the set field is
// locked every other kind option is disabled.
const protectedKind = computed<Source | null>(() => {
  if (boughtSelectDisabled.value && model.value.bought_item_id !== null) return 'bought'
  if (sourceSelectDisabled.value && model.value.source_item_id !== null) return 'source'
  return null
})

function isSourceOptionDisabled(option: { value: Source }): boolean {
  return protectedKind.value !== null && option.value !== protectedKind.value
}

const kindSwitchTooltip = computed<string | undefined>(() => {
  if (protectedKind.value === 'bought') return t('sourceItems.select.fieldLock.bought')
  if (protectedKind.value === 'source') return t('sourceItems.select.fieldLock.source')
  return undefined
})

const boughtItem = ref<BoughtItemResponse | null>(null)
const sourceItem = ref<SourceItemResponse | null>(null)
const madeItem = ref<MadeItemResponse | null>(null)

watch(
  model,
  async (value) => {
    const resolved = sourceFromModel(value)
    if (resolved !== null) source.value = resolved

    if (value.source_item_id !== null && value.source_item_id !== sourceItem.value?.id) {
      const result = await sourceItemsApi.list({ id: value.source_item_id, limit: 1 })
      sourceItem.value = result.items[0] ?? null
    } else if (value.source_item_id === null) {
      sourceItem.value = null
    }

    if (value.bought_item_id === null) boughtItem.value = null
    if (value.made_item_id === null) madeItem.value = null
  },
  { immediate: true },
)

function onSourceChange(next: Source): void {
  source.value = next
  boughtItem.value = null
  sourceItem.value = null
  madeItem.value = null
  model.value = { bought_item_id: null, source_item_id: null, made_item_id: null }
}

watch(boughtItem, (item) => {
  if (source.value === 'bought') {
    model.value = { bought_item_id: item?.id ?? null, source_item_id: null, made_item_id: null }
  }
})

watch(sourceItem, (item) => {
  if (source.value === 'source') {
    model.value = { bought_item_id: null, source_item_id: item?.id ?? null, made_item_id: null }
  }
})

watch(madeItem, (item) => {
  if (source.value === 'made') {
    model.value = { bought_item_id: null, source_item_id: null, made_item_id: item?.id ?? null }
  }
})

// ── Create Source Item mode ─────────────────────────────────────────────
// The parent dialog's Save calls resolve(), which passes the model through
// in the choose modes and creates the item first in 'create-source'.

const inlineCreateRef = ref<InstanceType<typeof SourceItemInlineCreateForm> | null>(null)
const resolving = ref(false)

const hasSelection = computed(() => {
  if (source.value === 'create-source') return true
  return (
    model.value.bought_item_id !== null ||
    model.value.source_item_id !== null ||
    model.value.made_item_id !== null
  )
})

async function resolve(): Promise<MaterialSource | null> {
  if (source.value !== 'create-source') return model.value
  if (!inlineCreateRef.value) return null

  resolving.value = true
  try {
    const created = await inlineCreateRef.value.submit()
    if (!created) return null

    const resolved: MaterialSource = {
      bought_item_id: null,
      source_item_id: created.id,
      made_item_id: null,
    }
    model.value = resolved
    return resolved
  } finally {
    resolving.value = false
  }
}

// The label for the parent's Save in create mode: reuse an identical item
// or create a new one. null in every other mode.
const submitLabel = computed<string | null>(() => {
  if (source.value !== 'create-source') return null
  return inlineCreateRef.value?.willReuseExisting
    ? t('sourceItems.select.createInline.applyLabel')
    : t('sourceItems.select.createInline.createAndApplyLabel')
})

defineExpose({ resolve, hasSelection, isBusy: resolving, submitLabel })
</script>

<template>
  <div class="material-source-select" :class="{ inline: props.inline }">
    <div class="source-switch-row">
      <SelectButton
        :model-value="source"
        :options="sourceOptions"
        option-label="label"
        option-value="value"
        :option-disabled="isSourceOptionDisabled"
        :allow-empty="false"
        @update:model-value="onSourceChange"
      >
        <!-- A disabled button gets no mouse events, so a native title carries the
             hint instead of v-tooltip. -->
        <template #option="{ option }">
          <span
            class="p-togglebutton-label"
            data-testid="material-source-option-label"
            :title="isSourceOptionDisabled(option) ? kindSwitchTooltip : undefined"
            >{{ option.label }}</span
          >
        </template>
      </SelectButton>
      <div v-if="source !== 'create-source'" class="source-picker">
        <SourceItemSelect
          v-if="source === 'source'"
          v-model="sourceItem"
          :aria-label="t('sourceItems.select.kind.source')"
          fluid
          :disabled="sourceSelectDisabled"
          v-tooltip.top="sourceSelectTooltip"
        />
        <BoughtItemSelect
          v-else-if="source === 'bought'"
          v-model="boughtItem"
          :aria-label="t('sourceItems.select.kind.bought')"
          fluid
          :disabled="boughtSelectDisabled"
          v-tooltip.top="boughtSelectTooltip"
        />
        <MadeItemSelect v-else v-model="madeItem" :aria-label="t('sourceItems.select.kind.made')" fluid />
      </div>
    </div>
    <SourceItemInlineCreateForm
      v-if="source === 'create-source'"
      ref="inlineCreateRef"
      class="inline-create-form"
    />
  </div>
</template>

<style scoped lang="scss">
.material-source-select {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.source-switch-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.material-source-select.inline .source-switch-row {
  flex-direction: row;
  align-items: center;
}

.material-source-select.inline .source-switch-row .source-picker {
  flex: 1;
  min-width: 0;
}

.inline-create-form {
  margin-top: var(--space-1);
}
</style>
