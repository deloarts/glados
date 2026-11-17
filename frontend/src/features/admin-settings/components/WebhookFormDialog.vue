<script setup lang="ts">
import { computed, reactive, ref, useId, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useClipboard } from '@/core/composables/useClipboard'

import { createWebhookSubscription } from '../api/createWebhookSubscription'
import { updateWebhookSubscription } from '../api/updateWebhookSubscription'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import type { WebhookSubscription } from '../types/webhookTypes'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const { copyToClipboard } = useClipboard()
const secretInputRef = useTemplateRef<{ $el: HTMLInputElement }>('secretInput')

const visible = defineModel<boolean>('visible', { required: true })

const props = defineProps<{
  subscription?: WebhookSubscription
  eventTypes: string[]
}>()

const emit = defineEmits<{ saved: [] }>()

const form = reactive({
  name: '',
  url: '',
  event_types: [] as string[],
  is_active: true,
})

const { submitting: saving, errorMessage, run } = useSubmitAction()

// After a successful create the dialog switches to the show-once secret view.
const createdSecret = ref<string | null>(null)

const isEdit = computed(() => props.subscription !== undefined)

const eventTypeOptions = computed(() => [
  { label: t('adminSettings.notifications.webhooks.allEvents'), value: '*' },
  ...props.eventTypes.map((e) => ({ label: e, value: e })),
])

watch(visible, (open) => {
  if (!open) return
  createdSecret.value = null
  errorMessage.value = null
  form.name = props.subscription?.name ?? ''
  form.url = props.subscription?.url ?? ''
  form.event_types = props.subscription ? [...props.subscription.event_types] : []
  form.is_active = props.subscription?.is_active ?? true
})

const isValid = computed(
  () =>
    form.name.trim() !== '' && /^https?:\/\//.test(form.url.trim()) && form.event_types.length > 0,
)

async function onSave(): Promise<void> {
  await run(async () => {
    if (props.subscription) {
      await updateWebhookSubscription(props.subscription.id, {
        name: form.name.trim(),
        url: form.url.trim(),
        event_types: form.event_types,
        is_active: form.is_active,
      })
      appToast.success(form.name, t('adminSettings.notifications.webhooks.saved'))
      emit('saved')
      visible.value = false
    } else {
      const created = await createWebhookSubscription({
        name: form.name.trim(),
        url: form.url.trim(),
        event_types: form.event_types,
        is_active: form.is_active,
      })
      emit('saved')
      createdSecret.value = created.secret
    }
  }, t('adminSettings.notifications.webhooks.saveFailed'))
}

async function onCopySecret(): Promise<void> {
  if (!createdSecret.value) return
  const copied = await copyToClipboard(
    createdSecret.value,
    t('adminSettings.notifications.webhooks.copied'),
  )
  if (!copied) secretInputRef.value?.$el.select()
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="
      createdSecret
        ? t('adminSettings.notifications.webhooks.secretTitle')
        : isEdit
          ? t('adminSettings.notifications.webhooks.edit')
          : t('adminSettings.notifications.webhooks.add')
    "
    style="width: var(--dialog-width-md)"
  >
    <template v-if="createdSecret">
      <Message severity="warn" :closable="false">
        {{ t('adminSettings.notifications.webhooks.secretWarning') }}
      </Message>
      <div class="secret-row">
        <InputText
          ref="secretInput"
          :model-value="createdSecret"
          readonly
          fluid
          class="secret-input"
        />
        <Button icon="mdi mdi-content-copy" severity="secondary" :aria-label="t('common.copy')" @click="onCopySecret" />
      </div>
      <div class="dialog-footer">
        <Button :label="t('common.close')" @click="visible = false" />
      </div>
    </template>

    <template v-else>
      <div class="form-fields">
        <div class="form-field">
          <label :for="`${uid}-name`">{{ t('adminSettings.notifications.webhooks.name') }}</label>
          <InputText v-model="form.name" :id="`${uid}-name`" fluid autofocus />
        </div>
        <div class="form-field">
          <label :for="`${uid}-url`">{{ t('adminSettings.notifications.webhooks.url') }}</label>
          <InputText v-model="form.url" :id="`${uid}-url`" fluid placeholder="https://" />
        </div>
        <div class="form-field">
          <label :id="`${uid}-events-label`" :for="`${uid}-events`">
            {{ t('adminSettings.notifications.webhooks.events') }}
          </label>
          <MultiSelect
            v-model="form.event_types"
            :input-id="`${uid}-events`"
            :aria-labelledby="`${uid}-events-label`"
            :options="eventTypeOptions"
            option-label="label"
            option-value="value"
            display="chip"
            filter
            fluid
          />
        </div>
        <div class="form-field form-field--toggle">
          <label :for="`${uid}-active`">{{ t('adminSettings.notifications.webhooks.active') }}</label>
          <ToggleSwitch v-model="form.is_active" :input-id="`${uid}-active`" />
        </div>
      </div>
      <Message v-if="errorMessage" severity="error" class="mt-2">{{ errorMessage }}</Message>
      <div class="dialog-footer">
        <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
        <Button
          :label="t('common.save')"
          icon="mdi mdi-content-save"
          :loading="saving"
          :disabled="!isValid"
          @click="onSave"
        />
      </div>
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.form-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  label {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }
}

.form-field--toggle {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.secret-row {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.secret-input {
  font-family: monospace;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-5);
}
</style>
