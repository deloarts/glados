<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { addAddress, isMailAddress, removeAddress, splitAddresses } from '../utils/meetingNotesMail'

/**
 * The addresses of one recipient field of the send dialog as chips, with a
 * field to type more. An address is added with Enter, a comma, a semicolon
 * or by leaving the field, and a pasted list is split into its addresses.
 * Text that is no address stays in the field and says so.
 */
const props = defineProps<{
  inputId: string
  labelId: string
  /** The name of a chip by its address, such as a suggested contact's. */
  nameOf?: (address: string) => string | null
  disabled?: boolean
  placeholder?: string
}>()

const addresses = defineModel<string[]>({ required: true })

const { t } = useI18n()
const draft = ref('')
const invalid = ref<string[]>([])

function commit(): void {
  const parts = splitAddresses(draft.value)
  if (!parts.length) {
    invalid.value = []
    return
  }
  let next = addresses.value
  const wrong: string[] = []
  for (const part of parts) {
    if (isMailAddress(part)) next = addAddress(next, part)
    else wrong.push(part)
  }
  addresses.value = next
  invalid.value = wrong
  draft.value = wrong.join(', ')
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' || event.key === ',' || event.key === ';') {
    event.preventDefault()
    commit()
  } else if (event.key === 'Backspace' && !draft.value && addresses.value.length) {
    addresses.value = addresses.value.slice(0, -1)
  }
}

function remove(address: string): void {
  addresses.value = removeAddress(addresses.value, address)
}

function chipLabel(address: string): string {
  const name = props.nameOf?.(address)
  return name ? `${name} <${address}>` : address
}

defineExpose({ commit })
</script>

<template>
  <div class="recipient-field">
    <div class="recipient-chips" :aria-labelledby="labelId" role="group">
      <Tag
        v-for="address in addresses"
        :key="address"
        severity="secondary"
        class="recipient-chip"
        :data-testid="`recipient-chip-${address}`"
      >
        <span>{{ chipLabel(address) }}</span>
        <Button
          icon="mdi mdi-close"
          text
          rounded
          size="small"
          class="recipient-remove"
          :disabled="disabled"
          :aria-label="t('meetings.sendDialog.removeRecipient', { address })"
          @click="remove(address)"
        />
      </Tag>
      <InputText
        :id="inputId"
        v-model="draft"
        class="recipient-input"
        autocomplete="off"
        :disabled="disabled"
        :placeholder="placeholder"
        :invalid="invalid.length > 0"
        @keydown="onKeydown"
        @blur="commit"
      />
    </div>
    <small v-if="invalid.length" class="field-error">
      {{ t('meetings.sendDialog.invalidAddress', { address: invalid.join(', ') }) }}
    </small>
  </div>
</template>

<style scoped lang="scss">
.recipient-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.recipient-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
}

.recipient-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.recipient-remove {
  width: 1.25rem;
  height: 1.25rem;
}

.recipient-input {
  flex: 1 1 12rem;
  min-width: 10rem;
  border: none;
  box-shadow: none;
}

.field-error {
  color: var(--p-red-500);
}
</style>
