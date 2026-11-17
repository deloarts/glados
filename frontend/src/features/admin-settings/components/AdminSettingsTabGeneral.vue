<script setup lang="ts">
import { computed, reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useHostStore } from '@/core/host/stores/hostStore'
import { localeEndonym } from '@/core/i18n/localeMessages'
import { formatPrice, setDisplayCurrency } from '@/core/utils/currency'
import { setDisplayTimezone } from '@/core/utils/dates'
import {
  dateFormatSample,
  dateFormatSelectOptions,
  timezoneNowPreview,
} from '@/shared/utils/dateFormatPreview'
import type { Schemas } from '@/core/api/generated'
import { useSettingsSave } from '../composables/useSettingsSave'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'

// Served unauthenticated, like the branding assets.
const API_ROOT = import.meta.env.VITE_API_URL ?? ''
const COMPANY_LOGO_URL = `${API_ROOT}/api/v1/public/company/logo`

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const store = useAdminSettingsStore()
const hostStore = useHostStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)
// Without write:settings the tab's controls stay visible but disabled,
// naming the missing permission.
const writeBlocked = useMissingPermission().missing(Permission.WRITE_SETTINGS)

interface Form {
  company_name: string
  company_legal_name: string
  contact_email: string
  imprint_url: string
  privacy_url: string
  support_url: string
  allow_headless_projects: boolean
  empty_value_placeholder: string
  office_launcher_enabled: boolean
  office_sharepoint_url: string
  default_language: string
  default_timezone: string
  default_date_format: string
  currency: string
}

const form = reactive<Form>({
  company_name: '',
  company_legal_name: '',
  contact_email: '',
  imprint_url: '',
  privacy_url: '',
  support_url: '',
  allow_headless_projects: true,
  empty_value_placeholder: '-',
  office_launcher_enabled: false,
  office_sharepoint_url: '',
  // Mirrors the backend defaults until the store hydrates the form.
  default_language: 'enGB',
  default_timezone: 'Europe/Vienna',
  default_date_format: 'iso',
  currency: 'EUR',
})

watch(
  () => store.settings?.general,
  (s) => {
    if (!s) return
    form.company_name = s.company_name ?? ''
    form.company_legal_name = s.company_legal_name ?? ''
    form.contact_email = s.contact_email ?? ''
    form.imprint_url = s.imprint_url ?? ''
    form.privacy_url = s.privacy_url ?? ''
    form.support_url = s.support_url ?? ''
    form.allow_headless_projects = s.allow_headless_projects
    form.empty_value_placeholder = s.empty_value_placeholder
    form.office_launcher_enabled = s.office_launcher_enabled
    form.office_sharepoint_url = s.office_sharepoint_url
    form.default_language = s.default_language
    form.default_timezone = s.default_timezone
    form.default_date_format = s.default_date_format
    form.currency = s.currency
  },
  { immediate: true },
)

// An empty placeholder is a valid choice, so the preview spells it out instead
// of showing a blank.
const placeholderPreview = computed(() =>
  form.empty_value_placeholder === ''
    ? t('adminSettings.general.emptyValuePlaceholderNothing')
    : form.empty_value_placeholder,
)

// ── Locales ──────────────────────────────────────────────────────────
const languageOptions = computed(() =>
  hostStore.languages.map((code) => ({ value: code, label: localeEndonym(code, true) })),
)

const dateFormatOptions = computed(() => dateFormatSelectOptions(hostStore.dateFormats))

const dateFormatPreview = computed(() => dateFormatSample(form.default_date_format))

const timezonePreview = computed(() => timezoneNowPreview(form.default_timezone))

// ── Currency ─────────────────────────────────────────────────────────
// Common ISO 4217 codes; the Select stays editable for any other valid code.
const CURRENCY_CODES = [
  'EUR',
  'USD',
  'GBP',
  'CHF',
  'SEK',
  'NOK',
  'DKK',
  'PLN',
  'CZK',
  'HUF',
  'JPY',
  'CNY',
]

const CURRENCY_SHAPE = /^[A-Z]{3}$/

// Normalises on every keystroke so the preview reflects what will be sent.
const currencyModel = computed<string>({
  get: () => form.currency,
  set: (value) => {
    form.currency = (value ?? '').trim().toUpperCase()
  },
})

const currencyInvalid = computed(() => !CURRENCY_SHAPE.test(form.currency))

// Shown only for a well-shaped code, so a half-typed edit shows nothing.
const currencyPreview = computed(() => {
  if (currencyInvalid.value) return ''
  try {
    return formatPrice(123456, undefined, form.currency)
  } catch {
    // Intl does not know this well-shaped code.
    return ''
  }
})

// ── Company logo ────────────────────────────────────────────────────
// The URL is stable and cached for an hour, so the preview is cache-busted on
// every change.
const logoInput = ref<HTMLInputElement | null>(null)
const uploadingLogo = ref(false)
const deletingLogo = ref(false)
const logoCacheBuster = ref(Date.now())

const logoSrc = computed(() => `${COMPANY_LOGO_URL}?v=${logoCacheBuster.value}`)

function openLogoPicker() {
  logoInput.value?.click()
}

async function onLogoSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  uploadingLogo.value = true
  try {
    await store.uploadCompanyLogoFile(file)
    logoCacheBuster.value = Date.now()
    appToast.success(t('adminSettings.general.companyLogo.uploaded'))
  } catch {
    appToast.error(t('adminSettings.general.companyLogo.uploadFailed'))
  } finally {
    uploadingLogo.value = false
    // Cleared so picking the same file again still fires a change event.
    input.value = ''
  }
}

async function onLogoRemove() {
  deletingLogo.value = true
  try {
    await store.removeCompanyLogo()
    logoCacheBuster.value = Date.now()
    appToast.success(t('adminSettings.general.companyLogo.removed'))
  } catch {
    appToast.error(t('adminSettings.general.companyLogo.uploadFailed'))
  } finally {
    deletingLogo.value = false
  }
}

// Empty strings are sent as null so clearing a field clears the stored value.
function orNull(value: string): string | null {
  return value.trim() === '' ? null : value.trim()
}

// The PUT is partial and sends only this tab's fields, so it never clobbers the
// number patterns the Numbering tab owns in the same domain.
const { saving, onSave } = useSettingsSave(async () => {
  const result = await store.saveGeneral({
    company_name: orNull(form.company_name),
    company_legal_name: orNull(form.company_legal_name),
    contact_email: orNull(form.contact_email),
    imprint_url: orNull(form.imprint_url),
    privacy_url: orNull(form.privacy_url),
    support_url: orNull(form.support_url),
    allow_headless_projects: form.allow_headless_projects,
    empty_value_placeholder: form.empty_value_placeholder,
    // Not orNull(): an empty URL means "hide the tile", while null means
    // "leave unchanged" and could never clear the field.
    office_launcher_enabled: form.office_launcher_enabled,
    office_sharepoint_url: form.office_sharepoint_url.trim(),
    // Always strings, these defaults have no unset state. The pickers only
    // offer values from /host/values, so the casts are safe.
    default_language: form.default_language as Schemas['Language'],
    default_timezone: form.default_timezone,
    default_date_format: form.default_date_format as Schemas['DateFormat'],
    currency: form.currency,
  })
  // hostStore.fetch() loads only once and survives logout, so the saved values
  // are pushed into it to take effect without a reload.
  hostStore.officeLauncherEnabled = result.office_launcher_enabled
  hostStore.officeSharepointUrl = result.office_sharepoint_url
  // i18n.global.locale stays untouched, since the admin's own session
  // language is not the tenant default.
  hostStore.defaultLanguage = result.default_language
  hostStore.defaultTimezone = result.default_timezone
  setDisplayTimezone(result.default_timezone)
  hostStore.defaultDateFormat = result.default_date_format
  hostStore.currency = result.currency
  setDisplayCurrency(result.currency)
  return result
})
</script>

<template>
  <AdminSettingsTabShell>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.save')"
            icon="mdi mdi-content-save"
            text
            severity="contrast"
            :loading="saving"
            :disabled="!canWrite || currencyInvalid"
            @click="onSave"
          />

          <template v-if="hostStore.storageEnabled">
            <Divider layout="vertical" />

            <span v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('adminSettings.general.companyLogo.upload')"
                icon="mdi mdi-image-plus-outline"
                severity="contrast"
                text
                :loading="uploadingLogo"
                :disabled="!canWrite"
                @click="openLogoPicker"
              />
            </span>
            <span v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('adminSettings.general.companyLogo.remove')"
                icon="mdi mdi-image-remove-outline"
                severity="danger"
                text
                :loading="deletingLogo"
                :disabled="!canWrite || !store.settings?.general.has_company_logo"
                @click="onLogoRemove"
              />
            </span>
          </template>
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="section-label">{{ t('adminSettings.general.companySection') }}</p>
      <div class="field-row">
        <label for="general-company-name">{{ t('adminSettings.general.companyName') }}</label>
        <InputText id="general-company-name" v-model="form.company_name" :disabled="!canWrite" />
      </div>
      <div class="field-row">
        <label for="general-company-legal-name">
          {{ t('adminSettings.general.companyLegalName') }}
          <small class="hint">{{ t('adminSettings.general.companyLegalNameHint') }}</small>
        </label>
        <InputText
          id="general-company-legal-name"
          v-model="form.company_legal_name"
          :disabled="!canWrite"
        />
      </div>

      <div class="field-row">
        <label :for="`${uid}-company-logo`">{{ t('adminSettings.general.companyLogo.label') }}</label>
        <div class="asset-row">
          <img
            v-if="store.settings?.general.has_company_logo"
            :src="logoSrc"
            alt=""
            class="logo-preview"
          />
          <span v-else-if="!hostStore.storageEnabled" class="hint">
            {{ t('adminSettings.general.companyLogo.storageDisabled') }}
          </span>
          <span v-else class="hint">{{ t('adminSettings.general.companyLogo.none') }}</span>
        </div>
        <!-- Driven by the upload button in the controls bar above. -->
        <input
          ref="logoInput"
          :id="`${uid}-company-logo`"
          type="file"
          accept="image/png,image/jpeg,image/svg+xml,image/webp"
          hidden
          @change="onLogoSelected"
        />
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.general.contactSection') }}</p>
      <div class="field-row">
        <label for="general-contact-email">{{ t('adminSettings.general.contactEmail') }}</label>
        <InputText
          id="general-contact-email"
          v-model="form.contact_email"
          type="email"
          :disabled="!canWrite"
        />
      </div>
      <div class="field-row">
        <label for="general-support-url">{{ t('adminSettings.general.supportUrl') }}</label>
        <InputText id="general-support-url" v-model="form.support_url" :disabled="!canWrite" />
      </div>
      <div class="field-row">
        <label for="general-imprint-url">{{ t('adminSettings.general.imprintUrl') }}</label>
        <InputText id="general-imprint-url" v-model="form.imprint_url" :disabled="!canWrite" />
      </div>
      <div class="field-row">
        <label for="general-privacy-url">{{ t('adminSettings.general.privacyUrl') }}</label>
        <InputText id="general-privacy-url" v-model="form.privacy_url" :disabled="!canWrite" />
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.general.projectsSection') }}</p>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-allow-headless-projects`">{{ t('adminSettings.general.allowHeadlessProjects') }}</label>
        <ToggleSwitch
          v-model="form.allow_headless_projects"
          :input-id="`${uid}-allow-headless-projects`"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.general.allowHeadlessProjectsHint') }}</small>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.general.displaySection') }}</p>
      <div class="field-row">
        <label for="general-empty-placeholder">
          {{ t('adminSettings.general.emptyValuePlaceholder') }}
        </label>
        <div class="field-input-row">
          <InputText
            id="general-empty-placeholder"
            v-model="form.empty_value_placeholder"
            class="placeholder-input"
            maxlength="16"
            :disabled="!canWrite"
          />
          <span class="field-example">
            {{ t('adminSettings.general.preview') }}:
            <span class="preview-value">{{ placeholderPreview }}</span>
          </span>
        </div>
        <small class="hint">{{ t('adminSettings.general.emptyValuePlaceholderHint') }}</small>
      </div>
      <div class="field-row">
        <label id="general-currency-label" for="general-currency">{{ t('adminSettings.general.currency') }}</label>
        <div class="field-input-row">
          <Select
            id="general-currency"
            aria-labelledby="general-currency-label"
            v-model="currencyModel"
            editable
            :options="CURRENCY_CODES"
            :disabled="!canWrite"
            :invalid="currencyInvalid"
            class="currency-select"
          />
          <span v-if="currencyPreview" class="field-example">
            {{ t('adminSettings.general.preview') }}:
            <span class="preview-value">{{ currencyPreview }}</span>
          </span>
        </div>
        <small class="hint">
          {{ t('adminSettings.general.currencyHint') }}
          <template v-if="currencyInvalid">
            {{ t('adminSettings.general.currencyInvalid') }}
          </template>
        </small>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.general.localesSection') }}</p>
      <div class="field-row">
        <label id="general-default-language-label" for="general-default-language">
          {{ t('adminSettings.general.defaultLanguage') }}
        </label>
        <Select
          id="general-default-language"
          aria-labelledby="general-default-language-label"
          v-model="form.default_language"
          :options="languageOptions"
          option-label="label"
          option-value="value"
          :disabled="!canWrite"
          fluid
        />
        <small class="hint">{{ t('adminSettings.general.defaultLanguageHint') }}</small>
      </div>
      <div class="field-row">
        <label id="general-default-timezone-label" for="general-default-timezone">
          {{ t('adminSettings.general.defaultTimezone') }}
        </label>
        <div class="field-input-row">
          <Select
            id="general-default-timezone"
            aria-labelledby="general-default-timezone-label"
            v-model="form.default_timezone"
            :options="hostStore.timezones"
            :filter="true"
            filter-match-mode="contains"
            :disabled="!canWrite"
            fluid
          />
          <span v-if="timezonePreview" class="field-example">
            {{ t('adminSettings.general.preview') }}:
            <span class="preview-value">{{ timezonePreview }}</span>
          </span>
        </div>
        <small class="hint">{{ t('adminSettings.general.defaultTimezoneHint') }}</small>
      </div>
      <div class="field-row">
        <label id="general-default-date-format-label" for="general-default-date-format">
          {{ t('adminSettings.general.defaultDateFormat') }}
        </label>
        <div class="field-input-row">
          <Select
            id="general-default-date-format"
            aria-labelledby="general-default-date-format-label"
            v-model="form.default_date_format"
            :options="dateFormatOptions"
            option-label="label"
            option-value="value"
            :disabled="!canWrite"
            fluid
          />
          <span v-if="dateFormatPreview" class="field-example">
            {{ t('adminSettings.general.preview') }}:
            <span class="preview-value">{{ dateFormatPreview }}</span>
          </span>
        </div>
        <small class="hint">{{ t('adminSettings.general.defaultDateFormatHint') }}</small>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.general.officeSection') }}</p>
      <div class="field-row field-row--toggle">
        <label :for="`${uid}-office-launcher-enabled`">{{ t('adminSettings.general.officeLauncherEnabled') }}</label>
        <ToggleSwitch
          v-model="form.office_launcher_enabled"
          :input-id="`${uid}-office-launcher-enabled`"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.general.officeLauncherEnabledHint') }}</small>
      </div>
      <div class="field-row">
        <label for="general-office-sharepoint-url">
          {{ t('adminSettings.general.officeSharepointUrl') }}
        </label>
        <InputText
          id="general-office-sharepoint-url"
          v-model="form.office_sharepoint_url"
          :disabled="!canWrite"
        />
        <small class="hint">{{ t('adminSettings.general.officeSharepointUrlHint') }}</small>
      </div>
    </div>
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
.field-input-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.placeholder-input {
  max-width: 8rem;
}

.currency-select {
  max-width: 8rem;
}

.field-example {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.preview-value {
  font-family: monospace;
  color: var(--p-text-color);
}

.asset-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.logo-preview {
  max-height: 3rem;
  max-width: 12rem;
  object-fit: contain;
}
</style>
