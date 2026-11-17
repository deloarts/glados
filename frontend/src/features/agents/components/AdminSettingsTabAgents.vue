<script setup lang="ts">
// The AI agents tab: the company's approval of AI processing, without which
// agent access cannot be switched on, then the access itself, the lifetime
// of agent tokens, what tool results may carry and the call budgets.
// Changing the approved providers, the AI policy link or whether names and
// prices leave renews the approval, so every user confirms again before
// their agent calls; the tab warns before saving such a change. The
// settings are loaded here, not with the aggregate.
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { formatISODateTime } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { AdminSettingsTabShell } from '@/features/admin-settings'
import { getAgentSettings, updateAgentSettings } from '../api/agentsApi'
import type { AgentSettings, UpdateAgentSettingsCommand } from '../types/agentTypes'

const { t } = useI18n()
const confirm = useConfirm()
const appToast = useAppToast()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

const settings = ref<AgentSettings | null>(null)
const saving = ref(false)

const form = reactive({
  processing_approved: false,
  approved_providers: '',
  ai_policy_url: '',
  enabled: false,
  token_max_lifetime_days: 30,
  token_idle_revoke_days: 14,
  include_person_names: false,
  include_costs: false,
  allowed_origins: '',
  calls_per_minute: 120,
  drafts_per_hour: 20,
})

function fill(value: AgentSettings): void {
  settings.value = value
  form.processing_approved = value.processing_approved_at != null
  form.approved_providers = value.approved_providers
  form.ai_policy_url = value.ai_policy_url ?? ''
  form.enabled = value.enabled
  form.token_max_lifetime_days = value.token_max_lifetime_days
  form.token_idle_revoke_days = value.token_idle_revoke_days
  form.include_person_names = value.include_person_names
  form.include_costs = value.include_costs
  form.allowed_origins = value.allowed_origins.join('\n')
  form.calls_per_minute = value.calls_per_minute
  form.drafts_per_hour = value.drafts_per_hour
}

onMounted(async () => {
  try {
    fill(await getAgentSettings())
  } catch (err) {
    appToast.error(t('adminSettings.errors.unknown'), extractApiError(err) ?? undefined)
  }
})

// Agent access needs the approval; withdrawing it switches access off.
const canEnable = computed(() => form.processing_approved && form.approved_providers.trim() !== '')

function onApprovalChange(approved: boolean): void {
  if (!approved) form.enabled = false
}

function command(): UpdateAgentSettingsCommand {
  return {
    // An approval naming no provider is no approval.
    processing_approved: canEnable.value,
    approved_providers: form.approved_providers.trim(),
    ai_policy_url: form.ai_policy_url.trim() || null,
    enabled: form.enabled && canEnable.value,
    token_max_lifetime_days: form.token_max_lifetime_days,
    token_idle_revoke_days: form.token_idle_revoke_days,
    include_person_names: form.include_person_names,
    include_costs: form.include_costs,
    allowed_origins: form.allowed_origins
      .split(/[\s,]+/)
      .map((origin) => origin.trim())
      .filter((origin) => origin !== ''),
    calls_per_minute: form.calls_per_minute,
    drafts_per_hour: form.drafts_per_hour,
  }
}

// Whether saving renews the approval, which asks every user to confirm again.
const renewsConsent = computed(() => {
  const current = settings.value
  if (!current || current.processing_approved_at == null || !form.processing_approved) return false
  return (
    current.approved_providers !== form.approved_providers.trim() ||
    (current.ai_policy_url ?? '') !== form.ai_policy_url.trim() ||
    current.include_person_names !== form.include_person_names ||
    current.include_costs !== form.include_costs
  )
})

async function save(): Promise<void> {
  saving.value = true
  try {
    fill(await updateAgentSettings(command()))
    appToast.success(t('adminSettings.saved'))
  } catch (err) {
    appToast.error(t('adminSettings.errors.unknown'), extractApiError(err) ?? undefined)
  } finally {
    saving.value = false
  }
}

function onSave(): void {
  if (!renewsConsent.value) {
    void save()
    return
  }
  confirm.require({
    message: t('agents.settings.renewConfirm'),
    header: t('agents.settings.renewTitle'),
    icon: 'mdi mdi-alert-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('common.save'), severity: 'warn' },
    accept: () => void save(),
  })
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
            :disabled="!canWrite || !settings"
            data-testid="agents-save"
            @click="onSave"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="section-label">{{ t('agents.settings.approvalSection') }}</p>
      <p class="hint">{{ t('agents.settings.approvalHint') }}</p>

      <div class="field-row">
        <label for="agents-providers">
          {{ t('agents.settings.approvedProviders') }}
          <small class="hint">{{ t('agents.settings.approvedProvidersHint') }}</small>
        </label>
        <InputText
          id="agents-providers"
          v-model="form.approved_providers"
          :placeholder="t('agents.settings.approvedProvidersPlaceholder')"
          :disabled="!canWrite"
          maxlength="500"
        />
      </div>
      <div class="field-row">
        <label for="agents-policy">
          {{ t('agents.settings.policyUrl') }}
          <small class="hint">{{ t('agents.settings.policyUrlHint') }}</small>
        </label>
        <InputText
          id="agents-policy"
          v-model="form.ai_policy_url"
          placeholder="https://"
          :disabled="!canWrite"
        />
      </div>
      <div class="field-row field-row--toggle">
        <label for="agents-approved">
          {{ t('agents.settings.approved') }}
          <small class="hint">
            {{
              settings?.processing_approved_at
                ? t('agents.settings.approvedAt', {
                    at: formatISODateTime(settings.processing_approved_at),
                  })
                : t('agents.settings.approvedHint')
            }}
          </small>
        </label>
        <ToggleSwitch
          v-model="form.processing_approved"
          input-id="agents-approved"
          :disabled="!canWrite || form.approved_providers.trim() === ''"
          data-testid="agents-approved"
          @update:model-value="onApprovalChange"
        />
      </div>

      <Divider />
      <p class="section-label">{{ t('agents.settings.accessSection') }}</p>
      <div class="field-row field-row--toggle">
        <label for="agents-enabled">
          {{ t('agents.settings.enabled') }}
          <small class="hint">{{ t('agents.settings.enabledHint') }}</small>
        </label>
        <span v-tooltip.top="canEnable ? undefined : t('agents.settings.enableNeedsApproval')">
          <ToggleSwitch
            v-model="form.enabled"
            input-id="agents-enabled"
            :disabled="!canWrite || !canEnable"
            data-testid="agents-enabled"
          />
        </span>
      </div>
      <div class="field-row">
        <label for="agents-origins">
          {{ t('agents.settings.allowedOrigins') }}
          <small class="hint">{{ t('agents.settings.allowedOriginsHint') }}</small>
        </label>
        <Textarea
          id="agents-origins"
          v-model="form.allowed_origins"
          rows="3"
          auto-resize
          :disabled="!canWrite"
        />
      </div>

      <Divider />
      <p class="section-label">{{ t('agents.settings.tokensSection') }}</p>
      <div class="field-row">
        <label for="agents-lifetime">
          {{ t('agents.settings.maxLifetime') }}
          <small class="hint">{{ t('agents.settings.maxLifetimeHint') }}</small>
        </label>
        <InputNumber
          v-model="form.token_max_lifetime_days"
          input-id="agents-lifetime"
          :min="1"
          :max="365"
          :use-grouping="false"
          :disabled="!canWrite"
        />
      </div>
      <div class="field-row">
        <label for="agents-idle">
          {{ t('agents.settings.idleRevoke') }}
          <small class="hint">{{ t('agents.settings.idleRevokeHint') }}</small>
        </label>
        <InputNumber
          v-model="form.token_idle_revoke_days"
          input-id="agents-idle"
          :min="1"
          :max="365"
          :use-grouping="false"
          :disabled="!canWrite"
        />
      </div>

      <Divider />
      <p class="section-label">{{ t('agents.settings.resultsSection') }}</p>
      <p class="hint">{{ t('agents.settings.resultsHint') }}</p>
      <div class="field-row field-row--toggle">
        <label for="agents-names">{{ t('agents.settings.includeNames') }}</label>
        <ToggleSwitch
          v-model="form.include_person_names"
          input-id="agents-names"
          :disabled="!canWrite"
        />
      </div>
      <div class="field-row field-row--toggle">
        <label for="agents-costs">{{ t('agents.settings.includeCosts') }}</label>
        <ToggleSwitch v-model="form.include_costs" input-id="agents-costs" :disabled="!canWrite" />
      </div>
      <Message v-if="renewsConsent" severity="warn" :closable="false">
        {{ t('agents.settings.renewWarning') }}
      </Message>

      <Divider />
      <p class="section-label">{{ t('agents.settings.budgetsSection') }}</p>
      <div class="field-row">
        <label for="agents-calls">{{ t('agents.settings.callsPerMinute') }}</label>
        <InputNumber
          v-model="form.calls_per_minute"
          input-id="agents-calls"
          :min="1"
          :max="10000"
          :use-grouping="false"
          :disabled="!canWrite"
        />
      </div>
      <div class="field-row">
        <label for="agents-drafts">
          {{ t('agents.settings.draftsPerHour') }}
          <small class="hint">{{ t('agents.settings.draftsPerHourHint') }}</small>
        </label>
        <InputNumber
          v-model="form.drafts_per_hour"
          input-id="agents-drafts"
          :min="0"
          :max="1000"
          :use-grouping="false"
          :disabled="!canWrite"
        />
      </div>
    </div>
  </AdminSettingsTabShell>
</template>
