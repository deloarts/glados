<script setup lang="ts">
import { ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { extractApiError } from '@/core/utils/errors'
import { dateToParam as formatDate, todayStart } from '@/core/utils/dates'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'

import type {
  LotPositionProvisionResponse,
  LotPositionResponse,
} from '../../types/productionLotsResponse'

const props = defineProps<{
  lotId: number
  position: LotPositionResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const detailStore = useProductionLotDetailStore()

const provisions = ref<LotPositionProvisionResponse[]>([])
const loading = ref(false)
const submitting = ref(false)
const errorMessage = ref<string | null>(null)

const quantity = ref<number | null>(null)
const provisionDate = ref<Date>(todayStart())
const note = ref('')

watch(visible, async (isVisible) => {
  if (!isVisible || !props.position) return
  quantity.value = null
  provisionDate.value = todayStart()
  note.value = ''
  errorMessage.value = null
  loading.value = true
  try {
    provisions.value = await detailStore.fetchProvisions(props.lotId, props.position.id)
  } finally {
    loading.value = false
  }
})

async function onSubmit(): Promise<void> {
  if (!props.position || !quantity.value || quantity.value <= 0) return

  submitting.value = true
  errorMessage.value = null

  try {
    await detailStore.recordProvision(props.lotId, props.position.id, {
      quantity: quantity.value,
      provision_date: formatDate(provisionDate.value)!,
      note: note.value.trim() || null,
    })
    provisions.value = await detailStore.fetchProvisions(props.lotId, props.position.id)
    quantity.value = null
    note.value = ''
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('production.lots.detail.provisions.errors.unknown')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('production.lots.detail.provisions.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div class="provisions">
      <div class="provisions-list">
        <div v-if="loading" class="provisions-loading">
          <i class="mdi mdi-loading mdi-spin" aria-hidden="true" />
        </div>
        <template v-else>
          <div v-for="provision in provisions" :key="provision.id" class="provision-row">
            <span class="provision-quantity">{{ provision.quantity }}</span>
            <span class="provision-date">{{ provision.provision_date }}</span>
            <span v-if="provision.note" class="provision-note">{{ provision.note }}</span>
          </div>
          <div v-if="provisions.length === 0" class="provisions-empty">
            {{ t('production.lots.detail.provisions.empty') }}
          </div>
        </template>
      </div>

      <Divider />

      <form class="provision-form" @submit.prevent="onSubmit">
        <div class="form-grid">
          <div class="field">
            <label :for="`${uid}-quantity`">{{ t('production.lots.detail.provisions.quantity') }} *</label>
            <InputNumber v-model="quantity" :input-id="`${uid}-quantity`" :min="0.001" :max-fraction-digits="3" fluid />
          </div>
          <div class="field">
            <label :for="`${uid}-date`">{{ t('production.lots.detail.provisions.date') }} *</label>
            <DatePicker v-model="provisionDate" :input-id="`${uid}-date`" fluid />
          </div>
        </div>
        <div class="field">
          <label :for="`${uid}-note`">{{ t('production.lots.detail.provisions.note') }}</label>
          <Textarea v-model="note" :id="`${uid}-note`" rows="2" auto-resize fluid />
        </div>

        <Message v-if="errorMessage" severity="error" :closable="false">
          {{ errorMessage }}
        </Message>
      </form>
    </div>

    <template #footer>
      <Button :label="t('common.close')" severity="secondary" outlined @click="visible = false" />
      <Button
        :label="t('production.lots.detail.provisions.record')"
        :loading="submitting"
        :disabled="!quantity || quantity <= 0"
        @click="onSubmit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.provisions {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.provisions-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: 10rem;
  overflow-y: auto;
}

.provisions-loading,
.provisions-empty {
  display: flex;
  justify-content: center;
  padding: var(--space-4);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.provision-row {
  display: flex;
  gap: var(--space-3);
  align-items: baseline;
  font-size: var(--font-size-sm);
}

.provision-quantity {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.provision-date {
  color: var(--p-text-muted-color);
}

.provision-note {
  color: var(--p-text-muted-color);
  font-style: italic;
}

.provision-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
</style>
