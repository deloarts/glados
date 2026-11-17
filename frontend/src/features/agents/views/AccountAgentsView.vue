<script setup lang="ts">
// The AI Agents tab of the account page: the user's own consent that an
// agent may process Glados data on their behalf, the agent token presets
// and the log of every call their agents made. A new agent token asks for
// the consent first when it is missing or older than the current terms,
// since the backend refuses an agent token without it.
import { computed, onMounted, ref, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { formatISODateTime } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { HelpButton } from '@/shared/help'
import { safeHref } from '@/shared/utils/isSafeHttpUrl'
import { getMyAgentConsent, giveAgentConsent, withdrawAgentConsent } from '../api/agentsApi'
import AgentCallsTable from '../components/AgentCallsTable.vue'
import AgentConsentDialog from '../components/AgentConsentDialog.vue'
import AgentTokenDialog from '../components/AgentTokenDialog.vue'
import type { AgentConsentStatus } from '../types/agentTypes'

const { t } = useI18n()
const confirm = useConfirm()
const appToast = useAppToast()
const hostStore = useHostStore()
const { hasPermission } = usePermissions()
const { missing } = useMissingPermission()
const callsTable = useTemplateRef<InstanceType<typeof AgentCallsTable>>('callsTable')

const status = ref<AgentConsentStatus | null>(null)
const loading = ref(false)
const showConsent = ref(false)
const showToken = ref(false)
const savingConsent = ref(false)
// Whether confirming the consent goes on to the token dialog.
const tokenAfterConsent = ref(false)

const canUse = computed(() => hasPermission(Permission.USE_MCP))
// An agent token is a personal access token, so creating one also needs
// Write Access Token, which the backend checks on every token it creates.
const canCreateToken = computed(() => canUse.value && hasPermission(Permission.WRITE_PAT))
const newTokenBlocked = computed(() => missing(Permission.USE_MCP, Permission.WRITE_PAT))
const accessReady = computed(() => status.value?.access_ready ?? hostStore.agentAccessEnabled)
const consentCurrent = computed(() => status.value?.consent_current ?? false)
const hasConsent = computed(() => status.value?.consented_at != null)
const policyHref = computed(() => safeHref(status.value?.ai_policy_url ?? null))

const consentState = computed<{ label: string; severity: 'success' | 'warn' | 'secondary' }>(() => {
  if (consentCurrent.value) return { label: t('agents.account.consentGiven'), severity: 'success' }
  if (hasConsent.value) return { label: t('agents.account.consentOutdated'), severity: 'warn' }
  return { label: t('agents.account.consentMissing'), severity: 'secondary' }
})

async function loadStatus(): Promise<void> {
  loading.value = true
  try {
    status.value = await getMyAgentConsent()
  } catch (err) {
    appToast.error(t('agents.account.loadFailed'), extractApiError(err) ?? undefined)
  } finally {
    loading.value = false
  }
}

onMounted(() => void loadStatus())

function refresh(): void {
  void loadStatus()
  callsTable.value?.reload()
}

function onNewToken(): void {
  if (consentCurrent.value) {
    showToken.value = true
    return
  }
  tokenAfterConsent.value = true
  showConsent.value = true
}

function onGiveConsent(): void {
  tokenAfterConsent.value = false
  showConsent.value = true
}

function onConsentCancel(): void {
  showConsent.value = false
  tokenAfterConsent.value = false
}

async function onConsentConfirm(): Promise<void> {
  if (!status.value) return
  savingConsent.value = true
  try {
    status.value = await giveAgentConsent(status.value.consent_version)
    showConsent.value = false
    appToast.success(t('agents.account.consentSaved'))
    if (tokenAfterConsent.value) showToken.value = true
  } catch (err) {
    appToast.error(t('agents.account.consentFailed'), extractApiError(err) ?? undefined)
  } finally {
    savingConsent.value = false
    tokenAfterConsent.value = false
  }
}

function onWithdraw(): void {
  async function onAccept(): Promise<void> {
    try {
      status.value = await withdrawAgentConsent()
      appToast.success(t('agents.account.withdrawn'))
    } catch (err) {
      appToast.error(t('agents.account.withdrawFailed'), extractApiError(err) ?? undefined)
    }
  }

  confirm.require({
    message: t('agents.account.withdrawConfirm'),
    header: t('agents.account.withdraw'),
    icon: 'mdi mdi-cancel',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('agents.account.withdraw'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}
</script>

<template>
  <PageLayout :card="false">
    <template #controls>
      <ControlsBar>
        <template #start>
          <span v-if="accessReady" v-tooltip.bottom="newTokenBlocked || undefined">
            <Button
              :label="t('agents.account.newToken')"
              icon="mdi mdi-plus"
              severity="contrast"
              text
              :disabled="!canCreateToken || !status"
              data-testid="agent-new-token"
              @click="onNewToken"
            />
          </span>
          <span
            v-if="accessReady && !consentCurrent"
            v-tooltip.bottom="missing(Permission.USE_MCP) || undefined"
          >
            <Button
              :label="t('agents.account.giveConsent')"
              icon="mdi mdi-check-decagram-outline"
              severity="contrast"
              text
              :disabled="!canUse || !status"
              data-testid="agent-give-consent"
              @click="onGiveConsent"
            />
          </span>
          <Button
            v-if="hasConsent"
            :label="t('agents.account.withdraw')"
            icon="mdi mdi-cancel"
            severity="danger"
            text
            data-testid="agent-withdraw-consent"
            @click="onWithdraw"
          />
        </template>
        <template #handbook>
          <HelpButton slug="account/ai-agents" rounded />
        </template>
      </ControlsBar>
    </template>
    <template #views>
      <ViewsBar
        id-prefix="agents"
        hide-views-toggle
        :syncing="loading"
        :has-active-filters="false"
        @sync="refresh"
      />
    </template>

    <div class="agents-view">
      <Message v-if="status && !accessReady" severity="info" :closable="false">
        {{ t('agents.account.accessOff') }}
      </Message>

      <SectionCard
        :title="t('agents.account.consentTitle')"
        :hint="t('agents.account.consentHint')"
        icon="mdi-check-decagram-outline"
      >
        <template #title-end>
          <Tag
            :value="consentState.label"
            :severity="consentState.severity"
            data-testid="agent-consent-state"
          />
        </template>
        <dl v-if="status" class="facts">
          <dt>{{ t('agents.account.providers') }}</dt>
          <dd>{{ status.approved_providers || t('agents.account.noProviders') }}</dd>
          <dt>{{ t('agents.account.leaves') }}</dt>
          <dd>
            {{ status.include_person_names ? t('agents.consent.namesSent') : t('agents.consent.namesHidden') }}
            {{ status.include_costs ? t('agents.consent.pricesSent') : t('agents.consent.pricesHidden') }}
          </dd>
          <template v-if="policyHref">
            <dt>{{ t('agents.consent.policy') }}</dt>
            <dd>
              <a :href="policyHref" target="_blank" rel="noopener noreferrer">{{ policyHref }}</a>
            </dd>
          </template>
          <template v-if="status.consented_at">
            <dt>{{ t('agents.account.consentedAt') }}</dt>
            <dd>{{ formatISODateTime(status.consented_at) }}</dd>
          </template>
        </dl>
      </SectionCard>

      <SectionCard
        :title="t('agents.account.callsTitle')"
        :hint="t('agents.account.callsHint')"
        icon="mdi-robot-outline"
        flush
        fill
      >
        <AgentCallsTable ref="callsTable" />
      </SectionCard>
    </div>
  </PageLayout>

  <AgentConsentDialog
    v-if="status"
    :visible="showConsent"
    :status="status"
    :saving="savingConsent"
    @confirm="() => void onConsentConfirm()"
    @cancel="onConsentCancel"
  />
  <AgentTokenDialog v-model:visible="showToken" />
</template>

<style scoped lang="scss">
.agents-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  min-height: 0;
}

.facts {
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
