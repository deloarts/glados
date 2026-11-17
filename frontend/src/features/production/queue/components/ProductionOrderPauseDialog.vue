<script setup lang="ts">
import { computed, onMounted, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { HelpDrawer } from '@/shared/help'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useProductionQueueStore } from '../../stores/productionQueueStore'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

const props = defineProps<{
  order: ProductionOrderResponse | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const explainVisible = ref(false)
// Prefixes the ids that tie each label to its control.
const uid = useId()
const { toastOnError } = useErrorToast()
const store = useProductionQueueStore()
const currentUserStore = useCurrentUserStore()

const operatorId = ref<number | null>(null)
const reason = ref('')
const { submitting, errorMessage, run } = useSubmitAction()

const operatorRequired = computed(() => currentUserStore.isSharedAccount)

const operatorOptions = computed(() =>
  store.operators.map((op) => ({ label: op.full_name, value: op.id })),
)

onMounted(() => {
  if (operatorRequired.value && store.operators.length === 0) {
    store.fetchOperators().catch(toastOnError())
  }
})

watch(visible, (isVisible) => {
  if (!isVisible) return
  operatorId.value = null
  reason.value = ''
  errorMessage.value = null
})

const isValid = computed(() => !operatorRequired.value || operatorId.value !== null)

async function onSubmit(): Promise<void> {
  const order = props.order
  if (!order) return
  if (!isValid.value) {
    errorMessage.value = t('productionQueue.operators.required')
    return
  }

  await run(async () => {
    await store.pause(order.id, {
      ...(operatorId.value !== null ? { operator_id: operatorId.value } : {}),
      reason: reason.value.trim() || undefined,
    })
    visible.value = false
  }, t('productionQueue.pause.errors.unknown'))
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-sm)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('productionQueue.pause.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('productionQueue.pause.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('productionQueue.pause.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <div v-if="order" class="pause-form">
      <div v-if="operatorRequired" class="field">
        <label :id="`${uid}-label-label`" :for="`${uid}-operators`"> {{ t('productionQueue.operators.label') }} * </label>
        <Select
          v-model="operatorId"
          :input-id="`${uid}-operators`"
          :aria-labelledby="`${uid}-label-label`"
          :options="operatorOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('productionQueue.operators.placeholderRequired')"
          :disabled="operatorOptions.length === 0"
          fluid
        />
        <Message v-if="operatorOptions.length === 0" severity="warn" :closable="false">
          {{ t('productionQueue.operators.noneAssigned') }}
        </Message>
      </div>

      <div class="field">
        <label :for="`${uid}-reason`">{{ t('productionQueue.pause.reason') }}</label>
        <Textarea v-model="reason" :id="`${uid}-reason`" rows="2" auto-resize fluid />
      </div>

      <Message v-if="errorMessage" severity="error" :closable="false">
        {{ errorMessage }}
      </Message>
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
        :label="t('productionQueue.pause.submit')"
        :loading="submitting"
        :disabled="!isValid"
        @click="onSubmit"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="production/queue" anchor="pause" />
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

.pause-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
</style>
