<script setup lang="ts">
import { computed, reactive, ref, shallowReactive, useId, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePhoneLayout } from '@/core/composables/usePhoneLayout'

import { storeToRefs } from 'pinia'
import { APERTURE_PRESET, APERTURE_PRIMARY, useEasterEggs } from '@/core/composables/useEasterEggs'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useUserAvatarsStore } from '@/core/stores/userAvatarsStore'
import UserAvatar from '@/shared/components/user/UserAvatar.vue'
import { useHostStore } from '@/core/host/stores/hostStore'
import { setDisplayDateFormat } from '@/core/utils/dates'
import type { DateFormatPreset } from '@/core/utils/dates'
import { dateFormatSample, dateFormatSelectOptions } from '@/shared/utils/dateFormatPreview'
import type { Schemas } from '@/core/api/generated'
import { updateCurrentUser } from '../api/updateCurrentUser'
import AccountPasswordDialog from '../components/AccountPasswordDialog.vue'
import { uploadAvatar } from '../api/uploadAvatar'
import { deleteAvatar } from '../api/deleteAvatar'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import { HelpButton } from '@/shared/help'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useConfirmDelete } from '@/shared/composables/useConfirmDelete'
import { useRegisteredAccountSections, type AccountSectionHandle } from '@/shared/account-page'

const { t } = useI18n()
// A phone keeps the theme only: the profile, the avatar, the regional
// settings, the sections and the visual aids are set up at a desk.
const { phoneMode } = usePhoneLayout()
const { confirmDelete } = useConfirmDelete()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const userStore = useCurrentUserStore()
const avatarsStore = useUserAvatarsStore()
const hostStore = useHostStore()
const layoutStore = useLayoutStore()
const { apertureMode } = useEasterEggs()
const { primaryColors, surfaces } = storeToRefs(layoutStore)
const { applyUserTheme, applyVisualAids } = layoutStore

// The server offers every preset it knows about; one of them is reserved for
// the Konami code and is only selectable once that has been entered.
const presetOptions = computed(() =>
  hostStore.themePresets.filter((preset) => apertureMode.value || preset !== APERTURE_PRESET),
)

// ── Date format ─────────────────────────────────────────────────────────────

const dateFormatOptions = computed(() => dateFormatSelectOptions(hostStore.dateFormats))

// The selected preset with a time; times are always 24-hour.
const dateFormatPreview = computed(() => dateFormatSample(form.date_format, true))

// ── Start page ──────────────────────────────────────────────────────────────

// Uses the sidebar's labels, so a start page reads like its nav entry. A page
// behind a switched-off feature is not offered, unless it is the one already
// chosen, which then falls back to the dashboard on sign-in.
const hiddenStartPages = computed(() => ({
  production: !hostStore.productionPlanningEnabled,
  todo: !hostStore.todosEnabled,
}))
const startPageOptions = computed(() =>
  hostStore.startPages
    .filter(
      (page) =>
        page === form.start_page ||
        !hiddenStartPages.value[page as keyof typeof hiddenStartPages.value],
    )
    .map((page) => ({
      value: page,
      label: t(`main.sidebar.${page}.label`),
    })),
)

// The server already excludes the reserved red; this keeps the rule next to
// the preset gate.
const filteredPrimaryColors = computed(() =>
  primaryColors.value.filter(
    (c) =>
      hostStore.themePrimaries.includes(c.name) &&
      (apertureMode.value || c.name !== APERTURE_PRIMARY),
  ),
)
const filteredSurfaces = computed(() =>
  surfaces.value.filter((s) => hostStore.themeSurfaces.includes(s.name)),
)

// ── Profile ──────────────────────────────────────────────────────────────────

const form = reactive({
  full_name: '',
  username: '',
  email: '',
  date_format: '' as string,
  start_page: '' as string,
  theme_preset: null as string | null,
  theme_primary: null as string | null,
  theme_surface: null as string | null,
  theme_dark_mode: false,
  button_flat_style: false,
  table_gridlines: false,
  table_striped_rows: false,
})

watch(
  () => userStore.user,
  (user) => {
    if (!user) return
    form.full_name = user.full_name
    form.username = user.username
    form.email = user.email
    form.date_format = user.date_format
    form.start_page = user.start_page
    form.theme_preset = user.theme_preset
    form.theme_primary = user.theme_primary
    form.theme_surface = user.theme_surface
    form.theme_dark_mode = user.theme_dark_mode
    form.button_flat_style = user.button_flat_style
    form.table_gridlines = user.table_gridlines
    form.table_striped_rows = user.table_striped_rows
  },
  { immediate: true },
)

// ── Visual aids preview ─────────────────────────────────────────────────────

const previewRows = [
  { name: 'Alpha', status: 'Active', quantity: 12 },
  { name: 'Bravo', status: 'Pending', quantity: 4 },
  { name: 'Charlie', status: 'Active', quantity: 7 },
]

const saving = ref(false)

// The sections features register, such as the time tracking credentials,
// each decide for themselves whether they apply to the signed-in user. A
// mounted section's handle is kept by its key, so Save reaches it.
const sectionHandles = shallowReactive(new Map<string, AccountSectionHandle>())

const sections = useRegisteredAccountSections().map((section) => ({
  section,
  visible: section.useVisible(),
  setHandle(el: Element | ComponentPublicInstance | null): void {
    if (el) sectionHandles.set(section.key, el as unknown as AccountSectionHandle)
    else sectionHandles.delete(section.key)
  },
}))
const visibleSections = computed(() => sections.filter(({ visible }) => visible.value))

const sectionsSaving = computed(() => [...sectionHandles.values()].some((handle) => handle.saving))

// A registered section saves on its own when it changed, alongside the
// profile and with its own toasts, so a refused time tracking sign-in never
// blocks the profile fields and its consent dialog never holds them back.
async function onSave() {
  const sectionSaves = [...sectionHandles.values()]
    .filter((handle) => handle.isDirty)
    .map((handle) => handle.save())
  await Promise.all([saveProfile(), ...sectionSaves])
}

async function saveProfile() {
  saving.value = true
  try {
    const updated = await updateCurrentUser({
      full_name: form.full_name,
      username: form.username,
      email: form.email,
      // The pickers only offer server values from these closed vocabularies, so
      // the value is cast at this boundary.
      date_format: (form.date_format || null) as DateFormatPreset | null,
      start_page: form.start_page as Schemas['StartPage'],
      theme_preset: form.theme_preset as Schemas['ThemePreset'] | null,
      theme_primary: form.theme_primary as Schemas['ThemePrimary'] | null,
      theme_surface: form.theme_surface as Schemas['ThemeSurface'] | null,
      theme_dark_mode: form.theme_dark_mode,
      button_flat_style: form.button_flat_style,
      table_gridlines: form.table_gridlines,
      table_striped_rows: form.table_striped_rows,
    })
    userStore.user = updated
    // Re-point the date formatters immediately, so dates already on screen
    // re-render in the newly chosen format without a reload.
    setDisplayDateFormat(updated.date_format)
    applyUserTheme(
      updated.theme_preset,
      updated.theme_primary,
      updated.theme_surface,
      updated.theme_dark_mode,
    )
    applyVisualAids(updated.button_flat_style, updated.table_gridlines, updated.table_striped_rows)
    appToast.success(t('accountMe.saved'))
  } catch {
    appToast.error(t('accountMe.errors.unknown'))
  } finally {
    saving.value = false
  }
}

// ── Password dialog ───────────────────────────────────────────────────────────

/**
 * A directory account has no local password, so the button is hidden.
 */
const canChangePassword = computed(() => userStore.user?.auth_provider !== 'ldap')

const passwordDialogVisible = ref(false)

// ── Avatar ───────────────────────────────────────────────────────────────────

const avatarInput = ref<HTMLInputElement | null>(null)
const uploadingAvatar = ref(false)
const deletingAvatar = ref(false)

function openAvatarPicker() {
  avatarInput.value?.click()
}

async function onAvatarSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingAvatar.value = true
  try {
    const updated = await uploadAvatar(file)
    userStore.user = updated
    avatarsStore.invalidate(updated.id)
    appToast.success(t('accountMe.avatarUpdated'))
  } catch {
    appToast.error(t('accountMe.errors.avatarUploadFailed'))
  } finally {
    uploadingAvatar.value = false
    input.value = ''
  }
}

async function onDeleteAvatar() {
  if (deletingAvatar.value) return
  if (!(await confirmDelete(t('accountMe.avatar.photoName')))) return
  deletingAvatar.value = true
  try {
    const updated = await deleteAvatar()
    userStore.user = updated
    avatarsStore.invalidate(updated.id)
    appToast.success(t('accountMe.avatarRemoved'))
  } catch {
    appToast.error(t('accountMe.errors.unknown'))
  } finally {
    deletingAvatar.value = false
  }
}

function getInitials(): string {
  const name = userStore.user?.full_name ?? userStore.user?.username ?? ''
  return name
    .split(' ')
    .map((p) => p[0] ?? '')
    .join('')
    .toUpperCase()
    .slice(0, 2)
}
</script>

<template>
  <PageLayout>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.save')"
            icon="mdi mdi-content-save"
            :loading="saving || sectionsSaving"
            severity="contrast"
            text
            @click="onSave"
          />
          <template v-if="!phoneMode">
            <Button
              v-if="canChangePassword"
              :label="t('accountMe.password.changeButton')"
              icon="mdi mdi-lock-reset"
              severity="contrast"
              text
              @click="passwordDialogVisible = true"
            />
            <span v-else class="password-ldap-note">
              <i class="mdi mdi-shield-account" aria-hidden="true" />
              {{ t('accountMe.password.ldapManaged') }}
            </span>
            <input
              ref="avatarInput"
              type="file"
              aria-hidden="true"
              tabindex="-1"
              accept="image/jpeg,image/png,image/webp,image/gif"
              class="avatar-file-input"
              @change="onAvatarSelected"
            />
            <Button
              :label="t('accountMe.avatar.upload')"
              icon="mdi mdi-upload"
              severity="contrast"
              text
              :loading="uploadingAvatar"
              :disabled="!hostStore.storageEnabled"
              @click="openAvatarPicker"
            />
            <Button
              v-if="userStore.user?.has_avatar"
              :label="t('accountMe.avatar.remove')"
              icon="mdi mdi-delete-outline"
              severity="danger"
              text
              :loading="deletingAvatar"
              :disabled="!hostStore.storageEnabled"
              @click="onDeleteAvatar"
            />
          </template>
        </template>
        <template #end>
          <HelpButton slug="account/me" rounded />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <template v-if="!phoneMode">
        <!-- Avatar row -->
        <div class="field-row">
          <span class="field-caption">{{ t('accountMe.avatar.title') }}</span>
          <div class="avatar-cell">
            <div class="avatar-preview">
              <UserAvatar
                :user-id="userStore.user?.id ?? 0"
                :has-avatar="userStore.user?.has_avatar ?? false"
                img-class="avatar-image"
              >
                <div class="avatar-initials">{{ getInitials() }}</div>
              </UserAvatar>
            </div>
            <span v-if="!hostStore.storageEnabled" class="storage-hint">
              <i class="mdi mdi-information-outline" aria-hidden="true" />
              {{ t('accountMe.avatar.storageDisabled') }}
            </span>
          </div>
        </div>

        <Divider />

        <!-- Profile fields -->
        <div class="field-row">
          <label :for="`${uid}-full-name`">{{ t('accountMe.profile.fullName') }}</label>
          <InputText v-model="form.full_name" :id="`${uid}-full-name`" />
        </div>
        <div class="field-row">
          <label :for="`${uid}-username`">{{ t('accountMe.profile.username') }}</label>
          <InputText v-model="form.username" :id="`${uid}-username`" />
        </div>
        <div class="field-row">
          <label :for="`${uid}-email`">{{ t('accountMe.profile.email') }}</label>
          <InputText v-model="form.email" :id="`${uid}-email`" type="email" />
        </div>

        <Divider />

        <!-- Regional -->
        <div class="field-row">
          <label :id="`${uid}-date-format-label`" :for="`${uid}-date-format`">
            {{ t('accountMe.regional.dateFormat') }}
          </label>
          <div class="regional-field">
            <Select
              v-model="form.date_format"
              :input-id="`${uid}-date-format`"
              :aria-labelledby="`${uid}-date-format-label`"
              :options="dateFormatOptions"
              option-label="label"
              option-value="value"
              :placeholder="t('accountMe.regional.dateFormatPlaceholder')"
              fluid
            />
            <small class="regional-hint">
              {{ t('accountMe.regional.dateFormatHint') }}
              <template v-if="dateFormatPreview">
                {{ t('accountMe.regional.dateFormatExample', { date: dateFormatPreview }) }}
              </template>
            </small>
          </div>
        </div>
        <div class="field-row">
          <label :id="`${uid}-start-page-label`" :for="`${uid}-start-page`">
            {{ t('accountMe.regional.startPage') }}
          </label>
          <div class="regional-field">
            <Select
              v-model="form.start_page"
              :input-id="`${uid}-start-page`"
              :aria-labelledby="`${uid}-start-page-label`"
              :options="startPageOptions"
              option-label="label"
              option-value="value"
              :placeholder="t('accountMe.regional.startPagePlaceholder')"
              fluid
            />
            <small class="regional-hint">{{ t('accountMe.regional.startPageHint') }}</small>
          </div>
        </div>

        <template v-for="{ section, setHandle } in visibleSections" :key="section.key">
          <Divider />
          <component :is="section.component" :ref="setHandle" />
        </template>

        <Divider />
      </template>

      <!-- Theme fields -->
      <div class="field-row">
        <label :id="`${uid}-preset-label`" :for="`${uid}-preset`">{{ t('accountMe.theme.preset') }}</label>
        <Select
          v-model="form.theme_preset"
          :input-id="`${uid}-preset`"
          :aria-labelledby="`${uid}-preset-label`"
          :options="presetOptions"
          fluid
        />
      </div>
      <div class="field-row">
        <label for="account-dark-mode">{{ t('accountMe.theme.darkMode') }}</label>
        <ToggleSwitch v-model="form.theme_dark_mode" input-id="account-dark-mode" />
      </div>
      <div class="field-row">
        <label :id="`${uid}-primary-label`" :for="`${uid}-primary`">{{ t('accountMe.theme.primary') }}</label>
        <Select
          v-model="form.theme_primary"
          :input-id="`${uid}-primary`"
          :aria-labelledby="`${uid}-primary-label`"
          :options="filteredPrimaryColors"
          option-label="name"
          option-value="name"
          fluid
        >
          <template #option="{ option }">
            <div class="color-option">
              <span class="color-swatch" :style="{ background: option.palette[500] }" />
              {{ option.name }}
            </div>
          </template>
        </Select>
      </div>
      <div class="field-row">
        <label :id="`${uid}-surface-label`" :for="`${uid}-surface`">{{ t('accountMe.theme.surface') }}</label>
        <Select
          v-model="form.theme_surface"
          :input-id="`${uid}-surface`"
          :aria-labelledby="`${uid}-surface-label`"
          :options="filteredSurfaces"
          option-label="name"
          option-value="name"
          fluid
        >
          <template #option="{ option }">
            <div class="color-option">
              <span class="color-swatch" :style="{ background: option.palette[500] }" />
              {{ option.name }}
            </div>
          </template>
        </Select>
      </div>

      <template v-if="!phoneMode">
        <Divider />

        <!-- Visual aids -->
        <div class="visual-aids-section">
          <div class="visual-aids-toggles">
            <div class="field-row">
              <label for="account-button-flat-style">{{ t('accountMe.visualAids.buttonFlatStyle') }}</label>
              <ToggleSwitch v-model="form.button_flat_style" input-id="account-button-flat-style" />
            </div>
            <div class="field-row">
              <label for="account-table-gridlines">{{ t('accountMe.visualAids.tableGridlines') }}</label>
              <ToggleSwitch v-model="form.table_gridlines" input-id="account-table-gridlines" />
            </div>
            <div class="field-row">
              <label for="account-table-striped-rows">{{ t('accountMe.visualAids.tableLineColoring') }}</label>
              <ToggleSwitch v-model="form.table_striped_rows" input-id="account-table-striped-rows" />
            </div>
          </div>
        </div>

        <div class="visual-aids-preview-card">
          <span class="section-label">{{ t('accountMe.visualAids.previewLabel') }}</span>
          <div class="visual-aids-preview-buttons">
            <Button
              severity="contrast"
              :text="form.button_flat_style"
              icon="mdi mdi-check"
              :label="t('accountMe.visualAids.previewButton')"
            />
            <SplitButton
              severity="contrast"
              :text="form.button_flat_style"
              :label="t('accountMe.visualAids.previewButton')"
              :model="[]"
            />
          </div>
          <DataTable
            :value="previewRows"
            :show-gridlines="form.table_gridlines"
            :striped-rows="form.table_striped_rows"
            size="small"
          >
            <Column field="name" :header="t('accountMe.visualAids.previewColumnName')" />
            <Column field="status" :header="t('accountMe.visualAids.previewColumnStatus')" />
            <Column field="quantity" :header="t('accountMe.visualAids.previewColumnQuantity')" />

            <template #empty>
              <EmptyState />
            </template>
          </DataTable>
        </div>
      </template>
    </div>
  </PageLayout>

  <AccountPasswordDialog v-model:visible="passwordDialogVisible" />
</template>

<style scoped lang="scss">
.password-ldap-note {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-3);
  font-size: var(--font-size-sm);
  opacity: 0.75;
}

// This settings form uses 1rem card padding. The form is taller than the
// viewport on most screens, so the card grows with it instead of keeping the
// global `.card` height: 100%, which let the lower fields spill out of it.
:deep(.view-data > .card) {
  padding: var(--space-4);
  height: auto;
  min-height: 100%;
}

// ── Avatar cell ───────────────────────────────────────────────────────────────

.avatar-cell {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.avatar-preview {
  flex-shrink: 0;
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 50%;
  overflow: hidden;
  background-color: var(--p-primary-500);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-initials {
  font-size: var(--font-size-lg);
  font-weight: 700;
  color: var(--on-accent);
  letter-spacing: 0.05em;
}

.avatar-file-input {
  display: none;
}

.storage-hint {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

// ── Theme fields ──────────────────────────────────────────────────────────────

.color-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.color-swatch {
  width: 0.9rem;
  height: 0.9rem;
  border-radius: 50%;
  flex-shrink: 0;
  border: 1px solid var(--p-content-border-color);
}

// ── Visual aids ───────────────────────────────────────────────────────────────

.visual-aids-section {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: var(--space-5);
}

.visual-aids-toggles {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.visual-aids-preview-card {
  flex: 1;
  min-width: 0;
  max-width: 41rem;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background-color: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  margin-top: var(--space-4);
}

.visual-aids-preview-buttons {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

// ── Regional ─────────────────────────────────────────────────────────────────

// Each picker stacks a hint under itself, so this cell is a column rather
// than the row's default centred cell.
.regional-field {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
  min-width: 0;
}

.regional-hint {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}
</style>
