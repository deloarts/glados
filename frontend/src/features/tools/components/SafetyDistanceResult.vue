<script setup lang="ts">
/**
 * The headline of the safety distance tool: the distance rounded up (S, or
 * s_h, s_r or a for the modes of ISO 13857 and ISO 13854), the formula or
 * table that produced it with its clause, K, T and Z where they apply, and
 * every finding of the calculation, errors and warnings first.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useLocaleFormat } from '@/core/i18n/composables/useLocaleFormat'
import { formatDistance, formatQuantity, formatRef, messageText, numberOptions } from '../utils/safetyDistance/format'
import type { SafetyDistanceFormat } from '../utils/safetyDistance/format'
import { modeGroup } from '../utils/safetyDistance/types'
import type { SafetyDistanceResult } from '../utils/safetyDistance/types'
import SafetyDistanceText from './SafetyDistanceText.vue'

const props = defineProps<{ result: SafetyDistanceResult; label: string }>()

const { t } = useI18n()
const { formatNumber } = useLocaleFormat()
const f: SafetyDistanceFormat = { t, number: (value, digits) => formatNumber(value, numberOptions(digits)) }

const P = 'tools.safetyDistance.result'

const alerts = computed(() => props.result.messages.filter((m) => m.level !== 'info'))
const notes = computed(() => props.result.messages.filter((m) => m.level === 'info'))
const failed = computed(() => props.result.messages.some((m) => m.level === 'error'))
const group = computed(() => modeGroup(props.result.mode))
</script>

<template>
  <section class="sd-result" data-testid="sd-result">
    <header class="sd-result-header">
      <h3 class="sd-result-title">{{ t(`${P}.titles.${group}`) }}</h3>
      <span class="sd-result-tag">{{ label }}</span>
    </header>

    <div class="sd-result-value" :class="{ 'sd-result-value--none': result.s === null }" data-testid="sd-s">
      <template v-if="result.s !== null">
        <SafetyDistanceText :text="result.symbol" /> = {{ formatDistance(result.s, f) }}
      </template>
      <template v-else>{{ failed ? t(`${P}.notPermitted`) : t(`${P}.none`) }}</template>
    </div>

    <div class="sd-result-formula">
      <SafetyDistanceText v-if="result.formula" :text="result.formula" data-testid="sd-formula" />
      <span class="sd-result-ref" data-testid="sd-ref">{{ formatRef(result.ref, f, true) }}</span>
    </div>

    <dl class="sd-result-figures">
      <div v-if="result.k !== null" class="sd-result-figure">
        <dt>{{ t(`${P}.approachSpeed`) }} K</dt>
        <dd data-testid="sd-k">{{ formatQuantity(result.k, 'mm/s', f) }}</dd>
      </div>
      <div v-if="result.t !== null" class="sd-result-figure">
        <dt>{{ t(`${P}.responseTime`) }} T</dt>
        <dd data-testid="sd-t-used">{{ formatQuantity(result.t, 's', f) }}</dd>
      </div>
      <div v-if="result.supplement !== null && result.s !== null" class="sd-result-figure">
        <dt>{{ t(`${P}.supplement`) }} Z</dt>
        <dd>{{ formatQuantity(result.supplement, 'mm', f) }}</dd>
      </div>
    </dl>
    <small v-if="result.s !== null && group === 'devices'" class="sd-result-note">{{ t(`${P}.roundedUp`) }}</small>

    <div v-if="alerts.length > 0" class="sd-result-alerts">
      <Message
        v-for="(message, index) in alerts"
        :key="index"
        :severity="message.level === 'error' ? 'error' : 'warn'"
        :closable="false"
        :data-testid="`sd-message-${message.code}`"
      >
        <SafetyDistanceText :text="messageText(message, f)" />
      </Message>
    </div>
    <ul v-if="notes.length > 0" class="sd-result-notes">
      <li v-for="(message, index) in notes" :key="index" :data-testid="`sd-message-${message.code}`">
        <SafetyDistanceText :text="messageText(message, f)" />
      </li>
    </ul>

    <p class="sd-result-disclaimer">{{ t(`${P}.disclaimers.${group}`) }}</p>
  </section>
</template>

<style scoped lang="scss">
.sd-result {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sd-result-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.sd-result-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.sd-result-tag {
  margin-left: auto;
  font-weight: 600;
  text-align: right;
}

.sd-result-value {
  font-size: calc(var(--font-size-xl) * 1.4);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--p-primary-color);

  &--none {
    font-size: var(--font-size-lg);
    color: var(--p-red-500);
  }
}

.sd-result-formula {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-1) var(--space-3);
  font-size: var(--font-size-md);
}

.sd-result-ref {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.sd-result-figures {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1) var(--space-5);
}

.sd-result-figure {
  display: flex;
  gap: var(--space-2);
  font-size: var(--font-size-sm);

  dt {
    color: var(--p-text-muted-color);
  }

  dd {
    margin: 0;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
}

.sd-result-note {
  color: var(--p-text-muted-color);
}

.sd-result-alerts {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.sd-result-notes {
  margin: 0;
  padding-left: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  line-height: 1.4;
}

.sd-result-disclaimer {
  margin: 0;
  padding-top: var(--space-2);
  border-top: 1px solid var(--p-content-border-color);
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  line-height: 1.4;
}
</style>
