<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, useId } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { getHostStats } from '../api/getHostStats'
import { getIntegrationsOverview } from '../api/getIntegrationsOverview'
import { getServicesHealth } from '../api/getServicesHealth'
import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { formatISODateTime } from '@/core/utils/dates'
import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'
import type {
  AdminFeatureSettings,
  HostStats,
  IntegrationStatus,
  ServiceHealth,
} from '../types/adminSettingsTypes'

// CPU load is only meaningful live, so the tab polls rather than showing a
// number frozen at the moment it was opened. The interval is cleared on
// unmount, so a settings screen left on another tab costs nothing.
const REFRESH_INTERVAL_MS = 5000

const { t } = useI18n()
// Prefixes the ids that tie each usage bar to its caption.
const uid = useId()
const { formatNumber } = useLocaleFormat()

const stats = ref<HostStats | null>(null)
const services = ref<ServiceHealth[]>([])
// Only the first load blanks the panel; later failures keep the last good
// reading on screen rather than flashing an error over a transient blip.
const loading = ref(true)
const errored = ref(false)
let timer: ReturnType<typeof setInterval> | undefined

async function refresh(): Promise<void> {
  try {
    const [statsResult, servicesResult] = await Promise.all([getHostStats(), getServicesHealth()])
    stats.value = statsResult
    services.value = servicesResult.services
    errored.value = false
  } catch {
    errored.value = stats.value === null
  } finally {
    loading.value = false
  }
}

// ── At a glance ─────────────────────────────────────────────────────────────

const router = useRouter()
const settingsStore = useAdminSettingsStore()

const integrations = ref<IntegrationStatus[]>([])
const integrationsFailed = ref(false)

// The settings tab each entry opens, and its icon.
const INTEGRATIONS: Record<string, { tab: string; icon: string }> = {
  mail: { tab: 'mail', icon: 'mdi-email-outline' },
  email_notifications: { tab: 'notifications', icon: 'mdi-bell-outline' },
  ldap: { tab: 'auth', icon: 'mdi-account-key-outline' },
  api_keys: { tab: 'apiKeys', icon: 'mdi-key-outline' },
  terminals: { tab: 'security', icon: 'mdi-monitor-dashboard' },
  storage: { tab: 'storage', icon: 'mdi-harddisk' },
  backups: { tab: 'backups', icon: 'mdi-database-arrow-down-outline' },
  pdm: { tab: 'solidworks-pdm', icon: 'mdi-cube-outline' },
  time_tracking: { tab: 'time-tracking', icon: 'mdi-clock-outline' },
  stock_service: { tab: 'stock-service', icon: 'mdi-package-variant-closed' },
  eplan_data_portal: { tab: 'eplan-data-portal', icon: 'mdi-database-search-outline' },
  agents: { tab: 'ai-agents', icon: 'mdi-robot-outline' },
}

const MODULES: { key: keyof AdminFeatureSettings; label: string; icon: string }[] = [
  { key: 'enable_production_planning', label: 'enableProductionPlanning', icon: 'mdi-factory' },
  { key: 'enable_calculations', label: 'enableCalculations', icon: 'mdi-calculator-variant-outline' },
  { key: 'enable_checklists', label: 'enableChecklists', icon: 'mdi-clipboard-check-outline' },
  { key: 'enable_devices', label: 'enableDevices', icon: 'mdi-chip' },
  { key: 'enable_sequences', label: 'enableSequences', icon: 'mdi-sitemap-outline' },
  { key: 'enable_todos', label: 'enableTodos', icon: 'mdi-checkbox-marked-outline' },
]

const modules = computed(() => {
  const features = settingsStore.settings?.features
  if (!features) return []
  return MODULES.map((module) => ({ ...module, on: Boolean(features[module.key]) }))
})

const INTEGRATION_DOT: Record<IntegrationStatus['state'], string> = {
  active: 'up',
  incomplete: 'warn',
  off: 'disabled',
}

function openSettingsTab(tab: string): void {
  void router.push(`/settings/${tab}`)
}

async function loadIntegrations(): Promise<void> {
  try {
    integrations.value = (await getIntegrationsOverview()).integrations
    integrationsFailed.value = false
  } catch {
    integrationsFailed.value = true
  }
}

onMounted(async () => {
  void loadIntegrations()
  await refresh()
  timer = setInterval(() => void refresh(), REFRESH_INTERVAL_MS)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

/** Binary units, matching how operating systems report memory and disk. */
function formatBytes(bytes: number): string {
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit++
  }
  const fractionDigits = value >= 100 || unit === 0 ? 0 : 1
  const formatted = formatNumber(value, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  })
  return `${formatted} ${units[unit]}`
}

/** Coarse, human-scale uptime, "3 d 4 h" rather than a precise duration. */
function formatUptime(since: string): string {
  const elapsedMs = Date.now() - new Date(since).getTime()
  if (!Number.isFinite(elapsedMs) || elapsedMs < 0) return t('adminSettings.host.unknown')

  const minutes = Math.floor(elapsedMs / 60000)
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  if (days > 0) return t('adminSettings.host.uptimeDays', { days, hours })
  if (hours > 0) return t('adminSettings.host.uptimeHours', { hours, minutes: minutes % 60 })
  return t('adminSettings.host.uptimeMinutes', { minutes })
}

const memoryLabel = computed(() =>
  stats.value
    ? `${formatBytes(stats.value.memory_used_bytes)} / ${formatBytes(stats.value.memory_total_bytes)}`
    : '',
)

const diskLabel = computed(() =>
  stats.value
    ? `${formatBytes(stats.value.disk_used_bytes)} / ${formatBytes(stats.value.disk_total_bytes)}`
    : '',
)

/** Green below 75%, amber to 90%, red above, the usual "should I worry" bands. */
function usageSeverity(percent: number): string {
  if (percent >= 90) return 'usage--critical'
  if (percent >= 75) return 'usage--warn'
  return 'usage--ok'
}

const SERVICE_ICONS: Record<string, string> = {
  frontend: 'mdi mdi-monitor',
  backend: 'mdi mdi-server',
  postgres: 'mdi mdi-database',
  redis: 'mdi mdi-flash-outline',
  storage: 'mdi mdi-folder-network-outline',
  pdm: 'mdi mdi-cube-outline',
  time_tracking: 'mdi mdi-clock-outline',
  stock: 'mdi mdi-package-variant-closed',
}

function serviceIcon(name: string): string {
  return SERVICE_ICONS[name] ?? 'mdi mdi-server-outline'
}

/**
 * Frontend and backend aren't things the backend has a client relationship
 * with like Postgres/Redis/storage, so there is nothing to poll: seeing this
 * panel at all already proves both are up, a down backend or frontend means
 * there is no panel to look at. Shown for a complete picture of the
 * ecosystem, not as real monitoring, always "up" when rendered.
 */
const allServices = computed<ServiceHealth[]>(() => [
  {
    name: 'frontend',
    label: t('adminSettings.host.serviceNames.frontend'),
    status: 'up',
    latency_ms: null,
    detail: null,
  },
  {
    name: 'backend',
    label: t('adminSettings.host.serviceNames.backend'),
    status: 'up',
    latency_ms: null,
    detail: null,
  },
  ...services.value,
])

function serviceStatusText(service: ServiceHealth): string {
  if (service.status === 'up') {
    return service.latency_ms != null
      ? t('adminSettings.host.serviceLatency', { ms: Math.round(service.latency_ms) })
      : t('adminSettings.host.serviceStatus.up')
  }
  if (service.status === 'disabled') return t('adminSettings.host.serviceStatus.disabled')
  return service.detail || t('adminSettings.host.serviceStatus.down')
}
</script>

<template>
  <AdminSettingsTabShell>
    <div v-if="loading" class="host-loading">
      <ProgressSpinner style="width: 2rem; height: 2rem" />
    </div>

    <Message v-else-if="errored" severity="error" :closable="false">
      {{ t('adminSettings.host.loadFailed') }}
    </Message>

    <div v-else-if="stats" class="settings-fields">
      <p class="section-label">{{ t('adminSettings.host.overviewSection') }}</p>
      <p class="hint">{{ t('adminSettings.host.overviewHint') }}</p>

      <p class="overview-label">{{ t('adminSettings.host.overviewIntegrations') }}</p>
      <Message v-if="integrationsFailed" severity="error" :closable="false">
        {{ t('adminSettings.host.overviewLoadFailed') }}
      </Message>
      <div v-else class="service-grid" data-testid="host-integrations">
        <button
          v-for="entry in integrations"
          :key="entry.key"
          type="button"
          class="service-card service-card--link"
          :class="`service-card--${INTEGRATION_DOT[entry.state]}`"
          :data-testid="`integration-${entry.key}`"
          @click="openSettingsTab(INTEGRATIONS[entry.key]?.tab ?? 'host')"
        >
          <span class="service-dot" />
          <i
            :class="`mdi ${INTEGRATIONS[entry.key]?.icon ?? 'mdi-puzzle-outline'}`"
            class="service-card-icon"
            aria-hidden="true"
          />
          <span class="service-body">
            <span class="service-name">{{ t(`adminSettings.host.integrationNames.${entry.key}`) }}</span>
            <span class="service-meta">{{ t(`adminSettings.host.integrationState.${entry.state}`) }}</span>
          </span>
        </button>
      </div>

      <template v-if="modules.length">
        <p class="overview-label">{{ t('adminSettings.host.overviewModules') }}</p>
        <div class="service-grid" data-testid="host-modules">
          <button
            v-for="module in modules"
            :key="module.key"
            type="button"
            class="service-card service-card--link"
            :class="module.on ? 'service-card--up' : 'service-card--disabled'"
            :data-testid="`module-${module.key}`"
            @click="openSettingsTab('features')"
          >
            <span class="service-dot" />
            <i :class="`mdi ${module.icon}`" class="service-card-icon" aria-hidden="true" />
            <span class="service-body">
              <span class="service-name">{{ t(`adminSettings.features.${module.label}`) }}</span>
              <span class="service-meta">{{
                t(`adminSettings.host.moduleState.${module.on ? 'on' : 'off'}`)
              }}</span>
            </span>
          </button>
        </div>
      </template>

      <Divider />

      <p class="section-label">{{ t('adminSettings.host.usageSection') }}</p>

      <div class="field-row">
        <span :id="`${uid}-cpu`" class="field-caption">
          {{ t('adminSettings.host.cpu') }}
          <span class="hint">({{ t('adminSettings.host.cores', { n: stats.cpu_count }) }})</span>
        </span>
        <div class="usage">
          <ProgressBar
            class="usage-bar"
            :aria-labelledby="`${uid}-cpu`"
            :value="Math.round(stats.cpu_percent)"
            :show-value="false"
            :class="usageSeverity(stats.cpu_percent)"
          />
          <span class="usage-percent">{{ Math.round(stats.cpu_percent) }}%</span>
        </div>
      </div>

      <div class="field-row">
        <span :id="`${uid}-memory`" class="field-caption">
          {{ t('adminSettings.host.memory') }}
          <span class="hint">({{ memoryLabel }})</span>
        </span>
        <div class="usage">
          <ProgressBar
            class="usage-bar"
            :aria-labelledby="`${uid}-memory`"
            :value="Math.round(stats.memory_percent)"
            :show-value="false"
            :class="usageSeverity(stats.memory_percent)"
          />
          <span class="usage-percent">{{ Math.round(stats.memory_percent) }}%</span>
        </div>
      </div>

      <div class="field-row">
        <span :id="`${uid}-disk`" class="field-caption">
          {{ t('adminSettings.host.disk') }}
          <span class="hint">({{ diskLabel }})</span>
        </span>
        <div class="usage">
          <ProgressBar
            class="usage-bar"
            :aria-labelledby="`${uid}-disk`"
            :value="Math.round(stats.disk_percent)"
            :show-value="false"
            :class="usageSeverity(stats.disk_percent)"
          />
          <span class="usage-percent">{{ Math.round(stats.disk_percent) }}%</span>
        </div>
      </div>
      <p class="hint">{{ t('adminSettings.host.diskHint') }}</p>

      <Divider />

      <p class="section-label">{{ t('adminSettings.host.servicesSection') }}</p>
      <div class="service-grid">
        <div
          v-for="service in allServices"
          :key="service.name"
          class="service-card"
          :class="`service-card--${service.status}`"
        >
          <span class="service-dot" />
          <i :class="serviceIcon(service.name)" class="service-card-icon" aria-hidden="true" />
          <div class="service-body">
            <span class="service-name">{{ service.label }}</span>
            <span class="service-meta">{{ serviceStatusText(service) }}</span>
          </div>
        </div>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.host.systemSection') }}</p>
      <div class="field-row field-row--readonly">
        <span class="field-caption">{{ t('adminSettings.host.hostname') }}</span>
        <span class="value">{{ stats.hostname }}</span>
      </div>
      <div class="field-row field-row--readonly">
        <span class="field-caption">{{ t('adminSettings.host.domain') }}</span>
        <span class="value">{{ stats.domain }}</span>
      </div>
      <div class="field-row field-row--readonly">
        <span class="field-caption">{{ t('adminSettings.host.platform') }}</span>
        <span class="value">{{ stats.platform }}</span>
      </div>
      <div class="field-row field-row--readonly">
        <span class="field-caption">{{ t('adminSettings.host.hostUptime') }}</span>
        <span class="value">
          {{ formatUptime(stats.boot_time) }}
          <span class="hint">({{ formatISODateTime(stats.boot_time) }})</span>
        </span>
      </div>

      <Divider />

      <p class="section-label">{{ t('adminSettings.host.applicationSection') }}</p>
      <div class="field-row field-row--readonly">
        <span class="field-caption">{{ t('adminSettings.host.appVersion') }}</span>
        <span class="value">{{ stats.app_version }}</span>
      </div>
      <div class="field-row field-row--readonly">
        <span class="field-caption">{{ t('adminSettings.host.pythonVersion') }}</span>
        <span class="value">{{ stats.python_version }}</span>
      </div>
      <div class="field-row field-row--readonly">
        <span class="field-caption">{{ t('adminSettings.host.appUptime') }}</span>
        <span class="value">
          {{ formatUptime(stats.process_start_time) }}
          <span class="hint">({{ formatISODateTime(stats.process_start_time) }})</span>
        </span>
      </div>
    </div>
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
.host-loading {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
}

.hint {
  white-space: nowrap;
}

/* Inline, not stacked: the qualifier in brackets belongs on the same line as
   the value it qualifies. The shared .field-row caption stacks its hint with
   flex-direction: column, which is right for a form field's help text but
   wrong for a parenthetical, so it is overridden for this whole tab. */
.field-row .field-caption {
  flex-direction: row;
  align-items: baseline;
  gap: var(--space-2);
}

.value {
  display: inline-flex;
  align-items: baseline;
  gap: var(--space-2);
}

/* The percentage sits beside the bar rather than inside the fill. OpenVue
   renders its built-in label within the filled portion, so a disk at 2% clipped
   "2%" against a seven-pixel-wide fill and an idle CPU showed no number at all,
   exactly the readings where you most want to see the figure. */
.usage {
  max-width: 22rem;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.usage-bar {
  flex: 1 1 auto;
  --p-progressbar-height: 0.7rem;
}

.usage-percent {
  flex: none;
  min-width: 2.6rem;
  text-align: right;
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
}

.usage--ok {
  --p-progressbar-value-background: var(--p-green-500);
}

.usage--warn {
  --p-progressbar-value-background: var(--p-amber-500);
}

.usage--critical {
  --p-progressbar-value-background: var(--p-red-500);
}

.service-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: var(--space-2);
  max-width: 42rem;
}

.service-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-3);
  border-radius: var(--p-content-border-radius);
  border: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
}

.overview-label {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--p-text-muted-color);
}

// A card that opens its settings tab: a plain button that keeps the card look.
.service-card--link {
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease;

  &:hover,
  &:focus-visible {
    border-color: var(--p-primary-color);
  }

  &:focus-visible {
    outline: 2px solid var(--p-primary-color);
    outline-offset: 1px;
  }
}

.service-dot {
  flex-shrink: 0;
  width: 9px;
  height: 9px;
  border-radius: 50%;
}

.service-card--up .service-dot {
  background: var(--p-green-500);
}

.service-card--down .service-dot {
  background: var(--p-red-500);
}

.service-card--warn .service-dot {
  background: var(--p-amber-500);
}

.service-card--disabled .service-dot {
  background: var(--p-surface-400);
}

.service-card-icon {
  flex-shrink: 0;
  font-size: var(--font-size-lg);
  color: var(--p-text-muted-color);
}

.service-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.service-name {
  font-weight: 600;
  font-size: var(--font-size-sm);
}

.service-meta {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.service-card--down .service-meta {
  color: var(--p-red-500);
}
</style>
