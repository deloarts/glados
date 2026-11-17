<script setup lang="ts">
import { computed, nextTick, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { sendMail } from '../api/sendMail'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { sanitizeMailHtml } from '@/shared/utils/sanitizeMailHtml'

interface Props {
  to?: string
  cc?: string
  replyTo?: string
  subject?: string
  body?: string
  /** A notice above the fields, such as an archived recipient. */
  warning?: string
}

const props = withDefaults(defineProps<Props>(), {
  to: '',
  cc: '',
  replyTo: '',
  subject: '',
  body: '',
  warning: '',
})

const visible = defineModel<boolean>('visible', { default: false })
const emit = defineEmits<{ sent: [] }>()

const { hasPermission } = usePermissions()
// Backstop for the callers' own gates, so a new entry point never meets a
// 403 at send time.
const canSend = computed(() => hasPermission(Permission.SEND_MAIL))

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()

const fieldTo = ref('')
const fieldCc = ref('')
const fieldSubject = ref('')
const fieldBody = ref('')
const bodyRef = ref<HTMLDivElement>()
const sending = ref(false)

watch(visible, async (isVisible) => {
  if (!isVisible) return
  fieldTo.value = props.to
  fieldCc.value = props.cc
  fieldSubject.value = props.subject
  fieldBody.value = props.body
  await nextTick()
  if (bodyRef.value) bodyRef.value.innerHTML = sanitizeMailHtml(props.body)
})

function onBodyInput(e: Event): void {
  fieldBody.value = (e.target as HTMLDivElement).innerHTML
}

async function onSend(): Promise<void> {
  sending.value = true
  try {
    await sendMail({
      to: fieldTo.value,
      subject: fieldSubject.value,
      // Sanitized again before sending, since a paste can bring anything into the
      // contenteditable body.
      html_body: sanitizeMailHtml(fieldBody.value),
      cc: fieldCc.value || undefined,
      reply_to: props.replyTo || undefined,
    })
    appToast.success(t('mail.compose.sentTitle'), t('mail.compose.sentDetail', { to: fieldTo.value }))
    emit('sent')
    visible.value = false
  } catch {
    appToast.error(t('mail.compose.errorTitle'), t('mail.compose.errorDetail'))
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('mail.compose.title')"
    :style="{ width: 'var(--dialog-width-full)' }"
    :pt="{ content: { style: 'padding-bottom: 0' } }"
  >
    <div class="compose-form">
      <Message v-if="props.warning" severity="warn" :closable="false">{{ props.warning }}</Message>
      <div class="compose-fields">
        <div class="compose-field">
          <label :for="`${uid}-to`">{{ t('mail.compose.to') }}</label>
          <InputText v-model="fieldTo" :id="`${uid}-to`" fluid autocomplete="off" />
        </div>
        <div class="compose-field">
          <label :for="`${uid}-cc`">{{ t('mail.compose.cc') }}</label>
          <InputText v-model="fieldCc" :id="`${uid}-cc`" fluid autocomplete="off" />
        </div>
        <div class="compose-field">
          <label :for="`${uid}-subject`">{{ t('mail.compose.subject') }}</label>
          <InputText v-model="fieldSubject" :id="`${uid}-subject`" fluid autocomplete="off" />
        </div>
      </div>

      <div ref="bodyRef" class="compose-body" contenteditable="true" @input="onBodyInput" />
    </div>

    <template #footer>
      <Button
        :label="t('common.cancel')"
        severity="secondary"
        :disabled="sending"
        @click="visible = false"
      />
      <Button
        :label="t('mail.compose.send')"
        icon="mdi mdi-send"
        :loading="sending"
        :disabled="!canSend"
        @click="onSend"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.compose-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
}

.compose-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.compose-field {
  display: flex;
  align-items: center;
  gap: var(--space-3);

  label {
    width: 4.5rem;
    flex-shrink: 0;
    font-size: var(--font-size-sm);
    font-weight: 500;
    color: var(--p-text-muted-color);
  }
}

.compose-body {
  min-height: 420px;
  max-height: 60vh;
  overflow-y: auto;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius);
  background: var(--p-content-background);
  font-family: inherit;
  font-size: var(--font-size-sm);
  line-height: 1.6;
  outline: none;

  &:focus {
    border-color: var(--p-primary-color);
    box-shadow: 0 0 0 1px var(--p-primary-color);
  }

  // Inline-styled tables from the template builder
  :deep(table) {
    border-collapse: collapse;
    width: auto;
    margin: var(--space-2) 0;
  }

  :deep(th),
  :deep(td) {
    padding: var(--space-1) var(--space-2);
    border: 1px solid var(--p-content-border-color);
    text-align: left;
    white-space: nowrap;
  }

  :deep(th) {
    background: var(--p-content-hover-background);
    font-weight: 600;
  }

  :deep(p) {
    margin: 0 0 0.5em;
  }
}
</style>
