<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useFitFormat } from '../composables/useFitFormat'
import type { FitPart, LimitResult } from '../utils/iso286/toleranceClass'

const props = defineProps<{
  part: FitPart
  code: string
  size: number | null
  result: LimitResult
}>()

const { t } = useI18n()
const fmt = useFitFormat()

const rows = computed(() => {
  const r = props.result
  if (!r.ok || props.size === null) return []
  const isHole = props.part === 'hole'
  return [
    {
      key: 'upper',
      label: t(`tools.fitCalculator.${isHole ? 'upperDeviationHole' : 'upperDeviationShaft'}`),
      um: fmt.deviationUm(r.upper),
      mm: fmt.deviationMm(r.upper),
    },
    {
      key: 'lower',
      label: t(`tools.fitCalculator.${isHole ? 'lowerDeviationHole' : 'lowerDeviationShaft'}`),
      um: fmt.deviationUm(r.lower),
      mm: fmt.deviationMm(r.lower),
    },
    { key: 'max', label: t('tools.fitCalculator.maxSize'), um: '', mm: fmt.limitSize(props.size, r.upper) },
    { key: 'min', label: t('tools.fitCalculator.minSize'), um: '', mm: fmt.limitSize(props.size, r.lower) },
    {
      key: 'tolerance',
      label: t('tools.fitCalculator.tolerance'),
      um: fmt.amountUm(r.upper - r.lower),
      mm: fmt.amountMm(r.upper - r.lower),
    },
  ]
})

const reason = computed(() =>
  props.result.ok ? '' : t(`tools.fitCalculator.reasons.${props.result.reason}`, { code: props.code }),
)
</script>

<template>
  <section class="fit-card" :data-testid="`fit-${part}-card`">
    <header class="fit-card-header">
      <span class="fit-card-swatch" :class="`fit-card-swatch--${part}`" aria-hidden="true" />
      <h3 class="fit-card-title">{{ t(`tools.fitCalculator.${part}`) }}</h3>
      <span class="fit-card-code">{{ code }}</span>
    </header>
    <dl v-if="rows.length" class="fit-rows">
      <div v-for="row in rows" :key="row.key" class="fit-row">
        <dt>{{ row.label }}</dt>
        <dd class="fit-row-um">{{ row.um }}</dd>
        <dd class="fit-row-mm" :data-testid="`fit-${part}-${row.key}`">{{ row.mm }}</dd>
      </div>
    </dl>
    <Message v-else severity="warn" :closable="false">{{ reason }}</Message>
  </section>
</template>

<style scoped lang="scss">
.fit-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  min-width: 0;
}

.fit-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.fit-card-swatch {
  width: 0.85rem;
  height: 0.85rem;
  border-radius: 3px;

  &--hole {
    background: var(--p-blue-500);
  }

  &--shaft {
    background: var(--p-orange-500);
  }
}

.fit-card-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.fit-card-code {
  margin-left: auto;
  font-weight: 600;
  font-size: var(--font-size-md);
}

.fit-rows {
  margin: 0;
  display: flex;
  flex-direction: column;
}

.fit-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-top: 1px solid var(--p-content-border-color);

  dt {
    flex: 1;
    color: var(--p-text-muted-color);
  }

  dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }
}

.fit-row-um {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

.fit-row-mm {
  min-width: 6.5rem;
  text-align: right;
  font-weight: 500;
}
</style>
