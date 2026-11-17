<script setup lang="ts">
// Edits the extra costs of one order and saves them as a whole list.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { HelpDrawer } from '@/shared/help'
import { useOrdersStore } from '../stores/ordersStore'
import { extraCostDraftError } from '@/shared/utils/extraCosts'
import ExtraCostsEditor from '@/shared/components/extra-costs/ExtraCostsEditor.vue'
import type { ExtraCostDraft } from '@/shared/utils/extraCosts'
import type { OrderResponse } from '../types/ordersResponse'

const emit = defineEmits<{ saved: [] }>()

const { t } = useI18n()
const ordersStore = useOrdersStore()

const visible = ref(false)
const order = ref<OrderResponse | null>(null)
const drafts = ref<ExtraCostDraft[]>([])
const explainVisible = ref(false)
const { submitting, errorMessage, run } = useSubmitAction()

const lineOptions = computed(() =>
  (order.value?.items ?? [])
    .filter((item) => item.canceled_at === null)
    .map((item) => ({ value: item.id, label: `${item.position}. ${item.item_article_name}` })),
)

function open(target: OrderResponse): void {
  order.value = target
  drafts.value = target.extra_costs.map((cost) => ({
    kind: cost.kind,
    amount: cost.amount,
    label: cost.label ?? '',
    note: cost.note ?? '',
    lineId: cost.order_item_id,
  }))
  errorMessage.value = null
  visible.value = true
}

async function onSave(): Promise<void> {
  const current = order.value
  if (!current) return
  const invalid = extraCostDraftError(drafts.value)
  if (invalid) {
    errorMessage.value = t(invalid)
    return
  }
  await run(async () => {
    await ordersStore.setExtraCosts(current.id, {
      expected_edit_version: current.edit_version,
      costs: drafts.value.map((draft) => ({
        kind: draft.kind,
        amount: draft.amount ?? 0,
        label: draft.label.trim() || null,
        note: draft.note.trim() || null,
        order_item_id: draft.lineId,
      })),
    })
    visible.value = false
    emit('saved')
  }, t('common.extraCosts.errors.unknown'))
}

defineExpose({ open })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <template #header>
      <div class="extra-costs-header">
        <span class="p-dialog-title">{{ t('common.extraCosts.dialogTitle') }}</span>
        <Button
          type="button"
          class="extra-costs-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('orders.explain.extraCosts')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('orders.explain.extraCosts')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <ExtraCostsEditor v-model="drafts" :line-options="lineOptions" :disabled="submitting" />

    <template #footer>
      <Message v-if="errorMessage" severity="error" :closable="false" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        icon="mdi mdi-content-save-outline"
        :label="t('common.save')"
        :loading="submitting"
        @click="onSave"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="procurement/order-documents" anchor="extra-costs" />
</template>

<style scoped lang="scss">
.extra-costs-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.extra-costs-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.footer-error {
  margin-right: auto;
}
</style>
