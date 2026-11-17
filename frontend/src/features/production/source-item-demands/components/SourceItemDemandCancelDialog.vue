<script setup lang="ts">
// The one prompt every cancel of a raw material demand goes through. The
// server cancels such a demand only with a choice for the lot it feeds:
// cancel the lot too, or cancel only the demand and leave the lot waiting
// on raw material until its source is switched. A plain Dialog, like
// ConfirmActionDialog, so the tables and dialogs that use it need no
// ConfirmationService to mount.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { SourceItemDemandResponse } from '@/features/source-items'


const props = defineProps<{
  demands: SourceItemDemandResponse[]
}>()

const emit = defineEmits<{ confirm: [cancelLot: boolean] }>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

const single = computed(() => (props.demands.length === 1 ? props.demands[0] : undefined))

const header = computed(() =>
  single.value
    ? t('sourceItems.demands.cancelPrompt.header', { id: single.value.id })
    : t('sourceItems.demands.cancelPrompt.headerMany', { count: props.demands.length }),
)

const question = computed(() =>
  single.value
    ? t('sourceItems.demands.cancelPrompt.question', { lot: single.value.lot_number ?? '' })
    : t('sourceItems.demands.cancelPrompt.questionMany', { count: props.demands.length }),
)

function choose(cancelLot: boolean): void {
  visible.value = false
  emit('confirm', cancelLot)
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :header="header" :style="{ width: 'var(--dialog-width-md)' }">
    <p class="prompt-question">{{ question }}</p>
    <ul class="prompt-options">
      <li>
        <strong>{{ t('sourceItems.demands.cancelPrompt.cancelLot') }}</strong>
        <span>{{ t('sourceItems.demands.cancelPrompt.cancelLotHint') }}</span>
      </li>
      <li>
        <strong>{{ t('sourceItems.demands.cancelPrompt.demandOnly') }}</strong>
        <span>{{ t('sourceItems.demands.cancelPrompt.demandOnlyHint') }}</span>
      </li>
    </ul>

    <template #footer>
      <Button
        :label="t('sourceItems.demands.cancelPrompt.back')"
        severity="secondary"
        outlined
        data-testid="cancel-prompt-back"
        @click="visible = false"
      />
      <Button
        :label="t('sourceItems.demands.cancelPrompt.demandOnly')"
        severity="warn"
        data-testid="cancel-prompt-demand-only"
        @click="choose(false)"
      />
      <Button
        :label="t('sourceItems.demands.cancelPrompt.cancelLot')"
        severity="danger"
        data-testid="cancel-prompt-cancel-lot"
        @click="choose(true)"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.prompt-question {
  margin: 0 0 var(--space-3);
  line-height: 1.5;
}

.prompt-options {
  margin: 0;
  padding-left: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  line-height: 1.5;

  span {
    display: block;
    color: var(--p-text-muted-color);
  }
}
</style>
