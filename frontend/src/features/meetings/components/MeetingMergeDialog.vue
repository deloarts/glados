<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { lineDiff } from '../utils/lineDiff'
import MeetingLineDiff from './MeetingLineDiff.vue'

/**
 * Someone else saved the card while the user wrote it. The dialog shows
 * their text, the user's text and the lines between them, and saves what
 * the user merges into the field below, which starts as the user's text.
 */
const props = defineProps<{
  theirs: string
  mine: string
  saving?: boolean
  error?: string
}>()

const emit = defineEmits<{ save: [text: string]; cancel: [] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const uid = useId()
const merged = ref('')

watch(
  () => [visible.value, props.mine, props.theirs] as const,
  ([open]) => {
    if (open) merged.value = props.mine
  },
  { immediate: true },
)

const diff = computed(() => lineDiff(props.theirs, props.mine))

function onHide(): void {
  emit('cancel')
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('meetings.merge.title')"
    :style="{ width: 'var(--dialog-width-lg)' }"
    data-testid="meeting-merge-dialog"
    @hide="onHide"
  >
    <div class="dialog-body">
      <Message severity="warn" size="small">{{ t('meetings.merge.notice') }}</Message>
      <div class="texts">
        <section class="text-pane">
          <span class="field-caption">{{ t('meetings.merge.theirs') }}</span>
          <pre class="text-box" data-testid="meeting-merge-theirs">{{ theirs || t('meetings.merge.empty') }}</pre>
        </section>
        <section class="text-pane">
          <span class="field-caption">{{ t('meetings.merge.mine') }}</span>
          <pre class="text-box" data-testid="meeting-merge-mine">{{ mine || t('meetings.merge.empty') }}</pre>
        </section>
      </div>
      <div>
        <span class="field-caption">{{ t('meetings.merge.diff') }}</span>
        <MeetingLineDiff :lines="diff" />
      </div>
      <div class="field">
        <label :for="`${uid}-merged`">{{ t('meetings.merge.merged') }}</label>
        <Textarea
          :id="`${uid}-merged`"
          v-model="merged"
          rows="8"
          auto-resize
          fluid
          data-testid="meeting-merge-text"
        />
        <small class="hint">{{ t('meetings.merge.mergedHint') }}</small>
      </div>
    </div>
    <template #footer>
      <Message v-if="error" severity="error" size="small" class="footer-error">{{ error }}</Message>
      <Button
        :label="t('meetings.merge.keepEditing')"
        severity="secondary"
        text
        :disabled="saving"
        @click="visible = false"
      />
      <Button
        :label="t('meetings.merge.save')"
        icon="mdi mdi-check"
        :loading="saving"
        data-testid="meeting-merge-save"
        @click="emit('save', merged)"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.texts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.text-pane {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.text-box {
  margin: 0;
  padding: var(--space-2);
  max-height: 14rem;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: var(--font-size-sm);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
  background: var(--p-content-hover-background);
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
