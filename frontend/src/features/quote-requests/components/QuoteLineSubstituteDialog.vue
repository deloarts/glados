<script setup lang="ts">
// Replaces a quote request line for every supplier with a line for another
// item of its kind. The old line is dropped and the new one takes over its
// quantity, project and demand shares; removing the new line asks for the
// old one again. A supplier already asked gets the request again for it.
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import FormField from '@/shared/components/forms/FormField.vue'
import { formatUnit } from '@/shared/utils/units'
import { substituteQuoteRequestLine } from '../api/substituteQuoteRequestLine'
import { substituteKind } from '../utils/quoteRequestFormat'
import SubstituteItemSelect from './SubstituteItemSelect.vue'
import type { SubstituteItemOption } from '../api/searchSubstituteItems'
import type {
  QuoteRequestLineResponse,
  QuoteRequestResponse,
} from '../types/quoteRequestsResponse'

const emit = defineEmits<{ saved: [request: QuoteRequestResponse] }>()

const { t } = useI18n()
const { submitting, errorMessage, run } = useSubmitAction()

const visible = ref(false)
const request = ref<QuoteRequestResponse | null>(null)
const line = ref<QuoteRequestLineResponse | null>(null)
const item = ref<SubstituteItemOption | null>(null)
const reason = ref('')

const kind = computed(() => (line.value ? substituteKind(line.value) : null))
const ownItemId = computed(() =>
  kind.value === 'BOUGHT' ? (line.value?.bought_item_id ?? null) : (line.value?.source_item_id ?? null),
)
const canSave = computed(() => item.value !== null)

function open(target: QuoteRequestResponse, targetLine: QuoteRequestLineResponse): void {
  request.value = target
  line.value = targetLine
  item.value = null
  reason.value = ''
  errorMessage.value = null
  visible.value = true
}

async function onSave(): Promise<void> {
  const target = request.value
  const current = line.value
  const chosen = item.value
  if (!target || !current || !chosen || !canSave.value) return
  await run(async () => {
    const saved = await substituteQuoteRequestLine(target.id, current.id, {
      bought_item_id: kind.value === 'BOUGHT' ? chosen.id : null,
      source_item_id: kind.value === 'SOURCE' ? chosen.id : null,
      reason: reason.value.trim() || null,
    })
    visible.value = false
    emit('saved', saved)
  }, t('quoteRequests.substitute.errors.unknown'))
}

defineExpose({ open })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('quoteRequests.substitute.title', { line: line?.position ?? '' })"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div v-if="line && kind" class="substitute-form">
      <div class="current">
        <span class="current-label">{{ t('quoteRequests.substitute.current') }}</span>
        <span class="current-name">{{ line.item_name }}</span>
        <span class="current-meta">
          {{ [line.item_code, `${line.quantity} ${formatUnit(line.unit)}`].filter(Boolean).join(' · ') }}
        </span>
      </div>
      <FormField :label="t('quoteRequests.substitute.item')" required v-slot="{ inputId, labelId }">
        <SubstituteItemSelect
          v-model="item"
          :kind="kind"
          :exclude-id="ownItemId"
          :input-id="inputId"
          :aria-labelledby="labelId"
          :disabled="submitting"
        />
      </FormField>
      <FormField :label="t('quoteRequests.substitute.reason')" v-slot="{ id }">
        <Textarea :id="id" v-model="reason" rows="2" auto-resize fluid :disabled="submitting" />
      </FormField>
      <Message severity="secondary" :closable="false" size="small">
        {{ t('quoteRequests.substitute.hint') }}
      </Message>
    </div>
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
        icon="mdi mdi-swap-horizontal"
        :label="t('quoteRequests.actions.substituteLine')"
        :loading="submitting"
        :disabled="!canSave"
        data-testid="substitute-save"
        @click="onSave"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.substitute-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.current {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.current-label,
.current-meta {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.current-name {
  font-weight: 600;
}

.footer-error {
  margin-right: auto;
}
</style>
