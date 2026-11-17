<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AutoCompleteCompleteEvent } from 'openvue/autocomplete'

import { useProductDeviceResourcesStore } from '@/features/product-devices'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'

/**
 * Asks for the name of a new sequence. The name is free text; the list of
 * proposed names (the resource list of sequence names) only fills it in.
 * For a copy, it starts from the copied sequence's name.
 */
const props = defineProps<{
  busy?: boolean
  /** The name of the sequence being copied; left out for a new, empty one. */
  copyOf?: string | null
}>()

const visible = defineModel<boolean>('visible', { default: false })
const emit = defineEmits<{ create: [name: string] }>()

const NAME_MAX_LENGTH = 200

const { t } = useI18n()
const { localize } = useLocalizedText()
const resources = useProductDeviceResourcesStore()

const name = ref('')
const submitted = ref(false)
const suggestions = ref<string[]>([])

watch(visible, (open) => {
  if (!open) return
  name.value = props.copyOf ? t('sequences.copy.name', { name: props.copyOf }).slice(0, NAME_MAX_LENGTH) : ''
  submitted.value = false
  void resources.load()
})

const proposals = computed(() => resources.optionsOf('sequence_name').map((option) => localize(option.label)))

function complete(event: AutoCompleteCompleteEvent): void {
  const query = event.query.trim().toLocaleLowerCase()
  suggestions.value = proposals.value.filter((proposal) => proposal.toLocaleLowerCase().includes(query))
}

const missing = computed(() => name.value.trim() === '')

function submit(): void {
  submitted.value = true
  if (missing.value) return
  emit('create', name.value.trim())
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="copyOf ? t('sequences.copy.title') : t('sequences.create.title')"
    :style="{ width: 'var(--dialog-width-sm)' }"
    :breakpoints="{ '640px': '95vw' }"
  >
    <form class="create-form" @submit.prevent="submit">
      <label for="sequence-create-name">{{ t('sequences.fields.name') }}</label>
      <AutoComplete
        v-model="name"
        input-id="sequence-create-name"
        :suggestions="suggestions"
        :maxlength="NAME_MAX_LENGTH"
        :invalid="submitted && missing"
        dropdown
        fluid
        data-testid="sequence-create-name"
        @complete="complete"
      />
      <small class="hint">{{ copyOf ? t('sequences.copy.hint') : t('sequences.create.hint') }}</small>
      <small v-if="submitted && missing" class="error">{{ t('sequences.create.nameRequired') }}</small>
    </form>
    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button
        :label="copyOf ? t('sequences.copy.submit') : t('sequences.create.submit')"
        :icon="copyOf ? 'mdi mdi-content-copy' : 'mdi mdi-plus'"
        :loading="busy"
        data-testid="sequence-create-submit"
        @click="submit"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.create-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.error {
  color: var(--p-red-500);
}
</style>
