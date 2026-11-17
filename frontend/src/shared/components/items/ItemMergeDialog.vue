<script setup lang="ts" generic="TItem extends MergeableItem">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

/**
 * The item fields this dialog reads directly, everything else about `TItem`
 * is opaque to it.
 */
export interface MergeableItem {
  id: number
  article_name: string
}

/** Why the server refuses a target for the merge. */
export type MergeTargetRefusal = 'archived' | 'not_active'

/**
 * A candidate target as the server judges it for the merge of the dialog's
 * item: whether it may take the merge, and whether the merge makes it
 * active again.
 */
export interface ItemMergeTarget<TItem> {
  item: TItem
  refusal: MergeTargetRefusal | null
  reactivates: boolean
}

/**
 * The single store member this dialog calls, kept as its own interface so
 * any feature's catalogue store (or a plain object wrapping one) can be
 * passed through without this component importing a concrete store type
 * from a feature.
 */
export interface ItemMergeOperations<TItem> {
  merge: (sourceId: number, targetId: number) => Promise<TItem>
}

const props = defineProps<{
  item: TItem | null
  operations: ItemMergeOperations<TItem>
  /**
   * Dot-path prefix shared by every i18n key this dialog reads, e.g.
   * `boughtItems.catalogue.merge`. The suffixes (`title`, `warning`,
   * `sourceLabel`, and so on) are identical across item kinds.
   */
  i18nPrefix: string
  /**
   * Second line under the source item's name, e.g. the order code for a
   * bought item or the part number/revision label for a made item.
   */
  itemLabel: (item: TItem) => string
  /**
   * The server's merge targets of the source matching a search, each with
   * its verdict. The dialog decides nothing about a target itself.
   */
  fetchTargets: (sourceId: number, query: string) => Promise<ItemMergeTarget<TItem>[]>
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()

const targetItem = ref<TItem | null>(null)
const loading = ref(false)

const header = computed(() => {
  const title = t(`${props.i18nPrefix}.title`)
  return props.item ? `${title}, ${props.item.article_name}` : title
})

watch(visible, (open) => {
  if (!open) {
    targetItem.value = null
  }
})

// The verdicts of every target the searches returned, kept across searches
// so a picked target keeps its verdict while the user searches on.
const verdicts = ref(new Map<number, Omit<ItemMergeTarget<unknown>, 'item'>>())

watch(
  () => props.item?.id,
  () => {
    verdicts.value = new Map()
  },
)

// Hands the target select its options, remembering each one's verdict.
async function fetchOptions(query: string): Promise<TItem[]> {
  if (!props.item) return []
  const targets = await props.fetchTargets(props.item.id, query)
  const next = new Map(verdicts.value)
  for (const target of targets) {
    next.set(target.item.id, { refusal: target.refusal, reactivates: target.reactivates })
  }
  verdicts.value = next
  return targets.map((target) => target.item)
}

function refusalText(refusal: MergeTargetRefusal | null | undefined): string {
  if (refusal === 'archived') return t(`${props.i18nPrefix}.targetArchived`)
  if (refusal === 'not_active') return t(`${props.i18nPrefix}.targetNotActive`)
  return ''
}

// Why a target may not take the merge, null when it may; the select shows
// such a target disabled with this as its tooltip.
function disabledReason(item: TItem): string | null {
  return refusalText(verdicts.value.get(item.id)?.refusal) || null
}

const targetVerdict = computed(() =>
  targetItem.value ? verdicts.value.get(targetItem.value.id) : undefined,
)

const reactivatesTarget = computed(() => !!targetVerdict.value?.reactivates)

const targetRefusal = computed(() => refusalText(targetVerdict.value?.refusal))

function setTargetItem(item: TItem | null): void {
  targetItem.value = item
}

async function onMerge(): Promise<void> {
  if (!props.item || !targetItem.value) return

  loading.value = true
  try {
    await props.operations.merge(props.item.id, targetItem.value.id)
    appToast.success(props.item.article_name, t(`${props.i18nPrefix}.success`))
    visible.value = false
  } catch {
    appToast.error(t(`${props.i18nPrefix}.errors.unknown`))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="header"
    :style="{ width: 'var(--dialog-width-md)' }"
    :draggable="false"
  >
    <div class="merge-body">
      <Message severity="warn" :closable="false" class="merge-warning">
        {{ t(`${i18nPrefix}.warning`) }}
      </Message>

      <div v-if="item" class="source-info">
        <div class="info-label">{{ t(`${i18nPrefix}.sourceLabel`) }}</div>
        <div class="info-row">
          <span class="info-id">#{{ item.id }}</span>
          <span class="info-name">{{ item.article_name }}</span>
        </div>
        <div class="info-sub">{{ itemLabel(item) }}</div>
      </div>

      <div class="target-field">
        <label :id="`${uid}-target-label`" :for="`${uid}-target`" class="form-label">
          {{ t(`${i18nPrefix}.targetLabel`) }}
        </label>
        <slot
          name="target-select"
          :input-id="`${uid}-target`"
          :label-id="`${uid}-target-label`"
          :target-item="targetItem"
          :set-target-item="setTargetItem"
          :exclude-id="item?.id"
          :fetch-options="fetchOptions"
          :disabled-reason="disabledReason"
        />
        <Message
          v-if="targetRefusal"
          severity="error"
          size="small"
          variant="simple"
          data-testid="merge-target-refusal"
        >
          {{ targetRefusal }}
        </Message>
        <Message
          v-else-if="reactivatesTarget"
          severity="info"
          size="small"
          variant="simple"
          data-testid="merge-target-reactivated"
        >
          {{ t(`${i18nPrefix}.targetReactivated`) }}
        </Message>
      </div>
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="loading"
        @click="visible = false"
      />
      <span v-tooltip.top="targetRefusal">
        <Button
          :label="t(`${i18nPrefix}.confirm`)"
          icon="mdi mdi-source-merge"
          severity="danger"
          :disabled="!targetItem || targetRefusal !== ''"
          :loading="loading"
          @click="onMerge"
        />
      </span>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.merge-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.merge-warning {
  margin: 0;
}

.source-info {
  padding: var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius);
  background: var(--p-surface-50);
}

.info-label {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  margin-bottom: var(--space-1);
}

.info-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.info-id {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.info-name {
  font-weight: 600;
}

.info-sub {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  margin-top: var(--space-1);
}

.target-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.form-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}
</style>
