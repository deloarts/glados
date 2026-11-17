<script setup lang="ts">
// The EPLAN Data Portal tab: the organisation's personal access token and
// how items from the portal are filled. The token is write-only; the field
// stays empty and saving it empty keeps the stored one, while the remove
// button clears it, which also switches the lookups off. The settings are
// loaded here, not with the aggregate, since no other tab needs them.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { useHostStore } from '@/core/host/stores/hostStore'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { extractApiError } from '@/core/utils/errors'
import { AdminSettingsTabShell, useAdminSettingsStore } from '@/features/admin-settings'
import type { AdminEdpSettings } from '@/features/admin-settings'
import { useArticleGroupsStore } from '@/features/article-groups'
import { labelName } from '@/shared/utils/localizeLabel'

const { t } = useI18n()
const toast = useAppToast()
const store = useAdminSettingsStore()
const articleGroupsStore = useArticleGroupsStore()
const hostStore = useHostStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

const form = reactive({
  enabled: false,
  base_url: '',
  pat: '',
  default_article_group_ids: [] as number[],
  language: 'de_DE' as 'de_DE' | 'en_US',
})

const languages = computed(() => [
  { value: 'de_DE', label: t('adminSettings.eplanDataPortal.languages.de_DE') },
  { value: 'en_US', label: t('adminSettings.eplanDataPortal.languages.en_US') },
])

const patConfigured = computed(() => store.edp?.pat_configured ?? false)
const liveArticleGroups = computed(() => articleGroupsStore.items.filter((g) => !g.archived))

watch(
  () => store.edp,
  (settings: AdminEdpSettings | null) => {
    if (!settings) return
    form.enabled = settings.enabled
    form.base_url = settings.base_url
    form.pat = ''
    form.default_article_group_ids = [...settings.default_article_group_ids]
    form.language = settings.language === 'en_US' ? 'en_US' : 'de_DE'
  },
  { immediate: true },
)

onMounted(() => {
  void store.fetchEdp()
  if (articleGroupsStore.items.length === 0) void articleGroupsStore.refresh()
})

function errorDetail(err: unknown): string | undefined {
  return extractApiError(err) ?? undefined
}

// ── Save ────────────────────────────────────────────────────────────────

const saving = ref(false)

async function save(pat: string | null): Promise<void> {
  saving.value = true
  try {
    const result = await store.saveEdp({
      enabled: form.enabled,
      base_url: form.base_url.trim(),
      pat,
      default_article_group_ids: form.default_article_group_ids,
      language: form.language,
    })
    // The capabilities are read once per app load; mirror the new state so
    // the Data Portal surfaces follow without a reload.
    hostStore.edpEnabled = result.enabled && result.is_configured
    toast.success(t('adminSettings.saved'))
  } catch (err: unknown) {
    toast.error(t('adminSettings.errors.unknown'), errorDetail(err))
  } finally {
    saving.value = false
  }
}

function onSave(): void {
  void save(form.pat.trim() || null)
}

function onRemoveToken(): void {
  form.enabled = false
  void save('')
}

// ── Test connection ─────────────────────────────────────────────────────

const testing = ref(false)

async function onTest(): Promise<void> {
  testing.value = true
  try {
    await store.testEdp({
      base_url: form.base_url.trim() || null,
      pat: form.pat.trim() || null,
    })
    toast.success(t('adminSettings.eplanDataPortal.testSuccess'))
  } catch (err: unknown) {
    toast.error(t('adminSettings.eplanDataPortal.testFailed'), errorDetail(err))
  } finally {
    testing.value = false
  }
}

const canTest = computed(() => canWrite && (patConfigured.value || !!form.pat.trim()))
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
            data-testid="edp-save"
            @click="onSave"
          />
          <Button
            :label="t('adminSettings.eplanDataPortal.testConnection')"
            icon="mdi mdi-lan-connect"
            text
            severity="contrast"
            :loading="testing"
            :disabled="!canTest"
            data-testid="edp-test"
            @click="onTest"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="hint">{{ t('adminSettings.eplanDataPortal.intro') }}</p>

      <p class="section-label">{{ t('adminSettings.eplanDataPortal.connectionSection') }}</p>

      <div class="field-row field-row--toggle">
        <label for="edp-enabled">
          {{ t('adminSettings.eplanDataPortal.enabled') }}
          <span class="hint">{{ t('adminSettings.eplanDataPortal.enabledHint') }}</span>
        </label>
        <ToggleSwitch v-model="form.enabled" input-id="edp-enabled" :disabled="!canWrite" />
      </div>

      <div class="field-row">
        <label for="edp-base-url">{{ t('adminSettings.eplanDataPortal.baseUrl') }}</label>
        <InputText
          id="edp-base-url"
          v-model="form.base_url"
          :disabled="!canWrite"
          autocomplete="off"
        />
      </div>

      <div class="field-row">
        <label for="edp-pat">
          {{ t('adminSettings.eplanDataPortal.pat') }}
          <span class="hint">{{ t('adminSettings.eplanDataPortal.patHint') }}</span>
        </label>
        <div class="edp-inline">
          <Password
            v-model="form.pat"
            input-id="edp-pat"
            :feedback="false"
            toggle-mask
            :placeholder="
              patConfigured
                ? t('adminSettings.eplanDataPortal.patStored')
                : t('adminSettings.eplanDataPortal.patMissing')
            "
            :disabled="!canWrite"
            autocomplete="off"
            data-testid="edp-pat"
          />
          <Button
            v-if="patConfigured"
            :label="t('adminSettings.eplanDataPortal.removeToken')"
            icon="mdi mdi-key-remove"
            severity="danger"
            outlined
            size="small"
            :disabled="!canWrite || saving"
            data-testid="edp-remove-token"
            @click="onRemoveToken"
          />
        </div>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.eplanDataPortal.itemsSection') }}</p>

      <div class="field-row">
        <label id="edp-language-label" for="edp-language">
          {{ t('adminSettings.eplanDataPortal.language') }}
          <span class="hint">{{ t('adminSettings.eplanDataPortal.languageHint') }}</span>
        </label>
        <Select
          v-model="form.language"
          input-id="edp-language"
          aria-labelledby="edp-language-label"
          :options="languages"
          option-label="label"
          option-value="value"
          :disabled="!canWrite"
        />
      </div>

      <div class="field-row">
        <label id="edp-article-groups-label" for="edp-article-groups">
          {{ t('adminSettings.eplanDataPortal.defaultArticleGroups') }}
          <span class="hint">{{ t('adminSettings.eplanDataPortal.defaultArticleGroupsHint') }}</span>
        </label>
        <MultiSelect
          v-model="form.default_article_group_ids"
          input-id="edp-article-groups"
          aria-labelledby="edp-article-groups-label"
          :options="liveArticleGroups"
          :option-label="labelName"
          option-value="id"
          display="chip"
          filter
          :loading="articleGroupsStore.loading"
          :disabled="!canWrite"
        />
      </div>
    </div>
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
p.hint {
  margin: 0;
}

.edp-inline {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}
</style>
