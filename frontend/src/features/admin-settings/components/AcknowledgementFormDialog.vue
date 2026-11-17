<script setup lang="ts">
import { computed, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { getUsers } from '@/core/api/users/getUsers'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { extractApiError } from '@/core/utils/errors'
import { createAcknowledgement } from '../api/createAcknowledgement'
import type { AnnouncementSeverity } from '../types/adminSettingsTypes'
import type { AcknowledgementShowWhen } from '../types/acknowledgementTypes'
import type { UserResponse } from '@/core/types/userResponse'

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()

const visible = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{ saved: [] }>()

interface Form {
  text: string
  severity: AnnouncementSeverity
  enabled: boolean
  show_when: AcknowledgementShowWhen
  recipient_ids: number[]
}

const form = reactive<Form>({
  text: '',
  severity: 'info',
  enabled: true,
  show_when: 'immediately',
  recipient_ids: [],
})

const users = ref<UserResponse[]>([])
const usersLoading = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)

const severityOptions = computed(() => [
  { value: 'info' as const, label: t('adminSettings.notifications.severities.info') },
  { value: 'warning' as const, label: t('adminSettings.notifications.severities.warning') },
  { value: 'danger' as const, label: t('adminSettings.notifications.severities.danger') },
])

const showWhenOptions = computed(() => [
  {
    value: 'immediately' as const,
    label: t('adminSettings.notifications.acknowledgements.showWhenOptions.immediately'),
  },
  {
    value: 'next_login' as const,
    label: t('adminSettings.notifications.acknowledgements.showWhenOptions.nextLogin'),
  },
])

// Every option carries a precomputed display label: MultiSelect's
// optionLabel also doubles as its default filter field, and a filter field
// has to be a plain string property, not the function form optionLabel also
// accepts (that would make its own default filterFields=[optionLabel] pass
// the function itself to resolveFieldData()).
const userOptions = computed(() =>
  users.value.map((u) => ({ ...u, display: `${u.full_name} (${u.username})` })),
)

// "{count}" is filled in by vue-i18n itself (named interpolation), not by
// MultiSelect's own {..} substitution in selectedItemsLabel: by the time
// OpenVue sees this string there is no brace left in it to rewrite.
const selectedItemsLabel = computed(() =>
  t(
    'adminSettings.notifications.acknowledgements.form.usersSelected',
    { count: form.recipient_ids.length },
    form.recipient_ids.length,
  ),
)

/**
 * Pages through the full active-user list rather than trusting a single
 * page: PageResponse.total can exceed API_MAX_PAGE_SIZE (the largest
 * `limit` any list endpoint accepts, see core/constants/table.ts), and
 * "all selected by default" must not silently drop anyone past the first
 * page.
 */
async function fetchAllActiveUsers(): Promise<UserResponse[]> {
  const all: UserResponse[] = []
  let skip = 0

  for (;;) {
    const page = await getUsers({
      is_active: true,
      is_service_account: false,
      limit: API_MAX_PAGE_SIZE,
      skip,
    })
    all.push(...page.items)
    skip += page.items.length
    if (page.items.length === 0 || all.length >= page.total) break
  }

  return all
}

async function loadUsers(): Promise<void> {
  usersLoading.value = true
  try {
    users.value = await fetchAllActiveUsers()
    // "All selected by default" is a snapshot taken now, including shared
    // accounts. API-key service users are left out of the list altogether
    // (is_service_account: false above): they never sign in, so an
    // acknowledgement addressed to one could never be confirmed and the
    // admin's progress column would never reach 100%.
    form.recipient_ids = users.value.map((u) => u.id)
  } catch {
    appToast.error(t('adminSettings.notifications.acknowledgements.form.usersLoadFailed'))
  } finally {
    usersLoading.value = false
  }
}

watch(visible, (open) => {
  if (!open) return
  form.text = ''
  form.severity = 'info'
  form.enabled = true
  form.show_when = 'immediately'
  form.recipient_ids = []
  errorMessage.value = null
  void loadUsers()
})

const isValid = computed(() => form.text.trim() !== '' && form.recipient_ids.length > 0)

async function onSave(): Promise<void> {
  saving.value = true
  errorMessage.value = null
  try {
    await createAcknowledgement({
      text: form.text.trim(),
      severity: form.severity,
      enabled: form.enabled,
      show_when: form.show_when,
      recipient_ids: form.recipient_ids,
    })
    appToast.success(t('adminSettings.notifications.acknowledgements.saved'))
    emit('saved')
    visible.value = false
  } catch (e) {
    errorMessage.value =
      extractApiError(e) ?? t('adminSettings.notifications.acknowledgements.saveFailed')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('adminSettings.notifications.acknowledgements.form.title')"
    style="width: var(--dialog-width-md)"
  >
    <div class="form-fields">
      <div class="form-field">
        <label :for="`${uid}-text`">{{ t('adminSettings.notifications.acknowledgements.form.text') }}</label>
        <Textarea v-model="form.text" :id="`${uid}-text`" rows="6" auto-resize fluid autofocus />
      </div>

      <div class="form-field">
        <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions the group below, which names it through aria-labelledby -->
        <label :id="`${uid}-severity`">
          {{ t('adminSettings.notifications.acknowledgements.form.severity') }}
        </label>
        <div role="group" :aria-labelledby="`${uid}-severity`" class="severity-options">
          <div v-for="option in severityOptions" :key="option.value" class="severity-option">
            <RadioButton
              v-model="form.severity"
              :input-id="`ack-severity-${option.value}`"
              :value="option.value"
              name="ack-severity"
            />
            <label :for="`ack-severity-${option.value}`">{{ option.label }}</label>
          </div>
        </div>
      </div>

      <div class="form-field">
        <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions the group below, which names it through aria-labelledby -->
        <label :id="`${uid}-show-when`">
          {{ t('adminSettings.notifications.acknowledgements.form.showWhen') }}
        </label>
        <div role="group" :aria-labelledby="`${uid}-show-when`" class="severity-options">
          <div v-for="option in showWhenOptions" :key="option.value" class="severity-option">
            <RadioButton
              v-model="form.show_when"
              :input-id="`ack-show-when-${option.value}`"
              :value="option.value"
              name="ack-show-when"
            />
            <label :for="`ack-show-when-${option.value}`">{{ option.label }}</label>
          </div>
        </div>
      </div>

      <div class="form-field form-field--toggle">
        <label :for="`${uid}-enabled`">{{ t('adminSettings.notifications.acknowledgements.form.enabled') }}</label>
        <ToggleSwitch v-model="form.enabled" :input-id="`${uid}-enabled`" />
      </div>

      <div class="form-field">
        <label :id="`${uid}-recipients-label`" :for="`${uid}-recipients`">
          {{ t('adminSettings.notifications.acknowledgements.form.recipients') }}
        </label>
        <MultiSelect
          v-model="form.recipient_ids"
          :input-id="`${uid}-recipients`"
          :aria-labelledby="`${uid}-recipients-label`"
          :options="userOptions"
          option-label="display"
          option-value="id"
          filter
          fluid
          :loading="usersLoading"
          :max-selected-labels="5"
          :selected-items-label="selectedItemsLabel"
          :placeholder="t('adminSettings.notifications.acknowledgements.form.recipients')"
        />
        <small class="hint">
          {{ t('adminSettings.notifications.acknowledgements.form.recipientsHint') }}
        </small>
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

  .hint {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }
}

.form-field--toggle {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.severity-options {
  display: flex;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.severity-option {
  display: flex;
  align-items: center;
  gap: var(--space-1);

  label {
    font-size: var(--font-size-md);
    color: var(--p-text-color);
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-5);
}
</style>
