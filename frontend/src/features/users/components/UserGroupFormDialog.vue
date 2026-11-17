<script setup lang="ts">
import { computed, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useUsersStore } from '@/core/stores/usersStore'
import { extractApiError } from '@/core/utils/errors'
import { useUserGroupsStore } from '../stores/userGroupsStore'
import PermissionChecklist from './PermissionChecklist.vue'

import type { UserGroupResponse } from '../types/userGroup'

interface Props {
  group?: UserGroupResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  saved: [group: UserGroupResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const store = useUserGroupsStore()
const usersStore = useUsersStore()
const currentUserStore = useCurrentUserStore()

interface FormState {
  name: string
  description: string
  permissions: string[]
  member_ids: number[]
}

const form = reactive<FormState>({ name: '', description: '', permissions: [], member_ids: [] })
const submitting = ref(false)
const submitted = ref(false)
const errorMessage = ref<string | null>(null)

const isEditMode = computed(() => !!props.group)
const currentUserId = computed(() => currentUserStore.user?.id ?? null)

// Nobody raises their own permissions through a group, so a member cannot
// change the permissions of their group, and nobody adds or removes
// themselves. The backend refuses both; the form says so up front.
const ownGroup = computed(
  () => currentUserId.value !== null && !!props.group?.member_ids.includes(currentUserId.value),
)

// Service accounts take their permissions from their API key and the
// system user passes every check, so neither is offered.
const memberOptions = computed(() =>
  usersStore.users
    .filter(
      (u) =>
        !u.is_systemuser &&
        !u.is_service_account &&
        (u.is_active || form.member_ids.includes(u.id)),
    )
    .map((u) => ({ ...u, disabled: u.id === currentUserId.value })),
)

const nameError = computed(() => submitted.value && !form.name.trim())

watch(visible, (isVisible) => {
  if (!isVisible) return
  errorMessage.value = null
  submitted.value = false
  void usersStore.ensureLoaded()
  Object.assign(form, {
    name: props.group?.name ?? '',
    description: props.group?.description ?? '',
    permissions: [...(props.group?.permissions ?? [])],
    member_ids: [...(props.group?.member_ids ?? [])],
  })
})

async function onSubmit(): Promise<void> {
  submitted.value = true
  if (!form.name.trim()) return

  submitting.value = true
  errorMessage.value = null
  const payload = {
    name: form.name.trim(),
    description: form.description.trim(),
    permissions: form.permissions,
    member_ids: form.member_ids,
  }
  try {
    const saved = props.group
      ? await store.update(props.group.id, payload)
      : await store.create(payload)
    visible.value = false
    emit('saved', saved)
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('settings.groups.errors.unknown')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="isEditMode ? t('settings.groups.editGroup') : t('settings.groups.createGroup')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <form id="user-group-form" class="group-form" @submit.prevent="onSubmit">
      <div class="group-fields">
        <div class="field">
          <label for="g-name">{{ t('settings.groups.fields.name') }} *</label>
          <InputText id="g-name" v-model="form.name" :invalid="nameError" fluid />
          <small v-if="nameError" class="error">{{ t('settings.groups.errors.nameRequired') }}</small>
        </div>

        <div class="field">
          <label for="g-description">{{ t('settings.groups.fields.description') }}</label>
          <Textarea id="g-description" v-model="form.description" rows="2" auto-resize fluid />
        </div>

        <div class="field">
          <label id="g-members-label" for="g-members">{{ t('settings.groups.fields.members') }}</label>
          <MultiSelect
            id="g-members"
            aria-labelledby="g-members-label"
            v-model="form.member_ids"
            :options="memberOptions"
            option-label="full_name"
            option-value="id"
            option-disabled="disabled"
            :loading="usersStore.loading"
            :placeholder="t('settings.groups.fields.membersPlaceholder')"
            display="chip"
            filter
            fluid
          />
          <small class="hint">{{ t('settings.groups.fields.membersHint') }}</small>
        </div>
      </div>

      <aside class="permissions-panel">
        <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions the group below, which names it through aria-labelledby -->
        <label :id="`${uid}-permissions`">{{ t('settings.groups.fields.permissions') }}</label>
        <Message v-if="ownGroup" severity="info" size="small">
          {{ t('settings.groups.ownGroupPermissions') }}
        </Message>
        <div class="permissions-list">
          <PermissionChecklist
            v-model:permissions="form.permissions"
            id-prefix="g-perm"
            :labelledby="`${uid}-permissions`"
            :disabled="ownGroup"
          />
        </div>
      </aside>
    </form>

    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        type="button"
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        type="submit"
        form="user-group-form"
        :label="t('common.save')"
        icon="mdi mdi-content-save-outline"
        :loading="submitting"
        data-testid="user-group-save"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
// Fields left, permissions right, as in the user dialog.
.group-form {
  display: grid;
  grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  gap: var(--space-5);
}

.group-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.error {
  color: var(--p-red-500);
}

.permissions-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-height: 0;

  > label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.permissions-list {
  padding: var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-sm);
  max-height: 24rem;
  overflow-y: auto;
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}

@media (max-width: $bp-lg) {
  .group-form {
    grid-template-columns: 1fr;
  }
}
</style>
