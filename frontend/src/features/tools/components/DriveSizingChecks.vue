<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { brakeStopText, keyFigures, verdictText } from '../utils/driveSizing/display'
import type { CheckRow } from '../utils/driveSizing/display'
import type { CheckStatus, DriveSizingSuccess } from '../utils/driveSizing/engine'
import { useDriveSizingFormat } from '../utils/driveSizing/format'

// Always shown next to the settings: the checks once the inputs are
// complete, otherwise what is still missing.
const props = defineProps<{
  result: DriveSizingSuccess | null
  rows: readonly CheckRow[]
  warnings: readonly string[]
  errors: readonly string[]
}>()

const { t } = useI18n()
const fmt = useDriveSizingFormat()

const SEVERITY: Record<CheckStatus, 'success' | 'danger' | 'warn' | 'info'> = {
  pass: 'success',
  fail: 'danger',
  warn: 'warn',
  info: 'info',
}

const failed = computed(() => props.rows.filter((row) => row.status === 'fail').length)

const verdict = computed(() => verdictText(failed.value, t))

const figures = computed(() => (props.result ? keyFigures(props.result, fmt) : []))

const brakeStopSentence = computed(() => brakeStopText(props.result?.brakeStop ?? null, t, fmt))

function barWidth(utilisation: number | null): string {
  return `${Math.min(100, Math.max(0, (utilisation ?? 0) * 100))}%`
}
</script>

<template>
  <section class="ds-checks" data-testid="ds-checks">
    <header class="ds-checks-header">
      <h3 class="ds-checks-title">{{ t('tools.driveSizing.checks.title') }}</h3>
      <Tag v-if="result" :value="verdict" :severity="failed === 0 ? 'success' : 'danger'" data-testid="ds-verdict" />
    </header>

    <Message v-if="!result" severity="warn" :closable="false" data-testid="ds-errors">
      <strong>{{ t('tools.driveSizing.issues.errorsTitle') }}</strong>
      <ul class="ds-issue-list">
        <li v-for="text in errors" :key="text">{{ text }}</li>
      </ul>
    </Message>
    <template v-else>

    <dl class="ds-figures">
      <div v-for="figure in figures" :key="figure.key" class="ds-figure">
        <dt>{{ t(`tools.driveSizing.figures.${figure.key}`) }}</dt>
        <dd :data-testid="`ds-figure-${figure.key}`">{{ figure.value }}</dd>
      </div>
    </dl>

    <div class="ds-checks-scroll">
      <table class="ds-checks-table">
        <thead>
          <tr>
            <th scope="col">{{ t('tools.driveSizing.checks.columns.check') }}</th>
            <th scope="col" class="ds-num">{{ t('tools.driveSizing.checks.columns.value') }}</th>
            <th scope="col" class="ds-num">{{ t('tools.driveSizing.checks.columns.limit') }}</th>
            <th scope="col">{{ t('tools.driveSizing.checks.columns.utilisation') }}</th>
            <th scope="col">{{ t('tools.driveSizing.checks.columns.status') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.key" :data-testid="`ds-check-${row.key}`">
            <th scope="row">
              <span class="ds-check-name">{{ row.name }}</span>
              <small class="ds-check-note">{{ row.note }}</small>
            </th>
            <td class="ds-num" :data-testid="`ds-check-${row.key}-value`">{{ row.value }}</td>
            <td class="ds-num">
              <span v-if="row.limitSymbol" class="ds-symbol">{{ row.limitSymbol[0] }}<sub>{{ row.limitSymbol[1] }}</sub></span>
              {{ row.limit }}
            </td>
            <td>
              <div v-if="row.utilisation !== null" class="ds-util">
                <span class="ds-bar" aria-hidden="true">
                  <span :class="['ds-bar-fill', `ds-bar-fill--${row.status}`]" :style="{ width: barWidth(row.utilisation) }" />
                </span>
                <span class="ds-util-text" :data-testid="`ds-check-${row.key}-utilisation`">{{ row.utilisationText }}</span>
              </div>
            </td>
            <td>
              <Tag :value="row.statusText" :severity="SEVERITY[row.status]" :data-testid="`ds-check-${row.key}-status`" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="brakeStopSentence" class="ds-brake-stop" data-testid="ds-brake-stop">
      <h4 class="ds-brake-stop-title">{{ t('tools.driveSizing.brakeStop.title') }}</h4>
      <p class="ds-brake-stop-text">{{ brakeStopSentence }}</p>
      <small class="ds-check-note">{{ t('tools.driveSizing.brakeStop.note') }}</small>
    </div>

    <Message v-if="warnings.length > 0" severity="warn" :closable="false" data-testid="ds-warnings">
      <strong>{{ t('tools.driveSizing.issues.warningsTitle') }}</strong>
      <ul class="ds-issue-list">
        <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
      </ul>
    </Message>
    </template>
  </section>
</template>

<style scoped lang="scss">
.ds-checks {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

.ds-checks-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.ds-checks-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.ds-figures {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
  gap: var(--space-2);
}

.ds-figure {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);

  dt {
    font-size: var(--font-size-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--p-text-muted-color);
  }

  dd {
    margin: 0;
    font-size: var(--font-size-lg);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
}

.ds-checks-scroll {
  overflow-x: auto;
}

.ds-checks-table {
  width: 100%;
  border-collapse: collapse;

  th,
  td {
    padding: var(--space-2) var(--space-2);
    text-align: left;
    vertical-align: middle;
    border-top: 1px solid var(--p-content-border-color);
  }

  thead th {
    border-top: none;
    font-size: var(--font-size-sm);
    font-weight: 600;
    white-space: nowrap;
    color: var(--p-text-muted-color);
  }

  tbody th {
    font-weight: 400;
  }
}

.ds-num {
  text-align: right !important;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.ds-check-name {
  display: block;
  font-weight: 600;
}

.ds-check-note {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.ds-symbol {
  margin-right: var(--space-1);
  font-style: italic;
  color: var(--p-text-muted-color);

  sub {
    font-style: normal;
  }
}

.ds-util {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 8rem;
}

.ds-bar {
  flex: 1;
  height: 0.5rem;
  overflow: hidden;
  background: var(--p-content-hover-background);
  border-radius: 999px;
}

.ds-bar-fill {
  display: block;
  height: 100%;
  border-radius: 999px;

  &--pass {
    background: var(--p-green-500);
  }

  &--fail {
    background: var(--p-red-500);
  }

  &--warn {
    background: var(--p-orange-500);
  }

  &--info {
    background: var(--p-blue-500);
  }
}

.ds-util-text {
  min-width: 3rem;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.ds-brake-stop {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.ds-brake-stop-title {
  margin: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.ds-brake-stop-text {
  margin: 0;
}

.ds-issue-list {
  margin: var(--space-1) 0 0;
  padding-left: var(--space-4);
}
</style>
