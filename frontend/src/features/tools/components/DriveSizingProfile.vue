<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { localeTag } from '@/core/utils/dates'
import { useDriveSizingFormat } from '../utils/driveSizing/format'
import { MAX_SEGMENTS, SEGMENT_LIMITS, toSegmentRow } from '../utils/driveSizing/model'
import type {
  MoveSegmentInput,
  Orientation,
  PauseSegmentInput,
  SegmentInput,
  SegmentRow,
} from '../utils/driveSizing/model'

const segments = defineModel<SegmentRow[]>({ required: true })

const props = defineProps<{
  orientation: Orientation
  /** Zero-based indexes of segments with an error or a remark, for highlighting. */
  errorSegments: readonly number[]
  warningSegments: readonly number[]
}>()

const { t } = useI18n()
const fmt = useDriveSizingFormat()

const hint = computed(() =>
  props.orientation === 'horizontal'
    ? t('tools.driveSizing.profile.hintHorizontal')
    : t('tools.driveSizing.profile.hintVertical'),
)

const holdingOptions = computed(() => [
  { value: true, label: t('tools.driveSizing.profile.holding.brake') },
  { value: false, label: t('tools.driveSizing.profile.holding.motor') },
])

const full = computed(() => segments.value.length >= MAX_SEGMENTS)

function patch(index: number, change: Partial<MoveSegmentInput> | Partial<PauseSegmentInput>) {
  segments.value = segments.value.map((row, i) =>
    i === index ? ({ ...row, ...change } as SegmentRow) : row,
  )
}

function moveRow(index: number, delta: -1 | 1) {
  const target = index + delta
  const rows = [...segments.value]
  const row = rows[index]
  const other = rows[target]
  if (!row || !other) return
  rows[index] = other
  rows[target] = row
  segments.value = rows
}

function remove(index: number) {
  segments.value = segments.value.filter((_, i) => i !== index)
}

function append(...added: SegmentInput[]) {
  segments.value = [...segments.value, ...added.map(toSegmentRow)].slice(0, MAX_SEGMENTS)
}

const last = computed(() => segments.value[segments.value.length - 1])

// A new move continues from where the profile stands: still moving, it
// brakes to a standstill in the same direction; at rest, it starts forward.
function addMove() {
  const previous = last.value
  const moving = previous?.kind === 'move' && (previous.endSpeed ?? 0) > 0
  const direction = moving && (previous.distanceMm ?? 0) < 0 ? -1 : 1
  const startSpeed = moving ? (previous.endSpeed ?? 0) : 0
  append({
    kind: 'move',
    distanceMm: direction * 100,
    startSpeed,
    endSpeed: moving ? 0 : 0.3,
    payload: previous?.payload ?? false,
  })
}

function addPositioning() {
  const payload = last.value?.payload ?? false
  append(
    { kind: 'move', distanceMm: 100, startSpeed: 0, endSpeed: 0.3, payload },
    { kind: 'move', distanceMm: 200, startSpeed: 0.3, endSpeed: 0.3, payload },
    { kind: 'move', distanceMm: 100, startSpeed: 0.3, endSpeed: 0, payload },
  )
}

function addPause() {
  append({ kind: 'pause', durationS: 1, payload: last.value?.payload ?? false, brake: false })
}

/** Time of a move from its distance and speeds, or an empty cell while it cannot be computed. */
function moveDuration(row: MoveSegmentInput): string {
  const { distanceMm, startSpeed, endSpeed } = row
  if (distanceMm === null || startSpeed === null || endSpeed === null) return ''
  const mean = (startSpeed + endSpeed) / 2
  if (mean <= 0 || distanceMm === 0) return ''
  return `${fmt.fixed(Math.abs(distanceMm) / 1000 / mean, 2)} s`
}

function aria(column: string, index: number): string {
  return t('tools.driveSizing.profile.fieldAria', {
    field: t(`tools.driveSizing.profile.columns.${column}`),
    n: index + 1,
  })
}
</script>

<template>
  <section class="ds-profile" data-testid="ds-profile">
    <header class="ds-profile-header">
      <h3 class="ds-profile-title">{{ t('tools.driveSizing.profile.title') }}</h3>
    </header>
    <p class="ds-profile-hint">{{ hint }}</p>

    <p v-if="segments.length === 0" class="ds-profile-empty">{{ t('tools.driveSizing.profile.empty') }}</p>
    <div v-else class="ds-profile-scroll">
      <table class="ds-profile-table">
        <thead>
          <tr>
            <th scope="col" class="ds-col-index">{{ t('tools.driveSizing.profile.columns.index') }}</th>
            <th scope="col">{{ t('tools.driveSizing.profile.columns.kind') }}</th>
            <th scope="col">{{ t('tools.driveSizing.profile.columns.distance') }} <span class="ds-unit">mm</span></th>
            <th scope="col">{{ t('tools.driveSizing.profile.columns.startSpeed') }} <span class="ds-unit">m/s</span></th>
            <th scope="col">{{ t('tools.driveSizing.profile.columns.endSpeed') }} <span class="ds-unit">m/s</span></th>
            <th scope="col">{{ t('tools.driveSizing.profile.columns.duration') }} <span class="ds-unit">s</span></th>
            <th scope="col">{{ t('tools.driveSizing.profile.columns.holding') }}</th>
            <th scope="col">{{ t('tools.driveSizing.profile.columns.payload') }}</th>
            <th scope="col">
              <span class="ds-visually-hidden">{{ t('tools.driveSizing.profile.columns.actions') }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in segments"
            :key="row.id"
            :class="{
              'ds-row--error': errorSegments.includes(index),
              'ds-row--warning': !errorSegments.includes(index) && warningSegments.includes(index),
            }"
            :data-testid="`ds-segment-${index}`"
          >
            <td class="ds-col-index row-number">{{ index + 1 }}</td>
            <td>
              <Tag
                :value="t(`tools.driveSizing.profile.kinds.${row.kind}`)"
                :severity="row.kind === 'move' ? 'info' : 'secondary'"
              />
            </td>
            <template v-if="row.kind === 'move'">
              <td>
                <InputNumber
                  :model-value="row.distanceMm"
                  :min="SEGMENT_LIMITS.distanceMm.min"
                  :max="SEGMENT_LIMITS.distanceMm.max"
                  :max-fraction-digits="1"
                  :locale="localeTag()"
                  :aria-label="aria('distance', index)"
                  size="small"
                  class="ds-cell-number"
                  :data-testid="`ds-segment-${index}-distance`"
                  @update:model-value="(value: number | null) => patch(index, { distanceMm: value })"
                />
              </td>
              <td>
                <InputNumber
                  :model-value="row.startSpeed"
                  :min="SEGMENT_LIMITS.speed.min"
                  :max="SEGMENT_LIMITS.speed.max"
                  :max-fraction-digits="3"
                  :locale="localeTag()"
                  :aria-label="aria('startSpeed', index)"
                  size="small"
                  class="ds-cell-number"
                  :data-testid="`ds-segment-${index}-start-speed`"
                  @update:model-value="(value: number | null) => patch(index, { startSpeed: value })"
                />
              </td>
              <td>
                <InputNumber
                  :model-value="row.endSpeed"
                  :min="SEGMENT_LIMITS.speed.min"
                  :max="SEGMENT_LIMITS.speed.max"
                  :max-fraction-digits="3"
                  :locale="localeTag()"
                  :aria-label="aria('endSpeed', index)"
                  size="small"
                  class="ds-cell-number"
                  :data-testid="`ds-segment-${index}-end-speed`"
                  @update:model-value="(value: number | null) => patch(index, { endSpeed: value })"
                />
              </td>
              <td class="ds-calculated" :title="t('tools.driveSizing.profile.calculatedDuration')">
                {{ moveDuration(row) }}
              </td>
              <td />
            </template>
            <template v-else>
              <td />
              <td />
              <td />
              <td>
                <InputNumber
                  :model-value="row.durationS"
                  :min="SEGMENT_LIMITS.durationS.min"
                  :max="SEGMENT_LIMITS.durationS.max"
                  :max-fraction-digits="2"
                  :locale="localeTag()"
                  :aria-label="aria('duration', index)"
                  size="small"
                  class="ds-cell-number"
                  :data-testid="`ds-segment-${index}-duration`"
                  @update:model-value="(value: number | null) => patch(index, { durationS: value })"
                />
              </td>
              <td>
                <SelectButton
                  :model-value="row.brake"
                  :options="holdingOptions"
                  option-label="label"
                  option-value="value"
                  :allow-empty="false"
                  :aria-label="aria('holding', index)"
                  size="small"
                  :data-testid="`ds-segment-${index}-holding`"
                  @update:model-value="(value: boolean) => patch(index, { brake: value })"
                />
              </td>
            </template>
            <td>
              <Checkbox
                :model-value="row.payload"
                binary
                :aria-label="aria('payload', index)"
                :data-testid="`ds-segment-${index}-payload`"
                @update:model-value="(value: boolean) => patch(index, { payload: value })"
              />
            </td>
            <td class="ds-actions">
              <Button
                icon="mdi mdi-arrow-up"
                text
                rounded
                size="small"
                severity="secondary"
                :disabled="index === 0"
                :aria-label="t('tools.driveSizing.profile.moveUp', { n: index + 1 })"
                @click="moveRow(index, -1)"
              />
              <Button
                icon="mdi mdi-arrow-down"
                text
                rounded
                size="small"
                severity="secondary"
                :disabled="index === segments.length - 1"
                :aria-label="t('tools.driveSizing.profile.moveDown', { n: index + 1 })"
                @click="moveRow(index, 1)"
              />
              <Button
                icon="mdi mdi-delete-outline"
                text
                rounded
                size="small"
                severity="danger"
                :aria-label="t('tools.driveSizing.profile.remove', { n: index + 1 })"
                :data-testid="`ds-segment-${index}-remove`"
                @click="remove(index)"
              />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="ds-profile-add">
      <span class="ds-profile-add-label">{{ t('tools.driveSizing.profile.addLabel') }}</span>
      <Button
        icon="mdi mdi-plus"
        :label="t('tools.driveSizing.profile.addMove')"
        severity="secondary"
        size="small"
        :disabled="full"
        data-testid="ds-add-move"
        @click="addMove"
      />
      <Button
        icon="mdi mdi-plus"
        :label="t('tools.driveSizing.profile.addPositioning')"
        severity="secondary"
        size="small"
        :disabled="segments.length + 3 > MAX_SEGMENTS"
        data-testid="ds-add-positioning"
        @click="addPositioning"
      />
      <Button
        icon="mdi mdi-plus"
        :label="t('tools.driveSizing.profile.addPause')"
        severity="secondary"
        size="small"
        :disabled="full"
        data-testid="ds-add-pause"
        @click="addPause"
      />
    </div>
  </section>
</template>

<style scoped lang="scss">
.ds-profile {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 0;
}

.ds-profile-title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: 600;
}

.ds-profile-hint,
.ds-profile-empty {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.ds-profile-scroll {
  overflow-x: auto;
}

.ds-profile-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);

  th {
    padding: var(--space-1) var(--space-2);
    text-align: left;
    font-weight: 600;
    white-space: nowrap;
    color: var(--p-text-muted-color);
    border-bottom: 1px solid var(--p-content-border-color);
  }

  td {
    padding: var(--space-1) var(--space-2);
    vertical-align: middle;
    border-bottom: 1px solid var(--p-content-border-color);
  }
}

.ds-unit {
  font-weight: 400;
}

.ds-col-index {
  width: 2.5rem;
}

.ds-row--error .ds-col-index {
  font-weight: 700;
  color: var(--p-red-500);
  box-shadow: inset 3px 0 0 var(--p-red-500);
}

.ds-row--warning .ds-col-index {
  font-weight: 700;
  color: var(--p-orange-500);
  box-shadow: inset 3px 0 0 var(--p-orange-500);
}

.ds-cell-number :deep(input) {
  width: 6.5rem;
}

.ds-calculated {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
}

.ds-actions {
  white-space: nowrap;
  text-align: right;
}

.ds-profile-add {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.ds-profile-add-label {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.ds-visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
