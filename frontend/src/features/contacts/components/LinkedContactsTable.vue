<script setup lang="ts">
/**
 * The contacts linked to a product or a project, for the Contacts section
 * of its overview: who they are, where the link comes from, whether they
 * receive the meeting notes, and Unlink. The owner's section loads the rows
 * and saves the changes; this table only shows them.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import ContactLinks from '@/shared/components/ContactLinks.vue'
import { contactDisplayName } from '../utils/contactLabels'
import type { ContactSummaryResponse } from '../types/contactResponse'

export interface LinkedContactRow {
  contact: ContactSummaryResponse
  receivesMeetingNotes: boolean
  /** Where the link comes from, such as the product of a project; none for the owner's own. */
  sourceLabel?: string | null
  /** Shown on the source tag, such as how to mute an inherited contact. */
  sourceHint?: string | null
  canUnlink: boolean
}

const props = defineProps<{
  rows: LinkedContactRow[]
  canWrite: boolean
  /** The tooltip of a disabled control, naming the missing permission. */
  writeBlocked: string
  /** The contact whose change is being saved. */
  savingId?: number | null
  /** Shows the source column, for a project's inherited contacts. */
  showSource?: boolean
}>()

const emit = defineEmits<{
  toggle: [contactId: number, receivesMeetingNotes: boolean]
  unlink: [contact: ContactSummaryResponse]
}>()

const { t } = useI18n()

const blocked = computed(() => props.writeBlocked || undefined)

function subtitle(contact: ContactSummaryResponse): string {
  return [contact.role, contact.organisation?.name].filter(Boolean).join(' · ')
}
</script>

<template>
  <DataTable :value="rows" data-key="contact.id" size="small" data-testid="linked-contacts-table">
    <template #empty>
      <span class="empty-note">{{ t('contacts.links.empty') }}</span>
    </template>
    <Column header="#" body-class="row-number" class="column-fit">
      <template #body="{ index }">{{ index + 1 }}</template>
    </Column>
    <Column :header="t('contacts.columns.name')" class="column-fit">
      <template #body="{ data }: { data: LinkedContactRow }">
        <div class="name-cell">
          <span class="name-line">
            <span class="contact-name">{{ contactDisplayName(t, data.contact) }}</span>
            <Tag
              v-if="data.contact.archived"
              :value="t('common.archivedTag')"
              severity="warn"
              icon="mdi mdi-archive-outline"
            />
          </span>
          <small v-if="subtitle(data.contact)" class="text-muted">{{ subtitle(data.contact) }}</small>
        </div>
      </template>
    </Column>
    <Column :header="t('contacts.columns.email')" class="column-fit">
      <template #body="{ data }: { data: LinkedContactRow }">
        <ContactLinks :email="data.contact.email" :phone="data.contact.phone ?? data.contact.mobile" />
      </template>
    </Column>
    <Column v-if="showSource" :header="t('contacts.links.source')" class="column-fit">
      <template #body="{ data }: { data: LinkedContactRow }">
        <Tag
          :value="data.sourceLabel ?? t('contacts.links.ownLink')"
          :severity="data.sourceLabel ? 'secondary' : 'info'"
          v-tooltip.top="data.sourceHint ?? undefined"
        />
      </template>
    </Column>
    <Column :header="t('contacts.links.meetingNotes')" class="column-fit">
      <template #body="{ data }: { data: LinkedContactRow }">
        <span v-tooltip.top="blocked">
          <ToggleSwitch
            :model-value="data.receivesMeetingNotes"
            :disabled="!canWrite || savingId === data.contact.id"
            :aria-label="`${t('contacts.links.meetingNotesHint')}: ${contactDisplayName(t, data.contact)}`"
            data-testid="linked-contact-meeting-notes"
            @update:model-value="(value: boolean) => emit('toggle', data.contact.id, value)"
          />
        </span>
      </template>
    </Column>
    <Column class="column-fit">
      <template #body="{ data }: { data: LinkedContactRow }">
        <div v-if="data.canUnlink" class="row-actions">
          <span v-tooltip.top="blocked ?? t('contacts.links.unlink')">
            <Button
              icon="mdi mdi-link-variant-off"
              size="small"
              severity="danger"
              text
              :disabled="!canWrite || savingId === data.contact.id"
              :aria-label="t('contacts.links.unlink')"
              data-testid="linked-contact-unlink"
              @click="emit('unlink', data.contact)"
            />
          </span>
        </div>
      </template>
    </Column>
    <Column />
  </DataTable>
</template>

<style scoped lang="scss">
.name-cell {
  display: flex;
  flex-direction: column;
}

.name-line {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.contact-name {
  font-weight: 600;
}
</style>
