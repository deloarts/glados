<script setup lang="ts">
import { computed, onScopeDispose, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime, instantToPickerDate, pickerDateToInstant } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { HelpDrawer } from '@/shared/help'
import {
  countTerminalBroadcastReach,
  endTerminalBroadcast,
  sendTerminalBroadcast,
} from '../api/terminalBroadcastsApi'
import {
  BROADCAST_MAX_DAYS,
  BROADCAST_TEXT_MAX_LENGTH,
  type BroadcastAudienceMode,
  type BroadcastQuickPick,
  audienceRequest,
  broadcastTagSeverity,
  quickPickUntil,
} from '../utils/terminalBroadcasts'

import type {
  TerminalBroadcastResponse,
  TerminalBroadcastSeverity,
  TerminalBroadcastStyle,
  TerminalResponse,
  TerminalScreenOption,
} from '../types/terminalResponse'

/** How long the reach count waits for the audience to settle before asking the server. */
const REACH_DEBOUNCE_MS = 300
const DAY_MS = 24 * 60 * 60 * 1000

/**
 * A one-time message on many terminals at once. The dialog lists the
 * messages shown right now, each with its audience, its end and End Now,
 * and below them a form for a new one: the text in Markdown, how urgent it
 * is, whether it runs as a banner or covers the screen, until when, and who
 * sees it. The audience is every terminal or a pick of terminals and of
 * infoscreens, and the dialog says how many terminals that reaches now.
 */
const props = defineProps<{
  broadcasts: TerminalBroadcastResponse[]
  /** The approved terminals, the ones a message can reach. */
  terminals: TerminalResponse[]
  screens: TerminalScreenOption[]
  canManage: boolean
  /** The tooltip of a disabled button, naming the missing permission. */
  missingHint: string
}>()

const emit = defineEmits<{
  sent: [broadcast: TerminalBroadcastResponse]
  ended: [broadcast: TerminalBroadcastResponse]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

const form = reactive({
  text: '',
  severity: 'info' as TerminalBroadcastSeverity,
  style: 'banner' as TerminalBroadcastStyle,
  showUntil: null as Date | null,
  audience: 'all' as BroadcastAudienceMode,
  terminalIds: [] as number[],
  infoscreenIds: [] as number[],
})
const submitted = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const endingId = ref<number | null>(null)
const explainVisible = ref(false)
const reach = ref<number | null>(null)

watch(visible, (open) => {
  if (!open) return
  form.text = ''
  form.severity = 'info'
  form.style = 'banner'
  form.showUntil = quickPickUntil('hour', new Date())
  form.audience = 'all'
  form.terminalIds = []
  form.infoscreenIds = []
  submitted.value = false
  errorMessage.value = null
  reach.value = null
})

const severityOptions = computed(() =>
  (['info', 'warning', 'danger'] as const).map((value) => ({
    value,
    label: t(`terminals.broadcast.severities.${value}`),
  })),
)

const styleOptions = computed(() =>
  (['banner', 'fullscreen'] as const).map((value) => ({
    value,
    label: t(`terminals.broadcast.styles.${value}`),
  })),
)

const audienceOptions = computed(() =>
  (['all', 'terminals', 'infoscreens', 'both'] as const).map((value) => ({
    value,
    label: t(`terminals.broadcast.audiences.${value}`),
  })),
)

const QUICK_PICKS: BroadcastQuickPick[] = ['quarterHour', 'hour', 'endOfDay']

const terminalOptions = computed(() =>
  props.terminals.map((terminal) => ({
    id: terminal.id,
    label: terminal.name ?? t('terminals.unnamed'),
  })),
)

const pickTerminals = computed(() => form.audience === 'terminals' || form.audience === 'both')
const pickScreens = computed(() => form.audience === 'infoscreens' || form.audience === 'both')

const request = computed(() =>
  audienceRequest(form.audience, form.terminalIds, form.infoscreenIds),
)

// The reach follows the audience while the dialog is open, debounced so a
// few quick clicks in a picker ask the server once.
let reachTimer: ReturnType<typeof setTimeout> | null = null
let reachEpoch = 0

function scheduleReach(): void {
  if (reachTimer) clearTimeout(reachTimer)
  if (!visible.value) return
  reachTimer = setTimeout(() => {
    reachTimer = null
    const epoch = ++reachEpoch
    countTerminalBroadcastReach(request.value)
      .then((count) => {
        if (epoch === reachEpoch) reach.value = count
      })
      .catch(() => {
        if (epoch === reachEpoch) reach.value = null
      })
  }, REACH_DEBOUNCE_MS)
}

watch([visible, request], scheduleReach, { deep: true })
onScopeDispose(() => {
  if (reachTimer) clearTimeout(reachTimer)
})

const textError = computed(() =>
  submitted.value && form.text.trim() === '' ? t('terminals.broadcast.errors.textRequired') : null,
)

const untilError = computed(() => {
  if (!submitted.value) return null
  if (!form.showUntil) return t('terminals.broadcast.errors.untilRequired')
  const instant = pickerDateToInstant(form.showUntil).getTime()
  if (instant <= Date.now()) return t('terminals.broadcast.errors.untilPast')
  if (instant > Date.now() + BROADCAST_MAX_DAYS * DAY_MS) {
    return t('terminals.broadcast.errors.untilTooFar', { days: BROADCAST_MAX_DAYS })
  }
  return null
})

const audienceError = computed(() => {
  if (!submitted.value || form.audience === 'all') return null
  const picked =
    (pickTerminals.value ? form.terminalIds.length : 0) +
    (pickScreens.value ? form.infoscreenIds.length : 0)
  return picked === 0 ? t('terminals.broadcast.errors.audienceEmpty') : null
})

const minUntil = computed(() => instantToPickerDate(new Date()))

function applyQuickPick(pick: BroadcastQuickPick): void {
  form.showUntil = quickPickUntil(pick, new Date())
}

function terminalName(id: number): string {
  const terminal = props.terminals.find((row) => row.id === id)
  return terminal?.name ?? t('terminals.unnamed')
}

function screenName(id: number): string {
  return props.screens.find((row) => row.id === id)?.name ?? `#${id}`
}

/** "All terminals", or the picked terminals and infoscreens by count, with their names in a tooltip. */
function audienceText(broadcast: TerminalBroadcastResponse): string {
  if (broadcast.all_terminals) return t('terminals.broadcast.audiences.all')
  const parts: string[] = []
  if (broadcast.terminal_ids.length > 0) {
    parts.push(
      t(
        'terminals.broadcast.terminalCount',
        { count: broadcast.terminal_ids.length },
        broadcast.terminal_ids.length,
      ),
    )
  }
  if (broadcast.infoscreen_ids.length > 0) {
    parts.push(
      t(
        'terminals.broadcast.screenCount',
        { count: broadcast.infoscreen_ids.length },
        broadcast.infoscreen_ids.length,
      ),
    )
  }
  return parts.join(', ')
}

function audienceNames(broadcast: TerminalBroadcastResponse): string | undefined {
  if (broadcast.all_terminals) return undefined
  return [
    ...broadcast.terminal_ids.map(terminalName),
    ...broadcast.infoscreen_ids.map(screenName),
  ].join(', ')
}

async function onSend(): Promise<void> {
  submitted.value = true
  if (textError.value || untilError.value || audienceError.value || !props.canManage) return
  if (!form.showUntil) return
  saving.value = true
  errorMessage.value = null
  try {
    const sent = await sendTerminalBroadcast({
      text: form.text.trim(),
      severity: form.severity,
      style: form.style,
      show_until: pickerDateToInstant(form.showUntil).toISOString(),
      ...request.value,
    })
    visible.value = false
    emit('sent', sent)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('terminals.broadcast.errors.unknown')
  } finally {
    saving.value = false
  }
}

async function onEnd(broadcast: TerminalBroadcastResponse): Promise<void> {
  endingId.value = broadcast.id
  errorMessage.value = null
  try {
    emit('ended', await endTerminalBroadcast(broadcast.id))
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('terminals.broadcast.errors.unknown')
  } finally {
    endingId.value = null
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-md)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('terminals.broadcast.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('terminals.broadcast.help')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('terminals.broadcast.help')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <div class="dialog-body">
      <fieldset class="dialog-section">
        <legend>{{ t('terminals.broadcast.activeSection') }}</legend>
        <p v-if="broadcasts.length === 0" class="hint" data-testid="terminal-broadcasts-empty">
          {{ t('terminals.broadcast.noneActive') }}
        </p>
        <ul v-else class="broadcasts" data-testid="terminal-broadcasts-active">
          <li
            v-for="broadcast in broadcasts"
            :key="broadcast.id"
            class="broadcast"
            data-testid="terminal-broadcast"
          >
            <div class="broadcast-head">
              <Tag
                :value="t(`terminals.broadcast.severities.${broadcast.severity}`)"
                :severity="broadcastTagSeverity(broadcast.severity)"
              />
              <Tag :value="t(`terminals.broadcast.styles.${broadcast.style}`)" severity="secondary" />
              <span class="broadcast-meta" v-tooltip.top="audienceNames(broadcast)">
                <i class="mdi mdi-account-group-outline" aria-hidden="true" />
                {{ audienceText(broadcast) }}
              </span>
              <span class="broadcast-meta">
                {{ t('terminals.broadcast.reachCount', { count: broadcast.reach_count }, broadcast.reach_count) }}
              </span>
              <span class="broadcast-meta">
                {{ t('terminals.broadcast.until', { date: formatISODateTime(broadcast.show_until) }) }}
              </span>
              <span v-if="broadcast.created_by" class="broadcast-meta">
                {{ t('terminals.broadcast.by', { name: broadcast.created_by.full_name }) }}
              </span>
            </div>
            <div class="broadcast-body">
              <p class="broadcast-text">{{ broadcast.text }}</p>
              <span v-tooltip.top="canManage ? undefined : missingHint">
                <Button
                  :label="t('terminals.broadcast.endNow')"
                  icon="mdi mdi-stop-circle-outline"
                  size="small"
                  severity="danger"
                  text
                  :disabled="!canManage"
                  :loading="endingId === broadcast.id"
                  data-testid="terminal-broadcast-end"
                  @click="onEnd(broadcast)"
                />
              </span>
            </div>
          </li>
        </ul>
      </fieldset>

      <fieldset class="dialog-section" :disabled="!canManage">
        <legend>{{ t('terminals.broadcast.newSection') }}</legend>
        <div class="field">
          <label for="terminal-broadcast-text">{{ t('terminals.broadcast.fields.text') }} *</label>
          <Textarea
            id="terminal-broadcast-text"
            v-model="form.text"
            rows="4"
            auto-resize
            :maxlength="BROADCAST_TEXT_MAX_LENGTH"
            :invalid="!!textError"
            fluid
            data-testid="terminal-broadcast-text"
          />
          <small class="hint">{{ t('terminals.broadcast.fields.textHint') }}</small>
          <small v-if="textError" class="field-error">{{ textError }}</small>
        </div>
        <div class="row">
          <div class="field">
            <span id="terminal-broadcast-severity" class="form-label">
              {{ t('terminals.broadcast.fields.severity') }}
            </span>
            <SelectButton
              v-model="form.severity"
              :options="severityOptions"
              option-label="label"
              option-value="value"
              :allow-empty="false"
              size="small"
              aria-labelledby="terminal-broadcast-severity"
              data-testid="terminal-broadcast-severity"
            />
          </div>
          <div class="field">
            <span id="terminal-broadcast-style" class="form-label">
              {{ t('terminals.broadcast.fields.style') }}
            </span>
            <SelectButton
              v-model="form.style"
              :options="styleOptions"
              option-label="label"
              option-value="value"
              :allow-empty="false"
              size="small"
              aria-labelledby="terminal-broadcast-style"
              data-testid="terminal-broadcast-style"
            />
          </div>
        </div>
        <small class="hint">{{ t(`terminals.broadcast.styleHints.${form.style}`) }}</small>
        <div class="field">
          <label for="terminal-broadcast-until">{{ t('terminals.broadcast.fields.showUntil') }} *</label>
          <div class="until-row">
            <Button
              v-for="pick in QUICK_PICKS"
              :key="pick"
              type="button"
              :label="t(`terminals.broadcast.quickPicks.${pick}`)"
              size="small"
              severity="secondary"
              outlined
              :data-testid="`terminal-broadcast-pick-${pick}`"
              @click="applyQuickPick(pick)"
            />
            <DatePicker
              v-model="form.showUntil"
              input-id="terminal-broadcast-until"
              show-time
              hour-format="24"
              show-icon
              :min-date="minUntil"
              :invalid="!!untilError"
              class="until-picker"
              data-testid="terminal-broadcast-until"
            />
          </div>
          <small v-if="untilError" class="field-error" data-testid="terminal-broadcast-until-error">
            {{ untilError }}
          </small>
        </div>
        <div class="field">
          <span id="terminal-broadcast-audience" class="form-label">
            {{ t('terminals.broadcast.fields.audience') }}
          </span>
          <SelectButton
            v-model="form.audience"
            :options="audienceOptions"
            option-label="label"
            option-value="value"
            :allow-empty="false"
            size="small"
            aria-labelledby="terminal-broadcast-audience"
            data-testid="terminal-broadcast-audience"
          />
        </div>
        <div v-if="pickTerminals" class="field">
          <label id="terminal-broadcast-terminals-label" for="terminal-broadcast-terminals">{{ t('terminals.broadcast.fields.terminals') }}</label>
          <MultiSelect
            v-model="form.terminalIds"
            input-id="terminal-broadcast-terminals"
            aria-labelledby="terminal-broadcast-terminals-label"
            :options="terminalOptions"
            option-label="label"
            option-value="id"
            :placeholder="t('terminals.broadcast.fields.terminalsPlaceholder')"
            display="chip"
            filter
            fluid
            data-testid="terminal-broadcast-terminals"
          />
        </div>
        <div v-if="pickScreens" class="field">
          <label id="terminal-broadcast-screens-label" for="terminal-broadcast-screens">{{ t('terminals.broadcast.fields.screens') }}</label>
          <MultiSelect
            v-model="form.infoscreenIds"
            input-id="terminal-broadcast-screens"
            aria-labelledby="terminal-broadcast-screens-label"
            :options="screens"
            option-label="name"
            option-value="id"
            :placeholder="t('terminals.broadcast.fields.screensPlaceholder')"
            display="chip"
            filter
            fluid
            data-testid="terminal-broadcast-screens"
          />
          <small class="hint">{{ t('terminals.broadcast.fields.screensHint') }}</small>
        </div>
        <small v-if="audienceError" class="field-error">{{ audienceError }}</small>
        <div class="reach" data-testid="terminal-broadcast-reach">
          <i class="mdi mdi-monitor-multiple" aria-hidden="true" />
          <span v-if="reach === null" class="text-muted">{{ t('terminals.broadcast.reachUnknown') }}</span>
          <span v-else>{{ t('terminals.broadcast.reachNow', { count: reach }, reach) }}</span>
        </div>
      </fieldset>
    </div>

    <template #footer>
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        type="button"
        :label="t('common.close')"
        severity="secondary"
        text
        :disabled="saving"
        @click="visible = false"
      />
      <span v-tooltip.top="canManage ? undefined : missingHint">
        <Button
          :label="t('terminals.broadcast.send')"
          icon="mdi mdi-send-outline"
          :loading="saving"
          :disabled="!canManage"
          data-testid="terminal-broadcast-send"
          @click="onSend"
        />
      </span>
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="resources/terminal-messages" />
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

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field {
  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.form-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3) var(--space-5);
}

.until-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.until-picker {
  flex: 1 1 12rem;
}

.broadcasts {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.broadcast {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-border-radius-md);
}

.broadcast-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1) var(--space-3);
}

.broadcast-meta {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.broadcast-body {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

// The text as typed, Markdown marks included, a few lines at most.
.broadcast-text {
  margin: 0;
  min-width: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.reach {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
}

.hint {
  margin: 0;
}

.field-error {
  color: var(--p-red-500);
  font-size: var(--font-size-sm);
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
