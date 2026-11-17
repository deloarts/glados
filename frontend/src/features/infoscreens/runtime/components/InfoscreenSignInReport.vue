<script setup lang="ts">
import { computed, useSlots } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePublicBrandingStore } from '@/core/stores/publicBrandingStore'

import { useTickingNow } from '../composables/useTickingNow'
import { clockParts } from '../utils/infoscreenFormat'
import type { SignInReport } from '../utils/signInReport'

// Every waiting screen of a wall display in one frame: a status code, a
// plain title and sentence, the sign-in steps with the one that stopped,
// what to check, and a footer with the retry attempt, the device and the
// build. The pairing code goes into the `side` slot, which takes the place
// of the check box. Sized against the short side of the display, so it
// reads the same on a landscape and a portrait screen.
defineProps<{
  report: SignInReport
}>()

const { t } = useI18n()
const slots = useSlots()
const brandingStore = usePublicBrandingStore()
const now = useTickingNow()

const clock = computed(() => clockParts(now.value).hoursMinutes)
const hasSide = computed(() => !!slots.side)
</script>

<template>
  <section
    class="sign-in-report"
    :class="{ 'sign-in-report--split': hasSide }"
    role="status"
    :data-state="report.state"
    data-testid="sign-in-report"
  >
    <header class="report-bar">
      <span class="report-brand">
        {{ brandingStore.appName }}
        <span class="report-brand-suffix">{{ t('infoscreenRuntime.title') }}</span>
      </span>
      <span class="report-clock">{{ clock }}</span>
    </header>

    <div class="report-body">
      <div class="report-main">
        <div class="report-head">
          <span class="report-code" :class="`tone--${report.tone}`" data-testid="report-code">
            {{ report.code }}
          </span>
          <h1 class="report-title" data-testid="report-title">{{ report.title }}</h1>
          <p class="report-text">{{ report.text }}</p>
        </div>

        <ol class="report-steps">
          <li
            v-for="(step, index) in report.steps"
            :key="step.id"
            class="report-step"
            :class="`step--${step.state}`"
            :data-state="step.state"
            :data-testid="`report-step-${step.id}`"
          >
            <span class="step-glyph" aria-hidden="true">
              <svg v-if="step.state === 'ok'" viewBox="0 0 24 24" class="glyph glyph--ok">
                <circle cx="12" cy="12" r="10" stroke-width="2" />
                <path d="M7.5 12.3l3 3 6-6.3" />
              </svg>
              <svg v-else-if="step.state === 'failed'" viewBox="0 0 24 24" class="glyph glyph--failed">
                <circle cx="12" cy="12" r="10" stroke-width="2" />
                <path d="M8.5 8.5l7 7M15.5 8.5l-7 7" />
              </svg>
              <svg v-else-if="step.state === 'waiting'" viewBox="0 0 24 24" class="glyph glyph--waiting">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 7v5l3.2 2" />
              </svg>
              <svg v-else-if="step.state === 'running'" viewBox="0 0 24 24" class="glyph glyph--running">
                <circle cx="12" cy="12" r="10" class="glyph-track" stroke-width="2" />
                <g class="glyph-spin"><path d="M12 2a10 10 0 0 1 10 10" /></g>
              </svg>
              <svg v-else viewBox="0 0 24 24" class="glyph glyph--idle">
                <circle cx="12" cy="12" r="10" stroke-dasharray="3 3.2" />
              </svg>
            </span>
            <span class="step-label">{{ index + 1 }}&nbsp;&nbsp;{{ step.label }}</span>
            <span class="step-value">{{ step.value }}</span>
            <span class="step-result" data-testid="report-step-result">{{ step.result }}</span>
          </li>
        </ol>

        <div v-if="report.hint && !hasSide" class="report-panel report-hint" data-testid="report-hint">
          <strong class="report-panel-label">{{ t('infoscreenRuntime.report.check') }}</strong>
          {{ report.hint }}
        </div>
      </div>

      <slot name="side" />
    </div>

    <footer class="report-foot">
      <span
        class="report-status"
        :class="{ 'report-status--healthy': report.footer.healthy }"
        data-testid="report-status"
      >
        {{ report.footer.status }}
      </span>
      <span data-testid="report-device">{{ report.footer.device }}</span>
      <span>{{ report.footer.build }}</span>
    </footer>
  </section>
</template>

<style scoped lang="scss">
// One unit is a pixel of a 1080 pixel short side, so the frame keeps its
// proportions on any display size and orientation. The colours below are
// shared with the pairing panel in the side slot through inheritance.
.sign-in-report {
  --u: calc(100vmin / 1080);
  --report-bg: var(--p-surface-50);
  --report-panel: var(--p-surface-0);
  --report-line: var(--p-content-border-color);
  --report-fg: var(--p-text-color);
  --report-muted: var(--p-text-muted-color);
  --report-faint: var(--p-surface-400);
  --report-ok: var(--p-green-700);
  --report-warn: var(--p-orange-600);
  --report-fail: var(--p-red-600);
  --report-wait: var(--p-primary-color);
  --report-mono: 'DejaVu Sans Mono', ui-monospace, monospace;

  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--report-bg);
  color: var(--report-fg);
  font-family: var(--font-body);
}

.p-dark .sign-in-report {
  --report-bg: var(--p-surface-950);
  --report-panel: var(--p-surface-900);
  --report-faint: var(--p-surface-600);
  --report-ok: var(--p-green-400);
  --report-warn: var(--p-amber-400);
  --report-fail: var(--p-red-400);
}

.report-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: calc(18 * var(--u)) calc(40 * var(--u));
  // The app's header: primary bar, white text in every theme.
  background: var(--p-primary-500);
  color: var(--on-accent);
  font-size: calc(34 * var(--u));
}

.report-brand {
  font-family: var(--font-brand);
  letter-spacing: 1px;
  text-transform: uppercase;
}

.report-brand-suffix {
  margin-left: calc(14 * var(--u));
  font-family: var(--font-head);
  letter-spacing: 0.04em;
  opacity: 0.75;
}

.report-clock {
  font-family: var(--font-head);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.report-body {
  flex: 1 1 auto;
  min-height: 0;
  display: grid;
  align-content: center;
  gap: calc(64 * var(--u));
  padding: calc(72 * var(--u)) calc(96 * var(--u)) calc(48 * var(--u));
}

.sign-in-report--split .report-body {
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  align-items: center;
}

.report-main {
  display: flex;
  flex-direction: column;
  gap: calc(40 * var(--u));
  min-width: 0;
}

.report-head {
  display: flex;
  flex-direction: column;
  gap: calc(16 * var(--u));
}

.report-code {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: calc(14 * var(--u));
  padding: calc(6 * var(--u)) calc(16 * var(--u)) calc(6 * var(--u)) calc(12 * var(--u));
  border: calc(2 * var(--u)) solid currentColor;
  border-radius: calc(6 * var(--u));
  font-family: var(--report-mono);
  font-size: calc(24 * var(--u));
  font-weight: 600;
  letter-spacing: 0.06em;

  &::before {
    content: '';
    width: calc(14 * var(--u));
    height: calc(14 * var(--u));
    border-radius: 50%;
    background: currentColor;
  }
}

.tone--run {
  color: var(--report-muted);

  &::before {
    animation: report-pulse 1.4s ease-in-out infinite;
  }
}

.tone--wait {
  color: var(--report-wait);
}

.tone--warn {
  color: var(--report-warn);
}

.tone--fail {
  color: var(--report-fail);
}

.report-title {
  margin: 0;
  font-family: var(--font-head);
  font-size: calc(64 * var(--u));
  font-weight: 700;
  line-height: 1.1;
  text-wrap: balance;
}

.report-text {
  margin: 0;
  max-width: 52ch;
  font-size: calc(32 * var(--u));
  line-height: 1.35;
  color: var(--report-muted);
}

.report-steps {
  display: grid;
  grid-template-columns: calc(40 * var(--u)) auto minmax(0, 1fr) auto;
  column-gap: calc(24 * var(--u));
  margin: 0;
  padding: 0;
  list-style: none;
  border-top: calc(2 * var(--u)) solid var(--report-line);
  font-size: calc(28 * var(--u));
}

.report-step {
  display: contents;

  > * {
    display: flex;
    align-items: center;
    min-width: 0;
    padding: calc(14 * var(--u)) 0;
    border-bottom: calc(2 * var(--u)) solid var(--report-line);
  }
}

.step-glyph {
  justify-content: center;
}

.glyph {
  width: calc(30 * var(--u));
  height: calc(30 * var(--u));
  fill: none;
  stroke-width: 2.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.glyph--ok {
  stroke: var(--report-ok);
}

.glyph--failed {
  stroke: var(--report-fail);
}

.glyph--waiting {
  stroke: var(--report-wait);
  stroke-width: 2.2;
}

.glyph--running {
  stroke: var(--report-muted);

  .glyph-track {
    stroke: var(--report-line);
  }
}

.glyph-spin {
  transform-origin: 50% 50%;
  animation: report-spin 1s linear infinite;
}

.glyph--idle {
  stroke: var(--report-faint);
  stroke-width: 2;
}

.step-label {
  font-weight: 700;
  white-space: nowrap;
}

.step-value {
  display: block;
  align-self: stretch;
  overflow: hidden;
  font-family: var(--report-mono);
  font-size: calc(24 * var(--u));
  line-height: 1.75;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: var(--report-muted);
}

.step-result {
  justify-content: flex-end;
  font-family: var(--report-mono);
  font-size: calc(24 * var(--u));
  white-space: nowrap;
}

.step--idle {
  .step-label,
  .step-value,
  .step-result {
    color: var(--report-faint);
  }
}

.step--ok .step-result {
  color: var(--report-ok);
}

.step--failed {
  .step-label,
  .step-result {
    color: var(--report-fail);
  }
}

.step--waiting {
  .step-label,
  .step-result {
    color: var(--report-wait);
  }
}

.step--running .step-result {
  color: var(--report-muted);
}

// A box of the panel colour, for what to check here and for the pairing
// panel's approve hint.
.report-panel {
  padding: calc(22 * var(--u)) calc(28 * var(--u));
  border: calc(2 * var(--u)) solid var(--report-line);
  border-radius: calc(8 * var(--u));
  background: var(--report-panel);
  font-size: calc(28 * var(--u));
  line-height: 1.4;
}

.report-panel-label {
  display: block;
  margin-bottom: calc(8 * var(--u));
  font-family: var(--report-mono);
  font-size: calc(20 * var(--u));
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--report-muted);
}

.report-foot {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: calc(8 * var(--u)) calc(40 * var(--u));
  padding: calc(14 * var(--u)) calc(40 * var(--u));
  border-top: calc(2 * var(--u)) solid var(--report-line);
  font-family: var(--report-mono);
  font-size: calc(21 * var(--u));
  color: var(--report-muted);

  > span {
    white-space: nowrap;
  }
}

.report-status::before {
  content: '';
  display: inline-block;
  width: calc(12 * var(--u));
  height: calc(12 * var(--u));
  margin-right: calc(12 * var(--u));
  border-radius: 50%;
  background: var(--report-warn);
  vertical-align: 1px;
  animation: report-pulse 1.6s ease-in-out infinite;
}

.report-status--healthy::before {
  background: var(--report-wait);
}

@media (orientation: portrait) {
  .report-body {
    gap: calc(56 * var(--u));
    padding: calc(72 * var(--u)) calc(64 * var(--u)) calc(48 * var(--u));
  }

  .sign-in-report--split .report-body {
    grid-template-columns: minmax(0, 1fr);
  }

  .report-steps {
    grid-template-columns: calc(40 * var(--u)) auto minmax(0, 1fr);
  }

  .report-step > .step-glyph,
  .report-step > .step-label,
  .report-step > .step-value {
    padding-bottom: calc(4 * var(--u));
    border-bottom: 0;
  }

  .report-step > .step-result {
    grid-column: 2 / -1;
    justify-content: flex-start;
    margin-top: calc(-2 * var(--u));
    padding-top: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .glyph-spin,
  .tone--run::before,
  .report-status::before {
    animation: none;
  }
}

@keyframes report-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes report-pulse {
  50% {
    opacity: 0.25;
  }
}
</style>
