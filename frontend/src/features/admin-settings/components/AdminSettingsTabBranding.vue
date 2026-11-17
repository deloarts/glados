<script setup lang="ts">
import { reactive, ref, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useConfirmDelete } from '@/shared/composables/useConfirmDelete'
import { useHostStore } from '@/core/host/stores/hostStore'
import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'
import { useSettingsSave } from '../composables/useSettingsSave'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''
const LOGIN_VIDEO_URL = `${API_ROOT}/api/v1/public/branding/login-video`
const LOGO_URL = `${API_ROOT}/api/v1/public/branding/logo`
const FAVICON_URL = `${API_ROOT}/api/v1/public/branding/favicon`

const { t } = useI18n()
const { confirmDelete } = useConfirmDelete()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const appToast = useAppToast()
const store = useAdminSettingsStore()
const hostStore = useHostStore()
const publicBrandingStore = usePublicBrandingStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)
// Without write:settings the tab's controls stay visible but disabled,
// naming the missing permission.
const writeBlocked = useMissingPermission().missing(Permission.WRITE_SETTINGS)

interface Form {
  app_name: string
  app_description: string
  footer_text: string
}

const form = reactive<Form>({
  app_name: '',
  app_description: '',
  footer_text: '',
})

watch(
  () => store.settings?.branding,
  (b) => {
    if (!b) return
    form.app_name = b.app_name
    form.app_description = b.app_description ?? ''
    form.footer_text = b.footer_text ?? ''
  },
  { immediate: true },
)

const { saving, onSave } = useSettingsSave(() =>
  store.saveBranding({
    app_name: form.app_name.trim(),
    app_description: form.app_description.trim() || null,
    footer_text: form.footer_text.trim() || null,
  }),
)

// ── Logo ──────────────────────────────────────────────────────────────────

const logoInput = ref<HTMLInputElement | null>(null)
const uploadingLogo = ref(false)
const deletingLogo = ref(false)

function openLogoPicker() {
  logoInput.value?.click()
}

async function onLogoSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingLogo.value = true
  try {
    await store.uploadLogo(file)
    await publicBrandingStore.fetch()
    appToast.success(t('adminSettings.branding.logo.uploaded'))
  } catch {
    appToast.error(t('adminSettings.branding.logo.uploadFailed'))
  } finally {
    uploadingLogo.value = false
    input.value = ''
  }
}

async function onDeleteLogo() {
  if (deletingLogo.value) return
  if (!(await confirmDelete(t('adminSettings.branding.logo.name')))) return
  deletingLogo.value = true
  try {
    await store.deleteLogo()
    await publicBrandingStore.fetch()
    appToast.success(t('adminSettings.branding.logo.removed'))
  } catch {
    appToast.error(t('adminSettings.branding.logo.removeFailed'))
  } finally {
    deletingLogo.value = false
  }
}

// ── Favicon ───────────────────────────────────────────────────────────────

const faviconInput = ref<HTMLInputElement | null>(null)
const uploadingFavicon = ref(false)
const deletingFavicon = ref(false)

function openFaviconPicker() {
  faviconInput.value?.click()
}

async function onFaviconSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingFavicon.value = true
  try {
    await store.uploadFavicon(file)
    await publicBrandingStore.fetch()
    appToast.success(t('adminSettings.branding.favicon.uploaded'))
  } catch {
    appToast.error(t('adminSettings.branding.favicon.uploadFailed'))
  } finally {
    uploadingFavicon.value = false
    input.value = ''
  }
}

async function onDeleteFavicon() {
  if (deletingFavicon.value) return
  if (!(await confirmDelete(t('adminSettings.branding.favicon.name')))) return
  deletingFavicon.value = true
  try {
    await store.deleteFavicon()
    await publicBrandingStore.fetch()
    appToast.success(t('adminSettings.branding.favicon.removed'))
  } catch {
    appToast.error(t('adminSettings.branding.favicon.removeFailed'))
  } finally {
    deletingFavicon.value = false
  }
}

// ── Login background video ────────────────────────────────────────────────

const videoInput = ref<HTMLInputElement | null>(null)
const uploadingVideo = ref(false)
const deletingVideo = ref(false)

function openVideoPicker() {
  videoInput.value?.click()
}

async function onVideoSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingVideo.value = true
  try {
    await store.uploadLoginVideo(file)
    appToast.success(t('adminSettings.branding.loginVideo.uploaded'))
  } catch {
    appToast.error(t('adminSettings.branding.loginVideo.uploadFailed'))
  } finally {
    uploadingVideo.value = false
    input.value = ''
  }
}

async function onDeleteVideo() {
  if (deletingVideo.value) return
  if (!(await confirmDelete(t('adminSettings.branding.loginVideo.name')))) return
  deletingVideo.value = true
  try {
    await store.deleteLoginVideo()
    appToast.success(t('adminSettings.branding.loginVideo.removed'))
  } catch {
    appToast.error(t('adminSettings.branding.loginVideo.removeFailed'))
  } finally {
    deletingVideo.value = false
  }
}
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
            :disabled="!canWrite"
            @click="onSave"
          />

          <template v-if="hostStore.storageEnabled">
            <Divider layout="vertical" />

            <span v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('adminSettings.branding.logo.upload')"
                icon="mdi mdi-image-plus-outline"
                severity="contrast"
                text
                :loading="uploadingLogo"
                :disabled="!canWrite"
                @click="openLogoPicker"
              />
            </span>
            <span v-if="store.settings?.branding.has_logo" v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('adminSettings.branding.logo.remove')"
                icon="mdi mdi-image-remove-outline"
                severity="danger"
                outlined
                :loading="deletingLogo"
                :disabled="!canWrite"
                @click="onDeleteLogo"
              />
            </span>

            <Divider layout="vertical" />

            <span v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('adminSettings.branding.favicon.upload')"
                icon="mdi mdi-web-plus"
                severity="contrast"
                text
                :loading="uploadingFavicon"
                :disabled="!canWrite"
                @click="openFaviconPicker"
              />
            </span>
            <span v-if="store.settings?.branding.has_favicon" v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('adminSettings.branding.favicon.remove')"
                icon="mdi mdi-web-remove"
                severity="danger"
                text
                :loading="deletingFavicon"
                :disabled="!canWrite"
                @click="onDeleteFavicon"
              />
            </span>

            <Divider layout="vertical" />

            <span v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('adminSettings.branding.loginVideo.upload')"
                icon="mdi mdi-video-plus-outline"
                severity="contrast"
                text
                :loading="uploadingVideo"
                :disabled="!canWrite"
                @click="openVideoPicker"
              />
            </span>
            <span v-if="store.settings?.branding.has_login_background_video" v-tooltip.bottom="writeBlocked || undefined">
              <Button
                :label="t('adminSettings.branding.loginVideo.remove')"
                icon="mdi mdi-video-off-outline"
                severity="danger"
                text
                :loading="deletingVideo"
                :disabled="!canWrite"
                @click="onDeleteVideo"
              />
            </span>
          </template>
        </template>
      </Toolbar>

      <!-- Hidden file inputs -->
      <input
        ref="logoInput"
        type="file"
        aria-hidden="true"
        tabindex="-1"
        accept="image/png,image/jpeg,image/svg+xml,image/webp"
        class="file-input"
        @change="onLogoSelected"
      />
      <input
        ref="faviconInput"
        type="file"
        aria-hidden="true"
        tabindex="-1"
        accept="image/x-icon,image/png,image/svg+xml"
        class="file-input"
        @change="onFaviconSelected"
      />
      <input
        ref="videoInput"
        type="file"
        aria-hidden="true"
        tabindex="-1"
        accept="video/mp4,video/webm"
        class="file-input"
        @change="onVideoSelected"
      />
    </template>

    <div class="settings-fields">
      <p class="section-label">{{ t('adminSettings.branding.identitySection') }}</p>
      <div class="field-row">
        <label :for="`${uid}-app-name`">{{ t('adminSettings.branding.appName') }}</label>
        <InputText v-model="form.app_name" :id="`${uid}-app-name`" :disabled="!canWrite" />
      </div>
      <div class="field-row">
        <label :for="`${uid}-app-description`">{{ t('adminSettings.branding.appDescription') }}</label>
        <InputText v-model="form.app_description" :id="`${uid}-app-description`" :disabled="!canWrite" />
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.branding.footerSection') }}</p>
      <div class="field-row">
        <label :for="`${uid}-footer-text`">{{ t('adminSettings.branding.footerText') }}</label>
        <InputText v-model="form.footer_text" :id="`${uid}-footer-text`" :disabled="!canWrite" />
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.branding.assetsSection') }}</p>

      <!-- Logo -->
      <div class="field-row">
        <span class="field-caption">{{ t('adminSettings.branding.logo.title') }}</span>
        <div class="asset-preview">
          <img
            v-if="store.settings?.branding.has_logo"
            :src="LOGO_URL"
            class="image-preview"
            alt="Logo preview"
          />
          <span v-else class="placeholder-icon mdi mdi-image-outline" />
        </div>
      </div>

      <!-- Favicon -->
      <div class="field-row">
        <span class="field-caption">{{ t('adminSettings.branding.favicon.title') }}</span>
        <div class="asset-preview asset-preview--favicon">
          <img
            v-if="store.settings?.branding.has_favicon"
            :src="FAVICON_URL"
            class="favicon-preview"
            alt="Favicon preview"
          />
          <span v-else class="placeholder-icon mdi mdi-web" />
        </div>
      </div>

      <!-- Login background video -->
      <div class="field-row">
        <span class="field-caption">{{ t('adminSettings.branding.loginVideo.title') }}</span>
        <div class="asset-preview asset-preview--video">
          <video
            v-if="store.settings?.branding.has_login_background_video"
            :src="LOGIN_VIDEO_URL"
            class="login-video-preview"
            muted
            loop
            autoplay
            playsinline
          />
          <span v-else class="placeholder-icon mdi mdi-video-outline" />
        </div>
      </div>
    </div>
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
.asset-preview {
  width: 10rem;
  height: 3.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--p-content-border-radius);
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
  overflow: hidden;

  &--favicon {
    width: 3.5rem;
  }

  &--video {
    width: 10rem;
    height: 5.5rem;
  }
}

.placeholder-icon {
  font-size: var(--font-size-2xl);
  color: var(--p-text-muted-color);
  opacity: 0.4;
}

.image-preview,
.favicon-preview {
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: var(--space-1);
}

.login-video-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.file-input {
  display: none;
}
</style>
