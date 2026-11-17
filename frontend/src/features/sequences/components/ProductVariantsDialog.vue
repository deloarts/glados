<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { getProductVariants, saveProductVariants } from '../api/productVariantsApi'
import type { ProductVariant } from '../types/sequence'

/**
 * The variants of a product, such as the part sizes the machine runs, as
 * one ordered list. Sequences give a value per variant where it differs.
 * A variant taken out of the list is archived, so sequences that name it
 * keep its name; adding the same name again brings it back.
 */
const props = defineProps<{
  productId: number
  canEdit: boolean
}>()

const visible = defineModel<boolean>('visible', { default: false })
const emit = defineEmits<{ saved: [variants: ProductVariant[]] }>()

const NAME_MAX_LENGTH = 100

interface Row {
  id: number | null
  name: string
  /** Stable for the list's keys while rows move. */
  rowKey: number
}

const { t } = useI18n()
const toast = useAppToast()

const rows = ref<Row[]>([])
const archived = ref<ProductVariant[]>([])
const loading = ref(false)
const saving = ref(false)
const submitted = ref(false)
let nextRowKey = 1

watch(visible, (open) => {
  if (open) void load()
})

async function load(): Promise<void> {
  loading.value = true
  submitted.value = false
  try {
    const all = await getProductVariants(props.productId, true)
    rows.value = all.filter((v) => !v.archived).map((v) => ({ id: v.id, name: v.name, rowKey: nextRowKey++ }))
    archived.value = all.filter((v) => v.archived)
  } catch (e) {
    toast.error(t('sequences.variants.title'), extractApiError(e) ?? t('sequences.errors.unknown'))
  } finally {
    loading.value = false
  }
}

function add(): void {
  rows.value.push({ id: null, name: '', rowKey: nextRowKey++ })
}

function move(index: number, by: -1 | 1): void {
  const target = index + by
  if (target < 0 || target >= rows.value.length) return
  const next = [...rows.value]
  const [row] = next.splice(index, 1)
  if (row) next.splice(target, 0, row)
  rows.value = next
}

function remove(index: number): void {
  rows.value.splice(index, 1)
}

const duplicates = computed(() => {
  const seen = new Map<string, number>()
  for (const row of rows.value) {
    const key = row.name.trim().toLocaleLowerCase()
    if (key) seen.set(key, (seen.get(key) ?? 0) + 1)
  }
  return new Set([...seen].filter(([, count]) => count > 1).map(([key]) => key))
})

function rowError(row: Row): string | null {
  if (!submitted.value) return null
  if (row.name.trim() === '') return t('sequences.variants.nameRequired')
  if (duplicates.value.has(row.name.trim().toLocaleLowerCase())) return t('sequences.variants.duplicate')
  return null
}

// A new row with the name of an archived variant brings that one back, so
// the sequences that name it keep resolving it.
function idFor(row: Row): number | null {
  if (row.id !== null) return row.id
  const name = row.name.trim().toLocaleLowerCase()
  return archived.value.find((v) => v.name.toLocaleLowerCase() === name)?.id ?? null
}

async function save(): Promise<void> {
  submitted.value = true
  if (rows.value.some((row) => rowError(row) !== null)) return
  saving.value = true
  try {
    const saved = await saveProductVariants(
      props.productId,
      rows.value.map((row) => ({ id: idFor(row), name: row.name.trim() })),
    )
    emit('saved', saved)
    toast.success(t('sequences.variants.title'), t('sequences.variants.saved'))
    visible.value = false
  } catch (e) {
    toast.error(t('sequences.variants.title'), extractApiError(e) ?? t('sequences.errors.unknown'))
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('sequences.variants.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
    :breakpoints="{ '640px': '95vw' }"
  >
    <p class="intro">{{ t('sequences.variants.intro') }}</p>
    <Message v-if="!canEdit" severity="secondary" class="rights" data-testid="product-variants-no-rights">
      {{ t('sequences.variants.noRights') }}
    </Message>
    <div v-if="!loading" class="variant-rows" data-testid="product-variants-rows">
      <div v-for="(row, index) in rows" :key="row.rowKey" class="variant-row">
        <div class="variant-name">
          <InputText
            v-model="row.name"
            :maxlength="NAME_MAX_LENGTH"
            :readonly="!canEdit"
            :invalid="rowError(row) !== null"
            :aria-label="t('sequences.variants.name')"
            fluid
            data-testid="product-variant-name"
          />
          <small v-if="rowError(row)" class="error">{{ rowError(row) }}</small>
        </div>
        <Button
          v-tooltip.bottom="t('sequences.variants.moveUp')"
          :aria-label="t('sequences.variants.moveUp')"
          icon="mdi mdi-arrow-up"
          severity="secondary"
          text
          :disabled="!canEdit || index === 0"
          @click="move(index, -1)"
        />
        <Button
          v-tooltip.bottom="t('sequences.variants.moveDown')"
          :aria-label="t('sequences.variants.moveDown')"
          icon="mdi mdi-arrow-down"
          severity="secondary"
          text
          :disabled="!canEdit || index === rows.length - 1"
          @click="move(index, 1)"
        />
        <Button
          v-tooltip.bottom="t('sequences.variants.remove')"
          :aria-label="t('sequences.variants.remove')"
          icon="mdi mdi-delete-outline"
          severity="secondary"
          text
          :disabled="!canEdit"
          data-testid="product-variant-remove"
          @click="remove(index)"
        />
      </div>
      <p v-if="rows.length === 0" class="empty">{{ t('sequences.variants.empty') }}</p>
      <Button
        :label="t('sequences.variants.add')"
        icon="mdi mdi-plus"
        severity="secondary"
        text
        class="add"
        :disabled="!canEdit"
        data-testid="product-variant-add"
        @click="add"
      />
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="t('common.save')"
        icon="mdi mdi-content-save-outline"
        :disabled="!canEdit"
        :loading="saving"
        data-testid="product-variants-save"
        @click="save"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.rights {
  margin-bottom: var(--space-3);
}

.intro {
  margin: 0 0 var(--space-3);
  color: var(--p-text-muted-color);
}

.variant-rows {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.variant-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1);
}

.variant-name {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.add {
  align-self: flex-start;
}

.empty {
  margin: 0;
  color: var(--p-text-muted-color);
}

.error {
  color: var(--p-red-500);
}
</style>
