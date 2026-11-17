<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { getMeetingScopeSuggestions, renameMeetingScope } from '../api/meetingsApi'

/**
 * Renames a scope on every card of the owner's valid meetings, for a scope
 * that was spelled in two ways or got a better name. On a product it covers
 * the meetings of its projects as well.
 */
const props = defineProps<{ ownerKind: 'project' | 'product'; ownerId: number }>()
const emit = defineEmits<{ renamed: [] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const uid = useId()
const toast = useAppToast()

const scopes = ref<{ scope: string; count: number }[]>([])
const fromScope = ref<string | null>(null)
const toScope = ref('')
const saving = ref(false)
const errorMessage = ref('')

const owner = computed(() =>
  props.ownerKind === 'product' ? { product_id: props.ownerId } : { project_id: props.ownerId },
)

watch(visible, async (open) => {
  if (!open) return
  fromScope.value = null
  toScope.value = ''
  errorMessage.value = ''
  try {
    scopes.value = (await getMeetingScopeSuggestions({ ...owner.value, limit: 100 })).suggestions
  } catch (err) {
    scopes.value = []
    errorMessage.value = extractApiError(err) ?? t('meetings.errors.unknown')
  }
})

const options = computed(() =>
  scopes.value.map((entry) => ({
    value: entry.scope,
    label: t('meetings.scopeRename.option', { scope: entry.scope, count: entry.count }),
  })),
)

const canSave = computed(
  () => !!fromScope.value && !!toScope.value.trim() && toScope.value.trim() !== fromScope.value,
)

async function onSave(): Promise<void> {
  if (!fromScope.value || !canSave.value) return
  saving.value = true
  errorMessage.value = ''
  try {
    const result = await renameMeetingScope({
      ...owner.value,
      from_scope: fromScope.value,
      to_scope: toScope.value.trim(),
    })
    toast.success(toScope.value.trim(), t('meetings.scopeRename.done', { count: result.renamed }))
    visible.value = false
    emit('renamed')
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('meetings.errors.unknown')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('meetings.scopeRename.title')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <div class="dialog-body">
      <p class="hint">{{ t('meetings.scopeRename.hint') }}</p>
      <div class="field">
        <label :id="`${uid}-from-label`" :for="`${uid}-from`">{{ t('meetings.scopeRename.from') }}</label>
        <Select
          v-model="fromScope"
          :input-id="`${uid}-from`"
          :aria-labelledby="`${uid}-from-label`"
          :options="options"
          option-label="label"
          option-value="value"
          filter
          :empty-message="t('meetings.scopeRename.noScopes')"
          fluid
          data-testid="meeting-scope-rename-from"
        />
      </div>
      <div class="field">
        <label :for="`${uid}-to`">{{ t('meetings.scopeRename.to') }}</label>
        <InputText
          :id="`${uid}-to`"
          v-model="toScope"
          maxlength="80"
          fluid
          data-testid="meeting-scope-rename-to"
          @keydown.enter="onSave"
        />
      </div>
    </div>
    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">{{ errorMessage }}</Message>
      <Button :label="t('common.cancel')" severity="secondary" text :disabled="saving" @click="visible = false" />
      <Button
        :label="t('meetings.scopeRename.action')"
        icon="mdi mdi-rename-outline"
        :loading="saving"
        :disabled="!canSave"
        data-testid="meeting-scope-rename-save"
        @click="onSave"
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

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
