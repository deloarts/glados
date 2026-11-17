<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'

import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import ControlsBar from '@/shared/components/resource-view/ControlsBar.vue'
import ViewsBar from '@/shared/components/resource-view/ViewsBar.vue'
import { formatISODateTime } from '@/core/utils/dates'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { HelpButton } from '@/shared/help'
import EmptyState from '@/shared/components/EmptyState.vue'
import SectionCard from '@/shared/components/resource-view/SectionCard.vue'
import {
  fetchSessions,
  fetchTrustedDevices,
  revokeAllTrustedDevices,
  revokeOtherSessions,
  revokeSession,
  revokeTrustedDevice,
  type SessionSummary,
  type TrustedDeviceSummary,
} from '../api/sessionsApi'

const { t } = useI18n()
const confirm = useConfirm()
const appToast = useAppToast()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const sessions = ref<SessionSummary[]>([])
const trustedDevices = ref<TrustedDeviceSummary[]>([])
const loading = ref(false)

async function refresh(): Promise<void> {
  loading.value = true
  try {
    ;[sessions.value, trustedDevices.value] = await Promise.all([
      fetchSessions(),
      fetchTrustedDevices(),
    ])
  } catch {
    appToast.error(t('account.sessions.errors.loadFailed'))
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

function deviceLabel(userAgent: string | null): string {
  return userAgent || t('account.sessions.unknownDevice')
}

function onRevokeSession(session: SessionSummary): void {
  async function onAccept(): Promise<void> {
    try {
      await revokeSession(session.public_id)
      if (session.is_current) {
        // Revoking your own session is signing out.
        useCurrentUserStore().sessionExpired()
        return
      }
      appToast.success(t('account.sessions.revoked'))
      await refresh()
    } catch {
      appToast.error(t('account.sessions.errors.unknown'))
    }
  }

  confirm.require({
    message: session.is_current
      ? t('account.sessions.revokeCurrentConfirm')
      : t('account.sessions.revokeConfirm'),
    header: t('account.sessions.revokeButton'),
    icon: 'mdi mdi-logout',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('account.sessions.revokeButton'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

function onRevokeOthers(): void {
  async function onAccept(): Promise<void> {
    try {
      const revoked = await revokeOtherSessions()
      appToast.success(t('account.sessions.othersRevoked', { count: revoked }))
      await refresh()
    } catch {
      appToast.error(t('account.sessions.errors.unknown'))
    }
  }

  confirm.require({
    message: t('account.sessions.revokeOthersConfirm'),
    header: t('account.sessions.revokeOthersButton'),
    icon: 'mdi mdi-logout-variant',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('account.sessions.revokeOthersButton'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

function onRevokeDevice(device: TrustedDeviceSummary): void {
  async function onAccept(): Promise<void> {
    try {
      await revokeTrustedDevice(device.public_id)
      appToast.success(t('account.sessions.devices.revoked'))
      await refresh()
    } catch {
      appToast.error(t('account.sessions.errors.unknown'))
    }
  }

  confirm.require({
    message: t('account.sessions.devices.revokeConfirm'),
    header: t('account.sessions.devices.revokeButton'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('account.sessions.devices.revokeButton'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

function onRevokeAllDevices(): void {
  async function onAccept(): Promise<void> {
    try {
      await revokeAllTrustedDevices()
      appToast.success(t('account.sessions.devices.allRevoked'))
      await refresh()
    } catch {
      appToast.error(t('account.sessions.errors.unknown'))
    }
  }

  confirm.require({
    message: t('account.sessions.devices.revokeAllConfirm'),
    header: t('account.sessions.devices.revokeAllButton'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('account.sessions.devices.revokeAllButton'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}
</script>

<template>
  <PageLayout :card="false">
    <template #controls>
      <ControlsBar>
        <template #start>
          <Button
            :label="t('account.sessions.revokeOthersButton')"
            icon="mdi mdi-logout-variant"
            severity="danger"
            text
            :disabled="loading || sessions.length < 2"
            @click="onRevokeOthers"
          />
          <Button
            :label="t('account.sessions.devices.revokeAllButton')"
            icon="mdi mdi-delete-outline"
            severity="danger"
            text
            :disabled="loading || trustedDevices.length === 0"
            @click="onRevokeAllDevices"
          />
        </template>
        <template #handbook>
          <HelpButton rounded />
        </template>
      </ControlsBar>
    </template>
    <template #views>
      <ViewsBar
        id-prefix="sessions"
        hide-views-toggle
        :syncing="loading"
        :has-active-filters="false"
        @sync="refresh()"
      />
    </template>

    <div class="sessions-view">
      <SectionCard
        :title="t('account.sessions.title')"
        :hint="t('account.sessions.description')"
        flush
        fill
      >
        <DataTable
          :value="sessions"
          data-key="public_id"
          :loading="loading"
          :show-gridlines="isTableGridlinesEnabled"
          :striped-rows="isTableStripedEnabled"
          scrollable
          scroll-height="flex"
          size="small"
        >
          <template #empty>
            <EmptyState :message="t('account.sessions.empty')" />
          </template>
          <Column header="#" class="column-fit" body-class="row-number">
            <template #body="{ index }">{{ index + 1 }}</template>
          </Column>
          <Column :header="t('account.sessions.columns.actions')" class="column-fit">
            <template #body="{ data }: { data: SessionSummary }">
              <Button
                icon="mdi mdi-logout"
                size="small"
                severity="danger"
                text
                v-tooltip.top.focus="t('account.sessions.revokeButton')"
                :aria-label="t('account.sessions.revokeButton')"
                @click="onRevokeSession(data)"
              />
            </template>
          </Column>
          <Column :header="t('account.sessions.columns.device')">
            <template #body="{ data }: { data: SessionSummary }">
              <span class="device-cell">
                {{ deviceLabel(data.user_agent) }}
                <Tag
                  v-if="data.is_current"
                  :value="t('account.sessions.current')"
                  severity="success"
                />
              </span>
            </template>
          </Column>
          <Column :header="t('account.sessions.columns.ip')" class="column-fit">
            <template #body="{ data }: { data: SessionSummary }">
              <template v-if="data.ip">{{ data.ip }}</template>
              <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
            </template>
          </Column>
          <Column :header="t('account.sessions.columns.signedIn')" class="column-fit">
            <template #body="{ data }: { data: SessionSummary }">
              {{ formatISODateTime(data.created_at) }}
            </template>
          </Column>
          <Column :header="t('account.sessions.columns.lastSeen')" class="column-fit">
            <template #body="{ data }: { data: SessionSummary }">
              {{ formatISODateTime(data.last_seen_at) }}
            </template>
          </Column>
        </DataTable>
      </SectionCard>

      <SectionCard
        :title="t('account.sessions.devices.title')"
        :hint="t('account.sessions.devices.description')"
        flush
        fill
      >
        <DataTable
          :value="trustedDevices"
          data-key="public_id"
          :loading="loading"
          :show-gridlines="isTableGridlinesEnabled"
          :striped-rows="isTableStripedEnabled"
          scrollable
          scroll-height="flex"
          size="small"
        >
          <template #empty>
            <EmptyState :message="t('account.sessions.devices.empty')" />
          </template>
          <Column header="#" class="column-fit" body-class="row-number">
            <template #body="{ index }">{{ index + 1 }}</template>
          </Column>
          <Column :header="t('account.sessions.columns.actions')" class="column-fit">
            <template #body="{ data }: { data: TrustedDeviceSummary }">
              <Button
                icon="mdi mdi-delete-outline"
                size="small"
                severity="danger"
                text
                v-tooltip.top.focus="t('account.sessions.devices.revokeButton')"
                :aria-label="t('account.sessions.devices.revokeButton')"
                @click="onRevokeDevice(data)"
              />
            </template>
          </Column>
          <Column :header="t('account.sessions.columns.device')">
            <template #body="{ data }: { data: TrustedDeviceSummary }">
              <span class="device-cell">{{ deviceLabel(data.user_agent) }}</span>
            </template>
          </Column>
          <Column :header="t('account.sessions.devices.columns.trustedSince')" class="column-fit">
            <template #body="{ data }: { data: TrustedDeviceSummary }">
              {{ formatISODateTime(data.created_at) }}
            </template>
          </Column>
          <Column :header="t('account.sessions.devices.columns.lastUsed')" class="column-fit">
            <template #body="{ data }: { data: TrustedDeviceSummary }">
              {{ formatISODateTime(data.last_used_at) }}
            </template>
          </Column>
          <Column :header="t('account.sessions.devices.columns.expires')" class="column-fit">
            <template #body="{ data }: { data: TrustedDeviceSummary }">
              {{ formatISODateTime(data.expires_at) }}
            </template>
          </Column>
        </DataTable>
      </SectionCard>
    </div>
  </PageLayout>
</template>

<style scoped lang="scss">
// The two cards share the data area evenly, and each table scrolls inside
// its own half instead of the page.
.sessions-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.muted {
  color: var(--p-text-muted-color);
}

.device-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  // Raw user-agent strings are long, keep rows readable.
  overflow-wrap: anywhere;
}
</style>
