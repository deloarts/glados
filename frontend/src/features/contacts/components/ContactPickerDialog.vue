<script setup lang="ts">
/**
 * Picks a contact to link to a product or a project. The contacts of the
 * record's customer come first, then every other live contact that matches
 * the search; archived contacts and those linked already are not offered.
 */
import { computed, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDebounceFn } from '@vueuse/core'

import { SEARCH_DEBOUNCE_MS } from '@/core/constants/table'
import { getContacts } from '../api/contactsApi'
import { contactDisplayName } from '../utils/contactLabels'
import type { ContactResponse } from '../types/contactResponse'

/** How many contacts each group offers at once; the search narrows them. */
const PAGE_SIZE = 20

const props = defineProps<{
  customerId?: number | null
  customerName?: string | null
  /** The contacts linked already. */
  excludeIds: number[]
  /** Set while the link is being saved. */
  saving?: boolean
  errorMessage?: string | null
}>()

const emit = defineEmits<{
  link: [contactId: number, receivesMeetingNotes: boolean]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const uid = useId()

const customerContacts = ref<ContactResponse[]>([])
const otherContacts = ref<ContactResponse[]>([])
const loading = ref(false)
const picked = ref<number | null>(null)
const receivesMeetingNotes = ref(true)
const submitted = ref(false)
let epoch = 0

async function search(query: string): Promise<void> {
  const current = ++epoch
  loading.value = true
  try {
    const term = query.trim() || undefined
    const [ofCustomer, all] = await Promise.all([
      props.customerId != null
        ? getContacts({ customer_id: props.customerId, search: term, limit: PAGE_SIZE, order_by: 'name' })
        : Promise.resolve(null),
      getContacts({ search: term, limit: PAGE_SIZE, order_by: 'name' }),
    ])
    if (current !== epoch) return
    customerContacts.value = ofCustomer?.items ?? []
    const customerIds = new Set(customerContacts.value.map((contact) => contact.id))
    otherContacts.value = all.items.filter((contact) => !customerIds.has(contact.id))
  } catch {
    if (current === epoch) {
      customerContacts.value = []
      otherContacts.value = []
    }
  } finally {
    if (current === epoch) loading.value = false
  }
}

const debouncedSearch = useDebounceFn((query: string) => search(query), SEARCH_DEBOUNCE_MS)

watch(visible, (open) => {
  if (!open) return
  picked.value = null
  receivesMeetingNotes.value = true
  submitted.value = false
  void search('')
})

interface ContactOption {
  id: number
  label: string
  sublabel: string
}

function toOption(contact: ContactResponse): ContactOption {
  return {
    id: contact.id,
    label: contactDisplayName(t, contact),
    sublabel: [contact.role, contact.organisation?.name, contact.email].filter(Boolean).join(' · '),
  }
}

const groups = computed(() => {
  const excluded = new Set(props.excludeIds)
  const offered = (contacts: ContactResponse[]) =>
    contacts.filter((contact) => !excluded.has(contact.id)).map(toOption)
  return [
    ...(props.customerId != null
      ? [
          {
            label: t('contacts.picker.customerGroup', { customer: props.customerName ?? '' }),
            items: offered(customerContacts.value),
          },
        ]
      : []),
    { label: t('contacts.picker.otherGroup'), items: offered(otherContacts.value) },
  ].filter((group) => group.items.length > 0)
})

const pickError = computed(() =>
  submitted.value && picked.value === null ? t('contacts.picker.required') : null,
)

function onLink(): void {
  submitted.value = true
  if (picked.value === null) return
  emit('link', picked.value, receivesMeetingNotes.value)
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('contacts.picker.title')"
    :style="{ width: 'var(--dialog-width-sm)' }"
  >
    <div class="dialog-body">
      <div class="field">
        <label :id="`${uid}-contact-label`" :for="`${uid}-contact`">{{ t('contacts.picker.contact') }} *</label>
        <Select
          v-model="picked"
          :input-id="`${uid}-contact`"
          :aria-labelledby="`${uid}-contact-label`"
          :options="groups"
          option-label="label"
          option-value="id"
          option-group-label="label"
          option-group-children="items"
          :loading="loading"
          :placeholder="t('contacts.picker.placeholder')"
          :invalid="!!pickError"
          filter
          :filter-fields="['label', 'sublabel']"
          reset-filter-on-hide
          fluid
          data-testid="contact-picker-select"
          @filter="(event) => debouncedSearch(event.value)"
        >
          <template #option="{ option }">
            <div class="option">
              <span>{{ option.label }}</span>
              <small v-if="option.sublabel" class="text-muted">{{ option.sublabel }}</small>
            </div>
          </template>
        </Select>
        <small v-if="pickError" class="field-error">{{ pickError }}</small>
      </div>
      <div class="flag-row">
        <ToggleSwitch
          v-model="receivesMeetingNotes"
          :input-id="`${uid}-meeting-notes`"
          data-testid="contact-picker-meeting-notes"
        />
        <label :for="`${uid}-meeting-notes`">{{ t('contacts.picker.receivesMeetingNotes') }}</label>
      </div>
    </div>

    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        type="button"
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="saving"
        @click="visible = false"
      />
      <Button
        type="button"
        :label="t('contacts.picker.link')"
        icon="mdi mdi-link-variant-plus"
        :loading="saving"
        data-testid="contact-picker-link"
        @click="onLink"
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

.option {
  display: flex;
  flex-direction: column;
}

.flag-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
