<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { phaseLabel } from '../utils/driveSizing/display'
import type { SegmentResult } from '../utils/driveSizing/engine'
import { useDriveSizingFormat } from '../utils/driveSizing/format'
import type { Orientation } from '../utils/driveSizing/model'

const props = defineProps<{
  segments: readonly SegmentResult[]
  orientation: Orientation
  maxTorqueNm: number
}>()

const { t } = useI18n()
const fmt = useDriveSizingFormat()

const rows = computed(() =>
  props.segments.map((segment) => ({
    segment,
    phase: phaseLabel(segment, props.orientation, t),
    position:
      segment.kind === 'move'
        ? `${fmt.fixed(segment.startMm, 0)} → ${fmt.fixed(segment.endMm, 0)}`
        : fmt.fixed(segment.startMm, 0),
    overTorque: Math.abs(segment.torqueNm) > props.maxTorqueNm,
  })),
)
</script>

<template>
  <section class="ds-segments" data-testid="ds-segments">
    <h3 class="ds-segments-title">{{ t('tools.driveSizing.segments.title') }}</h3>
    <div class="ds-segments-scroll">
      <table class="ds-segments-table">
        <thead>
          <tr>
            <th scope="col">{{ t('tools.driveSizing.segments.columns.index') }}</th>
            <th scope="col">{{ t('tools.driveSizing.segments.columns.phase') }}</th>
            <th scope="col" class="ds-num">{{ t('tools.driveSizing.segments.columns.mass') }} <span class="ds-unit">kg</span></th>
            <th scope="col" class="ds-num">{{ t('tools.driveSizing.segments.columns.position') }} <span class="ds-unit">mm</span></th>
            <th scope="col" class="ds-num">{{ t('tools.driveSizing.segments.columns.time') }} <span class="ds-unit">s</span></th>
            <th scope="col" class="ds-num">
              {{ t('tools.driveSizing.segments.columns.acceleration') }} <span class="ds-unit">m/s²</span>
            </th>
            <th scope="col" class="ds-num">{{ t('tools.driveSizing.segments.columns.force') }} <span class="ds-unit">N</span></th>
            <th scope="col" class="ds-num">{{ t('tools.driveSizing.segments.columns.speed') }} <span class="ds-unit">rpm</span></th>
            <th scope="col" class="ds-num">{{ t('tools.driveSizing.segments.columns.torque') }} <span class="ds-unit">Nm</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.segment.index" :data-testid="`ds-result-${row.segment.index}`">
            <td class="row-number">{{ row.segment.index + 1 }}</td>
            <td>
              <span :data-testid="`ds-result-${row.segment.index}-phase`">{{ row.phase }}</span>
              <span
                v-if="row.segment.regenerative"
                class="ds-regen"
                :title="t('tools.driveSizing.segments.regenerativeHint')"
              >{{ t('tools.driveSizing.segments.regenerative') }}</span>
            </td>
            <td class="ds-num">{{ fmt.num(row.segment.massKg, 2) }}</td>
            <td class="ds-num" :class="{ 'ds-over': row.segment.outOfStroke }">{{ row.position }}</td>
            <td class="ds-num">{{ fmt.fixed(row.segment.durationS, 3) }}</td>
            <td class="ds-num">{{ fmt.fixed(row.segment.accelerationMs2, 3) }}</td>
            <td class="ds-num">{{ fmt.fixed(row.segment.forceN, 1) }}</td>
            <td class="ds-num">{{ fmt.fixed(row.segment.speedRpm, 0) }}</td>
            <td
              class="ds-num ds-torque"
              :class="{ 'ds-over': row.overTorque }"
              :data-testid="`ds-result-${row.segment.index}-torque`"
            >
              {{ fmt.fixed(row.segment.torqueNm, 2) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <small class="ds-segments-note">{{ t('tools.driveSizing.segments.note') }}</small>
  </section>
</template>

<style scoped lang="scss">
.ds-segments {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.ds-segments-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.ds-segments-scroll {
  overflow-x: auto;
}

.ds-segments-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);

  th,
  td {
    padding: var(--space-1) var(--space-2);
    text-align: left;
    border-top: 1px solid var(--p-content-border-color);
  }

  thead th {
    border-top: none;
    font-weight: 600;
    white-space: nowrap;
    color: var(--p-text-muted-color);
  }
}

.ds-num {
  text-align: right !important;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.ds-unit {
  font-weight: 400;
}

.ds-torque {
  font-weight: 600;
}

.ds-over {
  font-weight: 700;
  color: var(--p-red-500);
}

.ds-regen {
  margin-left: var(--space-2);
  padding: 0 var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.ds-segments-note {
  color: var(--p-text-muted-color);
}
</style>
