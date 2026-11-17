<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { publishToolState, useInitialToolInputs } from '../composables/useToolState'
import { checkRows, issueText, torqueReferences } from '../utils/driveSizing/display'
import { sizeDrive, speedTrace, torqueTrace } from '../utils/driveSizing/engine'
import type { Issue } from '../utils/driveSizing/engine'
import { useDriveSizingFormat } from '../utils/driveSizing/format'
import { emptyDriveSizingInput, toSegmentRow } from '../utils/driveSizing/model'
import type { DriveSizingInput, DriveSizingSettings, SegmentRow } from '../utils/driveSizing/model'
import { decodeDriveSizingInputs, encodeDriveSizingInputs } from '../utils/driveSizing/inputs'
import { driveSizingSnapshot } from '../utils/driveSizing/snapshot'
import { describeAxis } from '../utils/driveSizing/summary'
import DriveSizingChart from './DriveSizingChart.vue'
import DriveSizingChecks from './DriveSizingChecks.vue'
import DriveSizingInputs from './DriveSizingInputs.vue'
import DriveSizingProfile from './DriveSizingProfile.vue'
import DriveSizingSegmentTable from './DriveSizingSegmentTable.vue'

const { t } = useI18n()
const toast = useAppToast()
const fmt = useDriveSizingFormat()

// A saved calculation is untrusted input like any other: whatever is unusable
// is left empty, and the user is told once. Without one the form starts
// cleared.
function startInput(): DriveSizingInput {
  const saved = useInitialToolInputs()
  if (saved) {
    const decoded = decodeDriveSizingInputs(saved)
    if (decoded.invalid) toast.warn('', t('tools.calculations.errors.invalidInputs'))
    return decoded.input
  }
  return emptyDriveSizingInput()
}

const { segments: initialSegments, ...initialSettings } = startInput()
const settings = ref<DriveSizingSettings>(initialSettings)
const segments = ref<SegmentRow[]>(initialSegments.map(toSegmentRow))

const input = computed<DriveSizingInput>(() => ({ ...settings.value, segments: segments.value }))
const result = computed(() => sizeDrive(input.value))
const success = computed(() => (result.value.ok ? result.value : null))

const axisLabel = computed(() =>
  describeAxis(
    {
      orientation: settings.value.orientation,
      angleDeg: settings.value.orientation === 'inclined' ? settings.value.angleDeg : null,
      ratio: settings.value.ratio,
      carriageMassKg: settings.value.carriageMassKg,
      payloadMassKg: settings.value.payloadMassKg,
    },
    t,
  ),
)

const errorTexts = computed(() =>
  result.value.ok ? [] : result.value.errors.map((issue) => issueText(issue, t, fmt)),
)
const warningTexts = computed(() => {
  const ok = success.value
  return ok ? ok.warnings.map((issue) => issueText(issue, t, fmt, ok.endPositionMm)) : []
})

function segmentIndexes(issues: readonly Issue[]): number[] {
  return issues.flatMap((issue) => (issue.segment === undefined ? [] : [issue.segment]))
}

// Segments to highlight in the editor. Without results these are the segments
// with an error; with results, a segment that leaves the stroke counts as an
// error and one with a remark on the profile as a warning.
const errorSegments = computed(() =>
  result.value.ok
    ? result.value.segments.filter((segment) => segment.outOfStroke).map((segment) => segment.index)
    : segmentIndexes(result.value.errors),
)
const warningSegments = computed(() => (success.value ? segmentIndexes(success.value.warnings) : []))

const rows = computed(() =>
  success.value
    ? checkRows(
        success.value,
        {
          brakeSafetyFactor: settings.value.brakeSafetyFactor ?? 0,
          maxSpeedGiven: settings.value.maxSpeedRpm !== null,
        },
        t,
        fmt,
      )
    : [],
)

const speedPoints = computed(() => (success.value ? speedTrace(success.value.segments) : []))
const torquePoints = computed(() => (success.value ? torqueTrace(success.value.segments) : []))

const chartReferences = computed(() =>
  success.value
    ? torqueReferences(success.value, settings.value.maxTorqueNm ?? 0, settings.value.ratedTorqueNm ?? 0)
    : [],
)

// The inputs record a saved calculation stores and hands back on opening.
const savedInputs = computed(() => encodeDriveSizingInputs(input.value))

publishToolState(() => ({
  inputs: savedInputs.value,
  results: driveSizingSnapshot(input.value, result.value),
  title: axisLabel.value,
  description: axisLabel.value,
}))
</script>

<template>
  <!-- Two columns that read as one sequence on normal screens: settings and
       checks side by side, then the motion profile, the charts and the
       segments. On very wide screens the columns stand next to each other,
       the motion profile and the segments on the right. -->
  <div class="ds">
    <div class="ds-col ds-col--main">
      <div class="ds-top">
        <DriveSizingInputs v-model="settings" class="ds-settings" />

        <DriveSizingChecks
          class="ds-panel ds-checks"
          :result="success"
          :rows="rows"
          :warnings="warningTexts"
          :errors="errorTexts"
        />
      </div>

      <section v-if="success" class="ds-panel ds-charts">
        <DriveSizingChart
          :title="t('tools.driveSizing.charts.speedTitle')"
          :description="t('tools.driveSizing.charts.speedAria')"
          :unit="t('tools.driveSizing.charts.speedUnit')"
          :points="speedPoints"
          :duration="success.cycleTimeS"
        />
        <DriveSizingChart
          :title="t('tools.driveSizing.charts.torqueTitle')"
          :description="t('tools.driveSizing.charts.torqueAria')"
          :unit="t('tools.driveSizing.charts.torqueUnit')"
          :points="torquePoints"
          :duration="success.cycleTimeS"
          :references="chartReferences"
        />
      </section>
    </div>

    <div class="ds-col ds-col--side">
      <DriveSizingProfile
        v-model="segments"
        class="ds-panel ds-profile"
        :orientation="settings.orientation"
        :error-segments="errorSegments"
        :warning-segments="warningSegments"
      />

      <DriveSizingSegmentTable
        v-if="success"
        class="ds-panel ds-segments"
        :segments="success.segments"
        :orientation="settings.orientation"
        :max-torque-nm="settings.maxTorqueNm ?? Number.POSITIVE_INFINITY"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
// A long page rather than a fixed frame: the tab panel scrolls as a whole.
.ds {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

// Up to 2000 px the two column wrappers dissolve and their parts line up in
// reading order: settings and checks, motion profile, charts, segments.
.ds-col {
  display: contents;
}

// The settings and the checks card stretch to the same height.
.ds-top {
  order: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);
  align-items: stretch;
  gap: var(--space-2);
}

.ds-profile {
  order: 2;
}

.ds-charts {
  order: 3;
}

.ds-segments {
  order: 4;
}

// Settings and checks stack once the third of the width gets too narrow for
// the input fields.
@media (max-width: $bp-lg) {
  .ds-top {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (min-width: $bp-3xl) {
  .ds {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }

  .ds-col {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-width: 0;
  }
}

.ds-panel {
  padding: var(--space-3) var(--space-4);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
}

.ds-charts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(24rem, 1fr));
  gap: var(--space-4);
}
</style>
