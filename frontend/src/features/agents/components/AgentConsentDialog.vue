<script setup lang="ts">
// The consent a user gives before their AI agent may use Glados: which AI
// providers the company approved, what leaves Glados, that the agent only
// prepares drafts, that every call is logged and how to withdraw.
// Confirming needs the checkbox; closing the dialog any other way counts as
// declining. The parent sends the consent only after "confirm".
// Company specific wording lives behind the optional AI policy link the
// admin configures.
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { safeHref } from '@/shared/utils/isSafeHttpUrl'
import type { AgentConsentStatus } from '../types/agentTypes'

const props = defineProps<{
  visible: boolean
  status: AgentConsentStatus
  saving?: boolean
}>()

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const { t } = useI18n()

const agreed = ref(false)

// Every opening asks again, an earlier tick never carries over.
watch(
  () => props.visible,
  (visible) => {
    if (visible) agreed.value = false
  },
)

const policyHref = computed(() => safeHref(props.status.ai_policy_url))

function onVisibleChange(visible: boolean): void {
  if (!visible) emit('cancel')
}

function onConfirm(): void {
  if (!agreed.value) return
  emit('confirm')
}
</script>

<template>
  <Dialog
    :visible="visible"
    modal
    :header="t('agents.consent.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
    data-testid="agent-consent-dialog"
    @update:visible="onVisibleChange"
  >
    <div class="consent-body">
      <p>{{ t('agents.consent.intro') }}</p>
      <ul class="consent-points">
        <li>{{ t('agents.consent.providers', { providers: status.approved_providers }) }}</li>
        <li>{{ t('agents.consent.onlyDrafts') }}</li>
        <li>
          {{
            status.include_person_names ? t('agents.consent.namesSent') : t('agents.consent.namesHidden')
          }}
        </li>
        <li>
          {{ status.include_costs ? t('agents.consent.pricesSent') : t('agents.consent.pricesHidden') }}
        </li>
        <li>{{ t('agents.consent.logged') }}</li>
        <li>{{ t('agents.consent.approvedOnly') }}</li>
        <li>{{ t('agents.consent.withdraw') }}</li>
      </ul>
      <p v-if="policyHref" class="consent-policy">
        {{ t('agents.consent.policyHint') }}
        <a :href="policyHref" target="_blank" rel="noopener noreferrer">{{
          t('agents.consent.policy')
        }}</a>
      </p>
      <div class="consent-agree">
        <Checkbox
          v-model="agreed"
          binary
          input-id="agent-consent-agree"
          :pt="{ input: { 'data-testid': 'agent-consent-agree' } }"
        />
        <label for="agent-consent-agree">{{ t('agents.consent.agree') }}</label>
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="emit('cancel')" />
      <Button
        :label="t('agents.consent.confirm')"
        icon="mdi mdi-check"
        :disabled="!agreed"
        :loading="saving"
        data-testid="agent-consent-confirm"
        @click="onConfirm"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.consent-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);

  p {
    margin: 0;
  }
}

.consent-points {
  margin: 0;
  padding-left: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.consent-policy {
  font-size: var(--font-size-sm);
}

.consent-agree {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
