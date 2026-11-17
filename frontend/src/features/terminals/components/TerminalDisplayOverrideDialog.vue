<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatISODateTime, instantToPickerDate, pickerDateToInstant } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { HelpDrawer } from '@/shared/help'
import { clearDisplayOverride, setDisplayOverride } from '../api/terminalsApi'
import { activeOverride, displayPowerState } from '../utils/terminalStatus'

import type { TerminalDisplayPower, TerminalResponse } from '../types/terminalResponse'

/** How far ahead the server accepts the end of an override. */
const MAX_OVERRIDE_DAYS = 31
const DAY_MS = 24 * 60 * 60 * 1000

/**
 * Switches a display off or on by hand, next to Reload and Identify. The
 * override ends at the next change of the screen's schedule unless another
 * end is picked, and clearing it hands the display back to the schedule at
 * once. The server decides; the device follows within seconds.
 */
const props = defineProps<{
  terminal: TerminalResponse | null
  /** The current time, so the state shown follows the clock. */
  now: number
}>()

const emit = defineEmits<{ saved: [terminal: TerminalResponse, cleared: boolean] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()

type EndMode = 'next' | 'until'

const form = reactive({
  power: 'off' as TerminalDisplayPower,
  endMode: 'next' as EndMode,
  until: null as Date | null,
})
const submitted = ref(false)
const saving = ref(false)
const errorMessage = ref<string | null>(null)
const explainVisible = ref(false)

const state = computed(() => (props.terminal ? displayPowerState(props.terminal, props.now) : null))
const override = computed(() =>
  props.terminal ? activeOverride(props.terminal, props.now) : null,
)

/**
 * The next change of the schedule, when it is known. While an override
 * holds, the terminal reports the end of the override instead, so the
 * schedule's own next change is not known here and the server works it out.
 */
const nextScheduleChange = computed(() => (override.value ? null : (state.value?.until ?? null)))

/** Without an override and without a change ahead, "until the next change" has no end. */
const nextAvailable = computed(() => override.value !== null || nextScheduleChange.value !== null)

watch(visible, (open) => {
  if (!open) return
  form.power = state.value?.power === 'off' ? 'on' : 'off'
  form.endMode = nextAvailable.value ? 'next' : 'until'
  form.until = null
  submitted.value = false
  errorMessage.value = null
})

const currentText = computed(() => {
  const current = state.value
  if (!current) return ''
  const power = t(`terminals.power.words.${current.power}`)
  if (current.manual && current.until) {
    return t('terminals.override.currentManual', {
      power,
      date: formatISODateTime(current.until),
    })
  }
  if (current.until) {
    return t('terminals.override.currentScheduled', {
      power,
      date: formatISODateTime(current.until),
    })
  }
  return t('terminals.override.currentSteady', { power })
})

const powerOptions = computed(() => [
  { value: 'off', label: t('terminals.override.switchOff'), icon: 'mdi mdi-monitor-off' },
  { value: 'on', label: t('terminals.override.switchOn'), icon: 'mdi mdi-monitor' },
])

const nextLabel = computed(() =>
  nextScheduleChange.value
    ? t('terminals.override.untilNextAt', { date: formatISODateTime(nextScheduleChange.value) })
    : t('terminals.override.untilNext'),
)

const minUntil = computed(() => instantToPickerDate(new Date(props.now)))
const maxUntil = computed(() => instantToPickerDate(new Date(props.now + MAX_OVERRIDE_DAYS * DAY_MS)))

const untilError = computed(() => {
  if (!submitted.value || form.endMode !== 'until') return null
  if (!form.until) return t('terminals.override.errors.untilRequired')
  const instant = pickerDateToInstant(form.until).getTime()
  if (instant <= Date.now()) return t('terminals.override.errors.untilPast')
  if (instant > Date.now() + MAX_OVERRIDE_DAYS * DAY_MS) {
    return t('terminals.override.errors.untilTooFar', { days: MAX_OVERRIDE_DAYS })
  }
  return null
})

async function onSave(): Promise<void> {
  submitted.value = true
  if (untilError.value || !props.terminal) return
  saving.value = true
  errorMessage.value = null
  try {
    const until =
      form.endMode === 'until' && form.until ? pickerDateToInstant(form.until).toISOString() : null
    const saved = await setDisplayOverride(props.terminal.id, { power: form.power, until })
    visible.value = false
    emit('saved', saved, false)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('terminals.errors.unknown')
  } finally {
    saving.value = false
  }
}

async function onClear(): Promise<void> {
  if (!props.terminal) return
  saving.value = true
  errorMessage.value = null
  try {
    const saved = await clearDisplayOverride(props.terminal.id)
    visible.value = false
    emit('saved', saved, true)
  } catch (err) {
    errorMessage.value = extractApiError(err) ?? t('terminals.errors.unknown')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: 'var(--dialog-width-sm)' }">
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('terminals.override.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('terminals.override.help')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('terminals.override.help')"
          @click="explainVisible = true"
        />
      </div>
    </template>

    <form class="dialog-body" @submit.prevent="onSave">
      <p class="current" data-testid="terminal-override-current">{{ currentText }}</p>
      <div class="field">
        <span class="form-label" id="terminal-override-power">{{ t('terminals.override.power') }}</span>
        <SelectButton
          v-model="form.power"
          :options="powerOptions"
          option-label="label"
          option-value="value"
          :allow-empty="false"
          aria-labelledby="terminal-override-power"
          data-testid="terminal-override-power"
        >
          <template #option="{ option }">
            <i :class="option.icon" aria-hidden="true" />
            <span>{{ option.label }}</span>
          </template>
        </SelectButton>
      </div>
      <fieldset class="end-choice">
        <legend class="form-label">{{ t('terminals.override.end') }}</legend>
        <label class="radio-row">
          <RadioButton
            v-model="form.endMode"
            value="next"
            input-id="terminal-override-next"
            :disabled="!nextAvailable"
            data-testid="terminal-override-next"
          />
          <span>{{ nextLabel }}</span>
        </label>
        <small v-if="!nextAvailable" class="hint">{{ t('terminals.override.noNextChange') }}</small>
        <label class="radio-row">
          <RadioButton
            v-model="form.endMode"
            value="until"
            input-id="terminal-override-until-mode"
            data-testid="terminal-override-until-mode"
          />
          <span>{{ t('terminals.override.untilAt') }}</span>
        </label>
        <DatePicker
          v-if="form.endMode === 'until'"
          v-model="form.until"
          input-id="terminal-override-until"
          show-time
          hour-format="24"
          show-icon
          :min-date="minUntil"
          :max-date="maxUntil"
          :invalid="!!untilError"
          :aria-label="t('terminals.override.untilAt')"
          fluid
          data-testid="terminal-override-until"
        />
        <small v-if="untilError" class="field-error" data-testid="terminal-override-until-error">
          {{ untilError }}
        </small>
      </fieldset>
    </form>

    <template #footer>
      <Button
        v-if="override"
        type="button"
        :label="t('terminals.override.clear')"
        icon="mdi mdi-calendar-sync-outline"
        severity="secondary"
        text
        class="footer-start"
        :disabled="saving"
        v-tooltip.top="t('terminals.override.clearHint')"
        data-testid="terminal-override-clear"
        @click="onClear"
      />
      <Message v-if="errorMessage" severity="error" size="small" class="footer-error">
        {{ errorMessage }}
      </Message>
      <Button
        type="button"
        :label="t('common.cancel')"
        severity="secondary"
        text
        :disabled="saving"
        @click="visible = false"
      />
      <Button
        :label="form.power === 'off' ? t('terminals.override.switchOff') : t('terminals.override.switchOn')"
        :icon="form.power === 'off' ? 'mdi mdi-monitor-off' : 'mdi mdi-monitor'"
        :loading="saving"
        data-testid="terminal-override-submit"
        @click="onSave"
      />
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="resources/display-schedule" anchor="override" />
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
  gap: var(--space-3);
}

.current {
  margin: 0;
}

.form-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.end-choice {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin: 0;
  padding: 0;
  border: none;

  legend {
    padding: 0;
    margin-bottom: var(--space-1);
  }
}

.radio-row {
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

.footer-start {
  margin-right: auto;
}

.footer-error {
  flex: 1 1 auto;
  align-self: center;
}
</style>
