<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { extractApiError } from '@/core/utils/errors'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { formatDateOrDash } from '@/core/utils/dates'
import { previewAutoAssignLots } from '../../lots/api/previewAutoAssignLots'
import { autoAssignLots } from '../../lots/api/autoAssignLots'

import type { AutoAssignLotGroupResponse } from '../../types/productionLotsResponse'
import { useMadeItemsDemandsStore, useMadeItemLabel } from '@/features/made-items'
import EmptyState from '@/shared/components/EmptyState.vue'

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const toast = useAppToast()
const demandsStore = useMadeItemsDemandsStore()
const { format: madeItemLabel } = useMadeItemLabel()

const groups = ref<AutoAssignLotGroupResponse[]>([])
const loadingPreview = ref(false)
const { submitting, errorMessage, run } = useSubmitAction()

watch(visible, async (open) => {
  if (!open) {
    groups.value = []
    errorMessage.value = null
    return
  }
  loadingPreview.value = true
  errorMessage.value = null
  try {
    groups.value = await previewAutoAssignLots()
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('madeItems.demands.autoAssign.errors.unknown')
  } finally {
    loadingPreview.value = false
  }
})

async function onConfirm(): Promise<void> {
  await run(async () => {
    const created = await autoAssignLots()
    toast.success(t('madeItems.demands.autoAssign.success', { count: created.length }))
    demandsStore.triggerRefresh()
    visible.value = false
  }, t('madeItems.demands.autoAssign.errors.unknown'))
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('madeItems.demands.autoAssign.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
    :draggable="false"
  >
    <div class="auto-assign-body">
      <p class="hint">{{ t('madeItems.demands.autoAssign.hint') }}</p>

      <div v-if="loadingPreview" class="loading-state">
        <ProgressSpinner style="width: 2.5rem; height: 2.5rem" stroke-width="4" />
      </div>

      <EmptyState v-else-if="groups.length === 0" :message="t('madeItems.demands.autoAssign.nothingToAssign')" icon="mdi mdi-checkbox-marked-outline" />

      <div v-else class="rows-list">
        <div
          v-for="group in groups"
          :key="`${group.made_item_id}|${group.project_id}`"
          class="row-card"
        >
          <div class="row-item">
            <span class="row-name">{{ group.item_article_name }}</span>
            <Tag
              v-if="group.high_priority"
              :value="t('madeItems.demands.filters.priorityHigh')"
              severity="warn"
            />
          </div>
          <span class="row-code">{{ madeItemLabel(group.item_part_number, group.item_revision) }}</span>
          <span class="row-project">{{ group.project_number }}, {{ group.project_customer }}</span>
          <div class="row-quantity">
            <span class="quantity-label">{{ t('madeItems.demands.autoAssign.lotQuantity') }}</span>
            <span class="quantity-value">{{ group.quantity }}</span>
          </div>
          <div class="row-quantity">
            <span class="quantity-label">{{
              t('madeItems.demands.autoAssign.requiredDeliveryDate')
            }}</span>
            <span class="quantity-value">{{ formatDateOrDash(group.required_delivery_date) }}</span>
          </div>
          <div v-if="group.demands.length > 1" class="demands-section">
            <span class="field-label">{{
              t('madeItems.demands.autoAssign.contributingDemands')
            }}</span>
            <div class="demand-ids">
              <span v-for="demand in group.demands" :key="demand.demand_item_id" class="demand-id">
                #{{ demand.demand_item_id }} ({{ demand.quantity }})
              </span>
            </div>
          </div>
        </div>
      </div>

      <Message v-if="errorMessage" severity="error" :closable="false">{{ errorMessage }}</Message>
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        outlined
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        :label="t('madeItems.demands.autoAssign.confirm')"
        icon="mdi mdi-factory"
        :disabled="groups.length === 0 || loadingPreview"
        :loading="submitting"
        @click="onConfirm"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.auto-assign-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-height: 60vh;
  overflow-y: auto;
}

.hint {
  margin: 0;
}

.loading-state {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
}



.rows-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.row-card {
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  padding: var(--space-2) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.row-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.row-name {
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.row-code,
.row-project {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.row-quantity {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

.quantity-label {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.quantity-value {
  font-weight: 600;
}

.demands-section {
  margin-top: var(--space-1);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.demand-ids {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}
</style>
