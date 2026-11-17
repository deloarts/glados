<script setup lang="ts">
// The consent the user gives before Glados may use their time tracking
// credentials: what is read, when, that nothing is stored, and how to
// withdraw. Confirming needs the checkbox; closing the dialog any other way
// counts as declining. The parent sends the save only after "confirm".
// The text is generic on purpose, company-specific wording lives behind the
// optional privacy policy link the admin configures.
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { safeHref } from '@/shared/utils/isSafeHttpUrl'

const props = defineProps<{
  visible: boolean
  providerName: string
  privacyPolicyUrl: string | null
  confirmLabel?: string
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

const privacyHref = computed(() => safeHref(props.privacyPolicyUrl))

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
    :header="t('timeTracking.consent.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
    :breakpoints="{ '50rem': '95vw' }"
    data-testid="time-tracking-consent-dialog"
    @update:visible="onVisibleChange"
  >
    <div class="consent-body">
      <p>{{ t('timeTracking.consent.intro', { provider: providerName }) }}</p>
      <ul class="consent-points">
        <li>{{ t('timeTracking.consent.readOnRequest') }}</li>
        <li>{{ t('timeTracking.consent.nothingStored') }}</li>
        <li>{{ t('timeTracking.consent.encrypted') }}</li>
        <li>{{ t('timeTracking.consent.sealed') }}</li>
        <li>{{ t('timeTracking.consent.adminsCannotSee') }}</li>
        <li>{{ t('timeTracking.consent.withdraw') }}</li>
      </ul>
      <p v-if="privacyHref" class="consent-privacy">
        {{ t('timeTracking.consent.privacyPolicyHint') }}
        <a :href="privacyHref" target="_blank" rel="noopener noreferrer">{{
          t('timeTracking.consent.privacyPolicy')
        }}</a>
      </p>
      <div class="consent-agree">
        <Checkbox
          v-model="agreed"
          binary
          input-id="time-tracking-consent-agree"
          :pt="{ input: { 'data-testid': 'time-tracking-consent-agree' } }"
        />
        <label for="time-tracking-consent-agree">{{ t('timeTracking.consent.agree') }}</label>
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="emit('cancel')" />
      <Button
        :label="confirmLabel ?? t('timeTracking.consent.confirm')"
        icon="mdi mdi-check"
        :disabled="!agreed"
        data-testid="time-tracking-consent-confirm"
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

.consent-privacy {
  font-size: var(--font-size-sm);
}

.consent-agree {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
</style>
