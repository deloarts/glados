<script setup lang="ts">
// The stock service tab: the stock service in the same stack, which talks
// to the stock system, and the API key Glados calls it with. Glados never
// talks to the stock system itself. The API key is write-only: an empty
// field keeps the stored one. A connection test shows what the service
// reports. No feature builds on the service yet, so the tab only sets up
// the connection. The settings are loaded here, not with the aggregate.
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { extractApiError, extractApiErrorCode } from '@/core/utils/errors'
import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import type { AdminStockSettings, StockServiceTestResult } from '../types/adminSettingsTypes'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'

const ERROR_KEYS: Readonly<Record<string, string>> = {
  StockServiceNotConfiguredError: 'adminSettings.stockService.errors.notConfigured',
  StockServiceUnavailableError: 'adminSettings.stockService.errors.unavailable',
  StockServiceProviderError: 'adminSettings.stockService.errors.provider',
}

const { t } = useI18n()
const toast = useAppToast()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

const form = reactive({
  enabled: false,
  service_url: '',
  api_key: '',
})

const settings = computed<AdminStockSettings | null>(() => store.stock)

watch(
  settings,
  (value) => {
    if (!value) return
    form.enabled = value.enabled
    form.service_url = value.service_url
    form.api_key = ''
  },
  { immediate: true },
)

onMounted(() => {
  void store.fetchStock()
})

function errorMessage(err: unknown): string {
  const code = extractApiErrorCode(err)
  const key = code ? ERROR_KEYS[code] : undefined
  if (key) return t(key)
  return extractApiError(err) ?? t('adminSettings.errors.unknown')
}

// ── Save ────────────────────────────────────────────────────────────────

const saving = ref(false)

async function onSave(): Promise<void> {
  saving.value = true
  try {
    await store.saveStock({
      enabled: form.enabled,
      service_url: form.service_url.trim(),
      ...(form.api_key ? { api_key: form.api_key } : {}),
    })
    toast.success(t('adminSettings.saved'))
  } catch (err: unknown) {
    toast.error(t('adminSettings.errors.unknown'), errorMessage(err))
  } finally {
    form.api_key = ''
    saving.value = false
  }
}

// ── Test connection ─────────────────────────────────────────────────────

const testing = ref(false)
const testResult = ref<StockServiceTestResult | null>(null)

const canTest = computed(
  () =>
    canWrite && !!form.service_url.trim() && (!!form.api_key || !!settings.value?.api_key_configured),
)

async function onTest(): Promise<void> {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = await store.testStockService({
      service_url: form.service_url.trim() || null,
      ...(form.api_key ? { api_key: form.api_key } : {}),
    })
    toast.success(t('adminSettings.stockService.testSuccess'))
  } catch (err: unknown) {
    toast.error(t('adminSettings.stockService.testFailed'), errorMessage(err))
  } finally {
    testing.value = false
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
            data-testid="stock-service-save"
            @click="onSave"
          />
          <Button
            :label="t('adminSettings.stockService.testConnection')"
            icon="mdi mdi-lan-connect"
            text
            severity="contrast"
            :loading="testing"
            :disabled="!canTest"
            data-testid="stock-service-test"
            @click="onTest"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="section-label">{{ t('adminSettings.stockService.serviceSection') }}</p>

      <div class="field-row field-row--toggle">
        <label for="stock-service-enabled">
          {{ t('adminSettings.stockService.enabled') }}
          <span class="hint">{{ t('adminSettings.stockService.enabledHint') }}</span>
        </label>
        <ToggleSwitch v-model="form.enabled" input-id="stock-service-enabled" :disabled="!canWrite" />
      </div>

      <div class="field-row">
        <label for="stock-service-url">
          {{ t('adminSettings.stockService.serviceUrl') }}
          <span class="hint">{{ t('adminSettings.stockService.serviceUrlHint') }}</span>
        </label>
        <InputText
          id="stock-service-url"
          v-model="form.service_url"
          :placeholder="t('adminSettings.stockService.serviceUrlPlaceholder')"
          :disabled="!canWrite"
          autocomplete="off"
        />
      </div>

      <div class="field-row">
        <label for="stock-service-api-key">
          {{ t('adminSettings.stockService.apiKey') }}
          <span class="hint">{{ t('adminSettings.stockService.apiKeyHint') }}</span>
        </label>
        <InputText
          id="stock-service-api-key"
          v-model="form.api_key"
          type="password"
          autocomplete="new-password"
          :placeholder="
            settings?.api_key_configured ? t('adminSettings.stockService.apiKeySaved') : ''
          "
          :disabled="!canWrite"
        />
      </div>

      <template v-if="testResult">
        <Divider />
        <p class="section-label">{{ t('adminSettings.stockService.testSection') }}</p>
        <dl class="test-result" data-testid="stock-service-test-result">
          <dt>{{ t('adminSettings.stockService.testService') }}</dt>
          <dd>{{ testResult.service }} {{ testResult.service_version }}</dd>
          <dt>{{ t('adminSettings.stockService.testProvider') }}</dt>
          <dd>{{ testResult.provider_label }} {{ testResult.server_version }}</dd>
          <dt>{{ t('adminSettings.stockService.testContract') }}</dt>
          <dd>{{ testResult.contract_version }}</dd>
        </dl>
        <Message
          v-if="!testResult.contract_supported"
          severity="warn"
          :closable="false"
          data-testid="stock-service-contract-unsupported"
        >
          {{ t('adminSettings.stockService.contractUnsupported') }}
        </Message>
      </template>
    </div>
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
.test-result {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: var(--space-1) var(--space-4);
  margin: 0;
  font-size: var(--font-size-sm);

  dt {
    color: var(--p-text-muted-color);
  }

  dd {
    margin: 0;
  }
}
</style>
