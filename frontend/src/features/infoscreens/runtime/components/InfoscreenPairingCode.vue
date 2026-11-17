<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { formatInstantTime } from '../utils/infoscreenFormat'

// The pairing code a waiting display shows, one character per box, large
// enough to read off the wall while typing it into the approve dialog, with
// how long it is valid and where to approve it. It sits in the side slot of
// the sign-in report and takes its unit and colours from there.
const props = defineProps<{
  code: string | null
  expiresAt: string | null
}>()

const { t } = useI18n()

const characters = computed(() => (props.code ? Array.from(props.code) : []))
const validUntil = computed(() => formatInstantTime(props.expiresAt))
</script>

<template>
  <section class="pairing">
    <h2 class="pairing-label">{{ t('infoscreenRuntime.register.heading') }}</h2>
    <div
      v-if="characters.length > 0"
      class="pairing-code"
      :aria-label="code ?? undefined"
      data-testid="pairing-code"
    >
      <span v-for="(character, index) in characters" :key="index" class="pairing-character">
        {{ character }}
      </span>
    </div>
    <p v-else class="pairing-meta">{{ t('infoscreenRuntime.register.waiting') }}</p>
    <p v-if="validUntil" class="pairing-meta">
      {{ t('infoscreenRuntime.register.validUntil', { time: validUntil }) }}
    </p>
    <div class="pairing-hint">
      <strong class="pairing-hint-label">{{ t('infoscreenRuntime.register.approve') }}</strong>
      {{ t('infoscreenRuntime.register.hint') }}
    </div>
  </section>
</template>

<style scoped lang="scss">
.pairing {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: calc(28 * var(--u));
  padding: calc(48 * var(--u)) calc(40 * var(--u));
  border: calc(2 * var(--u)) solid var(--report-line);
  border-radius: calc(10 * var(--u));
  background: var(--report-panel);
}

.pairing-label {
  margin: 0;
  font-family: var(--report-mono);
  font-size: calc(24 * var(--u));
  font-weight: 400;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--report-muted);
}

.pairing-code {
  display: flex;
  gap: calc(14 * var(--u));
}

.pairing-character {
  display: flex;
  align-items: center;
  justify-content: center;
  width: calc(104 * var(--u));
  height: calc(136 * var(--u));
  border: calc(3 * var(--u)) solid var(--report-line);
  border-radius: calc(8 * var(--u));
  background: var(--report-bg);
  font-family: var(--report-mono);
  font-size: calc(96 * var(--u));
  font-weight: 600;
  line-height: 1;

  // Two groups of three, as the approve dialog reads the code.
  &:nth-child(3) {
    margin-right: calc(22 * var(--u));
  }
}

.pairing-meta {
  margin: 0;
  font-family: var(--report-mono);
  font-size: calc(24 * var(--u));
  color: var(--report-muted);
}

.pairing-hint {
  align-self: stretch;
  padding: calc(22 * var(--u)) calc(28 * var(--u));
  border: calc(2 * var(--u)) solid var(--report-line);
  border-radius: calc(8 * var(--u));
  background: var(--report-panel);
  font-size: calc(28 * var(--u));
  line-height: 1.4;
}

.pairing-hint-label {
  display: block;
  margin-bottom: calc(8 * var(--u));
  font-family: var(--report-mono);
  font-size: calc(20 * var(--u));
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--report-muted);
}
</style>
