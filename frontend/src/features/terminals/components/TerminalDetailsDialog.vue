<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { formatISODateTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { HelpDrawer } from '@/shared/help'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import {
  displayName,
  displayResolution,
  displaySize,
  formatRam,
  uptimeParts,
} from '../utils/deviceDetails'
import { displayPowerState, screenSize } from '../utils/terminalStatus'

import type { TerminalResponse } from '../types/terminalResponse'

/**
 * Everything a terminal and its device reported: the terminal itself, the
 * computer behind the TV and the monitor. Addresses, serials, the host name
 * and the key fingerprint identify a device, so the server sends them only
 * to someone who may manage terminals; for anyone else they are marked as
 * hidden rather than shown as missing.
 */
const props = defineProps<{
  terminal: TerminalResponse | null
  /** The current time, so the display power follows the clock. */
  now: number
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const explainVisible = ref(false)

interface DetailRow {
  key: string
  label: string
  value: string | null
  /** Left out by the server because the reader may not manage terminals. */
  hidden?: boolean
  mono?: boolean
}

interface DetailSection {
  key: string
  title: string
  rows: DetailRow[]
  /** Shown instead of the rows when the device has not reported anything yet. */
  emptyMessage?: string
}

const identifyingVisible = computed(() => props.terminal?.identifying_details_visible ?? true)

const hiddenNote = computed(() =>
  t('terminals.details.hiddenNote', {
    permission: permissionLabel(t, Permission.MANAGE_TERMINALS),
  }),
)

function dateOrNull(iso: string | null | undefined): string | null {
  return iso ? formatISODateTime(iso) : null
}

function yesNo(value: boolean | null | undefined): string | null {
  if (value == null) return null
  return value ? t('common.yes') : t('common.no')
}

function identifying(key: string, label: string, value: string | null, mono = false): DetailRow {
  return { key, label, value, hidden: !identifyingVisible.value, mono }
}

function uptime(seconds: number | null | undefined): string | null {
  if (seconds == null) return null
  const parts = uptimeParts(seconds)
  if (parts.days > 0) return t('terminals.details.uptimeDays', parts)
  return t('terminals.details.uptimeHours', parts)
}

function powerText(terminal: TerminalResponse): string | null {
  const state = displayPowerState(terminal, props.now)
  if (!state) return null
  const power = t(`terminals.power.${state.power}`)
  if (state.manual && state.until) {
    return `${power}, ${t('terminals.power.manualUntil', { date: formatISODateTime(state.until) })}`
  }
  if (state.until) return `${power}, ${t('terminals.power.until', { date: formatISODateTime(state.until) })}`
  return power
}

const sections = computed<DetailSection[]>(() => {
  const terminal = props.terminal
  if (!terminal) return []
  const device = terminal.device
  const size = device ? displaySize(device) : null
  const notReported = t('terminals.details.notReported')

  const terminalRows: DetailRow[] = [
    { key: 'name', label: t('terminals.columns.name'), value: terminal.name },
    { key: 'location', label: t('terminals.columns.location'), value: terminal.location },
    { key: 'status', label: t('terminals.columns.status'), value: t(`terminals.status.${terminal.status}`) },
    { key: 'mode', label: t('terminals.columns.mode'), value: t(`terminals.modes.${terminal.mode}`) },
    { key: 'screen', label: t('terminals.columns.screen'), value: terminal.infoscreen_name },
    { key: 'power', label: t('terminals.columns.display'), value: powerText(terminal) },
    { key: 'firstSeen', label: t('terminals.columns.firstSeen'), value: dateOrNull(terminal.first_seen_at) },
    { key: 'lastSeen', label: t('terminals.columns.lastSeen'), value: dateOrNull(terminal.last_seen_at) },
    { key: 'approvedAt', label: t('terminals.details.approvedAt'), value: dateOrNull(terminal.approved_at) },
    {
      key: 'approvedBy',
      label: t('terminals.details.approvedBy'),
      value: terminal.approved_by?.full_name ?? null,
    },
    { key: 'revokedAt', label: t('terminals.details.revokedAt'), value: dateOrNull(terminal.revoked_at) },
    { key: 'apiKey', label: t('terminals.columns.apiKey'), value: terminal.api_key_name },
    identifying(
      'fingerprint',
      t('terminals.columns.fingerprint'),
      terminal.public_key_fingerprint,
      true,
    ),
    identifying('lastIp', t('terminals.details.lastIp'), terminal.last_ip, true),
    identifying('sessionIp', t('terminals.details.sessionIp'), terminal.last_session_ip, true),
    { key: 'web', label: t('terminals.details.webVersion'), value: terminal.frontend_version },
    { key: 'bridge', label: t('terminals.details.bridgeVersion'), value: terminal.bridge_version },
    { key: 'browser', label: t('terminals.columns.userAgent'), value: terminal.user_agent },
    { key: 'viewport', label: t('terminals.details.viewport'), value: screenSize(terminal) },
  ]

  const computerRows: DetailRow[] = device
    ? [
        { key: 'model', label: t('terminals.details.computerModel'), value: device.computer_model },
        identifying('serial', t('terminals.details.serial'), device.computer_serial, true),
        { key: 'ram', label: t('terminals.details.ram'), value: device.ram_mb != null ? formatRam(device.ram_mb) : null },
        {
          key: 'temperature',
          label: t('terminals.details.cpuTemperature'),
          value:
            device.cpu_temperature_c != null
              ? t('terminals.details.celsius', { value: device.cpu_temperature_c.toFixed(1) })
              : null,
        },
        { key: 'uptime', label: t('terminals.details.uptime'), value: uptime(device.uptime_seconds) },
        { key: 'os', label: t('terminals.details.os'), value: device.os_name },
        { key: 'kernel', label: t('terminals.details.kernel'), value: device.kernel },
        identifying('hostname', t('terminals.details.hostname'), device.hostname, true),
        { key: 'underVoltage', label: t('terminals.details.underVoltage'), value: yesNo(device.under_voltage) },
        { key: 'throttled', label: t('terminals.details.throttled'), value: yesNo(device.throttled) },
      ]
    : []

  const monitorRows: DetailRow[] = device
    ? [
        { key: 'monitor', label: t('terminals.details.monitorModel'), value: displayName(device) },
        identifying('monitorSerial', t('terminals.details.serial'), device.display_serial, true),
        { key: 'resolution', label: t('terminals.details.resolution'), value: displayResolution(device) },
        {
          key: 'size',
          label: t('terminals.details.size'),
          value: size ? t('terminals.details.sizeValue', size) : null,
        },
        { key: 'connector', label: t('terminals.details.connector'), value: device.display_connector },
        { key: 'connected', label: t('terminals.details.connected'), value: yesNo(device.display_connected) },
        { key: 'powerState', label: t('terminals.details.reportedPower'), value: device.display_power_state },
        { key: 'cec', label: t('terminals.details.cec'), value: yesNo(device.cec_available) },
        { key: 'reportedAt', label: t('terminals.details.reportedAt'), value: dateOrNull(device.reported_at) },
      ]
    : []

  return [
    { key: 'terminal', title: t('terminals.details.terminalSection'), rows: terminalRows },
    {
      key: 'computer',
      title: t('terminals.details.computerSection'),
      rows: computerRows,
      emptyMessage: notReported,
    },
    {
      key: 'monitor',
      title: t('terminals.details.monitorSection'),
      rows: monitorRows,
      emptyMessage: notReported,
    },
  ]
})

const title = computed(() =>
  props.terminal?.name
    ? t('terminals.details.titleNamed', { name: props.terminal.name })
    : t('terminals.details.title'),
)
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-md)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ title }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('terminals.details.help')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('terminals.details.help')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <div class="details" data-testid="terminal-details">
      <Message
        v-if="!identifyingVisible"
        severity="info"
        size="small"
        :closable="false"
        data-testid="terminal-details-hidden-note"
      >
        {{ hiddenNote }}
      </Message>

      <fieldset v-for="section in sections" :key="section.key" class="dialog-section">
        <legend>{{ section.title }}</legend>
        <p v-if="section.rows.length === 0" class="empty">{{ section.emptyMessage }}</p>
        <dl v-else class="detail-grid">
          <template v-for="row in section.rows" :key="row.key">
            <dt class="detail-label">{{ row.label }}</dt>
            <dd class="detail-value" :data-testid="`terminal-detail-${row.key}`">
              <span
                v-if="row.hidden"
                class="hidden-value"
                v-tooltip.top="hiddenNote"
                data-testid="terminal-detail-hidden"
              >
                <i class="mdi mdi-lock-outline" aria-hidden="true" />
                {{ t('terminals.details.hidden') }}
              </span>
              <span v-else-if="row.value" :class="{ mono: row.mono }">{{ row.value }}</span>
              <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
            </dd>
          </template>
        </dl>
      </fieldset>
    </div>

    <template #footer>
      <Button :label="t('common.close')" severity="secondary" text @click="visible = false" />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="resources/terminals" anchor="details" />
</template>

<style scoped lang="scss">
.dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.details {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(10rem, auto) 1fr;
  gap: var(--space-1) var(--space-5);
  margin: 0;
}

.detail-label {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.detail-value {
  margin: 0;
  font-size: var(--font-size-sm);
  overflow-wrap: anywhere;
}

.mono {
  font-family: monospace;
}

.hidden-value {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--p-text-muted-color);
  font-style: italic;
}

.empty {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}
</style>
