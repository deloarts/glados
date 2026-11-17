<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import EmptyState from '@/shared/components/EmptyState.vue'
import type { SequenceDocument } from '../composables/useSequenceDocument'
import { useSequenceNames } from '../composables/useSequenceNames'
import type { SequenceTiming } from '../composables/useSequenceTiming'
import { describeAction, describeCondition } from '../utils/describe'
import type { DescribeContext } from '../utils/describe'
import { GRAFCET, layoutGrafcet } from '../utils/grafcetLayout'

/**
 * The GRAFCET chart of a sequence (IEC 60848): steps, their actions with
 * qualifier, and the transitions with their conditions, laid out by
 * layoutGrafcet. Values that differ per variant are written for the
 * variant the page picks in its controls bar, or without the page's timing
 * for the one picked above the chart. It follows the steps on screen, so
 * it shows unsaved changes too.
 */
const props = withDefaults(
  defineProps<{
    doc: SequenceDocument
    timing?: SequenceTiming
    /** Draws the chart in a bordered box of its own; off inside a card. */
    framed?: boolean
  }>(),
  { timing: undefined, framed: true },
)

const { t } = useI18n()
const translate = (key: string, values?: Record<string, unknown>) => (values ? t(key, values) : t(key))
const names = props.timing?.names ?? useSequenceNames(props.doc)

const ownVariantId = ref<number | null>(null)
const variantId = computed<number | null>({
  get: () => (props.timing ? props.timing.variantId.value : ownVariantId.value),
  set: (id) => (props.timing ? props.timing.setVariant(id) : (ownVariantId.value = id)),
})
const variantOptions = computed(() => [
  { value: null, label: t('sequences.diagram.commonValues') },
  ...names.liveVariants.value.map((variant) => ({ value: variant.id, label: variant.name })),
])

const layout = computed(() => {
  const steps = props.doc.steps.value
  const numbers = new Map(steps.map((step, index) => [step.key, index + 1]))
  const context = (stepKey: string): DescribeContext => ({
    names,
    stepNumber: (key) => numbers.get(key) ?? null,
    stepKey,
    variantId: variantId.value,
    t: translate,
  })
  return layoutGrafcet(steps, {
    action: (action, stepKey) => describeAction(action, context(stepKey)),
    condition: (terms, stepKey) => describeCondition(terms, context(stepKey)),
  })
})

const G = GRAFCET

function points(link: Array<[number, number]>): string {
  return link.map(([x, y]) => `${x},${y}`).join(' ')
}
</script>

<template>
  <div class="grafcet-view">
    <div v-if="!timing && names.liveVariants.value.length > 0" class="toolbar">
      <span class="label">{{ t('sequences.diagram.variant') }}</span>
      <SelectButton
        v-model="variantId"
        :options="variantOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
        data-testid="sequence-grafcet-variant"
      />
    </div>
    <EmptyState v-if="layout.steps.length === 0" :message="t('sequences.editor.noSteps')" icon="mdi mdi-sitemap-outline" />
    <div v-else class="scroll" :class="{ framed }">
      <svg
        :width="layout.width"
        :height="layout.height"
        :viewBox="`0 0 ${layout.width} ${layout.height}`"
        class="grafcet"
        role="img"
        :aria-label="t('sequences.views.grafcet')"
        data-testid="sequence-grafcet"
      >
        <defs>
          <marker id="grafcet-arrow" viewBox="0 0 10 10" refX="5" refY="9" markerWidth="8" markerHeight="8" orient="auto">
            <path d="M0,0 L5,10 L10,0 Z" class="arrow-head" />
          </marker>
        </defs>

        <polyline v-for="(link, index) in layout.links" :key="`l${index}`" :points="points(link)" class="link" />

        <g v-for="step in layout.steps" :key="step.key" :data-testid="`grafcet-step-${step.number}`">
          <rect :x="step.x" :y="step.y" :width="G.step" :height="G.step" class="step" />
          <rect
            v-if="step.initial"
            :x="step.x + 4"
            :y="step.y + 4"
            :width="G.step - 8"
            :height="G.step - 8"
            class="step"
          />
          <text :x="step.x + G.step / 2" :y="step.y + G.step / 2 + 5" class="step-number">{{ step.number }}</text>
          <text v-if="step.timeoutMs" :x="step.x - 8" :y="step.y + G.step / 2 + 4" class="note end">
            {{ t('sequences.grafcet.timeout', { ms: step.timeoutMs }) }}
          </text>
          <text v-if="step.enteredFrom.length" :x="step.x - 8" :y="step.y - 4" class="note end">
            {{ t('sequences.grafcet.enteredFrom', { steps: step.enteredFrom.map((n) => `X${n}`).join(', ') }) }}
          </text>
        </g>

        <g v-for="(action, index) in layout.actions" :key="`a${index}`" data-testid="grafcet-action">
          <rect :x="action.x" :y="action.y" :width="layout.actionWidth" :height="action.height" class="action" />
          <line
            :x1="action.x + G.qualifierWidth"
            :x2="action.x + G.qualifierWidth"
            :y1="action.y"
            :y2="action.y + action.height"
            class="action"
          />
          <text :x="action.x + G.qualifierWidth / 2" :y="action.y + 17" class="qualifier">{{ action.qualifier }}</text>
          <!-- A device action as [ qualifier | device | command ], a text action across both cells. -->
          <template v-if="action.device !== null">
            <line
              :x1="action.x + G.qualifierWidth + layout.deviceWidth"
              :x2="action.x + G.qualifierWidth + layout.deviceWidth"
              :y1="action.y"
              :y2="action.y + G.actionHeight"
              class="action"
            />
            <text :x="action.x + G.qualifierWidth + G.cellPadding" :y="action.y + 17" class="action-text">
              {{ action.device }}
            </text>
            <text
              :x="action.x + G.qualifierWidth + layout.deviceWidth + G.cellPadding"
              :y="action.y + 17"
              class="action-text"
              data-testid="grafcet-action-command"
            >
              {{ action.text }}
            </text>
          </template>
          <text v-else :x="action.x + G.qualifierWidth + G.cellPadding" :y="action.y + 17" class="action-text">
            {{ action.text }}
          </text>
          <text v-if="action.condition" :x="action.x + G.qualifierWidth + G.cellPadding" :y="action.y + 32" class="note">
            {{ t('sequences.grafcet.if', { condition: action.condition }) }}
          </text>
        </g>

        <g v-for="(bar, index) in layout.transitions" :key="`t${index}`" data-testid="grafcet-transition">
          <line :x1="bar.x - 14" :x2="bar.x + 14" :y1="bar.y" :y2="bar.y" class="bar" />
          <text :x="bar.x + 20" :y="bar.y + 4" class="condition">
            <title>{{ bar.label }}</title>
            <!-- One term per line, all of which must hold. -->
            <tspan
              v-for="(line, lineIndex) in bar.lines"
              :key="lineIndex"
              :x="bar.x + 20"
              :dy="lineIndex === 0 ? 0 : G.conditionLineHeight"
            >
              {{ line }}
            </tspan>
          </text>
        </g>

        <g v-for="(jump, index) in layout.jumps" :key="`j${index}`">
          <line :x1="jump.x" :x2="jump.x" :y1="jump.y" :y2="jump.y + 10" class="link" marker-end="url(#grafcet-arrow)" />
          <text :x="jump.x" :y="jump.y + 24" class="jump">
            {{ jump.target === null ? t('sequences.grafcet.end') : `X${jump.target}` }}
          </text>
        </g>
      </svg>
    </div>
  </div>
</template>

<style scoped lang="scss">
.grafcet-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-height: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-2);

  .label {
    font-size: var(--font-size-sm);
    color: var(--p-text-muted-color);
  }
}

.scroll {
  overflow: auto;
  flex: 1 1 auto;
  min-height: 0;

  &.framed {
    border: 1px solid var(--p-content-border-color);
    border-radius: var(--p-content-border-radius);
    background: var(--p-content-background);
  }
}

.grafcet {
  display: block;
  font-family: inherit;

  .link {
    fill: none;
    stroke: var(--p-text-color);
    stroke-width: 1.5;
  }

  .arrow-head {
    fill: var(--p-text-color);
  }

  .step,
  .action {
    fill: var(--p-content-background);
    stroke: var(--p-text-color);
    stroke-width: 1.5;
  }

  .bar {
    stroke: var(--p-text-color);
    stroke-width: 3;
  }

  .step-number {
    fill: var(--p-text-color);
    font-size: var(--font-size-sm);
    font-weight: 600;
    text-anchor: middle;
  }

  .qualifier {
    fill: var(--p-text-color);
    font-size: var(--font-size-sm);
    font-weight: 600;
    text-anchor: middle;
  }

  .action-text,
  .condition {
    fill: var(--p-text-color);
    font-size: var(--font-size-sm);
  }

  .note {
    fill: var(--p-text-muted-color);
    font-size: var(--font-size-xs);

    &.end {
      text-anchor: end;
    }
  }

  .jump {
    fill: var(--p-text-color);
    font-size: var(--font-size-sm);
    font-weight: 600;
    text-anchor: middle;
  }
}
</style>
