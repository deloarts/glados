<script setup lang="ts">
import { computed, onMounted, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AutoCompleteCompleteEvent, AutoCompleteOptionSelectEvent } from 'openvue/autocomplete'

import { Permission } from '@/core/auth/permissions'
import { usePermissions } from '@/core/composables/usePermissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { useUsersStore } from '@/core/stores/usersStore'
import { extractApiError } from '@/core/utils/errors'
import UserAvatarPreview from '@/shared/components/user/UserAvatarPreview.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { contactDisplayName, createContact, getContacts } from '@/features/contacts'
import { ATTENDANCE_STATUSES, attendeeKey, parseGuest } from '../utils/attendees'
import type { AttendeeDraft } from '../utils/attendees'
import type { UserSummary } from '@/core/types/userResponse'

/**
 * Picks the people of a meeting: Glados users, contacts (for readers of
 * contacts) and guests typed as a name with an optional e-mail address.
 * A guest can be saved as a contact right away by a user with
 * write:contacts. Each attendee carries a status: present, excused or on the
 * distribution only. Users show their picture, so the user list is loaded
 * when the picker mounts and awaited before the first search filters it.
 */
const attendees = defineModel<AttendeeDraft[]>({ required: true })

const { t } = useI18n()
const uid = useId()
const toast = useAppToast()
const usersStore = useUsersStore()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()

const canReadContacts = computed(() => hasPermission(Permission.READ_CONTACTS))

type Suggestion =
  | { type: 'user'; key: string; id: number; label: string; user: UserSummary }
  | { type: 'contact'; key: string; id: number; label: string; detail: string | null; email: string | null }
  | { type: 'guest'; key: string; label: string }
  | { type: 'save-contact'; key: string; label: string; blocked: string }

interface SuggestionGroup {
  label: string
  items: Suggestion[]
}

const query = ref('')
const groups = ref<SuggestionGroup[]>([])
const saving = ref(false)
let epoch = 0

onMounted(() => void usersStore.ensureLoaded())

const taken = computed(() => new Set(attendees.value.map((attendee) => attendee.key)))

async function onComplete(event: AutoCompleteCompleteEvent): Promise<void> {
  const current = ++epoch
  const text = event.query.trim()
  if (!text) {
    groups.value = []
    return
  }
  await usersStore.ensureLoaded()
  if (current !== epoch) return
  const lower = text.toLowerCase()
  const users: Suggestion[] = usersStore.users
    // Only active people attend, never the system user or a service account.
    .filter(
      (user) =>
        user.is_active &&
        !user.is_systemuser &&
        !user.is_service_account &&
        !taken.value.has(attendeeKey('user', user.id)) &&
        `${user.full_name} ${user.username}`.toLowerCase().includes(lower),
    )
    .slice(0, 8)
    .map((user) => ({ type: 'user', key: `u${user.id}`, id: user.id, label: user.full_name, user }))
  let contacts: Suggestion[] = []
  if (canReadContacts.value) {
    try {
      const page = await getContacts({ search: text, limit: 8 })
      contacts = page.items
        .filter((contact) => !taken.value.has(attendeeKey('contact', contact.id)))
        .map((contact) => ({
          type: 'contact',
          key: `c${contact.id}`,
          id: contact.id,
          label: contactDisplayName(t, contact),
          detail: [contact.role, contact.organisation?.name].filter(Boolean).join(' · ') || null,
          email: contact.email,
        }))
    } catch {
      contacts = []
    }
  }
  if (current !== epoch) return
  const guest = parseGuest(text)
  const next: SuggestionGroup[] = []
  if (users.length) next.push({ label: t('meetings.attendees.groups.users'), items: users })
  if (contacts.length) next.push({ label: t('meetings.attendees.groups.contacts'), items: contacts })
  next.push({
    label: t('meetings.attendees.groups.guest'),
    items: [
      { type: 'guest', key: 'guest', label: t('meetings.attendees.addGuest', { name: guest.name }) },
      {
        type: 'save-contact',
        key: 'save-contact',
        label: t('meetings.attendees.saveAsContact', { name: guest.name }),
        blocked: missing(Permission.WRITE_CONTACTS),
      },
    ],
  })
  groups.value = next
}

function add(draft: Omit<AttendeeDraft, 'status'>): void {
  attendees.value = [...attendees.value, { ...draft, status: 'present' }]
}

async function saveGuestAsContact(text: string): Promise<void> {
  const guest = parseGuest(text)
  saving.value = true
  try {
    const contact = await createContact({
      name: guest.name,
      email: guest.email,
      receives_order_mails: false,
      receives_request_mails: false,
    })
    add({
      key: attendeeKey('contact', contact.id),
      kind: 'contact',
      userId: null,
      contactId: contact.id,
      attendeeId: null,
      name: contact.name,
      email: contact.email,
      detail: null,
    })
    toast.success(contact.name, t('meetings.attendees.contactSaved'))
  } catch (err) {
    toast.error(guest.name, extractApiError(err) ?? t('meetings.errors.unknown'))
  } finally {
    saving.value = false
  }
}

function onSelect(event: AutoCompleteOptionSelectEvent): void {
  const option = event.value as Suggestion
  const text = query.value
  query.value = ''
  if (option.type === 'user') {
    add({
      key: attendeeKey('user', option.id),
      kind: 'user',
      userId: option.id,
      contactId: null,
      attendeeId: null,
      name: option.label,
      email: null,
      detail: null,
    })
  } else if (option.type === 'contact') {
    add({
      key: attendeeKey('contact', option.id),
      kind: 'contact',
      userId: null,
      contactId: option.id,
      attendeeId: null,
      name: option.label,
      email: option.email,
      detail: option.detail,
    })
  } else if (option.type === 'guest') {
    const guest = parseGuest(text)
    if (!guest.name) return
    add({
      key: attendeeKey('guest', `new-${Date.now()}-${attendees.value.length}`),
      kind: 'guest',
      userId: null,
      contactId: null,
      attendeeId: null,
      name: guest.name,
      email: guest.email,
      detail: null,
    })
  } else if (!option.blocked) {
    void saveGuestAsContact(text)
  }
}

function remove(key: string): void {
  attendees.value = attendees.value.filter((attendee) => attendee.key !== key)
}

function setStatus(key: string, status: AttendeeDraft['status']): void {
  attendees.value = attendees.value.map((attendee) => (attendee.key === key ? { ...attendee, status } : attendee))
}

const statusOptions = computed(() =>
  ATTENDANCE_STATUSES.map((value) => ({ value, label: t(`meetings.attendees.status.${value}`) })),
)

const KIND_ICONS = {
  user: 'mdi mdi-account-outline',
  contact: 'mdi mdi-card-account-mail-outline',
  guest: 'mdi mdi-account-question-outline',
} as const
</script>

<template>
  <div class="attendee-picker">
    <label :for="`${uid}-search`">{{ t('meetings.attendees.people') }}</label>
    <AutoComplete
      v-model="query"
      :input-id="`${uid}-search`"
      :suggestions="groups"
      option-label="label"
      option-group-label="label"
      option-group-children="items"
      :option-disabled="(option: Suggestion) => option.type === 'save-contact' && !!option.blocked"
      :delay="150"
      :loading="saving"
      :placeholder="t('meetings.attendees.placeholder')"
      fluid
      data-testid="meeting-attendee-search"
      @complete="onComplete"
      @option-select="onSelect"
    >
      <template #optiongroup="{ option }">
        <span class="group-label">{{ (option as SuggestionGroup).label }}</span>
      </template>
      <template #option="{ option }">
        <div v-if="(option as Suggestion).type === 'user'" class="suggestion suggestion-user">
          <UserAvatarPreview :user="(option as { user: UserSummary }).user" />
        </div>
        <div v-else class="suggestion" :title="(option as Suggestion).type === 'save-contact' ? (option as { blocked: string }).blocked || undefined : undefined">
          <span>{{ (option as Suggestion).label }}</span>
          <small v-if="(option as Suggestion).type === 'contact'" class="text-muted">
            {{ (option as { detail: string | null }).detail }}
          </small>
          <small
            v-if="(option as Suggestion).type === 'save-contact' && (option as { blocked: string }).blocked"
            class="text-muted"
          >
            {{ (option as { blocked: string }).blocked }}
          </small>
        </div>
      </template>
    </AutoComplete>
    <small class="hint">
      {{ canReadContacts ? t('meetings.attendees.hint') : t('meetings.attendees.hintWithoutContacts') }}
    </small>

    <ul v-if="attendees.length" class="attendee-list" data-testid="meeting-attendee-list">
      <li v-for="attendee in attendees" :key="attendee.key" class="attendee-row">
        <UserAvatarPreview
          v-if="attendee.kind === 'user' && attendee.userId != null && usersStore.getById(attendee.userId)"
          :user="usersStore.getById(attendee.userId) ?? null"
          :show-name="false"
        />
        <i v-else :class="KIND_ICONS[attendee.kind]" aria-hidden="true" data-testid="meeting-attendee-kind-icon" />
        <span class="attendee-name">
          <span>{{ attendee.name || t('meetings.attendees.anonymised') }}</span>
          <small v-if="attendee.detail || attendee.email" class="text-muted">
            {{ attendee.detail ?? attendee.email }}
          </small>
        </span>
        <Select
          :model-value="attendee.status"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          size="small"
          :aria-label="t('meetings.attendees.statusOf', { name: attendee.name })"
          @update:model-value="setStatus(attendee.key, $event)"
        />
        <Button
          icon="mdi mdi-close"
          size="small"
          severity="secondary"
          text
          :aria-label="t('meetings.attendees.remove', { name: attendee.name })"
          @click="remove(attendee.key)"
        />
      </li>
    </ul>
    <span v-else class="empty-note">{{ t('meetings.attendees.none') }}</span>
  </div>
</template>

<style scoped lang="scss">
.attendee-picker {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.suggestion {
  display: flex;
  flex-direction: column;
}

.group-label {
  font-weight: 600;
}

.attendee-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.attendee-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 2rem;

  > i {
    width: 1.75rem;
    text-align: center;
  }
}

.suggestion-user {
  flex-direction: row;
  align-items: center;
}

.attendee-name {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-width: 0;
}
</style>
